#!/usr/bin/env python3
"""Package the private HP VESA candidate plus signed Recovery as a Ventoy IMG.

Creates one new regular image inside .local, never writes a USB or internal EFI.
This is first-boot test media, not a complete offline macOS installer.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile

from check_recovery_probe import ARCHIVE, ARCHIVE_SHA, ROOT, SCRIPT_SHA
from validate_efi import validate


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--recovery", default=".local/recovery-repair/recovery")
    args = parser.parse_args()
    candidate, recovery = [(ROOT / value).resolve(strict=True) for value in (args.candidate, args.recovery)]
    if any(not path.is_relative_to(ROOT / ".local") for path in (candidate, recovery)):
        raise ValueError("Candidate and recovery must remain private")
    report = json.loads((candidate / "report.json").read_text())
    if report["opencore_version"] != "1.0.8" or report["ocvalidate_exit_code"] != 0:
        raise ValueError("Candidate has no matching validation")
    for item in report["files"]:
        path = (candidate / item["path"]).resolve(strict=True)
        if not path.is_relative_to(candidate) or sha(path) != item["sha256"]:
            raise ValueError("Candidate bytes differ")
    validate(candidate)
    if sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Pinned OpenCore archive differs")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="first-boot-", dir=ROOT / ".local/install-prep"))
    with zipfile.ZipFile(ARCHIVE) as archive:
        verifier = out / "macrecovery.py"
        verifier.write_bytes(archive.read("Utilities/macrecovery/macrecovery.py"))
    if sha(verifier) != SCRIPT_SHA:
        raise ValueError("Pinned chunk verifier differs")
    spec = importlib.util.spec_from_file_location("pinned_first_boot_verifier", verifier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    chunks = list(module.verify_chunklist(recovery / "BaseSystem.chunklist"))
    with (recovery / "BaseSystem.dmg").open("rb") as stream:
        for length, digest in chunks:
            data = stream.read(length)
            if len(data) != length or hashlib.sha256(data).digest() != digest:
                raise ValueError("Recovery differs from Apple signed chunklist")
        if stream.read(1):
            raise ValueError("Recovery has trailing data")
    files = out / "files"
    files.mkdir()
    shutil.copytree(candidate / "EFI", files / "EFI")
    media = files / "com.apple.recovery.boot"
    media.mkdir()
    for name in ("BaseSystem.dmg", "BaseSystem.chunklist"):
        shutil.copyfile(recovery / name, media / name)
    shutil.copyfile(ROOT / "scripts/collect_macos_handoff.sh", files / "collect_macos_handoff.sh")
    (files / "FIRST-BOOT.txt").write_text(
        "HP VESA first-boot test only; no complete offline installation payload.\n"
        "Select this IMG in existing Ventoy, then choose the macOS recovery entry in OpenCore.\n"
        "Do not use Reset NVRAM or install to an unidentified partition.\n"
        "Photograph the final error or Recovery screen. Private identity is embedded; do not publish this image.\n")
    fat = out / "payload.fat"
    with fat.open("xb") as stream:
        stream.truncate(1280 * 2**20)
    commands = []

    def run(command):
        result = subprocess.run(command, capture_output=True, timeout=120)
        commands.append({"command": command, "exit_code": result.returncode})
        if result.returncode:
            raise ValueError(result.stderr.decode(errors="replace"))

    run(["mkfs.vfat", "-F", "32", "-n", "HPRECOVERY", str(fat)])
    for entry in sorted(files.iterdir()):
        run(["mcopy", "-i", str(fat), "-s", str(entry), "::/"])
    image = out / "HP-Tahoe-VESA-Recovery.img"
    mbr = bytearray(512)
    mbr[440:444] = os.urandom(4)
    mbr[446:462] = struct.pack("<B3sB3sII", 0x80, b"\xfe\xff\xff", 0xEF, b"\xfe\xff\xff", 2048, fat.stat().st_size // 512)
    mbr[510:] = b"\x55\xaa"
    with image.open("xb") as stream:
        stream.write(mbr)
        stream.seek(2**20)
        with fat.open("rb") as source:
            shutil.copyfileobj(source, stream)
    # Independently extract the copied EFI and signed inputs via mtools.
    extracted = out / "roundtrip"
    extracted.mkdir()
    run(["mcopy", "-i", str(image) + "@@1048576", "-s", "::/EFI", str(extracted)])
    validate(extracted)
    for item in report["files"]:
        if sha(extracted / item["path"]) != item["sha256"]:
            raise ValueError("Image roundtrip EFI differs")
    run(["mcopy", "-i", str(image) + "@@1048576", "-s", "::/com.apple.recovery.boot", str(extracted)])
    for name in ("BaseSystem.dmg", "BaseSystem.chunklist"):
        if sha(extracted / "com.apple.recovery.boot" / name) != sha(recovery / name):
            raise ValueError("Image roundtrip Recovery differs")
    result = subprocess.run([str(candidate / "ocvalidate"), str(extracted / "EFI/OC/config.plist")], capture_output=True, timeout=20)
    (out / "roundtrip-ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError("Roundtrip config failed matching ocvalidate")
    receipt = {"status": "first_boot_test_image_unbooted_on_HP", "image": str(image.relative_to(ROOT)),
               "bytes": image.stat().st_size, "sha256": sha(image), "runner_sha256": sha(Path(__file__)),
               "candidate_report_sha256": sha(candidate / "report.json"), "apple_signed_chunks_verified": len(chunks),
               "roundtrip_bytes_verified": True, "roundtrip_ocvalidate_exit": 0, "commands": commands,
               "full_offline_installation_payload": False, "hp_boot_tested": False,
               "ventoy_apple_boot_chain_tested": False, "physical_devices_written": False,
               "private_identity_embedded": True}
    (out / "report.json").write_text(json.dumps(receipt, indent=2) + "\n")
    # Only exact generated intermediates are removed after the independent readback.
    fat.unlink()
    shutil.rmtree(extracted)
    shutil.rmtree(files)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
