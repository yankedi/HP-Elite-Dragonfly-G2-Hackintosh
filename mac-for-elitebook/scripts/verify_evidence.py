#!/usr/bin/env python3
"""Verify hashes, expected binary signatures and ACPI checksums locally."""

import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    errors = []
    files = manifest["files"]
    paths = set()
    for item in files:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or item["path"] in paths:
            errors.append(f"Unsafe or duplicate path: {item['path']}")
            continue
        paths.add(item["path"])
        if not path.is_file():
            errors.append(f"Missing file: {item['path']}")
            continue
        data = path.read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            errors.append(f"Content mismatch: {item['path']}")
        if "/acpi/tables/" in item["path"]:
            if path.name in ("MSDM", "SLIC"):
                errors.append(f"Excluded licensing table collected: {path.name}")
            signature = data[:4]
            if len(data) < 8 or int.from_bytes(data[4:8], "little") != len(data):
                errors.append(f"Invalid ACPI length: {item['path']}")
            if signature != b"FACS" and sum(data) % 256:
                errors.append(f"Invalid ACPI checksum: {item['path']}")
        if path.name == "edid" and (len(data) < 128 or len(data) % 128 or data[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00" or any(sum(data[i:i+128]) % 256 for i in range(0, len(data), 128))):
            errors.append(f"Invalid EDID: {item['path']}")
        if path.name == "i915_vbt" and (len(data) < 32 or not data.startswith(b"$VBT")):
            errors.append("Missing or invalid Intel VBT header")
        if path.name == "report_descriptor" and not data:
            errors.append(f"Empty HID descriptor: {item['path']}")
    for suffix in ("/DSDT", "/i915_vbt", "/edid", "/DMI"):
        if not any(p.endswith(suffix) for p in paths):
            errors.append(f"Required evidence not captured: {suffix}")
    for command in manifest["commands"]:
        if command["exit_code"]:
            errors.append(f"Observation failed ({command['exit_code']}): {command['file']}")
    if manifest.get("binary_collection_exit_code") != 0:
        errors.append("Binary collection failed")
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        raise SystemExit(1)
    print(f"Verified {len(files)} files: SHA-256, ACPI lengths/checksums, EDID and VBT signatures.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_evidence.py <capture-directory>")
    verify(Path(sys.argv[1]))
