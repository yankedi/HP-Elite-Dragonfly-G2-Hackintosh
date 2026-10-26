#!/usr/bin/env python3
"""Explicit one-case launcher for this HP; no retries or GPU case loop."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
sys.path.insert(0, str(WORKSPACE / 'ga410/tools'))
import normal_ssh
import remote

BINARY_SHA = '207cbd59630de9c84c96e2871417a2ac14f23a9207f6635657172635a5adb3ca'
SOURCE_SHA = 'f962b7dff955cdf6fe9bafd1a4a151a7acd1f831394f9e40d8b33b20edce9789'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=['A', 'B', 'C'], required=True)
    p.add_argument('--user-present', action='store_true', required=True)
    p.add_argument('--approved', action='store_true', required=True)
    a = p.parse_args()
    normal_ssh.configure(); remote.ROOT = ROOT
    out = ROOT / 'private'; out.mkdir(exist_ok=True)
    if (out / 'STOP-GPU.json').exists(): raise RuntimeError('Prior unsafe/failing run requires review; no further GPU work')
    if hashlib.sha256((ROOT / 'tools/iosurface-pixel-probe.m').read_bytes()).hexdigest() != SOURCE_SHA:
        raise RuntimeError('Source differs from pinned built version')
    boot = json.loads((WORKSPACE / 'ga414/reports/RUNTIME-BOOT.json').read_text())
    if boot['status'] != 'NOAUX_RUNTIME_CONFIRMED' or not boot['patch_applied_once_and_counts_verified']:
        raise RuntimeError('Original NOAUX boot proof unavailable')
    for field in ('identity_receipt', 'dmesg_receipt'):
        record = boot[field]; data = (WORKSPACE / record['path']).read_bytes()
        if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
            raise RuntimeError('Original boot proof hash mismatch')
    claim = out / ('GPU-CASE-' + a.case + '-CLAIM.json')
    with claim.open('x') as f:
        json.dump(dict(case=a.case, user_present=True, approved=True, utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       binary_sha256=BINARY_SHA, source_sha256=SOURCE_SHA, bpr='align16',
                       original_same_session_NOAUX_proof_sha256=hashlib.sha256((WORKSPACE / 'ga414/reports/RUNTIME-BOOT.json').read_bytes()).hexdigest()), f, indent=2)
    try:
        before = remote.run('case-' + a.case + '-health-before', '/usr/bin/python3 /private/tmp/ga414-runtime/health.py', timeout=80)
        health = json.loads(before['stdout'])
        if health['status'] != 'HEALTH_GATE_PASS' or health['session'] != boot['session'] or health['NG_UUID'] != boot['NG_UUID']:
            raise RuntimeError('Same-session GA414 identity/health gate failed')
        command = '''/usr/bin/python3 - <<'REMOTE'
import hashlib,json,subprocess
from pathlib import Path
c=CASE
root=Path('/private/tmp/ga415-runtime')
binary=root/'build-v2/iosurface-pixel-probe'
if hashlib.sha256(binary.read_bytes()).hexdigest()!=BINARY_SHA:raise RuntimeError('Probe binary mismatch')
dest=root/('gpu-'+c)
if dest.exists():raise RuntimeError('Case directory already exists; no retry')
stdout=root/('gpu-'+c+'.stdout');stderr=root/('gpu-'+c+'.stderr')
with stdout.open('xb') as o,stderr.open('xb') as e:
 r=subprocess.run([str(binary),'--execute-once','--case',c,'--bpr','align16','--output',str(dest),
                   '--claim-path',str(root/('GPU-ONCE-'+c))],stdout=o,stderr=e,timeout=60)
with (root/('gpu-'+c+'.exit')).open('x') as f:f.write(str(r.returncode)+'\\n')
print(json.dumps({'case':c,'returncode':r.returncode,'stdout':stdout.read_text(),'stderr':stderr.read_text()}))
raise SystemExit(0 if r.returncode==0 else 3)
REMOTE'''.replace('c=CASE', 'c=' + repr(a.case)).replace('!=BINARY_SHA', '!=' + repr(BINARY_SHA))
        run = remote.run('case-' + a.case + '-GPU-ONCE', command, timeout=90, check=False)
        if run['returncode'] != 0:
            raise RuntimeError('One-shot probe did not complete cleanly; preserve outputs, no further GPU submissions')
        after = remote.run('case-' + a.case + '-health-after', '/usr/bin/python3 /private/tmp/ga414-runtime/health.py', timeout=80)
        if json.loads(after['stdout'])['status'] != 'HEALTH_GATE_PASS': raise RuntimeError('Post-case health gate failed')
        if not os.environ.get('GA410_SUDO_PASSWORD'):
            raise SystemExit('Set GA410_SUDO_PASSWORD in the caller environment')
        faults = remote.run('case-' + a.case + '-kernel-fault-check', '''/usr/bin/python3 - <<'REMOTE'
import subprocess,re,json
r=subprocess.run(['/sbin/dmesg'],capture_output=True,text=True,timeout=15)
matches=[s for s in r.stdout.splitlines() if re.search(r'PIPE_CONTROL|gpuRestart|GPU Restart|GPU Hang|RCS.*hang|GPU.*hang|GPU.*reset|Graphics.*panic',s,re.I)]
print(json.dumps({'returncode':r.returncode,'matches':matches,'stderr':r.stderr}))
REMOTE''', sudo=True, timeout=30)
        f = json.loads(faults['stdout'])
        if f['returncode'] != 0 or f['matches']: raise RuntimeError('Kernel fault inspection needs review before further cases')
        remote.run('case-' + a.case + '-archive', '/usr/bin/tar -cf /private/tmp/ga415-runtime/gpu-' + a.case + '.tar -C /private/tmp/ga415-runtime gpu-' + a.case + ' gpu-' + a.case + '.stdout gpu-' + a.case + '.stderr gpu-' + a.case + '.exit', timeout=30)
        archive = out / ('gpu-' + a.case + '.tar')
        remote.download('/private/tmp/ga415-runtime/gpu-' + a.case + '.tar', archive)
        dest = out / ('case-' + a.case); dest.mkdir()
        with tarfile.open(archive) as t: t.extractall(dest, filter='data')
        print('ONE_CASE_CAPTURED; independently verify pixels before any next case:', dest)
    except BaseException as e:
        stop = out / 'STOP-GPU.json'
        if not stop.exists(): stop.write_text(json.dumps(dict(case=a.case, reason=str(e), no_automatic_retry=True), indent=2) + '\n')
        raise


if __name__ == '__main__': main()
