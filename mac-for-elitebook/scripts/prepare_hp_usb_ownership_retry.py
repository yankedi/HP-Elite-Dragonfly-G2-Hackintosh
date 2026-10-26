#!/usr/bin/env python3
"""Prepare a private, single-change USB ownership trial from the tested HP IMG.

Changes only UEFI.Quirks.ReleaseUsbOwnership, preserving every other file and
configuration field. Does not mount a USB, write a physical disk, or boot a VM.
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

BASE_CONFIG_SHA = "92cc051cdbb41840928b2a2137e8ef622bc586f78a9a96bdc209b0f01974cc33"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = (ROOT / args.source).resolve(strict=True)
    if not source.is_relative_to(ROOT / ".local") or not source.is_file() or source.stat().st_size != 1343225856:
        raise ValueError("Expected a private captured HP Recovery regular image")
    if sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("OpenCore release archive differs from pin")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-usb-ownership-", dir=ROOT / ".local/install-prep"))
    image = out / "HP-Tahoe-VESA-Recovery.img"
    original_sha = sha(source)
    shutil.copyfile(source, image)

    def mcopy(disk, *arguments):
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", *map(str, arguments)],
                       check=True, capture_output=True, timeout=120)

    before, after = out / "before", out / "after"
    before.mkdir()
    mcopy(source, "-s", "::*", before)
    validate(before)
    old_path = before / "EFI/OC/config.plist"
    if sha(old_path) != BASE_CONFIG_SHA:
        raise ValueError("Expected the captured input-trial configuration")
    old = plistlib.loads(old_path.read_bytes())
    if old["UEFI"]["Quirks"]["ReleaseUsbOwnership"] is not False:
        raise ValueError("USB ownership flag already changed")
    new = copy.deepcopy(old)
    new["UEFI"]["Quirks"]["ReleaseUsbOwnership"] = True
    changed = out / "retry-config.plist"
    changed.write_bytes(plistlib.dumps(new, sort_keys=False))
    mcopy(image, "-o", changed, "::/EFI/OC/config.plist")
    after.mkdir()
    mcopy(image, "-s", "::*", after)
    validation = validate(after)
    roundtrip = plistlib.loads((after / "EFI/OC/config.plist").read_bytes())
    if roundtrip != new:
        raise ValueError("Readback configuration differs")
    roundtrip["UEFI"]["Quirks"]["ReleaseUsbOwnership"] = False
    if roundtrip != old:
        raise ValueError("Unrelated configuration changed")

    def inventory(directory):
        return {str(p.relative_to(directory)): sha(p) for p in directory.rglob("*") if p.is_file()}

    left, right = inventory(before), inventory(after)
    if left.keys() != right.keys():
        raise ValueError("Filesystem file set changed")
    differences = [name for name in left if left[name] != right[name]]
    if differences != ["EFI/OC/config.plist"]:
        raise ValueError("Unrelated image files changed: " + repr(differences))
    with zipfile.ZipFile(ARCHIVE) as release:
        validator = out / "ocvalidate"
        validator.write_bytes(release.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")], capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or sha(source) != original_sha:
        raise ValueError("Matching ocvalidate failed or captured source changed")
    report = {
        "schema_version": 1, "source": str(source.relative_to(ROOT)), "source_sha256": original_sha,
        "image": str(image.relative_to(ROOT)), "bytes": image.stat().st_size, "sha256": sha(image),
        "only_config_change": "UEFI.Quirks.ReleaseUsbOwnership: false -> true",
        "source_config_sha256": BASE_CONFIG_SHA, "candidate_config_sha256": sha(after / "EFI/OC/config.plist"),
        "all_other_config_fields_preserved": True, "private_identity_preserved": True,
        "all_other_image_files_identical": len(left) - 1,
        "other_efi_files_identical": sum(name.startswith("EFI/") and name != "EFI/OC/config.plist" for name in left),
        "preserved_file_sha256": {name: digest for name, digest in left.items() if name != "EFI/OC/config.plist"},
        "opencore_version": "1.0.8", "ocvalidate_exit": result.returncode, "validation": validation,
        "runner_sha256": sha(Path(__file__)), "physical_devices_written": False, "vm_executed": False,
        "hp_retry_executed": False,
        "limit": "Tests firmware USB ownership release hypothesis only. Not proof of USB operation or Ventoy causation."
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)),
                      **{k: v for k, v in report.items() if k not in ("preserved_file_sha256", "validation")}}, indent=2))


if __name__ == "__main__":
    main()
