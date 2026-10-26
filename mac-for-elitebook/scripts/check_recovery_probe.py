#!/usr/bin/env python3
"""Verify an Apple recovery image with OpenCore's pinned original chunk verifier.

This does not install or boot macOS. Exit 2 means no complete verified image.
--download performs a bounded latest-recovery route probe, not a Tahoe build pin.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / ".cache/assets/OpenCorePkg/1.0.8/OpenCore-1.0.8-RELEASE.zip"
ARCHIVE_SHA = "2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b"
SCRIPT_SHA = "3023a9b4ca79a5255d93c00f25ab5df37e6f938b729b797d9ecea56184b17aff"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--input", default=".local/nonboot-vm/recovery")
    args = parser.parse_args()
    data_dir = (ROOT / args.input).resolve()
    if not data_dir.is_relative_to(ROOT / ".local"):
        raise ValueError("Recovery probe input must be in private .local")
    if sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Pinned OpenCore archive differs")
    base = ROOT / ".local/nonboot-vm"
    base.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="recovery-check-", dir=base))
    with zipfile.ZipFile(ARCHIVE) as package:
        source = package.read("Utilities/macrecovery/macrecovery.py")
    if hashlib.sha256(source).hexdigest() != SCRIPT_SHA:
        raise ValueError("Pinned macrecovery script differs")
    verifier = run / "macrecovery.py"
    verifier.write_bytes(source)
    spec = importlib.util.spec_from_file_location("pinned_macrecovery", verifier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = {"schema_version": 1, "runner_sha256": sha(Path(__file__)), "opencore_version": "1.0.8",
              "macrecovery_sha256": SCRIPT_SHA, "private_input_directory": str(data_dir.relative_to(ROOT)),
              "macos_booted": False, "macos_installed": False, "build_identified": False,
              "baseline_changed": False}
    if args.download:
        command = ["python3", str(verifier), "-b", "Mac-CFF7D910A743CAAF", "-m", "00000000000000000", "-os", "latest", "-o", str(data_dir), "download"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=75)
            out, err, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            out, err, code = error.stdout or b"", error.stderr or b"", None
        (run / "download.stdout").write_bytes(out)
        (run / "download.stderr").write_bytes(err)
        report["download"] = {"command": command, "exit_code": code, "timeout_seconds": 75}
    cnkl, image = data_dir / "BaseSystem.chunklist", data_dir / "BaseSystem.dmg"
    report["inputs"] = [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha(p)} for p in [cnkl, image] if p.is_file()]
    try:
        # Exhaust the generator: Apple RSA signature verification occurs after the chunk entries.
        chunks = list(module.verify_chunklist(cnkl))
        report.update(chunklist_apple_signature_verified=True, chunk_count=len(chunks), expected_image_bytes=sum(x[0] for x in chunks))
        tampered = run / "tampered.chunklist"
        payload = bytearray(cnkl.read_bytes())
        payload[-1] ^= 1
        tampered.write_bytes(payload)
        try:
            list(module.verify_chunklist(tampered))
            report["tampered_signature_rejected"] = False
        except (AssertionError, RuntimeError, ValueError):
            report["tampered_signature_rejected"] = True
        with image.open("rb") as stream:
            verified = 0
            for index, (length, expected_hash) in enumerate(chunks, 1):
                chunk = stream.read(length)
                if len(chunk) != length:
                    raise ValueError(f"Chunk {index} truncated: expected {length}, read {len(chunk)} bytes")
                if hashlib.sha256(chunk).digest() != expected_hash:
                    raise ValueError(f"Chunk {index} SHA-256 mismatch")
                verified += 1
            if stream.read(1):
                raise ValueError("Image has trailing data beyond signed chunklist")
        report.update(status="verified_image_build_still_unidentified", image_verified=True, verified_chunks=verified)
    except (OSError, AssertionError, RuntimeError, ValueError) as error:
        report.update(status="blocked_incomplete_or_invalid_image", image_verified=False, failure=str(error) or type(error).__name__)
    report["logs"] = {p.name: sha(p) for p in run.glob("*.std*")}
    (run / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({**report, "report": str((run / "report.json").relative_to(ROOT))}, indent=2))
    if not report["image_verified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
