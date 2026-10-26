#!/usr/bin/env python3
"""Fetch/resume a recovery DMG, verifying Apple's signature and every chunk.

Official latest-recovery queries do not pin a macOS build. A mirror can supply
both files or the DMG alone; the same pinned Apple signature verifier applies.
All downloads, receipts and tokens stay in the ignored .local directory.
"""

import argparse
import contextlib
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import re
import urllib.request
import zipfile

from check_recovery_probe import ARCHIVE, ARCHIVE_SHA, ROOT, SCRIPT_SHA, sha


def transfer(url, target, expected_size=None, token=None):
    offset = target.stat().st_size if target.exists() else 0
    headers = {"User-Agent": "InternetRecovery/1.0", "Accept-Encoding": "identity"}
    if token:
        headers["Cookie"] = "AssetToken=" + token
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    received = 0
    with urllib.request.urlopen(request, timeout=45) as response:
        if offset:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if response.status != 206 or not match or int(match[1]) != offset:
                raise ValueError("Server did not honor the exact continuation offset")
            if expected_size is not None and int(match[3]) != expected_size:
                raise ValueError("Continuation total differs from signed chunklist")
        elif response.status != 200:
            raise ValueError(f"Unexpected initial HTTP status {response.status}")
        with target.open("ab" if offset else "wb") as stream:
            while True:
                try:
                    data = response.read(2**20)
                except http.client.IncompleteRead as error:
                    data = error.partial
                    if expected_size is not None and offset + received + len(data) > expected_size:
                        raise ValueError("Response exceeds signed size") from error
                    stream.write(data)
                    received += len(data)
                    break
                if not data:
                    break
                if expected_size is not None and offset + received + len(data) > expected_size:
                    raise ValueError("Response exceeds signed size")
                stream.write(data)
                received += len(data)
    return {"offset": offset, "received_bytes": received}


def verify_prefix(image, chunks):
    """Reject corrupt full chunks before resuming; final verification checks all."""
    if not image.exists():
        return
    if image.stat().st_size > sum(length for length, _ in chunks):
        raise ValueError("Existing image exceeds signed size")
    with image.open("rb") as stream:
        for length, expected in chunks:
            data = stream.read(length)
            if len(data) < length:
                break
            if hashlib.sha256(data).digest() != expected:
                raise ValueError("Existing image contains a corrupt complete chunk")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".local/recovery-download")
    parser.add_argument("--image-url", help="Optional mirror DMG URL; no Apple token is sent")
    parser.add_argument("--chunklist-url", help="Mirror chunklist URL, or provide an existing local chunklist")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--attempts", type=int, default=4)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / ".local") or not 1 <= args.attempts <= 10:
        raise ValueError("Use a private .local output and 1..10 attempts")
    output.mkdir(parents=True, exist_ok=True)
    if sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Pinned OpenCore archive differs")
    with zipfile.ZipFile(ARCHIVE) as archive:
        source = archive.read("Utilities/macrecovery/macrecovery.py")
    if hashlib.sha256(source).hexdigest() != SCRIPT_SHA:
        raise ValueError("Pinned macrecovery differs")
    verifier = output / "macrecovery.py"
    verifier.write_bytes(source)
    spec = importlib.util.spec_from_file_location("pinned_macrecovery", verifier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    chunklist, image = output / "BaseSystem.chunklist", output / "BaseSystem.dmg"
    token = None
    if not args.verify_only:
        image_url, chunklist_url = args.image_url, args.chunklist_url
        if not image_url:
            session = module.get_session(argparse.Namespace(verbose=False))
            info = module.get_image_info(session, "Mac-CFF7D910A743CAAF", os_type="latest")
            image_url, chunklist_url = info["AU"], info["CU"]
            token = info["AT"]
            (output / "private-session.json").write_text(json.dumps(info) + "\n")
        if chunklist_url:
            fresh = output / "incoming.chunklist"
            fresh.unlink(missing_ok=True)
            transfer(chunklist_url, fresh, token=info["CT"] if token else None)
            list(module.verify_chunklist(fresh))
            if chunklist.exists() and fresh.read_bytes() != chunklist.read_bytes():
                raise ValueError("Latest product changed; use a fresh output directory")
            fresh.replace(chunklist)
    chunks = list(module.verify_chunklist(chunklist))
    verify_prefix(image, chunks)
    expected = sum(length for length, _ in chunks)
    receipts = []
    if not args.verify_only:
        for _ in range(args.attempts):
            if image.exists() and image.stat().st_size == expected:
                break
            try:
                receipts.append(transfer(image_url, image, expected, token))
            except (OSError, ValueError, http.client.HTTPException) as error:
                # Errors and URLs may contain authentication data; keep details private.
                receipts.append({"error": str(error), "bytes": image.stat().st_size if image.exists() else 0})
            verify_prefix(image, chunks)
    (output / "private-transfer.json").write_text(json.dumps(receipts, indent=2) + "\n")
    with (output / "verification.log").open("w") as log, contextlib.redirect_stdout(log):
        module.verify_image(image, chunklist)
    report = {"schema_version": 1, "runner_sha256": sha(Path(__file__)),
              "image_verified": True, "chunks": len(chunks), "bytes": image.stat().st_size,
              "image_sha256": sha(image), "chunklist_sha256": sha(chunklist),
              "macrecovery_sha256": SCRIPT_SHA, "mirror_requested": bool(args.image_url),
              "build_identified": False, "macos_booted": False}
    (output / "fetch-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
