#!/usr/bin/env python3
"""Enlarge the next boot's kernel log buffer, preserving XHCI trial hardware settings."""

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
GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
ARGUMENT = "msgbuf=1048576"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = (ROOT / args.source).resolve(strict=True)
    if not source.is_relative_to(ROOT / ".local") or not source.is_file():
        raise ValueError("Expected a private XHCI candidate image")
    if sha(source) != SOURCE_SHA or sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Source image or OpenCore release digest differs")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-logbuffer-", dir=ROOT / ".local/install-prep"))
    image = out / "HP-Tahoe-VESA-XHCI-Log.img"
    shutil.copyfile(source, image)

    def extract(disk, destination):
        destination.mkdir()
        subprocess.run(["mcopy", "-i", str(disk) + "@@1048576", "-s", "::*", str(destination)],
                       check=True, capture_output=True, timeout=90)

    before, after = out / "before", out / "after"
    extract(source, before)
    config_path = before / "EFI/OC/config.plist"
    if sha(config_path) != CONFIG_SHA:
        raise ValueError("Expected exact delivered XHCI configuration")
    original = plistlib.loads(config_path.read_bytes())
    config = copy.deepcopy(original)
    args_before = original["NVRAM"]["Add"][GUID]["boot-args"]
    if any(word.startswith("msgbuf=") for word in args_before.split()):
        raise ValueError("Log buffer argument already exists")
    config["NVRAM"]["Add"][GUID]["boot-args"] = args_before + " " + ARGUMENT
    reverted = copy.deepcopy(config)
    reverted["NVRAM"]["Add"][GUID]["boot-args"] = args_before
    if reverted != original:
        raise ValueError("Unrelated configuration changed")
    changed = out / "log-config.plist"
    changed.write_bytes(plistlib.dumps(config, sort_keys=False))
    subprocess.run(["mcopy", "-i", str(image) + "@@1048576", "-o", str(changed),
                    "::/EFI/OC/config.plist"], check=True, capture_output=True, timeout=30)
    extract(image, after)
    inventory = lambda directory: {str(p.relative_to(directory)): sha(p)
                                   for p in directory.rglob("*") if p.is_file()}
    left, right = inventory(before), inventory(after)
    if left.keys() != right.keys() or [name for name in left if left[name] != right[name]] != ["EFI/OC/config.plist"]:
        raise ValueError("Expected only the config file to change")
    if plistlib.loads((after / "EFI/OC/config.plist").read_bytes()) != config:
        raise ValueError("Configuration readback differs")
    validation = validate(after)
    with zipfile.ZipFile(ARCHIVE) as package:
        validator = out / "ocvalidate"
        validator.write_bytes(package.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o700)
    result = subprocess.run([str(validator), str(after / "EFI/OC/config.plist")],
                            capture_output=True, timeout=20)
    (out / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or sha(source) != SOURCE_SHA:
        raise ValueError("Validator failed or source changed")
    report = {"schema_version": 1, "source": str(source.relative_to(ROOT)), "source_sha256": SOURCE_SHA,
              "image": str(image.relative_to(ROOT)), "sha256": sha(image), "bytes": image.stat().st_size,
              "config_sha256": sha(after / "EFI/OC/config.plist"), "only_change": "Append " + ARGUMENT,
              "other_image_files_identical": len(left) - 1, "other_config_fields_and_identity_preserved": True,
              "kernel_add_acpi_driver_and_usb_settings_preserved": True, "requested_log_buffer_bytes": 1048576,
              "opencore_version": "1.0.8", "ocvalidate_exit": result.returncode, "validation": validation,
              "runner_sha256": sha(Path(__file__)), "physical_media_written": False, "hp_tested": False,
              "vm_executed": False,
              "limit": "Diagnostic only, not a USB fix. Public XNU12377.1.9 supports msgbuf up to1MiB; actual12377.161.14 buffer acceptance and early-log retention require a physical boot. No new binary kexts, so prior native injection evidence remains applicable without another link run."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)),
                      **{k: v for k, v in report.items() if k != "validation"}}, indent=2))


if __name__ == "__main__":
    main()
