#!/usr/bin/env python3
"""Prepare a private Tahoe Wi-Fi-only candidate; no physical writes or VM.

Adds the pinned AirportItlwm Tahoe release to the delivered ownership baseline.
Keeps input, graphics, ACPI, USB settings, private identity and Recovery intact.
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

SOURCE_SHA = "0610299a23fff511149ddb84f1d8da15d63f25b66aeb00e3bceb55118010f490"
CONFIG_SHA = "38734ef1fee5f24796274448fa91ac75869c6058a08a8125d2c3510cdcbc784f"
ASSET_SHA = "f47b8320f90b71c25d1bf3d37e471c6e50c016e2e70c1eb7069e599b22dc6878"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--wifi-archive", required=True)
    args = parser.parse_args()
    source, archive = [(ROOT / p).resolve(strict=True) for p in (args.source, args.wifi_archive)]
    if any(not p.is_relative_to(ROOT / ".local") or not p.is_file() for p in (source, archive)):
        raise ValueError("Expected private regular input files")
    if sha(source) != SOURCE_SHA or sha(archive) != ASSET_SHA or sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Pinned input digest mismatch")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-wifi-", dir=ROOT / ".local/install-prep"))
    image = out / "HP-Tahoe-VESA-WiFi.img"
    shutil.copyfile(source, image)

    def mcopy(disk, *arguments):
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", *map(str, arguments)],
                       capture_output=True, check=True, timeout=120)

    before, after = out / "before", out / "after"
    before.mkdir()
    mcopy(source, "-s", "::*", before)
    validate(before)
    old_path = before / "EFI/OC/config.plist"
    if sha(old_path) != CONFIG_SHA:
        raise ValueError("Expected exact delivered ownership configuration")
    old = plistlib.loads(old_path.read_bytes())
    new = copy.deepcopy(old)
    asset = out / "asset"
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            path = Path(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe archive path")
        package.extractall(asset)
    bundle = asset / "AirportItlwm.kext"
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    if info["CFBundleIdentifier"] != "com.zxystd.AirportItlwm" or info["CFBundleVersion"] != "2.4.0":
        raise ValueError("Unexpected Wi-Fi bundle identity")
    new["Kernel"]["Add"].append({
        "Arch": "x86_64", "BundlePath": "AirportItlwm.kext",
        "Comment": "Pinned Tahoe alpha; AX201 Recovery Wi-Fi experiment, runtime untested",
        "Enabled": True, "ExecutablePath": "Contents/MacOS/" + info["CFBundleExecutable"],
        "MaxKernel": "25.99.99", "MinKernel": "25.0.0", "PlistPath": "Contents/Info.plist"})
    revert = copy.deepcopy(new)
    revert["Kernel"]["Add"].pop()
    if revert != old:
        raise ValueError("Unrelated configuration change")
    config = out / "wifi-config.plist"
    config.write_bytes(plistlib.dumps(new, sort_keys=False))
    mcopy(image, "-o", config, "::/EFI/OC/config.plist")
    mcopy(image, "-s", bundle, "::/EFI/OC/Kexts/")
    after.mkdir()
    mcopy(image, "-s", "::*", after)
    validation = validate(after)
    if plistlib.loads((after / "EFI/OC/config.plist").read_bytes()) != new:
        raise ValueError("Readback config mismatch")
    inventory = lambda directory: {str(p.relative_to(directory)): sha(p)
                                   for p in directory.rglob("*") if p.is_file()}
    left, right, added = inventory(before), inventory(after), inventory(bundle)
    if any(name not in right or right[name] != digest for name, digest in left.items()
           if name != "EFI/OC/config.plist"):
        raise ValueError("Unrelated existing IMG file changed")
    expected_new = {"EFI/OC/Kexts/AirportItlwm.kext/" + name: digest for name, digest in added.items()}
    if {name: digest for name, digest in right.items() if name not in left} != expected_new:
        raise ValueError("Added bundle files differ from release")
    with zipfile.ZipFile(ARCHIVE) as release:
        validator = out / "ocvalidate"
        validator.write_bytes(release.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")],
                            capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or sha(source) != SOURCE_SHA:
        raise ValueError("Validation failed or source changed")
    report = {
        "schema_version": 1, "source": str(source.relative_to(ROOT)), "source_sha256": SOURCE_SHA,
        "image": str(image.relative_to(ROOT)), "sha256": sha(image), "bytes": image.stat().st_size,
        "asset_sha256": ASSET_SHA, "config_sha256": sha(after / "EFI/OC/config.plist"),
        "only_config_change": "Append pinned Tahoe AirportItlwm to Kernel.Add for Darwin 25.x",
        "other_config_fields_preserved": True, "other_image_files_identical": len(left) - 1,
        "added_files": expected_new, "private_identity_preserved": True,
        "opencore_version": "1.0.8", "ocvalidate_exit": result.returncode,
        "validation": validation, "runner_sha256": sha(Path(__file__)),
        "physical_devices_written": False, "vm_executed": False, "hp_wifi_tested": False,
        "limit": "Static checks do not prove Wi-Fi probing, Recovery UI, association, DHCP, SSH or Internet."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)),
                      **{k: v for k, v in report.items() if k not in ("validation", "added_files")}}, indent=2))


if __name__ == "__main__":
    main()
