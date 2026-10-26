#!/usr/bin/env python3
"""Audit R1/R2 author closure without rewriting independent review evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    archive = LAB / "logs/diagnostic-core/pre-alias-fix"
    original = load(archive / "snapshot-hashes.json")
    for name, item in original.items():
        path = archive / name
        assert sha(path) == item["sha256"] and path.stat().st_size == item["bytes"], path
    for name in original:
        if name.startswith(("track-b/samples/initial/", "logs/sample-core/initial/")) or name in {
                "track-b/reports/independent-fault-review.md",
                "logs/independent-fault-review/findings.json",
                "reference/diagnostic-core/core-provenance.json"}:
            assert sha(LAB / name) == original[name]["sha256"], name
    result_hashes = {}
    stdout_hashes = set()
    for compiler in ("clang", "gcc"):
        path = LAB / f"logs/diagnostic-core/{compiler}-results.json"
        result = load(path)
        assert len(result["builds"]) == 4 and result["freestanding_debug_release"] == "PASS"
        assert {(b["mode"], b["sanitized"]) for b in result["builds"]} == {
            (mode, sanitized) for mode in ("Debug", "Release") for sanitized in (False, True)}
        for name, digest in result["source_sha256"].items():
            assert sha(HERE / name) == digest, name
        for build in result["builds"]:
            assert build["status"] == "OFFLINE_PASS" and build["groups"] == 28
            assert sha(LAB / build["executable"]) == build["executable_sha256"]
            stdout_hashes.add(build["stdout_sha256"])
        result_hashes[compiler] = sha(path)
    assert len(stdout_hashes) == 1
    delivery = load(LAB / "logs/diagnostic-core/delivery-receipt.json")
    assert delivery["header_sha256"] == sha(HERE / "kern_tglfault34.hpp")
    assert delivery["patch_sha256"] == sha(LAB / delivery["patch"])
    assert delivery["patch_check_exit"] == 0
    for name, digest in delivery["baseline_unchanged_sha256"].items():
        assert sha(HERE / "ga33-base" / name) == digest
    identical = []
    for name in ("validPPGTT", "validGGTT", "valid0", "DATA1MBZ", "failedread"):
        for suffix in (".bin", ".json"):
            filename = name + suffix
            old = LAB / "track-b/samples/initial" / filename
            new = LAB / "track-b/samples/post-alias-fix" / filename
            assert old.read_bytes() == new.read_bytes(), filename
            if suffix == ".bin":
                assert new.stat().st_size == 108
            else:
                data = load(new)
                assert data["context_id"] is None and data["pml4"] is None
            identical.append(filename)
    assert (LAB / "track-b/samples/initial/sample-hashes.json").read_bytes() == (
        LAB / "track-b/samples/post-alias-fix/sample-hashes.json").read_bytes()
    old_sample = load(LAB / "logs/sample-core/initial/sample-build-receipt.json")
    new_sample = load(LAB / "logs/sample-core/post-alias-fix/sample-build-receipt.json")
    for name, digest in old_sample["source_sha256"].items():
        assert sha(archive / name) == digest and sha(LAB / name) == digest
    header_name = "track-b/diagnostic-src/kern_tglfault34.hpp"
    assert old_sample["guarded_existing_sha256_unchanged"][header_name] == original[header_name]["sha256"]
    assert new_sample["guarded_existing_sha256_unchanged"][header_name] == sha(LAB / header_name)
    names = ["kern_tglfault34.hpp", "test_tglfault34.cpp", "build_core.py", "deliver_core.py",
             "audit_alias_fix.py"]
    result = {
        "status": "AUTHOR_REGRESSION_CLOSURE_PASS",
        "R1": "entry Request snapshot; epoch/token alias changes -> ResetRace, 1 read/2 guards, old metadata retained",
        "R2": "entry Callbacks tuple snapshot; null/replacement read/observe/context do not retarget dispatch",
        "independent_reviewer_rerun": "PENDING_MAIN_SESSION",
        "original_snapshot_files_verified": len(original),
        "original_snapshot_index_sha256": sha(archive / "snapshot-hashes.json"),
        "original_header_sha256": original[header_name]["sha256"],
        "current_source_sha256": {name: sha(HERE / name) for name in names},
        "compiler_result_sha256": result_hashes,
        "hosted_builds": 8, "groups_per_build": 28, "group_invocations": 224,
        "freestanding_builds": 4, "common_stdout_sha256": next(iter(stdout_hashes)),
        "patch_sha256": delivery["patch_sha256"], "patch_numstat": delivery["patch_numstat"],
        "identical_initial_postfix_samples": identical,
        "initial_sample_receipt_preserved_sha256": sha(LAB / "logs/sample-core/initial/sample-build-receipt.json"),
        "postfix_sample_receipt_sha256": sha(LAB / "logs/sample-core/post-alias-fix/sample-build-receipt.json"),
        "review_findings_unchanged_sha256": sha(LAB / "logs/independent-fault-review/findings.json"),
        "core_format_sha256": sha(LAB / "track-b/fault-record-format.md"),
        "core_build_report_sha256": sha(LAB / "track-b/reports/core-build.md"),
        "hardware": "NONE", "attachment": "NONE", "whole_kext": "NOT_BUILT",
        "wire_version": 1, "wire_size": 108, "source_img": None, "result_img": None,
    }
    output = LAB / "logs/diagnostic-core/alias-fix-closure.json"
    if output.exists():
        raise SystemExit("closure audit already exists; preserve it and choose a new audit output before rerunning")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
