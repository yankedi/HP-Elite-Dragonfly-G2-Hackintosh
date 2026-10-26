#!/usr/bin/env python3
"""Build a local PCH-only RHUB fallback trial from the stock DBGENH image.

No physical disks or running target are touched. The new AML is compiled and
evaluated only in a tiny local namespace fixture, not in the HP firmware.
"""

import argparse
import copy
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile

from check_recovery_probe import ROOT, ARCHIVE, ARCHIVE_SHA
from prepare_hp_slide_retry import sha
from validate_efi import validate

SOURCE_SHA = "c94f6010c804365c0730474fbfa18391223a43723549b30c4c3139b6932b4f19"
CONFIG_SHA = "4a6ac7f1170420669cd2d4c96d018db244d2cc5edd38919d294649c8d8a296f4"
TEMPLATE_SHA = "732d6acc8f298de65a2ad86b52e6a3d0844c0d02016e5bb002974329a2225be7"
ASL = ROOT / "acpi/SSDT-RHUB-HP.dsl"
AML_NAME = "SSDT-RHUB-HP.aml"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--upstream-template", required=True)
    args = parser.parse_args()
    source, template = [(ROOT / value).resolve(strict=True)
                        for value in (args.source, args.upstream_template)]
    if any(not p.is_relative_to(ROOT / ".local") or not p.is_file()
           for p in (source, template)):
        raise ValueError("Expected private regular inputs")
    if (sha(source), sha(template), sha(ARCHIVE)) != (SOURCE_SHA, TEMPLATE_SHA, ARCHIVE_SHA):
        raise ValueError("Pinned input digest mismatch")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-rhub-", dir=ROOT / ".local/install-prep"))

    def run(name, command):
        result = subprocess.run(list(map(str, command)), cwd=out,
                                capture_output=True, timeout=120)
        (out / (name + ".log")).write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError(f"{name} failed: {result.returncode}")
        return result

    run("iasl", ["iasl", "-ve", "-p", out / "SSDT-RHUB-HP", ASL])
    aml = out / AML_NAME
    payload = aml.read_bytes()
    if payload[:4] != b"SSDT" or sum(payload) % 256:
        raise ValueError("Invalid compiled table header/checksum")
    run("disassemble", ["iasl", "-d", aml])
    disassembly = (out / "SSDT-RHUB-HP.dsl").read_text()
    if "TXHC" in disassembly or "PC00.XHCI.RHUB" not in disassembly:
        raise ValueError("Unexpected table scope")
    # AML execution checks namespace linking and Darwin isolation. It neither
    # executes an OS nor loads the HP tables or their hardware methods.
    fixture = out / "namespace-fixture.dsl"
    fixture.write_text('''DefinitionBlock ("", "SSDT", 2, "HPDIAG", "RHFix", 1)
{
    Scope (\\_SB)
    {
        Device (PC00)
        {
            Name (_HID, "PNP0A08")
            Device (XHCI)
            {
                Name (_ADR, 0x00140000)
                Device (RHUB) { Name (_ADR, Zero) }
            }
        }
    }
}
''')
    run("fixture-compile", ["iasl", "-ve", fixture])
    command = (r"evaluate \_SB.PC00.XHCI.RHUB._STA; osi install Darwin; "
               r"evaluate \_SB.PC00.XHCI.RHUB._STA; osi remove Darwin; "
               r"evaluate \_SB.PC00.XHCI.RHUB._STA")
    result = run("acpiexec", ["acpiexec", "-di", "-b", command,
                               fixture.with_suffix(".aml"), aml])
    text = (result.stdout + result.stderr).decode(errors="replace")
    values = re.findall(r"\[Integer\]\s*=\s*([0-9A-Fa-f]+)", text)
    if [int(value, 16) for value in values] != [15, 0, 15] or "AE_" in text:
        raise ValueError("Darwin-only namespace fixture check failed")

    image = out / "HP-Tahoe-VESA-XHCI-RHUB.img"
    shutil.copyfile(source, image)

    def mcopy(disk, *arguments):
        run("mcopy-latest", ["mcopy", "-i", str(disk) + "@@1048576", *arguments])

    before, after = out / "before", out / "after"
    before.mkdir()
    mcopy(source, "-s", "::*", before)
    validate(before)
    if sha(before / "EFI/OC/config.plist") != CONFIG_SHA:
        raise ValueError("Expected exact DBGENH configuration")
    original = plistlib.loads((before / "EFI/OC/config.plist").read_bytes())
    config = copy.deepcopy(original)
    if (before / "EFI/OC/ACPI" / AML_NAME).exists():
        raise ValueError("Trial table already present")
    config["ACPI"]["Add"].append({
        "Comment": "PCH a0ed RHUB Darwin-only fallback trial; TXHC control unchanged",
        "Enabled": True, "Path": AML_NAME})
    reverted = copy.deepcopy(config)
    reverted["ACPI"]["Add"].pop()
    if reverted != original:
        raise ValueError("Unrelated config change")
    changed = out / "rhub-config.plist"
    changed.write_bytes(plistlib.dumps(config, sort_keys=False))
    mcopy(image, "-o", changed, "::/EFI/OC/config.plist")
    mcopy(image, aml, "::/EFI/OC/ACPI/")
    after.mkdir()
    mcopy(image, "-s", "::*", after)
    validation = validate(after)
    if plistlib.loads((after / "EFI/OC/config.plist").read_bytes()) != config:
        raise ValueError("Config readback mismatch")
    inventory = lambda directory: {str(p.relative_to(directory)): sha(p)
                                   for p in directory.rglob("*") if p.is_file()}
    left, right = inventory(before), inventory(after)
    if any(right.get(name) != digest for name, digest in left.items()
           if name != "EFI/OC/config.plist"):
        raise ValueError("Original IMG file changed")
    if {n: d for n, d in right.items() if n not in left} != {"EFI/OC/ACPI/" + AML_NAME: sha(aml)}:
        raise ValueError("Unexpected new file or AML readback mismatch")
    with zipfile.ZipFile(ARCHIVE) as package:
        validator = out / "ocvalidate"
        validator.write_bytes(package.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    run("ocvalidate", [validator, after / "EFI/OC/config.plist"])
    if sha(source) != SOURCE_SHA:
        raise ValueError("Source image changed")
    report = {
        "schema_version": 1, "source": str(source.relative_to(ROOT)),
        "source_sha256": SOURCE_SHA, "image": str(image.relative_to(ROOT)),
        "sha256": sha(image), "bytes": image.stat().st_size,
        "runner_sha256": sha(Path(__file__)), "asl_sha256": sha(ASL),
        "upstream_template_sha256": TEMPLATE_SHA,
        "aml_sha256": sha(aml), "aml_checksum_valid": True,
        "iasl_exit": 0, "acpiexec_namespace_fixture_exit": 0,
        "fixture_non_darwin_darwin_non_darwin_STA": [15, 0, 15],
        "opencore_version": "1.0.8", "ocvalidate_exit": 0,
        "config_sha256": sha(after / "EFI/OC/config.plist"),
        "only_config_change": "Append PCH-only Darwin RHUB _STA fallback SSDT to ACPI.Add",
        "other_config_fields_and_identity_preserved": True,
        "other_image_files_identical": len(left) - 1,
        "all_existing_kexts_including_DebugEnhancer_unchanged": True,
        "validation": validation,
        "physical_media_written": False, "hp_tested": False,
        "vm_executed": False,
        "limit": "Local AML fixture and static image checks only. PCH USB port creation/fallback and bootability require a user physical boot. TXHC control unchanged. HP_XHC_P table load error is not directly repaired; speed warnings are not patched. No claim of root cause or working port map."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)),
                      **{k: v for k, v in report.items() if k != "validation"}}, indent=2))


if __name__ == "__main__":
    main()
