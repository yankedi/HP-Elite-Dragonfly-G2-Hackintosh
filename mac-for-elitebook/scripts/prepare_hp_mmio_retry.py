#!/usr/bin/env python3
"""Prepare a private HP retry changing only DevirtualiseMmio to true.

Preserves the failed slide=0 image, all identities, other EFI bytes and Recovery.
Does not run a VM, touch firmware, or write a physical device.
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--analysis", required=True)
    args = parser.parse_args()
    source, analysis = [(ROOT / value).resolve(strict=True) for value in (args.source, args.analysis)]
    if any(not p.is_relative_to(ROOT / ".local") or not p.is_file() for p in (source, analysis)):
        raise ValueError("Inputs must be private regular files")
    if source.stat().st_size != 1343225856 or sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Image size or OpenCore archive pin differs")
    diagnosis = json.loads(analysis.read_text())
    if not (diagnosis["slide_zero_retry_still_failed"] and diagnosis["booter_mmio_ranges_match_linux_runtime_mmio"]):
        raise ValueError("Expected captured slide-zero failure and firmware MMIO correspondence")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-mmio-", dir=ROOT / ".local/install-prep"))
    image = out / "HP-Tahoe-VESA-Recovery.img"
    source_sha = sha(source)
    shutil.copyfile(source, image)

    def mcopy(disk, *arguments):
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", *map(str, arguments)],
                       check=True, capture_output=True, timeout=60)

    before = out / "before"
    before.mkdir()
    mcopy(source, "-s", "::/EFI", before)
    validate(before)
    old_path = before / "EFI/OC/config.plist"
    old = plistlib.loads(old_path.read_bytes())
    if old["Booter"]["Quirks"]["DevirtualiseMmio"] is not False or "slide=0" not in old["NVRAM"]["Add"][GUID]["boot-args"].split():
        raise ValueError("Expected unmodified slide=0 baseline")
    new = copy.deepcopy(old)
    new["Booter"]["Quirks"]["DevirtualiseMmio"] = True
    config = out / "retry-config.plist"
    config.write_bytes(plistlib.dumps(new, sort_keys=False))
    mcopy(image, "-o", config, "::/EFI/OC/config.plist")
    after = out / "after"
    after.mkdir()
    mcopy(image, "-s", "::/EFI", after)
    validate(after)
    roundtrip = plistlib.loads((after / "EFI/OC/config.plist").read_bytes())
    if roundtrip != new:
        raise ValueError("Readback config differs")
    roundtrip["Booter"]["Quirks"]["DevirtualiseMmio"] = False
    if roundtrip != old:
        raise ValueError("Additional plist fields changed")
    old_files = {p.relative_to(before) for p in (before / "EFI").rglob("*") if p.is_file()}
    new_files = {p.relative_to(after) for p in (after / "EFI").rglob("*") if p.is_file()}
    if old_files != new_files:
        raise ValueError("EFI file set changed")
    unchanged = 0
    for relative in old_files - {Path("EFI/OC/config.plist")}:
        if sha(before / relative) != sha(after / relative):
            raise ValueError("Unrelated EFI bytes changed")
        unchanged += 1
    with zipfile.ZipFile(ARCHIVE) as archive:
        validator = out / "ocvalidate"
        validator.write_bytes(archive.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")], capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or sha(source) != source_sha:
        raise ValueError("Validation failed or preserved source changed")
    report = {"schema_version": 1, "source": str(source.relative_to(ROOT)), "source_sha256": source_sha,
              "image": str(image.relative_to(ROOT)), "bytes": image.stat().st_size, "sha256": sha(image),
              "only_config_change": "Booter.Quirks.DevirtualiseMmio: false -> true",
              "boot_args_unchanged": old["NVRAM"]["Add"][GUID]["boot-args"],
              "other_efi_files_identical": unchanged, "private_identity_preserved": True,
              "opencore_version": "1.0.8", "ocvalidate_exit": result.returncode,
              "analysis_sha256": sha(analysis), "runner_sha256": sha(Path(__file__)),
              "physical_devices_written": False, "vm_executed": False, "hp_retry_executed": False}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
