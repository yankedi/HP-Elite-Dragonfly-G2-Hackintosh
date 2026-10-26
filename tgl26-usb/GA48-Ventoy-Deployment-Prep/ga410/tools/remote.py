#!/usr/bin/env python3
"""Record real SSH operations without persisting credentials."""
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def configure():
    """Build an SSH argv from explicit public-environment configuration."""
    global SSH
    target = os.environ.get('GA410_SSH_TARGET', '')
    if not re.fullmatch(r'(?:[A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9][A-Za-z0-9._:-]*', target):
        raise RuntimeError('Set GA410_SSH_TARGET to an authorized user@host or host')
    SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
           '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
           '-o', 'ServerAliveCountMax=2']
    key = os.environ.get('GA410_SSH_KEY')
    if key:
        SSH += ['-i', str(Path(key).expanduser()), '-o', 'IdentitiesOnly=yes']
    known_hosts = os.environ.get('GA410_KNOWN_HOSTS')
    if known_hosts:
        SSH += ['-o', 'UserKnownHostsFile=' + str(Path(known_hosts).expanduser())]
    SSH.append(target)
    return SSH


SSH = configure()


def run(name, command, *, sudo=False, timeout=120, check=True):
    out = ROOT / 'private/commands'
    out.mkdir(parents=True, exist_ok=True)
    log = out / (name + '.json')
    if log.exists():
        raise FileExistsError('Refusing to repeat a recorded operation: ' + name)
    actual = 'sudo -S -p "" /bin/bash -c ' + shlex.quote(command) if sudo else command
    secret = (os.environ['GA410_SUDO_PASSWORD'] + '\n').encode() if sudo else None
    try:
        r = subprocess.run(SSH + [actual], input=secret, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        row = {'name': name, 'command': actual,
               'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'returncode': None, 'error': 'LOCAL_SSH_TIMEOUT', 'timeout_seconds': timeout,
               'stdout': (error.stdout or b'').decode(errors='replace'),
               'stderr': (error.stderr or b'').decode(errors='replace'),
               'remote_process_completion_unknown': True}
        log.write_text(json.dumps(row, indent=2) + '\n')
        raise RuntimeError('SSH timed out; see recorded evidence: ' + name) from error
    row = {'name': name, 'command': actual, 'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'returncode': r.returncode, 'stdout': r.stdout.decode(errors='replace'), 'stderr': r.stderr.decode(errors='replace')}
    log.write_text(json.dumps(row, indent=2) + '\n')
    print(name, 'rc=', r.returncode, flush=True)
    print(row['stdout'][-6000:], row['stderr'][-3000:], flush=True)
    if check and r.returncode:
        raise RuntimeError('Operation failed; see recorded stdout/stderr: ' + name)
    return row


def upload(local, remote, *, timeout=120):
    import hashlib
    command = 'umask 077; set -C; /bin/cat > ' + shlex.quote(remote)
    with Path(local).open('rb') as f:
        r = subprocess.run(SSH + [command], stdin=f, capture_output=True, timeout=timeout)
    with Path(local).open('rb') as f:
        source_hash = hashlib.file_digest(f, 'sha256').hexdigest()
    row = {'command': command, 'returncode': r.returncode, 'stdout': r.stdout.decode(), 'stderr': r.stderr.decode(), 'bytes': Path(local).stat().st_size, 'source_sha256': source_hash}
    dest = ROOT / 'private/commands' / ('upload-' + Path(remote).name + '.json')
    dest.write_text(json.dumps(row, indent=2) + '\n')
    if r.returncode:
        raise RuntimeError(str(row))


def download(remote, local, *, sudo=False, timeout=120):
    command = '/bin/cat ' + shlex.quote(remote)
    if sudo:
        command = 'sudo -S -p "" ' + command
    secret = (os.environ['GA410_SUDO_PASSWORD'] + '\n').encode() if sudo else None
    try:
        with Path(local).open('xb') as f:
            r = subprocess.run(SSH + [command], input=secret, stdout=f, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        row = {'command': command, 'returncode': None, 'error': 'TIMEOUT', 'timeout_seconds': timeout, 'partial_stdout_file': str(local), 'partial_bytes': Path(local).stat().st_size, 'stderr': (error.stderr or b'').decode(errors='replace')}
        (ROOT / 'private/commands' / ('download-' + Path(local).name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
        raise
    row = {'command': command, 'returncode': r.returncode, 'stderr': r.stderr.decode(), 'local_bytes': Path(local).stat().st_size}
    dest = ROOT / 'private/commands' / ('download-' + Path(local).name + '.json')
    dest.write_text(json.dumps(row, indent=2) + '\n')
    if r.returncode:
        raise RuntimeError(str(row))
