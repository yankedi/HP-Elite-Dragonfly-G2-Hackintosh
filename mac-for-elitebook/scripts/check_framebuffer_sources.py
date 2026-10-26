#!/usr/bin/env python3
"""Fetch pinned community sources and test the Latitude patch series locally."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / ".local" / "source-check"
SOURCE_MANIFEST = ROOT / "manifests" / "graphics-sources.json"
REPORT_PATH = ROOT / "manifests" / "framebuffer-patch-check.json"
GENERATOR = "scripts/check_framebuffer_sources.py"
SCHEMA = "mac-for-elitebook/framebuffer-patch-check-v1"
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_PATCH_BYTES = 4 * 1024 * 1024
MAX_TAR_MEMBERS = 50000
MAX_EXTRACTED_BYTES = 512 * 1024 * 1024

EXPECTED_SOURCES = {
    "acidanthera-whatevergreen": {
        "url": "https://github.com/acidanthera/WhateverGreen",
        "commit": "0762cecc2a70054cd4dc3cf4d08979aca6acd9bb",
    },
    "latitude-7320-tahoe-framebuffer-study": {
        "url": "https://github.com/holdmysocks/latitude-7320-detachable-hackintosh",
        "commit": "1010490d3421628c9d6fd0bd518b6c4b6f8ee33c",
    },
}
PATCH_NAMES = [
    "0001-tigerlake-icllp-mmio-tracer.patch",
    "0002-tgl-function-tracer.patch",
    "0003-tgl-register-map.patch",
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def private_directory(path, create=False, require_private=True):
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink in private path: {path.relative_to(ROOT)}")
    if not path.exists():
        if not create:
            return False
        path.mkdir(mode=0o700)
    if not path.is_dir():
        raise RuntimeError(f"Expected a directory: {path.relative_to(ROOT)}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if require_private and mode & 0o077:
        raise RuntimeError(f"Existing directory is not private (mode {mode:04o}): {path.relative_to(ROOT)}")
    return True


def load_pinned_sources():
    data = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    by_id = {item.get("id"): item for item in data.get("sources", [])}
    pinned = {}
    for source_id, expected in EXPECTED_SOURCES.items():
        item = by_id.get(source_id)
        if item is None:
            raise RuntimeError(f"Source missing from {SOURCE_MANIFEST.relative_to(ROOT)}: {source_id}")
        for field in ("url", "commit"):
            if item.get(field) != expected[field]:
                raise RuntimeError(
                    f"Pinned source mismatch for {source_id}.{field}: "
                    f"expected {expected[field]!r}, got {item.get(field)!r}"
                )
        pinned[source_id] = dict(expected)
    return pinned


def existing_report_guard():
    if REPORT_PATH.is_symlink():
        raise RuntimeError("Refusing to replace a symlink at manifests/framebuffer-patch-check.json")
    if not REPORT_PATH.exists():
        return None
    if not REPORT_PATH.is_file():
        raise RuntimeError("Existing report path is not a regular file; refusing to replace it")
    raw = REPORT_PATH.read_bytes()
    try:
        old = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise RuntimeError(f"Existing report is not valid JSON; refusing to replace it: {error}") from error
    if old.get("schema") != SCHEMA or old.get("generator") != GENERATOR:
        raise RuntimeError("Existing report is not recognized as this script's output; refusing to replace it")
    return sha256(raw)


def fetch_bytes(url, timeout, max_bytes):
    request = Request(
        url,
        headers={
            "User-Agent": "mac-for-elitebook-source-check/1.0",
            "Accept": "application/octet-stream",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", None)
        final_url = response.geturl()
        pieces = []
        total = 0
        while True:
            chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise RuntimeError(f"Download exceeded size limit of {max_bytes} bytes")
            pieces.append(chunk)
        return b"".join(pieces), status, final_url


def write_new_private_file(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def fetch_to_file(url, path, timeout, max_bytes):
    record = {"url": url, "local_path": str(path.relative_to(ROOT)), "exit_code": 1}
    try:
        payload, status, final_url = fetch_bytes(url, timeout, max_bytes)
        write_new_private_file(path, payload)
        record.update(
            {
                "http_status": status,
                "final_url": final_url,
                "bytes": len(payload),
                "sha256": sha256(payload),
                "exit_code": 0,
                "status": "fetched",
            }
        )
        return payload, record
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as error:
        record.update({"status": "failed", "error": f"{type(error).__name__}: {error}"})
        if isinstance(error, HTTPError):
            record["http_status"] = error.code
        return None, record


def safe_extract_archive(archive_bytes, destination):
    if not hasattr(tarfile, "data_filter"):
        raise RuntimeError("This Python tarfile implementation has no data filter; refusing extraction")
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        members = archive.getmembers()
        if not members or len(members) > MAX_TAR_MEMBERS:
            raise RuntimeError(f"Unexpected tar member count: {len(members)}")
        roots = set()
        total_size = 0
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or not name.parts or ".." in name.parts or "\\" in member.name:
                raise RuntimeError(f"Unsafe archive member path: {member.name!r}")
            roots.add(name.parts[0])
            total_size += max(0, member.size)
            if total_size > MAX_EXTRACTED_BYTES:
                raise RuntimeError("Archive expanded-size limit exceeded")
            # The standard-library data filter rejects path traversal, absolute
            # links, and links that escape the extraction directory.
            tarfile.data_filter(member, str(destination))
        if len(roots) != 1:
            raise RuntimeError(f"Expected one archive root directory; found {sorted(roots)!r}")
        archive.extractall(path=destination, members=members, filter="data")
        source_root = destination / next(iter(roots))
        if source_root.is_symlink() or not source_root.is_dir():
            raise RuntimeError("Archive root is not a regular directory")
        return source_root


def run_git(cwd, args, timeout):
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[-16000:],
            "stderr": result.stderr[-16000:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        return {
            "exit_code": 124,
            "stdout": stdout[-16000:],
            "stderr": (stderr + "\nGit command timed out")[-16000:],
            "timed_out": True,
        }


def make_patch_records(patch_entries):
    records = []
    for name in PATCH_NAMES:
        fetched = patch_entries.get(name)
        records.append(
            {
                "name": name,
                "url": fetched["url"] if fetched else None,
                "local_path": fetched["local_path"] if fetched else None,
                "bytes": fetched.get("bytes") if fetched else None,
                "sha256": fetched.get("sha256") if fetched else None,
                "fetch": fetched,
                "git_apply_check": {"exit_code": None, "status": "not_run"},
                "git_apply": {"exit_code": None, "status": "not_run"},
                "status": "not_run",
            }
        )
    return records


def save_report(report, previous_sha, run_dir):
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    staged = run_dir / "report-output.json"
    write_new_private_file(staged, payload)
    if previous_sha is None:
        try:
            os.link(staged, REPORT_PATH)
        except FileExistsError as error:
            raise RuntimeError("Report appeared during run; refusing to overwrite it") from error
        staged.unlink()
        return
    current = REPORT_PATH.read_bytes()
    if sha256(current) != previous_sha:
        raise RuntimeError("Existing report changed during run; refusing to overwrite it")
    os.replace(staged, REPORT_PATH)


def check_git_ignore():
    result = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", ".local/source-check/probe"],
        check=False,
        shell=False,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(".local/source-check is not Git-ignored; refusing to write there")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=30.0, help="network/git timeout in seconds (default: 30)")
    args = parser.parse_args()
    if not (1 <= args.timeout <= 120):
        parser.error("--timeout must be between 1 and 120 seconds")

    try:
        pins = load_pinned_sources()
        previous_sha = existing_report_guard()
        check_git_ignore()
        private_directory(ROOT / ".local", create=False, require_private=False)
        private_directory(PRIVATE_ROOT, create=True)
        runs_dir = PRIVATE_ROOT / "runs"
        private_directory(runs_dir, create=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        run_dir = Path(tempfile.mkdtemp(prefix=f"{timestamp}-", dir=runs_dir))
        os.chmod(run_dir, 0o700)
        inputs_dir = run_dir / "inputs"
        patches_dir = inputs_dir / "patches"
        extract_dir = run_dir / "extract"
        inputs_dir.mkdir(mode=0o700)
        patches_dir.mkdir(mode=0o700)
        extract_dir.mkdir(mode=0o700)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"source check setup failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 2

    weg_commit = pins["acidanthera-whatevergreen"]["commit"]
    latitude_commit = pins["latitude-7320-tahoe-framebuffer-study"]["commit"]
    archive_url = f"https://codeload.github.com/acidanthera/WhateverGreen/tar.gz/{weg_commit}"
    archive_path = inputs_dir / f"WhateverGreen-{weg_commit}.tar.gz"
    archive_bytes, archive_fetch = fetch_to_file(archive_url, archive_path, args.timeout, MAX_ARCHIVE_BYTES)

    patch_entries = {}
    for name in PATCH_NAMES:
        url = (
            "https://raw.githubusercontent.com/holdmysocks/latitude-7320-detachable-hackintosh/"
            f"{latitude_commit}/WhateverGreen-patches/{name}"
        )
        local_path = patches_dir / name
        _, fetched = fetch_to_file(url, local_path, args.timeout, MAX_PATCH_BYTES)
        patch_entries[name] = fetched

    extraction = {"exit_code": None, "status": "not_run"}
    git_init = {"exit_code": None, "status": "not_run"}
    source_copy = None
    if archive_bytes is not None:
        try:
            extracted = safe_extract_archive(archive_bytes, extract_dir)
            source_copy = run_dir / "source"
            os.rename(extracted, source_copy)
            extraction.update(
                {
                    "exit_code": 0,
                    "status": "extracted_with_tarfile_data_filter",
                    "source_copy": str(source_copy.relative_to(ROOT)),
                }
            )
            git_init = run_git(source_copy, ["init", "--quiet"], args.timeout)
            git_init["status"] = "initialized" if git_init["exit_code"] == 0 else "failed"
        except (OSError, tarfile.TarError, RuntimeError, ValueError) as error:
            extraction.update(
                {"exit_code": 1, "status": "failed", "error": f"{type(error).__name__}: {error}"}
            )

    patch_records = make_patch_records(patch_entries)
    stop_reason = None
    can_apply = (
        source_copy is not None
        and extraction["exit_code"] == 0
        and git_init["exit_code"] == 0
        and all(patch_entries[name].get("exit_code") == 0 for name in PATCH_NAMES)
    )
    if not can_apply:
        stop_reason = "archive extraction, git init, or patch retrieval did not succeed"
    else:
        for record in patch_records:
            patch_path = ROOT / record["local_path"]
            checked = run_git(source_copy, ["apply", "--check", "--", str(patch_path)], args.timeout)
            checked["status"] = "passed" if checked["exit_code"] == 0 else "failed"
            record["git_apply_check"] = checked
            if checked["exit_code"] != 0:
                record["status"] = "check_failed"
                stop_reason = f"git apply --check failed for {record['name']}"
                break
            applied = run_git(source_copy, ["apply", "--", str(patch_path)], args.timeout)
            applied["status"] = "applied" if applied["exit_code"] == 0 else "failed"
            record["git_apply"] = applied
            if applied["exit_code"] != 0:
                record["status"] = "apply_failed_after_check"
                stop_reason = f"git apply failed after successful check for {record['name']}"
                break
            record["status"] = "checked_and_applied"

    all_passed = all(record["status"] == "checked_and_applied" for record in patch_records)
    report = {
        "schema": SCHEMA,
        "generator": GENERATOR,
        "generated_at_utc": utc_now(),
        "run_id": run_dir.name,
        "purpose": "Sequential git apply --check/apply evidence for an exact pinned source archive and three unmodified Latitude community patches.",
        "scope": {
            "private_root": ".local/source-check/",
            "apple_os_or_system_kext_obtained": False,
            "kext_compilation_proven": False,
            "hp_elite_dragonfly_g2_test_proven": False,
            "statement": "This is Linux source-patch applicability evidence only; it is not proof of Kext compilation, Tahoe runtime compatibility, or an HP Elite Dragonfly G2 test.",
        },
        "source_archive": {
            "repository": pins["acidanthera-whatevergreen"]["url"],
            "commit": weg_commit,
            "url": archive_url,
            "local_path": archive_fetch.get("local_path"),
            "bytes": archive_fetch.get("bytes"),
            "sha256": archive_fetch.get("sha256"),
            "fetch": archive_fetch,
        },
        "patch_source": {
            "repository": pins["latitude-7320-tahoe-framebuffer-study"]["url"],
            "commit": latitude_commit,
            "patches": patch_records,
        },
        "steps": {
            "safe_extraction": extraction,
            "git_init": git_init,
        },
        "working_copy": str(source_copy.relative_to(ROOT)) if source_copy else None,
        "summary": {
            "all_three_checked_and_applied_in_order": all_passed,
            "checks_passed": sum(record["git_apply_check"].get("exit_code") == 0 for record in patch_records),
            "patches_applied": sum(record["git_apply"].get("exit_code") == 0 for record in patch_records),
            "stop_reason": stop_reason,
        },
    }
    try:
        save_report(report, previous_sha, run_dir)
    except (OSError, RuntimeError) as error:
        print(f"could not save report: {type(error).__name__}: {error}", file=sys.stderr)
        print(f"private run data retained at {run_dir.relative_to(ROOT)}", file=sys.stderr)
        return 2

    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    print(f"report: {REPORT_PATH.relative_to(ROOT)}")
    print(f"private inputs/worktree: {run_dir.relative_to(ROOT)}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
