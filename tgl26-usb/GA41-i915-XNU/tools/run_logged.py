#!/usr/bin/env python3
"""Run one command, retaining exact argv/cwd/environment and raw stdout/stderr.

Usage: python3 -B tools/run_logged.py LABEL COMMAND ARG ...
Never overwrites an earlier run. Does not access devices or download anything.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
label, *command = sys.argv[1:]
assert label and command and "/" not in label
logdir = root / "logs" / label
logdir.mkdir(exist_ok=False)
record = {"argv": command, "cwd": str(Path.cwd()),
          "started": datetime.now(timezone.utc).isoformat(),
          "env": {k: v for k, v in os.environ.items() if k in
                  ("PATH", "CC", "CXX", "ASAN_OPTIONS", "UBSAN_OPTIONS", "PKG_CONFIG_PATH")}}
(logdir / "command.json").write_text(json.dumps(record, indent=2) + "\n")
with (logdir / "stdout.txt").open("wb") as out, (logdir / "stderr.txt").open("wb") as err:
    result = subprocess.run(command, stdout=out, stderr=err, check=False)
record["exit_code"] = result.returncode
record["ended"] = datetime.now(timezone.utc).isoformat()
(logdir / "command.json").write_text(json.dumps(record, indent=2) + "\n")
print((logdir / "stdout.txt").read_text(errors="replace")[-15000:])
print((logdir / "stderr.txt").read_text(errors="replace")[-15000:], file=sys.stderr)
print("LOG", logdir, "EXIT", result.returncode)
sys.exit(result.returncode)
