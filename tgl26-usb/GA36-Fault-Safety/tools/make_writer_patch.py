#!/usr/bin/env python3
"""Produce a reproducible unified patch; no historical or candidate source edits."""
import difflib
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRACK = ROOT / "track-a"
diff = []
for name in ("kern_igfx.cpp", "kern_igfx.hpp", "kern_tglhang.hpp", "kern_capture36.hpp", "thag36.py"):
    old = TRACK / "baseline" / name
    new = TRACK / "candidate" / name
    a = old.read_text().splitlines(True) if old.exists() else []
    b = new.read_text().splitlines(True)
    diff.extend(difflib.unified_diff(a, b, fromfile="a/" + name if old.exists() else "/dev/null", tofile="b/" + name))
path = TRACK / "CAS-FIX.patch"
path.write_text("".join(diff))
p = subprocess.run(["patch", "--dry-run", "--batch", "-p1", "-i", str(path)], cwd=TRACK / "baseline", capture_output=True, text=True, timeout=30)
(TRACK / "logs/patch-check.txt").write_text(p.stdout + p.stderr)
p.check_returncode()
hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (TRACK / "candidate").iterdir() if p.is_file()}
(TRACK / "logs/candidate-hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
print("PASS reproducible CAS-FIX.patch applies in dry-run; candidate hashes recorded")
