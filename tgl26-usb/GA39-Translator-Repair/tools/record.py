#!/usr/bin/env python3
"""CPU subprocess evidence, fresh run directories and bounded execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def record(command, output, cwd=ROOT, timeout=120):
    output = Path(output).resolve()
    if ROOT not in output.parents or output.exists():
        raise ValueError('Fresh output inside GA39 required')
    output.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    begin = time.monotonic()
    p = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    (output / 'stdout.txt').write_bytes(p.stdout)
    (output / 'stderr.txt').write_bytes(p.stderr)
    d = {'command': command, 'cwd': str(cwd), 'exit': p.returncode,
          'elapsed_seconds': time.monotonic() - begin,
          'selected_environment': {k: env.get(k) for k in ['GA38_RUN', 'PYTHONDONTWRITEBYTECODE', 'ASAN_OPTIONS', 'UBSAN_OPTIONS']},
         'stdout_sha256': hashlib.sha256(p.stdout).hexdigest(),
         'stderr_sha256': hashlib.sha256(p.stderr).hexdigest()}
    (output / 'receipt.json').write_text(json.dumps(d, sort_keys=True, indent=2) + '\n')
    print(json.dumps(d, sort_keys=True))
    return p.returncode


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--timeout', type=int, default=120)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.command[1:] if a.command[:1] == ['--'] else a.command
    raise SystemExit(record(cmd, a.output, timeout=a.timeout))
