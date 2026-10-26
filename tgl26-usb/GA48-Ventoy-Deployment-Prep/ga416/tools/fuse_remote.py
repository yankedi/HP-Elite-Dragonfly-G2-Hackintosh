#!/usr/bin/env python3
"""Record NixOS HP fuse commands through pinned, already-known Tailscale SSH."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'ga416/private/linux-fuse'
target = os.environ.get('GA416_SSH_TARGET', '')
if not re.fullmatch(r'(?:[A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9][A-Za-z0-9._:-]*', target):
    raise SystemExit('Set GA416_SSH_TARGET to an authorized user@host or host')
SSH = ['ssh', '-o', 'ConnectTimeout=8', '-o', 'BatchMode=yes',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=5',
       '-o', 'ServerAliveCountMax=2', target]


def run(name, command, timeout=60, check=True):
    path = OUT / (name + '.json')
    if path.exists(): raise FileExistsError(path)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        r = subprocess.run(SSH + [command], capture_output=True, text=True, timeout=timeout)
        row = {'command': SSH + [command], 'started_utc': started,
               'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'returncode': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}
    except subprocess.TimeoutExpired as exc:
        row = {'command': SSH + [command], 'started_utc': started, 'returncode': None,
               'stdout': (exc.stdout or b'').decode(errors='replace'),
               'stderr': (exc.stderr or b'').decode(errors='replace'), 'error': 'SSH_TIMEOUT'}
    path.write_text(json.dumps(row, indent=2) + '\n')
    print(name, 'rc=', row['returncode'])
    print(row['stdout'][-15000:]); print(row['stderr'][-3000:])
    if check and row['returncode'] != 0: raise RuntimeError('See receipt ' + str(path))
    return row


if __name__ == '__main__':
    run(sys.argv[1], sys.stdin.read(), timeout=180)
