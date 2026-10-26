#!/usr/bin/env python3
"""Acquire only the public, pinned LLVM PR head; private inputs stay external."""
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SHA = "d575e43643f7c90a1a2728352a24867d7105d9e9"
OUT = ROOT / "toolchain" / "pr204805"
OUT.mkdir(parents=True, exist_ok=True)
records = []
for name, url in [
    ("head.patch", f"https://github.com/llvm/llvm-project/commit/{SHA}.patch"),
    ("source.tar.gz", f"https://codeload.github.com/llvm/llvm-project/tar.gz/{SHA}"),
]:
    dest = OUT / name
    if dest.exists():
        raise SystemExit(f"Refusing to overwrite acquisition: {dest}")
    with urllib.request.urlopen(url, timeout=120) as src, dest.open("xb") as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)
    digest = hashlib.file_digest(dest.open("rb"), "sha256").hexdigest()
    records.append({"url": url, "path": str(dest), "sha256": digest,
                    "bytes": dest.stat().st_size})
    print(json.dumps(records[-1]), flush=True)
(OUT / "acquisition.json").write_text(json.dumps({"head": SHA, "files": records}, indent=2) + "\n")
with tarfile.open(OUT / "source.tar.gz") as archive:
    archive.extractall(OUT, filter="data")
print("EXTRACTED", flush=True)
