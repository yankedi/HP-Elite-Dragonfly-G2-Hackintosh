#!/usr/bin/env python3
"""Prepare a stock DebugEnhancer logging trial from the exact-XHCI baseline.

Local build only. The ineffective msgbuf boot argument is absent from this
baseline. Buffer allocation and early-log retention still require a real boot.
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
from prepare_hp_slide_retry import sha
from validate_efi import validate

SOURCE_SHA = "e55eb607858afda49cda89fe8a9f023143ff49ce20a937424cd9ba704a66ae72"
CONFIG_SHA = "16a96225ef43189b85bef7405451a9ec84dd047a8e111b5071cf9dfc3398b2c4"
ASSET_SHA = "2c0978c43fb6179fd5195ddec14c4dd9ab2eb46262021a33fcab78b5568ef67f"
LICENSE_SHA = "9ef9bc3812b1e479b33d940623482ae56de90282a04de9e1776b4f0b218471f4"
COMMIT = "8792fba2b28e51599e45e1293de868a179563d3a"
BUNDLE = "DebugEnhancer.kext"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--license", required=True)
    args = parser.parse_args()
    source, archive, license_path = [(ROOT / p).resolve(strict=True)
                                     for p in (args.source, args.archive, args.license)]
    if any(not p.is_relative_to(ROOT / ".local") or not p.is_file()
           for p in (source, archive, license_path)):
        raise ValueError("Expected private regular input files")
    if (sha(source), sha(archive), sha(license_path), sha(ARCHIVE)) != (
            SOURCE_SHA, ASSET_SHA, LICENSE_SHA, ARCHIVE_SHA):
        raise ValueError("Pinned input digest mismatch")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-dbgenh-", dir=ROOT / ".local/install-prep"))
    image = out / "HP-Tahoe-VESA-XHCI-DBGENH.img"
    shutil.copyfile(source, image)

    def mcopy(disk, *arguments):
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", *map(str, arguments)],
                       capture_output=True, check=True, timeout=120)

    before, after = out / "before", out / "after"
    before.mkdir()
    mcopy(source, "-s", "::*", before)
    validate(before)
    config_path = before / "EFI/OC/config.plist"
    if sha(config_path) != CONFIG_SHA:
        raise ValueError("Expected exact XHCI configuration")
    original = plistlib.loads(config_path.read_bytes())
    config = copy.deepcopy(original)
    if "msgbuf=" in config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]:
        raise ValueError("Expected baseline without ineffective msgbuf argument")
    asset = out / "asset"
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            path = Path(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe archive path")
        package.extractall(asset)
    bundle = asset / BUNDLE
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    if info["CFBundleIdentifier"] != "as.lvs1974.DebugEnhancer" or info["CFBundleVersion"] != "1.1.1":
        raise ValueError("Unexpected diagnostic bundle identity")
    shutil.copyfile(license_path, bundle / "LICENSE.txt")
    config["Kernel"]["Add"].append({
        "Arch": "x86_64", "BundlePath": BUNDLE,
        "Comment": "Pinned stock 1.1.1 logging/buffer trial; actual HP allocation untested",
        "Enabled": True, "ExecutablePath": "Contents/MacOS/" + info["CFBundleExecutable"],
        "MaxKernel": "25.99.99", "MinKernel": "25.0.0", "PlistPath": "Contents/Info.plist"})
    reverted = copy.deepcopy(config)
    reverted["Kernel"]["Add"].pop()
    if reverted != original:
        raise ValueError("Unrelated configuration changed")
    changed = out / "dbgenh-config.plist"
    changed.write_bytes(plistlib.dumps(config, sort_keys=False))
    mcopy(image, "-o", changed, "::/EFI/OC/config.plist")
    mcopy(image, "-s", bundle, "::/EFI/OC/Kexts/")
    after.mkdir()
    mcopy(image, "-s", "::*", after)
    validation = validate(after)
    if plistlib.loads((after / "EFI/OC/config.plist").read_bytes()) != config:
        raise ValueError("Configuration readback differs")
    inventory = lambda directory: {str(p.relative_to(directory)): sha(p)
                                   for p in directory.rglob("*") if p.is_file()}
    left, right = inventory(before), inventory(after)
    if any(right.get(name) != digest for name, digest in left.items()
           if name != "EFI/OC/config.plist"):
        raise ValueError("Existing IMG file changed")
    added = {"EFI/OC/Kexts/" + BUNDLE + "/" + name: digest
             for name, digest in inventory(bundle).items()}
    if {name: digest for name, digest in right.items() if name not in left} != added:
        raise ValueError("Diagnostic bundle readback differs")
    with zipfile.ZipFile(ARCHIVE) as package:
        validator = out / "ocvalidate"
        validator.write_bytes(package.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")],
                            capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or sha(source) != SOURCE_SHA:
        raise ValueError("Validation failed or source changed")
    report = {
        "schema_version": 1, "source": str(source.relative_to(ROOT)), "source_sha256": SOURCE_SHA,
        "image": str(image.relative_to(ROOT)), "sha256": sha(image), "bytes": image.stat().st_size,
        "asset_sha256": ASSET_SHA, "upstream_commit": COMMIT,
        "config_sha256": sha(after / "EFI/OC/config.plist"),
        "only_config_change_from_xhci": "Append stock DebugEnhancer1.1.1 to Kernel.Add",
        "ineffective_msgbuf_argument_absent": True, "no_extra_debug_bootargs": True,
        "other_config_fields_and_identity_preserved": True,
        "other_image_files_identical": len(left) - 1, "added_files": added,
        "opencore_version": "1.0.8", "ocvalidate_exit": result.returncode,
        "validation": validation, "runner_sha256": sha(Path(__file__)),
        "physical_media_written": False, "hp_tested": False, "vm_executed": False,
        "limit": "Diagnostic only. Stock fallback requests10MiB independently of kernel route group; actual KC lacks _log_setsize and unmangled _IOHibernateSystemSleep. Buffer fallback symbols/layout verified separately. Expected route-group failure does not imply allocation failure or success. No USB power/class/port changes; runtime allocation, earliest logs and bootability remain untested."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)),
                      **{k: v for k, v in report.items() if k not in ("validation", "added_files")}}, indent=2))


if __name__ == "__main__":
    main()
