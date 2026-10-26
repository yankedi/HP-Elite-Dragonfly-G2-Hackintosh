#!/usr/bin/env python3
"""Build a disposable Ventoy/FAT32 protocol-test disk using regular files only.

This deliberately differs from the physical Lexar's exFAT data volume. A pass
would only establish this virtual FAT32 route; no macOS support is inferred.
"""

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import uuid
import lzma

ROOT = Path(__file__).resolve().parents[1]
ASSET_SHA = "d86ff9de63d94c8b8f1f6b14d23c55af4b88e8207bf2893890892a6a97b1ad54"


def main():
    base = ROOT / ".local/install-prep/ventoy-test"
    asset = base / "ventoy-1.1.18-linux.tar.gz"
    if hashlib.sha256(asset.read_bytes()).hexdigest() != ASSET_SHA:
        raise ValueError("Pinned Ventoy asset differs")
    source = base / "ventoy-1.1.18"
    if not (base / "MediaProbe.efi").is_file():
        raise ValueError("Compile the UEFI media probe first")
    out = Path(tempfile.mkdtemp(prefix="probe-", dir=base))
    efi = out / "files/EFI/BOOT"
    efi.mkdir(parents=True)
    shutil.copyfile(base / "MediaProbe.efi", efi / "BOOTX64.EFI")
    marker = out / "files/OCMEDIAPROBE.TXT"
    marker.write_text("OC_MEDIA_PROBE_2026\n")
    # Partitioned marker image: coherent MBR ESP rather than a GRUB-only loop.
    probe_fs = out / "probe.fat"
    with probe_fs.open("xb") as stream:
        stream.truncate(64 * 2**20)
    subprocess.run(["mkfs.vfat", "-F", "32", "-n", "MEDIAPROBE", str(probe_fs)], check=True)
    for entry in (efi.parent, marker):
        subprocess.run(["mcopy", "-i", str(probe_fs), "-s", str(entry), "::/"], check=True)

    def entry(kind, start, count, active=False):
        return struct.pack("<B3sB3sII", 0x80 if active else 0, b"\xfe\xff\xff", kind, b"\xfe\xff\xff", start, count)

    probe = out / "probe.img"
    mbr = bytearray(512)
    mbr[446:462] = entry(0xEF, 2048, probe_fs.stat().st_size // 512)
    mbr[510:] = b"\x55\xaa"
    with probe.open("xb") as stream:
        stream.write(mbr)
        stream.seek(2048 * 512)
        with probe_fs.open("rb") as part:
            shutil.copyfileobj(part, stream)
    fat = out / "ventoy-data.fat"
    with fat.open("xb") as stream:
        stream.truncate(478 * 2**20)
    subprocess.run(["mkfs.vfat", "-F", "32", "-n", "VENTOYTEST", str(fat)], check=True)
    plugin = out / "ventoy"
    plugin.mkdir()
    (plugin / "ventoy.json").write_text(json.dumps({"control": [{"VTOY_DEFAULT_IMAGE": "/probe.img"}, {"VTOY_MENU_TIMEOUT": "3"}]}) + "\n")
    (plugin / "ventoy_grub.cfg").write_text('menuentry "UEFI media probe F6 loopback" {\n'
        '  loopback ocprobe /probe.img\n'
        '  chainloader (ocprobe,msdos1)/EFI/BOOT/BOOTX64.EFI\n}\n')
    for item in (probe, plugin):
        subprocess.run(["mcopy", "-i", str(fat), "-s", str(item), "::/"], check=True)
    disk = out / "ventoy.raw"
    first, second = 2048, 2048 + fat.stat().st_size // 512
    system_image = lzma.decompress((source / "ventoy/ventoy.disk.img.xz").read_bytes())
    boot = bytearray((source / "boot/boot.img").read_bytes()[:512])
    boot[384:400] = uuid.uuid4().bytes
    boot[440:444] = uuid.uuid4().bytes[:4]
    boot[446:510] = entry(0x0C, first, second - first, True) + entry(0xEF, second, len(system_image) // 512) + bytes(32)
    boot[510:] = b"\x55\xaa"
    with disk.open("xb") as stream:
        stream.write(boot)
        stream.write(lzma.decompress((source / "boot/core.img.xz").read_bytes())[:2047 * 512])
        stream.seek(first * 512)
        with fat.open("rb") as part:
            shutil.copyfileobj(part, stream)
        stream.seek(second * 512)
        stream.write(system_image)
    report = {"disk": str(disk.relative_to(ROOT)), "probe": str(probe.relative_to(ROOT)),
              "ventoy_release_sha256": ASSET_SHA, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "assembly_basis": "Pinned VentoyWorker.sh MBR install writes; FAT32 data partition",
              "data_filesystem": "FAT32", "physical_lexar_filesystem": "exFAT; not equivalent",
              "physical_devices_written": False, "test_executed": False}
    (out / "prepare.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
