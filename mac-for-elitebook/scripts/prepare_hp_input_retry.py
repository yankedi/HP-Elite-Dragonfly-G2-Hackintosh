#!/usr/bin/env python3
"""Add pinned VoodooI2C/HID with HP Tiger Lake IDs to a private Recovery IMG.

Keeps the successful MMIO/CPU/graphics/PS2/ACPI baseline. This is a polling-
requested input experiment, not proof of touchpad, touchscreen or USB operation.
Does not deploy to physical devices or execute a VM.
"""

import argparse
import copy
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import zipfile

from check_recovery_probe import ROOT, ARCHIVE, ARCHIVE_SHA
from prepare_hp_slide_retry import sha, GUID
from validate_efi import validate

INPUT_SHA = "368e5eb60794583c340764813bd7e8244e94d3d3c06ea5b67034addd539487f4"
BASE_CONFIG_SHA = "6258d3b307ae2defb31b7733ace6486b6c8dfa56aea37eeb3c7ec7ff753d39d5"
CORE = "VoodooI2C.kext"
INPUT_BUNDLES = [CORE + "/Contents/PlugIns/" + name + ".kext" for name in
                 ("VoodooGPIO", "VoodooI2CServices", "VoodooInput")]
INPUT_BUNDLES += [CORE, "VoodooI2CHID.kext"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--input-archive", default=".local/install-prep/input-sources/VoodooI2C-2.9.1-RELEASE.zip")
    args = parser.parse_args()
    source, archive = [(ROOT / value).resolve(strict=True) for value in (args.source, args.input_archive)]
    if any(not p.is_relative_to(ROOT / ".local") or not p.is_file() for p in (source, archive)):
        raise ValueError("Inputs must be private regular files")
    if sha(archive) != INPUT_SHA or sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Pinned input or OpenCore archive differs")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-input-", dir=ROOT / ".local/install-prep"))
    image = out / "HP-Tahoe-VESA-Recovery.img"
    original_sha = sha(source)
    shutil.copyfile(source, image)

    def mcopy(disk, *arguments):
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", *map(str, arguments)],
                       check=True, capture_output=True, timeout=90)

    before, after = out / "before", out / "after"
    before.mkdir()
    mcopy(source, "-s", "::/EFI", before)
    validate(before)
    old_path = before / "EFI/OC/config.plist"
    if sha(old_path) != BASE_CONFIG_SHA:
        raise ValueError("Expected the captured successful MMIO baseline config")
    old = plistlib.loads(old_path.read_bytes())
    new = copy.deepcopy(old)
    new["NVRAM"]["Add"][GUID]["boot-args"] += " -vi2c-force-polling"
    kexts = out / "new-kexts"
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            name = Path(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Archive path escapes extraction directory")
            if member.is_dir() or name.parts[0] not in (CORE, "VoodooI2CHID.kext"):
                continue
            path = kexts / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(package.read(member))
    core_info = kexts / CORE / "Contents/Info.plist"
    original_info = plistlib.loads(core_info.read_bytes())
    patched = copy.deepcopy(original_info)
    controller = patched["IOKitPersonalities"]["VoodooI2CPCILakeController"]
    controller["IOPCIMatch"] += " 0xa0e88086 0xa0e98086"
    core_info.write_bytes(plistlib.dumps(patched, sort_keys=False))
    for bundle in INPUT_BUNDLES:
        info = plistlib.loads((kexts / bundle / "Contents/Info.plist").read_bytes())
        new["Kernel"]["Add"].append({
            "Arch": "x86_64", "BundlePath": bundle,
            "Comment": "HP Tiger Lake I2C polling-requested experiment; runtime untested",
            "Enabled": True, "ExecutablePath": "Contents/MacOS/" + info["CFBundleExecutable"],
            "MaxKernel": "25.99.99", "MinKernel": "25.0.0", "PlistPath": "Contents/Info.plist"})
    # Audit all other configuration fields, including private identity and MMIO.
    revert = copy.deepcopy(new)
    revert["NVRAM"]["Add"][GUID]["boot-args"] = old["NVRAM"]["Add"][GUID]["boot-args"]
    revert["Kernel"]["Add"] = revert["Kernel"]["Add"][:-len(INPUT_BUNDLES)]
    if revert != old:
        raise ValueError("Unrelated config fields changed")
    config = out / "retry-config.plist"
    config.write_bytes(plistlib.dumps(new, sort_keys=False))
    mcopy(image, "-o", config, "::/EFI/OC/config.plist")
    for name in (CORE, "VoodooI2CHID.kext"):
        mcopy(image, "-s", kexts / name, "::/EFI/OC/Kexts/")
    observer = ROOT / "scripts/collect_macos_handoff.sh"
    mcopy(image, "-o", observer, "::/collect_macos_handoff.sh")
    mcopy(image, "::/collect_macos_handoff.sh", out / observer.name)
    if sha(observer) != sha(out / observer.name):
        raise ValueError("Observer readback differs")
    after.mkdir()
    mcopy(image, "-s", "::/EFI", after)
    validation = validate(after)
    if plistlib.loads((after / "EFI/OC/config.plist").read_bytes()) != new:
        raise ValueError("Readback config differs")
    preserved = []
    for path in (before / "EFI").rglob("*"):
        if path.is_file() and path != old_path:
            relative = path.relative_to(before)
            if sha(path) != sha(after / relative):
                raise ValueError("Baseline EFI file changed: " + str(relative))
            preserved.append(str(relative))
    for path in kexts.rglob("*"):
        if path.is_file() and sha(path) != sha(after / "EFI/OC/Kexts" / path.relative_to(kexts)):
            raise ValueError("Added kext readback differs")
    with zipfile.ZipFile(ARCHIVE) as package:
        validator = out / "ocvalidate"
        validator.write_bytes(package.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")], capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or sha(source) != original_sha:
        raise ValueError("Matching validation failed or captured baseline changed")
    report = {"schema_version": 1, "source": str(source.relative_to(ROOT)), "source_sha256": original_sha,
              "image": str(image.relative_to(ROOT)), "bytes": image.stat().st_size, "sha256": sha(image),
              "input_archive_sha256": INPUT_SHA, "opencore_version": "1.0.8", "opencore_ocvalidate_exit": 0,
              "added_bundles": INPUT_BUNDLES, "other_efi_files_identical": len(preserved),
              "private_identity_preserved": True, "baseline_configuration_preserved_except_input": True,
              "only_config_change": "Append five ordered I2C bundles to Kernel.Add and -vi2c-force-polling to boot-args",
              "core_info_change": "VoodooI2CPCILakeController IOPCIMatch appends exact 8086:a0e8 and 8086:a0e9 IDs",
              "patched_core_info_sha256": sha(core_info), "validation": validation,
              "observer_sha256": sha(observer),
              "runner_sha256": sha(Path(__file__)), "physical_devices_written": False, "vm_executed": False,
              "hp_input_retry_tested": False,
              "limit": "Polling flag skips GPIO after a valid-APIC check; no hard-coded GPIO/IRQ, OSI, ACPI or USB changes. Runtime link, probe and pointer operation untested."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
