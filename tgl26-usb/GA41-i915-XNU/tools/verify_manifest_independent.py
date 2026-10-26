#!/usr/bin/env python3
"""Read-only independent implementation; does not import manifest.py."""
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = root / "manifest.json"
data = json.loads(manifest.read_text())
pin = hashlib.sha256(manifest.read_bytes()).hexdigest()
assert (root / "manifest.sha256").read_text() == pin + "  manifest.json\n"
excluded = {"manifest.json", "manifest.sha256", "logs/manifest-verification.json"}
assert set(data["exclusions"]) == excluded
found = set()
for base, dirs, files in os.walk(root, followlinks=False):
    for name in list(dirs):
        p = Path(base) / name
        if p.is_symlink():
            dirs.remove(name)
            files.append(name)
    found.update(str((Path(base) / name).relative_to(root)) for name in files)
assert found - excluded == set(data["local"]), "unexpected/missing local files"
for section in ("local", "external"):
    for name, row in data[section].items():
        p = root / name if section == "local" else Path(name)
        if row["kind"] == "symlink":
            assert p.is_symlink() and os.readlink(p) == row["target"], str(p)
            assert p.exists(), str(p)
            if "resolved_sha256" not in row:
                assert p.is_dir(), str(p)
                continue
            expected = row["resolved_sha256"]
        else:
            assert not p.is_symlink() and p.is_file() and p.stat().st_size == row["bytes"], str(p)
            expected = row["sha256"]
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while True:
                block = f.read(262144)
                if not block:
                    break
                h.update(block)
        assert h.hexdigest() == expected, str(p)
print(json.dumps({"status": "PASS", "implementation": "independent, no manifest.py import",
                  "local_entries": len(data["local"]), "external_files": len(data["external"]),
                  "manifest_sha256": pin, "hardware_approval": "NO"}))
