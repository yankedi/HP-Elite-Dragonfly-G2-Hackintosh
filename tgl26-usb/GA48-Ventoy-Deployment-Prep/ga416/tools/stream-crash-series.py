#!/usr/bin/env python3
"""One bounded, read-only SSH log stream, saved off-target with no automatic restart."""
import argparse
import datetime
import os
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
    parser.add_argument('--session', required=True, help='Expected boot UUID; refuse another boot')
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--level', choices=['info', 'debug'], default='debug')
    args = parser.parse_args()
    expected = str(uuid.UUID(args.session)).upper()
    if not 1 <= args.seconds <= 2700:
        parser.error('--seconds must be between 1 and 2700')
    normal_ssh.configure()
    work = ROOT / 'ga416/private/crash-series'
    work.mkdir(parents=True, exist_ok=True)
    label = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem = 'passive-stream-' + label
    predicate = 'process == "kernel" OR process == "watchdogd" OR process == "WindowServer" OR process == "VTDecoderXPCService" OR process == "TrackpadExtension" OR process == "MTLCompilerService" OR process == "timed"'
    code = f'''
import subprocess,time,json
session=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
assert session=={expected!r},'Boot changed; no automatic restart'
print('PASSIVE_STREAM_START '+json.dumps({{'session':session,'epoch':time.time(),'maximum_seconds':{args.seconds},'level':{args.level!r}}}),flush=True)
p=subprocess.Popen(['/usr/bin/log','stream','--style','ndjson','--level',{args.level!r},'--source','--backtrace','--timeout',str({args.seconds}),'--predicate',{predicate!r}])
print('PASSIVE_STREAM_CHILD '+json.dumps({{'pid':p.pid,'epoch':time.time(),'role':'live log stream, not historical log show'}}),flush=True)
try:
 rc=p.wait(timeout={args.seconds}+10)
except subprocess.TimeoutExpired:
 p.terminate()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 print('PASSIVE_STREAM_DURATION_LIMIT',flush=True)
else:
 print('PASSIVE_STREAM_EXIT '+str(rc),flush=True)
'''
    command = 'sudo -S -p "" /usr/bin/python3 -c ' + shlex.quote(code)
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    spec = {'status': 'STARTING', 'started_utc': start, 'boot_session': expected,
            'duration_seconds': args.seconds, 'level': args.level,
            'predicate': predicate, 'source_and_available_backtraces': True,
            'persistent_log_configuration_changed': False,
            'target_writes': False, 'new_GPU_tests': 0,
            'automatic_retry': False, 'command': remote.SSH + [command],
            'stdout': str((work / (stem + '.stdout')).relative_to(ROOT)),
            'stderr': str((work / (stem + '.stderr')).relative_to(ROOT))}
    with (work / (stem + '.start.json')).open('x') as f:
        json.dump(spec, f, indent=2)
        f.write('\n')
    secret = os.environ['GA410_SUDO_PASSWORD'] + '\n'
    with (work / (stem + '.stdout')).open('xb') as stdout, (work / (stem + '.stderr')).open('xb') as stderr:
        p = subprocess.Popen(remote.SSH + [command], stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
        try:
            p.communicate(input=secret.encode(), timeout=args.seconds+40)
            status = 'SSH_STREAM_ENDED'
        except subprocess.TimeoutExpired:
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
            status = 'LOCAL_TIME_LIMIT'
    result = {**spec, 'status': status, 'returncode': p.returncode,
              'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for key in ['stdout', 'stderr']:
        data = (ROOT / spec[key]).read_bytes()
        result[key + '_bytes'] = len(data)
        result[key + '_sha256'] = hashlib.sha256(data).hexdigest()
    result['capture_handshake_received'] = b'PASSIVE_STREAM_START ' in (ROOT / spec['stdout']).read_bytes()
    result['end_does_not_prove_cause'] = 'SSH loss can mean hang, panic, power-off or network failure; correlate with next boot panic.'
    with (work / (stem + '.result.json')).open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
