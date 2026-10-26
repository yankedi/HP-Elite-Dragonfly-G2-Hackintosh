#!/usr/bin/env python3
"""Prepare one local HP retry changing only boot-args to force slide=0.

Input is a regular IMG file, possibly on an already mounted read-only USB.
The source, its boot log and the private identity are preserved. No VM runs,
USB mounts, physical disk writes or firmware changes are performed.
"""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import zipfile

from check_recovery_probe import ROOT, ARCHIVE, ARCHIVE_SHA
from validate_efi import validate

GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve(strict=True)
    if not source.is_file() or source.stat().st_size != 1343225856:
        raise ValueError("Expected the regular first-boot image")
    if sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("OpenCore archive pin differs")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-slide0-", dir=ROOT / ".local/install-prep"))
    original = out / "original-with-hp-log.img"
    shutil.copyfile(source, original)
    image = out / "HP-Tahoe-VESA-Recovery.img"
    shutil.copyfile(original, image)
    before = out / "before"
    before.mkdir()

    def mcopy(disk, *arguments):
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", *map(str, arguments)],
                       check=True, capture_output=True, timeout=60)

    mcopy(original, "-s", "::/EFI", before)
    validate(before)
    config_path = before / "EFI/OC/config.plist"
    old = plistlib.loads(config_path.read_bytes())
    new = copy.deepcopy(old)
    old_args = old["NVRAM"]["Add"][GUID]["boot-args"]
    words = [word for word in old_args.split() if not word.startswith("slide=")]
    new_args = " ".join([*words, "slide=0"])
    new["NVRAM"]["Add"][GUID]["boot-args"] = new_args
    retry = out / "retry-config.plist"
    retry.write_bytes(plistlib.dumps(new, sort_keys=False))
    mcopy(image, "-o", retry, "::/EFI/OC/config.plist")
    after = out / "after"
    after.mkdir()
    mcopy(image, "-s", "::/EFI", after)
    validate(after)
    roundtrip = plistlib.loads((after / "EFI/OC/config.plist").read_bytes())
    if roundtrip != new:
        raise ValueError("Roundtrip config differs")
    roundtrip["NVRAM"]["Add"][GUID]["boot-args"] = old_args
    if roundtrip != old:
        raise ValueError("Unexpected additional config changes")
    for path in (before / "EFI").rglob("*"):
        if path.is_file() and path != config_path:
            if sha(path) != sha(after / path.relative_to(before)):
                raise ValueError("Unrelated EFI bytes changed")
    with zipfile.ZipFile(ARCHIVE) as archive:
        validator = out / "ocvalidate"
        validator.write_bytes(archive.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")], capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError("Matching ocvalidate failed")
    report = {"source": str(source), "original_sha256": sha(original), "image": str(image.relative_to(ROOT)),
              "sha256": sha(image), "bytes": image.stat().st_size, "only_config_change": "NVRAM boot-args: append slide=0",
              "old_boot_args": old_args, "new_boot_args": new_args, "other_efi_files_identical": True,
              "private_identity_preserved": True, "opencore_ocvalidate_exit": 0,
              "reason": "HP log: KC read Ok(0), EB.MM.AKM Err(0xE) from EB.MM.MKP, automatic slide=91, then STOP 0x16",
              "status": "controlled_physical_retry_pending", "physical_devices_written": False,
              "vm_executed": False, "runner_sha256": sha(Path(__file__))}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
