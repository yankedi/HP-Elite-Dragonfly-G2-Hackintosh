#!/usr/bin/env python3
"""Run a CPU-only command with immutable local logs and a timeout receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def record(command, output, cwd=ROOT, timeout=120):
    out = Path(output).resolve()
    if ROOT not in out.parents or out.exists():
        raise ValueError('Fresh output under GA40 required')
    out.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               XDG_CACHE_HOME=str(ROOT / 'cache'), TMPDIR=str(ROOT / 'tmp'))
    start = time.monotonic()
    try:
        p = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout)
        code, stdout, stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, exc.stdout or b'', exc.stderr or b''
    (out / 'stdout.txt').write_bytes(stdout)
    (out / 'stderr.txt').write_bytes(stderr)
    row = {'command': command, 'cwd': str(cwd), 'exit': code,
           'elapsed_seconds': time.monotonic() - start,
           'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
           'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
           'environment': {k: env.get(k) for k in ['PYTHONDONTWRITEBYTECODE', 'XDG_CACHE_HOME', 'TMPDIR', 'VK_ICD_FILENAMES', 'VK_DRIVER_FILES']}}
    (out / 'receipt.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(row))
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--cwd', type=Path, default=ROOT)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    raise SystemExit(record(command, args.output, args.cwd, args.timeout))
