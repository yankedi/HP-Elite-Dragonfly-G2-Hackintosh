#!/usr/bin/env python3
"""Private handoff manifest: content, symlinks, and explicit external sources.
Does not run builds, rewrite inputs, open devices, or contact the network.
"""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {"manifest.json", "manifest.sha256", "logs/manifest-verification.json"}

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def entries():
    for directory, dirs, files in os.walk(ROOT, followlinks=False):
        for name in list(dirs):
            path = Path(directory) / name
            if path.is_symlink():
                dirs.remove(name)
                yield path
        for name in files:
            path = Path(directory) / name
            if path.relative_to(ROOT).as_posix() not in EXCLUDE:
                yield path

def describe(path):
    if path.is_symlink():
        row = {"kind": "symlink", "target": os.readlink(path)}
        if path.is_file():
            row["resolved_sha256"] = sha(path)
        elif not path.is_dir():
            raise RuntimeError("Broken symlink: " + str(path))
        return row
    return {"kind": "file", "bytes": path.stat().st_size, "sha256": sha(path)}

def external_files():
    # Original inputs remain private and sealed; external store/toolchain
    # directories are separately pinned in reference/nix-inputs.json.
    old = ROOT.parent / "GA40-NullMoth-Intel"
    found = {old / "manifest.json", old / "manifest.sha256"}
    for source in ("mesa", "nullmoth"):
        for directory, dirs, files in os.walk(old / "sources" / source):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                found.add(Path(directory) / name)
    for path in (old / "tools/intel-env.sh", old / "cache/intel-toolenv/glslang/bin/glslangValidator"):
        found.add(path)
    return {str(p): describe(p) for p in sorted(found)}

def main():
    mode = sys.argv[1]
    manifest = ROOT / "manifest.json"
    if mode == "create":
        if manifest.exists():
            raise RuntimeError("Manifest exists; never silently replace a seal")
        data = {"format": 1, "scope": "GA41 private engineering delivery; no hardware validation",
                "exclusions": sorted(EXCLUDE),
                "local": {str(p.relative_to(ROOT)): describe(p) for p in sorted(entries())},
                "external": external_files()}
        manifest.write_text(json.dumps(data, indent=2) + "\n")
        (ROOT / "manifest.sha256").write_text(sha(manifest) + "  manifest.json\n")
    elif mode != "verify":
        raise RuntimeError("Expected create or verify")
    data = json.loads(manifest.read_text())
    assert (ROOT / "manifest.sha256").read_text() == sha(manifest) + "  manifest.json\n"
    actual = {str(p.relative_to(ROOT)) for p in entries()}
    assert actual == set(data["local"]), (actual - set(data["local"]), set(data["local"]) - actual)
    for rel, row in data["local"].items():
        assert describe(ROOT / rel) == row, rel
    for name, row in data["external"].items():
        assert describe(Path(name)) == row, name
    print(json.dumps({"status": "PASS", "local_entries": len(data["local"]),
                      "external_files": len(data["external"]), "manifest_sha256": sha(manifest),
                      "hardware_approval": "NO"}))

if __name__ == "__main__":
    main()
