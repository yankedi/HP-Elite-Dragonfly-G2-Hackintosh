#!/usr/bin/env python3
"""New-session one-shot launcher; exact GA414/GA412 binaries, no build or retry."""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga416'
BASE = '/private/tmp/ga416-acceptance-8B9C5493'
SESSION = 'REDACTED-SESSION-ID'
HASHES = {'managed-rt-probe': 'b324901b7c4dd8b62f812fb08b0e98950eb303c160a2bc9764302178d930db37',
          'trace-managed-cpu.dylib': '642fc8a409b198253fdca4fb9f32b6f980bf119573d2f868794aafdc234648e9'}


def main():
    if sys.argv[1:] != ['--user-present-approved-once']:
        raise SystemExit('requires --user-present-approved-once')
    sys.path.insert(0, str(ROOT / 'ga410/tools'))
    import normal_ssh
    import remote
    normal_ssh.configure(); remote.ROOT = GA
    if not os.environ.get('GA410_SUDO_PASSWORD'):
        raise SystemExit('Set GA410_SUDO_PASSWORD in the caller environment')
    # Preserve old GA414 and GA415 claims; this run gets its own pinned claim.
    claim_path = GA / 'private/r8-once-authorized.json'
    if claim_path.exists(): raise RuntimeError('Attempt already claimed; never retry')
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / 'ga412/private/native-build-v2' / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Archived binary changed')
    with (GA / 'private/r8-launch.log').open('x') as log, contextlib.redirect_stdout(log):
        h = remote.run('r8-health-immediate-pre', '/usr/bin/python3 ' + BASE + '/health.py', sudo=True, timeout=65)
        health = json.loads(h['stdout'])
        if health['status'] != 'HEALTH_GATE_PASS': raise RuntimeError('Health failed; no GPU attempt')
        before = json.loads(json.loads((GA / 'private/commands/health-before-desktop.json').read_text())['stdout'])
        if {x['path']: x['sha256'] for x in health['diagnostics']} != {x['path']: x['sha256'] for x in before['diagnostics']}:
            raise RuntimeError('New diagnostics require review; no GPU attempt')
        initial = json.loads(json.loads(next((GA / 'private/commands').glob('boot-health-*.json')).read_text())['stdout'])
        required = ['GA414 NOAUX: postflight original=0 patched=1 verified=1 expected=0/1',
                    'XeNG NOAUX: fillSurfaceStateAuxInfo sempre AUX_NONE: aplicado',
                    'XE-NOCCS3: IntelAccelerator::submitCCSResolve -> retorno imediato: aplicado',
                    'HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80']
        if not all(s in initial['dmesg']['stdout'] for s in required): raise RuntimeError('Runtime evidence missing')
        preflight = r'''/usr/bin/python3 - <<'REMOTE'
import hashlib,subprocess
from pathlib import Path
base=Path(BASE)
assert subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()==SESSION
for name,digest in HASHES.items():
 assert hashlib.sha256((base/name).read_bytes()).hexdigest()==digest,name
assert not (base/'r8-once-claim').exists()
assert not (base/'r8-capture').exists()
print('EXACT_BINARIES_AND_FRESH_CLAIM_PASS')
REMOTE'''.replace('BASE', repr(BASE)).replace('SESSION', repr(SESSION)).replace('HASHES', repr(HASHES))
        remote.run('r8-sealed-binary-preflight', preflight, timeout=30)
        script = f'''set -eu
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = {SESSION}
umask 077
mkdir {BASE}/r8-once-claim
set +e
GA411_TRACE_DYLIB={BASE}/trace-managed-cpu.dylib {BASE}/managed-rt-probe R8 legacy {BASE}/r8-capture > {BASE}/r8.stdout 2> {BASE}/r8.stderr
rc=$?
printf '%s\n' "$rc" > {BASE}/r8.exit
printf 'R8_EXIT=%s\n' "$rc"
exit "$rc"
'''
        claim = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'session': SESSION,
                 'authorization': '用户在场明确要求健康通过后执行一次GA414 R8 Managed RT回归',
                 'maximum_execution_attempts': 1, 'explicit_command_buffers': 1, 'automatic_retry': False,
                 'binary_sha256': HASHES, 'script': script}
        with claim_path.open('x') as f: json.dump(claim, f, indent=2, ensure_ascii=False)
        attempt = remote.run('r8-execute-ONCE', '/bin/bash -c ' + shlex.quote(script), timeout=90, check=False)
        # Failure or timeout never re-enters the submission. Everything below is read-only evidence.
        after = remote.run('r8-health-post', '/usr/bin/python3 ' + BASE + '/health.py', sudo=True, timeout=65, check=False)
        if attempt['returncode'] != 0 or after['returncode'] != 0:
            (GA / 'private/STOP-GPU.json').write_text(json.dumps({'attempt_rc': attempt['returncode'], 'health_rc': after['returncode'], 'no_retry': True}) + '\n')
        archive = remote.run('r8-archive', f'set -eu\n/usr/bin/tar -czf {BASE}/r8.tar.gz -C {BASE} r8-capture r8.stdout r8.stderr r8.exit r8-once-claim\n/usr/bin/shasum -a 256 {BASE}/r8.tar.gz', timeout=30, check=False)
        if archive['returncode'] != 0: raise RuntimeError('Capture incomplete; no retry')
        dest = GA / 'private/r8.tar.gz'
        remote.download(BASE + '/r8.tar.gz', dest, timeout=30)
        if hashlib.sha256(dest.read_bytes()).hexdigest() not in archive['stdout']: raise RuntimeError('Archive hash mismatch')
        with tarfile.open(dest) as t: t.extractall(GA / 'private/captures', filter='data')
    print(json.dumps({'GPU_attempts': 1, 'execution_rc': attempt['returncode'], 'post_health_rc': after['returncode'],
                      'pixel_result': 'PENDING_INDEPENDENT_AUDIT'}))


if __name__ == '__main__':
    main()
