#!/usr/bin/env python3
"""Reconstruct the verified Apple installer app locally, preserving signed bytes.

The package's own postinstall links the entire hybrid XAR/UDIF package as
Contents/SharedSupport/SharedSupport.dmg. This reproduces that file layout using
a local hard link; it does not execute a package script or install macOS.
"""

import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import plistlib
import struct
import tempfile
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unpack_pbzx(data):
    if data[:4] != b"pbzx" or len(data) < 12:
        raise ValueError("Expected selected Apple's PBZX payload")
    flags = struct.unpack_from(">Q", data, 4)[0]
    offset, result = 12, bytearray()
    while flags & (1 << 24):
        flags, length = struct.unpack_from(">QQ", data, offset)
        offset += 16
        chunk = data[offset:offset + length]
        if len(chunk) != length or len(result) > 128 * 2**20:
            raise ValueError("Unexpected PBZX bounds")
        offset += length
        result.extend(lzma.decompress(chunk) if chunk.startswith(b"\xfd7zXZ\0") else chunk)
    if offset != len(data):
        raise ValueError("Trailing PBZX data")
    return result


def unpack_odc(data, root):
    position, entries = 0, []
    while position + 76 <= len(data):
        if data[position:position + 6] != b"070707":
            raise ValueError("Expected portable ASCII CPIO")
        mode = int(data[position + 18:position + 24], 8)
        namesize = int(data[position + 59:position + 65], 8)
        size = int(data[position + 65:position + 76], 8)
        if namesize < 1 or namesize > 4096:
            raise ValueError("Invalid CPIO name")
        name = data[position + 76:position + 76 + namesize - 1].decode()
        position += 76 + namesize
        content = data[position:position + size]
        if len(content) != size:
            raise ValueError("Truncated CPIO entry")
        position += size
        if name == "TRAILER!!!":
            return entries
        relative = Path(name)
        if name == ".":
            continue
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe CPIO name")
        target = root / relative
        kind = mode & 0o170000
        if kind == 0o040000:
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(mode & 0o777)
            entries.append({"path": str(relative), "type": "directory", "mode": mode & 0o777})
        elif kind == 0o100000:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(content)
            target.chmod(mode & 0o777)
            entries.append({"path": str(relative), "type": "file", "mode": mode & 0o777,
                            "bytes": size, "sha256": hashlib.sha256(content).hexdigest()})
        elif kind == 0o120000:
            entries.append({"path": str(relative), "type": "symlink", "target": content.decode()})
        else:
            raise ValueError("Unsupported CPIO entry")
        # Delay links so no subsequently extracted entry can traverse one.
        if position == len(data):
            raise ValueError("Missing CPIO trailer")
    raise ValueError("Truncated CPIO header")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=".local/install-prep/full-installer/InstallAssistant.pkg")
    parser.add_argument("--verification", required=True)
    args = parser.parse_args()
    package = (ROOT / args.package).resolve(strict=True)
    verification = (ROOT / args.verification).resolve(strict=True)
    if any(not p.is_relative_to(ROOT / ".local") for p in (package, verification)):
        raise ValueError("Inputs must remain private")
    evidence = json.loads(verification.read_text())
    if not all(evidence.get(key) for key in ("toc_rsa_signature_verified", "certificate_chain_verified_at_current_time", "tampered_signature_rejected")):
        raise ValueError("Apple signature audit not complete")
    package_sha = sha(package)
    if evidence["package_sha256"] != package_sha or not all(m["verified"] for m in evidence["members"]):
        raise ValueError("Package differs from verified receipt")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="offline-app-", dir=ROOT / ".local/install-prep"))
    with package.open("rb") as stream:
        magic, header, version, packed, unpacked, algo = struct.unpack(">4sHHQQI", stream.read(28))
        if magic != b"xar!" or header != 28 or packed > 2**20:
            raise ValueError("Unexpected XAR header")
        toc = ET.fromstring(zlib.decompress(stream.read(packed)))
        members = [n for n in toc.findall("./toc/file") if n.findtext("name") == "Payload"]
        if len(members) != 1:
            raise ValueError("Expected one app payload")
        node = members[0].find("data")
        length = int(node.findtext("length"))
        if length > 32 * 2**20:
            raise ValueError("Unexpected selected app prefix size")
        stream.seek(header + packed + int(node.findtext("offset")))
        payload = stream.read(length)
        checksum = node.find("archived-checksum")
        if hashlib.new(checksum.attrib["style"], payload).hexdigest() != checksum.text:
            raise ValueError("Signed app payload checksum differs")
    entries = unpack_odc(unpack_pbzx(payload), out)
    # Restore symlinks only after all regular files have been created.
    for item in entries:
        if item["type"] == "symlink":
            target = out / item["path"]
            destination = item["target"]
            if Path(destination).is_absolute() or not (target.parent / destination).resolve().is_relative_to(out):
                raise ValueError("Unsafe app symlink")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(destination)
    app = out / "Applications/Install macOS Tahoe.app"
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if info["CFBundleDisplayName"] != "Install macOS Tahoe":
        raise ValueError("Unexpected installer app")
    support = app / "Contents/SharedSupport"
    support.mkdir()
    os.link(package, support / "SharedSupport.dmg")
    if (support / "SharedSupport.dmg").stat().st_ino != package.stat().st_ino:
        raise ValueError("SharedSupport hardlink layout differs")
    report = {"schema_version": 1, "app": str(app.relative_to(ROOT)), "status": "offline_app_reconstructed_not_executed",
              "package_sha256": package_sha, "verification_report_sha256": sha(verification),
              "payload_checksum_verified": True, "shared_support_layout": "whole verified hybrid package hardlinked as SharedSupport.dmg",
              "app_display_name": info["CFBundleDisplayName"], "entries": entries,
              "runner_sha256": sha(Path(__file__)), "physical_devices_written": False,
              "package_scripts_executed": False, "macos_installed": False}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "entries"}, indent=2))


if __name__ == "__main__":
    main()
