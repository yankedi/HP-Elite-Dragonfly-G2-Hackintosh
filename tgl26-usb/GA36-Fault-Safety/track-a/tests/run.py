#!/usr/bin/env python3
"""Build/run the exact freestanding writer core; all outputs remain in GA36."""
import json
import os
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "pipeline"
LOG.mkdir(parents=True, exist_ok=True)
results = []
for compiler in ("clang++", "g++"):
    path = os.environ.get("CXX_GCC" if compiler == "g++" else "CXX_CLANG") or shutil.which(compiler)
    if not path:
        raise SystemExit(f"required compiler missing: {compiler}")
    for mode, flags in (("release", ["-O2"]), ("asan-ubsan", ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"])):
        name = compiler.replace("+", "p") + "-" + mode
        binary = LOG / name
        cmd = [path, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pthread", *flags, str(ROOT / "tests/pipeline.cpp"), "-o", str(binary)]
        build = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        (LOG / (name + "-build.txt")).write_text("$ " + " ".join(cmd) + "\n" + build.stdout + build.stderr)
        if build.returncode:
            raise SystemExit(f"build failed: {name}")
        run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        (LOG / (name + "-run.txt")).write_text(run.stdout + run.stderr)
        results.append({"name": name, "compiler": path, "exit": run.returncode, "stdout": run.stdout, "stderr": run.stderr})
        if run.returncode or run.stderr:
            raise SystemExit(f"test failed: {name}")
(LOG / "results.json").write_text(json.dumps(results, indent=2) + "\n")
print("PASS", len(results), "compiler/sanitizer builds")
