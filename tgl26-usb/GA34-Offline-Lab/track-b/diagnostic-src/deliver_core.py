#!/usr/bin/env python3
"""Generate and check a HEADER-ONLY, UNATTACHED offline patch/receipt."""
import hashlib
import json
import pathlib
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
LAB = HERE.parent.parent
EXPECTED_BASE = {
    "kern_igfx.cpp": "6f2f73e5d404c4c5daf8294f6d8f59ae5d02fb040e24fbe99713949750ede395",
    "kern_igfx.hpp": "b3825be3dd8c6da5da63e17ff9329124a9faaa708535b0737048d568a09ce838",
    "kern_tglhang.hpp": "8678dfb3be0e9c92f984a3a23a3a48e0f056b19078307e1412688a1426bdf5b4",
    "test_tglhang.cpp": "ac8125f71bc6f1dcee7616229fec89c57211c5c84426554da4e88f857d3c4558",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for name, digest in EXPECTED_BASE.items():
        source = HERE / "ga33-base" / name
        assert sha(source) == digest, f"baseline changed: {source}"
        assert b"tglfault34" not in source.read_bytes(), f"unexpected attachment: {source}"
    header = HERE / "kern_tglfault34.hpp"
    lines = header.read_text().splitlines(keepends=True)
    assert lines[-1].endswith("\n")
    patch = LAB / "track-b" / "ga33-add-unattached-tglfault34.patch"
    destination = LAB / "logs" / "diagnostic-core" / "delivery-receipt.json"
    if patch.exists() or destination.exists():
        archive = LAB / "logs/diagnostic-core/previous" / f"delivery-{time.time_ns()}"
        archive.mkdir(parents=True)
        for old in (patch, destination):
            if old.exists():
                (archive / old.name).write_bytes(old.read_bytes())
    patch.write_text("diff --git a/kern_tglfault34.hpp b/kern_tglfault34.hpp\n"
                     "new file mode 100644\n--- /dev/null\n+++ b/kern_tglfault34.hpp\n"
                     f"@@ -0,0 +1,{len(lines)} @@\n" + "".join("+" + x for x in lines))
    results = {}
    for compiler in ("clang", "gcc"):
        source = LAB / "logs" / "diagnostic-core" / f"{compiler}-results.json"
        result = json.loads(source.read_text())
        for name, digest in result["source_sha256"].items():
            assert sha(HERE / name) == digest, f"stale build: {compiler}/{name}"
        assert len(result["builds"]) == 4
        assert all(x["status"] == "OFFLINE_PASS" and x["groups"] == 28 for x in result["builds"])
        assert result["freestanding_debug_release"] == "PASS"
        results[compiler] = {"receipt": str(source.relative_to(LAB)), "sha256": sha(source)}
    check = subprocess.run(["git", "apply", "--check", str(patch)],
                           cwd=HERE / "ga33-base", capture_output=True, text=True, check=True)
    stat = subprocess.run(["git", "apply", "--numstat", str(patch)],
                          cwd=HERE / "ga33-base", capture_output=True, text=True, check=True)
    assert stat.stdout == f"{len(lines)}\t0\tkern_tglfault34.hpp\n", stat.stdout
    # Reconstruction verifies all patch payload bytes, without applying edits to
    # the baseline or any previous tree. git apply --check performs no writes.
    payload = patch.read_text().split("@@\n", 1)[1]
    reconstructed = "".join(line[1:] for line in payload.splitlines(keepends=True))
    assert reconstructed.encode() == header.read_bytes()
    for name, digest in EXPECTED_BASE.items():
        assert sha(HERE / "ga33-base" / name) == digest
    receipt = {"status": "OFFLINE_PASS", "whole_kext": "NOT_BUILT",
               "attachment": "NONE", "hardware": "NONE", "records_capacity": 8,
               "wire_version": 1, "wire_size": 108,
               "baseline_unchanged_sha256": EXPECTED_BASE,
               "header_sha256": sha(header), "patch": str(patch.relative_to(LAB)),
               "patch_sha256": sha(patch), "patch_numstat": stat.stdout,
               "patch_check_exit": check.returncode, "compiler_receipts": results}
    destination.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
