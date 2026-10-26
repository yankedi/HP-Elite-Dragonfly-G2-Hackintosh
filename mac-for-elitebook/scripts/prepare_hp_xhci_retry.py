#!/usr/bin/env python3
"""Add one exact a0ed -> AppleUSBXHCISPT personality to the Wi-Fi baseline.

The injector is plist-only and derived from pinned community source. Does not
load/unload a live driver, write physical media, or execute XNU or a VM.
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

from audit_hp_recovery_paths import kc_plists, KC_SHA
from check_recovery_probe import ROOT, ARCHIVE, ARCHIVE_SHA
from prepare_hp_slide_retry import sha
from validate_efi import validate

SOURCE_SHA = "8ff91489c5c533644af60eee9ed5cd245fa805e6065263b4562992586845c54c"
CONFIG_SHA = "a9af19b6af4663cf9f2f889c11573bdf1024de1834073528e79c3b95e3d53bb0"
UPSTREAM_SHA = "9b66b803577d7dea089bc5dc6352f25fb2f2de9c3333cb899c9a838ad7106571"
LICENSE_SHA = "aadacb665026ca53bf5b43db82a24aca07c39f1a3d45f9cea770aae0cbd5b7d9"
COMMIT = "ce55e00966ac90c5e2504fb39b4ecf3fcebab51a"
BUNDLE = "XHCI-unsupported.kext"
PERSONALITY = "AppleUSBXHCISPT 500"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Private Wi-Fi baseline IMG")
    parser.add_argument("--upstream", required=True, help="Private pinned source directory")
    args = parser.parse_args()
    source, upstream = [(ROOT / p).resolve(strict=True) for p in (args.source, args.upstream)]
    if any(not p.is_relative_to(ROOT / ".local") for p in (source, upstream)) or not source.is_file():
        raise ValueError("Expected private source inputs")
    original_info = upstream / BUNDLE / "Contents/Info.plist"
    license_path = upstream / "License.md"
    kc = ROOT / ".local/recovery-repair/BootKernelExtensions.kc"
    if (sha(source), sha(original_info), sha(license_path), sha(kc), sha(ARCHIVE)) != (
            SOURCE_SHA, UPSTREAM_SHA, LICENSE_SHA, KC_SHA, ARCHIVE_SHA):
        raise ValueError("Pinned source, license, kernel or OpenCore digest mismatch")
    apple_id = "com.apple.driver.usb.AppleUSBXHCIPCI"
    apple = next(p for p in kc_plists(kc.read_bytes()) if p["CFBundleIdentifier"] == apple_id)
    native = apple["IOKitPersonalities"]
    assert native["AppleUSBXHCISPT"]["IOClass"] == "AppleUSBXHCISPT"
    # Missing IOProbeScore defaults to zero, also observed in the live registry.
    generic_score = native["AppleUSBXHCIPCI"].get("IOProbeScore", 0)
    assert generic_score < 900
    base_info = plistlib.loads(original_info.read_bytes())
    chosen = copy.deepcopy(base_info["IOKitPersonalities"][PERSONALITY])
    if chosen["IOPCIPrimaryMatch"] != "0x43ed8086 0xa0ed8086" or chosen["IOClass"] != "AppleUSBXHCISPT":
        raise ValueError("Unexpected pinned community personality")
    chosen["IOPCIPrimaryMatch"] = "0xa0ed8086"
    info = copy.deepcopy(base_info)
    info["IOKitPersonalities"] = {PERSONALITY: chosen}
    if "CFBundleExecutable" in info:
        raise ValueError("Expected a plist-only upstream injector")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-xhci-", dir=ROOT / ".local/install-prep"))
    image = out / "HP-Tahoe-VESA-XHCI.img"
    shutil.copyfile(source, image)

    def mcopy(disk, *arguments):
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", *map(str, arguments)],
                       check=True, capture_output=True, timeout=120)

    before, after = out / "before", out / "after"
    before.mkdir()
    mcopy(source, "-s", "::*", before)
    validate(before)
    old_path = before / "EFI/OC/config.plist"
    if sha(old_path) != CONFIG_SHA:
        raise ValueError("Expected exact delivered Wi-Fi configuration")
    old = plistlib.loads(old_path.read_bytes())
    new = copy.deepcopy(old)
    new["Kernel"]["Add"].append({
        "Arch": "x86_64", "BundlePath": BUNDLE,
        "Comment": "Exact a0ed -> SPT personality only; community-derived, HP runtime untested",
        "Enabled": True, "ExecutablePath": "", "MaxKernel": "25.99.99",
        "MinKernel": "25.0.0", "PlistPath": "Contents/Info.plist"})
    reverted = copy.deepcopy(new)
    reverted["Kernel"]["Add"].pop()
    if reverted != old:
        raise ValueError("Unrelated configuration changed")
    bundle = out / BUNDLE
    (bundle / "Contents").mkdir(parents=True)
    (bundle / "Contents/Info.plist").write_bytes(plistlib.dumps(info, sort_keys=False))
    shutil.copyfile(license_path, bundle / "License.md")
    (bundle / "PROVENANCE.txt").write_text(
        "Derived from DalianSky/OS-X-USB-Inject-All commit " + COMMIT + ".\n"
        "Original XHCI-unsupported plist SHA-256: " + UPSTREAM_SHA + "\n"
        "Original RehabMan/GPL metadata preserved; see License.md.\n"
        "Modifications: retain only AppleUSBXHCISPT 500; narrow PCI ID list to 8086:a0ed.\n"
        "No executable, PCI spoof, port map or patch. Does not match 8086:9a13.\n"
        "Matches an Apple class already present in the actual 25G83 KC; HP behavior untested.\n")
    config = out / "xhci-config.plist"
    config.write_bytes(plistlib.dumps(new, sort_keys=False))
    mcopy(image, "-o", config, "::/EFI/OC/config.plist")
    mcopy(image, "-s", bundle, "::/EFI/OC/Kexts/")
    after.mkdir()
    mcopy(image, "-s", "::*", after)
    validation = validate(after)
    if plistlib.loads((after / "EFI/OC/config.plist").read_bytes()) != new:
        raise ValueError("Config readback differs")
    inventory = lambda path: {str(p.relative_to(path)): sha(p) for p in path.rglob("*") if p.is_file()}
    left, right = inventory(before), inventory(after)
    if any(name not in right or right[name] != digest for name, digest in left.items()
           if name != "EFI/OC/config.plist"):
        raise ValueError("Existing image file changed")
    added = {"EFI/OC/Kexts/" + BUNDLE + "/" + p: d for p, d in inventory(bundle).items()}
    if {p: d for p, d in right.items() if p not in left} != added:
        raise ValueError("Added injector/license/provenance readback differs")
    with zipfile.ZipFile(ARCHIVE) as package:
        validator = out / "ocvalidate"
        validator.write_bytes(package.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")],
                            capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or sha(source) != SOURCE_SHA:
        raise ValueError("Matching validator failed or source changed")
    report = {
        "schema_version": 1, "source": str(source.relative_to(ROOT)), "source_sha256": SOURCE_SHA,
        "image": str(image.relative_to(ROOT)), "sha256": sha(image), "bytes": image.stat().st_size,
        "config_sha256": sha(after / "EFI/OC/config.plist"), "only_config_change": "Append one plist-only exact a0ed -> AppleUSBXHCISPT injector",
        "upstream_commit": COMMIT, "upstream_plist_sha256": UPSTREAM_SHA,
        "upstream_personality_changes": "Keep one SPT 500 personality; narrow two-ID match to a0ed only; all remaining bundle metadata/personality fields preserved",
        "injected_personality": chosen, "other_config_fields_preserved": True,
        "other_image_files_identical": len(left) - 1, "added_files": added,
        "private_identity_preserved": True, "actual_apple_kc_sha256": KC_SHA,
        "actual_kc_class_present": True, "actual_kc_spt_version": apple["CFBundleVersion"],
        "generic_probe_score": generic_score,
        "opencore_version": "1.0.8", "ocvalidate_exit": result.returncode,
        "validation": validation, "runner_sha256": sha(Path(__file__)),
        "validator_sha256": sha(ROOT / "scripts/validate_efi.py"),
        "physical_media_written": False, "hp_tested": False, "vm_executed": False,
        "limit": "SPT matching is a hypothesis for a0ed only; neither port enumeration nor USB operation is established. Existing Wi-Fi/input retained. No 9a13 personality, runtime driver change, port-map or other USB quirk added."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)),
                      **{k: v for k, v in report.items() if k not in ("validation", "added_files")}}, indent=2))


if __name__ == "__main__":
    main()
