#!/usr/bin/env python3
"""Parse fixed private HID descriptors using a hash-pinned upstream hid-tools tree."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifests/nonboot-hid-check.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_tree_digest(directory):
    """Hash a source/dependency tree deterministically, ignoring Python bytecode."""
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    files = []
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks are not permitted in pinned source/dependency trees")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        files.append(path)

    digest = hashlib.sha256()
    total_bytes = 0
    for path in sorted(files, key=lambda item: item.relative_to(directory).as_posix()):
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        payload = path.read_bytes()
        total_bytes += len(payload)
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(hashlib.sha256(payload).digest())

    return {
        "file_count_excluding_python_bytecode": len(files),
        "bytes_excluding_python_bytecode": total_bytes,
        "sha256": digest.hexdigest(),
    }


def normalized_distribution_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def validate_local_pins(manifest, source_dir, deps_dir):
    errors = []
    parser = manifest["parser"]

    try:
        source_tree = file_tree_digest(source_dir)
        expected_source = parser["source_tree"]
        if any(source_tree[key] != expected_source[key] for key in source_tree):
            errors.append("hid-tools source tree does not match the pinned tree digest")
        version_text = (source_dir / "hidtools/_version.py").read_text()
        match = re.search(r'__version__\s*=\s*[\'\"]([^\'\"]+)', version_text)
        if not match or match.group(1) != parser["version"]:
            errors.append("hid-tools package version does not match the pinned version")
        license_sha = sha256((source_dir / "COPYING").read_bytes())
        if license_sha != parser["license"]["license_file_sha256"]:
            errors.append("hid-tools COPYING file does not match the pinned license hash")
    except (OSError, ValueError) as error:
        source_tree = None
        errors.append(f"Cannot verify hid-tools source tree: {type(error).__name__}")

    try:
        deps_tree = file_tree_digest(deps_dir)
        expected_deps = parser["runtime_dependencies"]
        tree_keys = (
            "file_count_excluding_python_bytecode",
            "bytes_excluding_python_bytecode",
        )
        if any(deps_tree[key] != expected_deps[key] for key in tree_keys) or deps_tree["sha256"] != expected_deps["tree_sha256"]:
            errors.append("Python dependency tree does not match the pinned tree digest")
        distributions = {
            normalized_distribution_name(distribution.metadata["Name"]): distribution.version
            for distribution in importlib.metadata.distributions(path=[str(Path(deps_dir).resolve())])
            if distribution.metadata.get("Name")
        }
        for package in expected_deps["packages"]:
            key = normalized_distribution_name(package["name"])
            if distributions.get(key) != package["version"]:
                errors.append(f"Pinned dependency version mismatch: {package['name']}")
    except (OSError, ValueError) as error:
        deps_tree = None
        errors.append(f"Cannot verify Python dependency tree: {type(error).__name__}")

    runtime = parser["runtime_dependencies"]["python"]
    if runtime == "CPython 3.13, Linux x86_64":
        if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 13):
            errors.append("Pinned dependency wheel requires CPython 3.13")
        if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
            errors.append("Pinned dependency wheel requires Linux x86_64")

    archive = parser["source_archive"]
    archive_path = ROOT / archive["local_path"]
    archive_check = {"path": archive["local_path"], "available": archive_path.is_file()}
    if archive_path.is_file():
        payload = archive_path.read_bytes()
        archive_check.update({"bytes": len(payload), "sha256": sha256(payload)})
        if len(payload) != archive["bytes"] or sha256(payload) != archive["sha256"]:
            errors.append("Local upstream source archive differs from its pinned size/SHA-256")
        else:
            archive_check["verified"] = True
    else:
        archive_check["verified"] = False

    wheel_checks = []
    for package in parser["runtime_dependencies"]["packages"]:
        wheel_path = ROOT / package["local_path"]
        result = {"name": package["name"], "path": package["local_path"], "available": wheel_path.is_file()}
        if wheel_path.is_file():
            payload = wheel_path.read_bytes()
            result.update({"bytes": len(payload), "sha256": sha256(payload)})
            if sha256(payload) != package["sha256"]:
                errors.append(f"Local {package['name']} wheel differs from its pinned SHA-256")
            else:
                result["verified"] = True
        else:
            result["verified"] = False
        wheel_checks.append(result)

    return {
        "source_tree": source_tree,
        "dependency_tree": deps_tree,
        "source_archive": archive_check,
        "dependency_wheels": wheel_checks,
        "errors": errors,
    }


def parser_usage_record(field):
    usage_name = field.usage_name
    name_suppressed = "serial" in usage_name.lower()
    return {
        "usage_page_id": f"0x{field.usage_page >> 16:04x}",
        "usage_id": f"0x{field.usage & 0xffff:04x}",
        "usage_page_name": field.usage_page_name or None,
        "usage_name": None if name_suppressed else usage_name,
        "usage_name_suppressed": name_suppressed,
    }


def summarize_descriptor(parser_module, payload, record):
    descriptor = parser_module.ReportDescriptor.from_bytes(payload)
    errors = []
    if descriptor.size != len(payload):
        errors.append("parser item length differs from captured descriptor length")

    collection_counts = Counter()
    collection_depth = 0
    minimum_depth = 0
    for item in descriptor.rdesc_items:
        if item.item == "Collection":
            value = item.value
            kind = {0: "physical", 1: "application", 2: "logical"}.get(value, f"other_{value}")
            collection_counts[kind] += 1
            collection_depth += 1
        elif item.item == "End Collection":
            collection_counts["end"] += 1
            collection_depth -= 1
            minimum_depth = min(minimum_depth, collection_depth)
    balanced = minimum_depth >= 0 and collection_depth == 0
    if not balanced:
        errors.append("parsed Collection/End Collection items are not balanced")
    if collection_counts["application"] == 0:
        errors.append("no Application collection was parsed")

    report_types = (
        ("input", descriptor.input_reports),
        ("output", descriptor.output_reports),
        ("feature", descriptor.feature_reports),
    )
    reports_summary = {}
    all_applications = {}
    global_usages = {}
    logical_ranges = set()

    for kind, reports in report_types:
        summaries = []
        for report_id, report in sorted(reports.items()):
            if report_id != -1 and not 1 <= report_id <= 255:
                errors.append(f"invalid Report ID in {kind} report")
            if report.bitsize <= 0:
                errors.append(f"empty {kind} report")
            if report.bitsize % 8:
                errors.append(f"non-byte-aligned {kind} report")
            wire_bytes = (report.bitsize + 7) // 8
            if report.size != wire_bytes:
                errors.append(f"parser byte length differs from bit length in {kind} report")
            report_id_bits = 8 if report_id >= 0 else 0
            payload_bits = report.bitsize - report_id_bits
            if payload_bits < 0:
                errors.append(f"negative payload size in {kind} report")

            app_usage = report.application
            app_record = {
                "application_usage_page_id": f"0x{app_usage >> 16:04x}" if app_usage is not None else None,
                "application_usage_id": f"0x{app_usage & 0xffff:04x}" if app_usage is not None else None,
                "application_name": report.application_name,
            }
            app_key = (app_record["application_usage_page_id"], app_record["application_usage_id"], report.application_name)
            all_applications[app_key] = app_record

            report_usages = {}
            report_ranges = set()
            for field in report.fields:
                if field.size <= 0 or field.count <= 0:
                    errors.append(f"invalid field dimensions in {kind} report")
                if field.logical_min > field.logical_max:
                    errors.append(f"Logical Minimum exceeds Logical Maximum in {kind} report")
                report_ranges.add((field.logical_min, field.logical_max))
                logical_ranges.add((field.logical_min, field.logical_max))

                usage = parser_usage_record(field)
                usage_key = (
                    usage["usage_page_id"], usage["usage_id"], usage["usage_page_name"],
                    usage["usage_name"], field.logical_min, field.logical_max,
                )
                current = global_usages.setdefault(usage_key, {
                    **usage,
                    "logical_min": field.logical_min,
                    "logical_max": field.logical_max,
                    "field_count": 0,
                })
                current["field_count"] += 1
                report_usages[(usage["usage_page_id"], usage["usage_id"])] = usage

            summaries.append({
                "report_id": report_id if report_id >= 0 else None,
                "application": report.application_name,
                "bits_including_report_id": report.bitsize,
                "payload_bits": payload_bits,
                "wire_bytes": wire_bytes,
                "field_count": len(report.fields),
                "unique_usage_count": len(report_usages),
                "logical_ranges": [list(value) for value in sorted(report_ranges)],
            })
        reports_summary[kind] = summaries

    if not descriptor.input_reports:
        errors.append("no Input reports parsed")

    return {
        "id": record["id"],
        "label": record["label"],
        "descriptor_bytes": len(payload),
        "descriptor_sha256": sha256(payload),
        "parser_item_count": len(descriptor.rdesc_items),
        "collections": {
            "counts_by_type": dict(sorted(collection_counts.items())),
            "depth_balanced": balanced,
        },
        "applications": sorted(all_applications.values(), key=lambda item: (
            item["application_usage_page_id"] or "", item["application_usage_id"] or "", item["application_name"]
        )),
        "reports": reports_summary,
        "logical_ranges_seen": [list(value) for value in sorted(logical_ranges)],
        "usages": sorted(global_usages.values(), key=lambda item: (
            item["usage_page_id"], item["usage_id"], item["logical_min"], item["logical_max"], item["usage_name"] or ""
        )),
        "errors": errors,
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def command_record(command, env, run_dir, label):
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{label}.stdout.log"
    stderr_path = log_dir / f"{label}.stderr.log"
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            timeout=60,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        exit_code = None
        timed_out = True

    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    return {
        "command": command,
        "working_directory": ".",
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": {
            "path": str(stdout_path.relative_to(ROOT)),
            "bytes": len(stdout),
            "sha256": sha256(stdout),
        },
        "stderr": {
            "path": str(stderr_path.relative_to(ROOT)),
            "bytes": len(stderr),
            "sha256": sha256(stderr),
        },
    }, stderr


def validate_capture_inputs(manifest):
    capture_root = (ROOT / manifest["capture_directory"]).resolve(strict=True)
    private_hardware_root = (ROOT / ".local/hardware").resolve()
    if not capture_root.is_relative_to(private_hardware_root):
        raise ValueError("Fixed capture directory escapes .local/hardware")

    records = []
    errors = []
    for item in manifest["inputs"]:
        path = (capture_root / item["path"]).resolve(strict=True)
        if not path.is_relative_to(capture_root):
            raise ValueError("Fixed descriptor path escapes its capture directory")
        payload = path.read_bytes()
        actual_sha = sha256(payload)
        record = {
            "id": item["id"],
            "label": item["label"],
            "path": str(path.relative_to(ROOT)),
            "expected_bytes": item["bytes"],
            "actual_bytes": len(payload),
            "expected_sha256": item["sha256"],
            "actual_sha256": actual_sha,
            "hash_verified": len(payload) == item["bytes"] and actual_sha == item["sha256"],
            "payload": payload,
        }
        if not record["hash_verified"]:
            errors.append(f"Captured input hash/length mismatch: {item['id']}")
        records.append(record)
    return records, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=ROOT / ".local/nonboot-hid/src",
        help="path to an extracted copy of the exact source tree pinned in the manifest",
    )
    parser.add_argument(
        "--deps-dir",
        type=Path,
        default=ROOT / ".local/nonboot-hid/deps",
        help="path to the exact unpacked Python dependency tree pinned in the manifest",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text())
    source_dir = args.source_dir.resolve()
    deps_dir = args.deps_dir.resolve()
    source_checks = validate_local_pins(manifest, source_dir, deps_dir)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = ROOT / ".local/nonboot-hid" / f"run-{stamp}-{os.getpid()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "inputs").mkdir()

    report = {
        "schema_version": 1,
        "status": "failed",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": "manifests/nonboot-hid-check.json",
        "runner": "scripts/check_nonboot_hid.py",
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "parser": {
            "project": manifest["parser"]["project"],
            "version": manifest["parser"]["version"],
            "commit": manifest["parser"]["commit"],
            "source_archive_sha256": manifest["parser"]["source_archive"]["sha256"],
        },
        "environment": {
            "python": sys.version.split()[0],
            "implementation": sys.implementation.name,
            "platform": platform.platform(),
            "source_dir": str(source_dir),
            "dependency_dir": str(deps_dir),
        },
        "pin_checks": source_checks,
        "inputs": [],
        "devices": [],
        "negative_cases": [],
        "errors": list(source_checks["errors"]),
        "scope": manifest["scope"],
        "private_logs_only": True,
        "runtime_hid_reports_read": False,
    }

    if source_checks["errors"]:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report_path = run_dir / "report.json"
        write_json(report_path, report)
        write_json(ROOT / ".local/nonboot-hid/latest.json", {
            "report": str(report_path.relative_to(ROOT)),
            "sha256": sha256(report_path.read_bytes()),
        })
        print(json.dumps({"status": "failed", "report": str(report_path.relative_to(ROOT))}))
        raise SystemExit(1)

    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join((str(deps_dir), str(source_dir))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(deps_dir), str(source_dir)]
    try:
        from hidtools import hid as hid_module
    except Exception as error:
        report["errors"].append(f"Cannot import pinned parser: {type(error).__name__}")
        hid_module = None

    inputs, input_errors = validate_capture_inputs(manifest)
    report["errors"].extend(input_errors)
    tool = source_dir / "hid-decode"
    for item in inputs:
        report["inputs"].append({key: value for key, value in item.items() if key != "payload"})
        item_result = {"id": item["id"]}
        if not item["hash_verified"]:
            item_result["skipped_reason"] = "fixed capture hash/length mismatch"
        else:
            command = [sys.executable, str(tool), str(ROOT / item["path"])]
            execution, _ = command_record(command, env, run_dir, f"{item['id']}-hid-decode")
            item_result["command_result"] = execution
            item_result["expected_exit_code"] = manifest["checks"]["descriptor_parse_exit_code"]
            if execution["exit_code"] != item_result["expected_exit_code"] or execution["timed_out"]:
                report["errors"].append(f"hid-decode failed for captured descriptor: {item['id']}")
        if hid_module is not None and item["hash_verified"]:
            try:
                summary = summarize_descriptor(hid_module, item["payload"], item)
                item_result["summary"] = summary
                if summary["errors"]:
                    report["errors"].extend(f"{item['id']}: {error}" for error in summary["errors"])
            except Exception as error:
                item_result["parser_exception"] = type(error).__name__
                report["errors"].append(f"Descriptor summary failed for {item['id']}: {type(error).__name__}")
        report["devices"].append(item_result)

    negative_inputs_dir = run_dir / "inputs"
    for case in manifest["negative_cases"]:
        payload = bytes.fromhex(case["descriptor_hex"])
        path = negative_inputs_dir / f"{case['id']}.descriptor"
        path.write_bytes(payload)
        command = [sys.executable, str(tool), str(path)]
        execution, stderr = command_record(command, env, run_dir, f"{case['id']}-hid-decode")
        expected_exception = case["expected_exception"]
        observed_exception = expected_exception if expected_exception.encode() in stderr else None
        passed = execution["exit_code"] == manifest["checks"]["negative_cli_exit_code"] and observed_exception == expected_exception
        result = {
            "id": case["id"],
            "description": case["description"],
            "input_bytes": len(payload),
            "input_sha256": sha256(payload),
            "command_result": execution,
            "expected_exception": expected_exception,
            "observed_exception": observed_exception,
            "passed": passed,
        }
        report["negative_cases"].append(result)
        if not passed:
            report["errors"].append(f"Pinned parser did not reject negative case as expected: {case['id']}")

    report["summary"] = {
        "captured_descriptors_hash_verified": all(item["hash_verified"] for item in inputs),
        "captured_descriptors_parsed": sum("summary" in item for item in report["devices"]),
        "negative_cases_passed": sum(case["passed"] for case in report["negative_cases"]),
        "negative_cases_total": len(report["negative_cases"]),
        "errors": len(report["errors"]),
    }
    report["status"] = "passed" if not report["errors"] else "failed"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()

    report_path = run_dir / "report.json"
    write_json(report_path, report)
    latest_path = ROOT / ".local/nonboot-hid/latest.json"
    write_json(latest_path, {
        "report": str(report_path.relative_to(ROOT)),
        "sha256": sha256(report_path.read_bytes()),
    })
    print(json.dumps({
        "status": report["status"],
        "report": str(report_path.relative_to(ROOT)),
        "report_sha256": sha256(report_path.read_bytes()),
        "inputs": [{"id": item["id"], "sha256": item["actual_sha256"]} for item in inputs],
        "summary": report["summary"],
    }, sort_keys=True))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
