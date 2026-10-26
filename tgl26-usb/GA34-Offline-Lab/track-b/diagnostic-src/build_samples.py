#!/usr/bin/env python3
"""One Clang ASan/UBSan build/run; immutable existing core and audit inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
LAB = HERE.parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", default="initial")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", args.run_name):
        raise SystemExit("run name must be 1..64 ASCII letters/digits/_/-")
    output = LAB / "track-b/samples" / args.run_name
    logs = LAB / "logs/sample-core" / args.run_name
    if output.exists() or logs.exists():
        raise SystemExit("run already exists; use a new --run-name to preserve all prior artifacts")
    guarded_names = ["track-b/diagnostic-src/kern_tglfault34.hpp",
                     "track-b/diagnostic-src/test_tglfault34.cpp", "track-b/fault-record-format.md",
                     "reference/diagnostic-core/core-provenance.json",
                     "track-b/ga33-add-unattached-tglfault34.patch"]
    before = {name: digest(LAB / name) for name in guarded_names}
    sources = {str(path.relative_to(LAB)): digest(path) for path in
               [HERE / "sample_fault34.cpp", HERE / "kern_tglfault34_boottext.hpp", Path(__file__).resolve()]}
    output.mkdir(parents=True)
    logs.mkdir(parents=True)
    compiler = shutil.which("clang++")
    if not compiler:
        raise SystemExit("clang++ unavailable")
    executable = logs / "sample_fault34"
    with (logs / "clang-build-run.log").open("x") as log:
        def run(command):
            log.write("$ " + shlex.join([str(x) for x in command]) + "\n")
            log.flush()
            env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1:abort_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            p = subprocess.run(command, cwd=HERE, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write(p.stdout + f"EXIT {p.returncode}\n")
            log.flush()
            if p.returncode:
                raise SystemExit(f"failed; preserved log: {log.name}")
            return p.stdout
        version = run([compiler, "--version"])
        run([compiler, "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
             "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
             HERE / "sample_fault34.cpp", "-o", executable])
        stdout = run([executable, output])
        assert "SCANNER_PASS cases=24" in stdout
        assert "SAMPLE_CORE_PASS samples=5" in stdout
    sample_hashes = {}
    for name in ("validPPGTT", "validGGTT", "valid0", "DATA1MBZ", "failedread"):
        binary = output / (name + ".bin")
        receipt = output / (name + ".json")
        data = json.loads(receipt.read_text())
        assert len(binary.read_bytes()) == 108
        assert data["input_kind"] == "SYNTHETIC_MOCK_ONLY"
        assert data["context_id"] is None and data["pml4"] is None
        assert data["decoded_file_roundtrip"] is True
        for path in (binary, receipt):
            sample_hashes[path.name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    assert before == {name: digest(LAB / name) for name in guarded_names}, "existing audited input changed"
    (output / "sample-hashes.json").write_text(json.dumps(sample_hashes, indent=2) + "\n")
    result = {"status": "SAMPLE_CORE_PASS", "input": "SYNTHETIC_MOCK_ONLY", "compiler": compiler,
              "compiler_version": version, "scanner_cases": 24, "samples": 5,
              "hardware": "NONE", "attachment": "NONE", "context_id": None, "pml4": None,
              "source_sha256": sources, "guarded_existing_sha256_unchanged": before,
              "executable_sha256": digest(executable),
              "sample_hashes_path": str((output / "sample-hashes.json").relative_to(LAB)),
              "sample_hashes_sha256": digest(output / "sample-hashes.json"),
              "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest()}
    (logs / "sample-build-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(stdout, end="")
    print(f"RECEIPT {logs / 'sample-build-receipt.json'}")


if __name__ == "__main__":
    main()
