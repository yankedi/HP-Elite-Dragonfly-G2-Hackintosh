#!/usr/bin/env python3
"""Real compiler/sanitizer matrix; no hardware or whole-kext build claims."""
import argparse
import hashlib
import json
import pathlib
import shlex
import shutil
import subprocess
import os
import time

HERE = pathlib.Path(__file__).resolve().parent
LAB = HERE.parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--label", choices=("clang", "gcc"), required=True)
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if not compiler:
        raise SystemExit(f"missing compiler: {args.compiler}")
    root = LAB / "logs" / "diagnostic-core"
    build = HERE / "build" / args.label
    root.mkdir(parents=True, exist_ok=True)
    build.mkdir(parents=True, exist_ok=True)
    logpath = root / f"{args.label}-matrix.log"
    resultpath = root / f"{args.label}-results.json"
    if logpath.exists() or resultpath.exists():
        archive = root / "previous" / f"{args.label}-{time.time_ns()}"
        archive.mkdir(parents=True)
        for old in (logpath, resultpath):
            if old.exists():
                old.rename(archive / old.name)
    source_hashes = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                     for name in ("kern_tglfault34.hpp", "test_tglfault34.cpp",
                                  "freestanding_tglfault34.cpp", "build_core.py")}
    entries = []
    with logpath.open("w") as log:
        log.write("SOURCE_SHA256 " + json.dumps(source_hashes, sort_keys=True) + "\n")
        def run(command, env=None):
            log.write("$ " + shlex.join([str(x) for x in command]) + "\n")
            log.flush()
            effective = dict(os.environ if env is None else env)
            # Nix wrappers append fortify defines after command-line -U. Disable
            # only fortify/fortify3 for the real -O0 matrix, retaining other flags.
            hardening = effective.get("NIX_HARDENING_ENABLE", "").split()
            effective["NIX_HARDENING_ENABLE"] = " ".join(
                flag for flag in hardening if flag not in {"fortify", "fortify3"})
            log.write("NIX_HARDENING_ENABLE=" + effective["NIX_HARDENING_ENABLE"] + "\n")
            p = subprocess.run(command, cwd=HERE, env=effective, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write(p.stdout)
            log.write(f"EXIT {p.returncode}\n")
            log.flush()
            if p.returncode:
                raise SystemExit(f"command failed ({p.returncode}); see {logpath}")
            return p.stdout

        version = run([compiler, "--version"])
        common = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                  "-U_FORTIFY_SOURCE",  # Nix's optimization-dependent fortify is incompatible with -O0.
                  "-fno-exceptions", "-fno-rtti"]
        for mode, options in (("Debug", ["-O0", "-g3"]), ("Release", ["-O2", "-g", "-DNDEBUG"])):
            for sanitized in (False, True):
                label = f"{mode}-{'asan-ubsan' if sanitized else 'plain'}"
                executable = build / label
                flags = ["-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                         "-fno-omit-frame-pointer"] if sanitized else []
                run(common + options + flags + ["test_tglfault34.cpp", "-o", executable])
                env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1:abort_on_error=1",
                           UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
                output = run([executable], env)
                if "OFFLINE_PASS groups=28" not in output:
                    raise SystemExit("missing complete test receipt")
                entries.append({"mode": mode, "sanitized": sanitized, "status": "OFFLINE_PASS",
                                "groups": 28, "stdout_sha256": hashlib.sha256(output.encode()).hexdigest(),
                                "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                                "executable": str(executable.relative_to(LAB))})
            obj = build / f"freestanding-{mode}.o"
            run(common + options + ["-ffreestanding", "-fno-builtin", "-fno-stack-protector",
                "-c", "freestanding_tglfault34.cpp", "-o", obj])
            symbols = run(["nm", "-u", obj])
            # Compiler-provided memory primitives are permitted. No allocator,
            # I/O, thread, exception runtime, driver, kernel or MMIO dependency.
            unexpected = [line for line in symbols.splitlines()
                          if line.split()[-1] not in {"memcpy", "memset", "memmove"}]
            if unexpected:
                raise SystemExit(f"unexpected freestanding dependencies: {unexpected}")
        result = {"compiler": compiler, "version": version, "builds": entries,
                  "source_sha256": source_hashes,
                  "freestanding_debug_release": "PASS", "hardware": "NONE",
                  "attachment": "NONE", "whole_kext": "NOT_BUILT"}
        resultpath.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{args.label}: 4 real builds, 28 groups/build PASS; freestanding Debug/Release PASS; {logpath}")


if __name__ == "__main__":
    main()
