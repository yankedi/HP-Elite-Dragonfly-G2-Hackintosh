#!/usr/bin/env python3
"""Fetch the selected Apple full installer into .local without installing it.

This records transport/length/hash evidence only. XAR signature, inner build,
offline completeness and media bootability must be assessed separately.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
URL = ("https://swcdn.apple.com/content/downloads/37/33/140-93587-A_GRFFH93NOL/"
       "f944yaqo1cjhh2m0kxrl0zhcpg9yb9qphv/InstallAssistant.pkg")
EXPECTED_BYTES = 18384624402
DISCOVERY = "https://mrmacintosh.com/macos-tahoe-full-installer-database-download-directly-from-apple/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".local/install-prep/full-installer")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / ".local"):
        raise ValueError("Full installer output must stay in private .local")
    output.mkdir(parents=True, exist_ok=True)
    target = output / "InstallAssistant.pkg"
    if target.is_symlink() or target.exists() and not target.is_file():
        raise ValueError("Package output must be a regular private file")
    before = target.stat().st_size if target.exists() else 0
    if before > EXPECTED_BYTES:
        raise ValueError("Existing file exceeds selected Apple package size")
    command = ["curl", "--proto", "=https", "--proto-redir", "=https", "--fail", "--location",
               "--retry", "3", "--connect-timeout", "30", "--max-time", "1800",
               "--speed-time", "60", "--speed-limit", "1024", "--continue-at", "-",
               "--dump-header", str(output / "download.headers"), "--output", str(target), URL]
    if before != EXPECTED_BYTES:
        with (output / "download.stdout").open("wb") as out, (output / "download.stderr").open("wb") as err:
            result = subprocess.run(command, stdout=out, stderr=err, timeout=1900)
        if result.returncode:
            raise SystemExit(f"Download exited {result.returncode}; retained prefix and private logs for continuation")
    size = target.stat().st_size
    if size != EXPECTED_BYTES:
        raise SystemExit(f"Incomplete package: {size}/{EXPECTED_BYTES}; rerun to continue")
    with target.open("rb") as stream:
        magic = stream.read(4)
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if magic != b"xar!":
        raise ValueError("Downloaded package is not an XAR container")
    report = {"schema_version": 1, "fetched_at": datetime.now(timezone.utc).isoformat(),
              "url": URL, "discovery": DISCOVERY, "version_claim": "26.6.2", "build_claim": "25G83",
              "bytes": size, "sha256": digest, "prefix_before_download_bytes": before,
              "xar_magic_verified": True, "xar_signature_verified": False,
              "internal_build_verified": False, "bootable_media_created": False,
              "macos_installed": False, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / "fetch-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
