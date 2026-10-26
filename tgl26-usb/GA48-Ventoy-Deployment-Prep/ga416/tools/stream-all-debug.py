#!/usr/bin/env python3
"""Unfiltered, untimed debug stream; losslessly gzip all received bytes off-target."""
import argparse
import datetime
import os
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True)
    parser.add_argument('--output-directory', type=Path,
                        default=ROOT / 'ga416/private/crash-series')
    args = parser.parse_args()
    expected = str(uuid.UUID(args.session)).upper()
    normal_ssh.configure()
    work = args.output_directory.resolve()
    work.mkdir(parents=True, exist_ok=True)
    label = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem = 'all-debug-' + label
    code = f'''
import json,subprocess,time
session=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
assert session=={expected!r},'Boot changed; no automatic cross-boot retry'
print('ALL_DEBUG_START '+json.dumps({{'boot':session,'epoch':time.time(),'predicate':None,'duration_limit':None}}),flush=True)
p=subprocess.Popen(['/usr/bin/log','stream','--style','ndjson','--level','debug','--source','--backtrace','--unreliable'])
print('ALL_DEBUG_CHILD '+json.dumps({{'pid':p.pid,'epoch':time.time()}}),flush=True)
rc=p.wait()
print('ALL_DEBUG_EXIT '+str(rc),flush=True)
raise SystemExit(rc if rc>=0 else 128-rc)
'''
    command = 'sudo -S -p "" /usr/bin/python3 -c ' + shlex.quote(code)
    spec = {
        'status': 'STARTING', 'boot': expected,
        'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'predicate': None, 'process_filter': None, 'level': 'debug',
        'duration_limit': None, 'size_limit': None, 'sampling_or_discard': False,
        'format': 'ndjson with source/available backtrace/reliability annotation',
        'compression': 'lossless gzip level 1 on development host',
        'automatic_cross_boot_retry': False,
        'stdout': str((work / (stem + '.ndjson.gz')).relative_to(ROOT)),
        'stderr': str((work / (stem + '.stderr')).relative_to(ROOT)),
        'command': remote.SSH + [command],
    }
    (work / (stem + '.start.json')).write_text(json.dumps(spec, indent=2) + '\n')
    secret = os.environ['GA410_SUDO_PASSWORD'] + '\n'
    count = 0
    digest = hashlib.sha256()
    first = bytearray()
    error = None
    p = None
    ready = False
    try:
        with (ROOT / spec['stderr']).open('xb') as stderr, (ROOT / spec['stdout']).open('xb') as raw:
            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', compresslevel=1) as output:
                p = subprocess.Popen(remote.SSH + [command], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=stderr)
                p.stdin.write(secret.encode())
                p.stdin.close()
                while True:
                    chunk = p.stdout.read1(65536)
                    if not chunk:
                        break
                    if len(first) < 65536:
                        first.extend(chunk[:65536 - len(first)])
                    digest.update(chunk)
                    count += len(chunk)
                    output.write(chunk)
                    output.flush()
                    raw.flush()
                    if not ready and b'ALL_DEBUG_START ' in first:
                        for line in first.splitlines():
                            if not line.startswith(b'{'):
                                continue
                            try:
                                event = json.loads(line)
                            except (ValueError, UnicodeDecodeError):
                                continue
                            if 'eventMessage' not in event:
                                continue
                            readiness = {
                                'status': 'STREAM_HANDSHAKE_AND_REAL_EVENT_VERIFIED',
                                'boot': expected, 'local_collector_pid': __import__('os').getpid(),
                                'verified_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                'received_bytes_at_verification': count,
                                'first_event_timestamp': event.get('timestamp'),
                                'first_event_machTimestamp': event.get('machTimestamp'),
                                'first_event_process': event.get('processImagePath'),
                                'stdout': spec['stdout'], 'start_receipt': str((work / (stem + '.start.json')).relative_to(ROOT)),
                                'note': 'Live evidence, not completion; gzip trailer/hash finalized when stream ends.',
                            }
                            with (work / (stem + '.ready.json')).open('x') as f:
                                f.write(json.dumps(readiness, indent=2) + '\n')
                            print(json.dumps(readiness), flush=True)
                            ready = True
                            break
                p.stdout.close()
                p.wait()
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        if p is not None and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
    compressed_digest = hashlib.sha256()
    target = ROOT / spec['stdout']
    if target.exists():
        with target.open('rb') as f:
            for block in iter(lambda: f.read(1048576), b''):
                compressed_digest.update(block)
    result = {
        **spec, 'status': 'CAPTURE_ENDED', 'error': error,
        'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'returncode': p.returncode if p else None,
        'uncompressed_bytes': count, 'uncompressed_sha256': digest.hexdigest(),
        'compressed_bytes': target.stat().st_size if target.exists() else 0,
        'compressed_sha256': compressed_digest.hexdigest(),
        'handshake_received': b'ALL_DEBUG_START ' in first,
        'end_not_cause': 'Correlate disconnection with user observation and new panic; end alone proves no cause.',
    }
    (work / (stem + '.result.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if error:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
