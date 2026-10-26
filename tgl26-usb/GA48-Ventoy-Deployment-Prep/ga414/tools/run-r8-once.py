#!/usr/bin/env python3
"""Reuse exact GA412 binaries, gated by real GA414 boot logs; one GPU attempt."""
import argparse
import datetime
import json
import shlex
import sys
from common import *

sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote

BASE = '/private/tmp/ga414-runtime'
SESSION = 'REDACTED-SESSION-ID'
HASHES = {'managed-rt-probe': 'b324901b7c4dd8b62f812fb08b0e98950eb303c160a2bc9764302178d930db37',
          'trace-managed-cpu.dylib': '642fc8a409b198253fdca4fb9f32b6f980bf119573d2f868794aafdc234648e9'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-preflight-unsigned-original', action='store_true',
                        help='Reuse uploaded exact GA412 originals after codesign check rejected their inherited unsigned status; GPU has not started')
    options = parser.parse_args()
    require(not (WORK / 'r8-once-started.json').exists(), 'GPU attempt already claimed; never repeat')
    log_row = json.loads((WORK / 'commands/runtime-current-dmesg.json').read_text())
    require(log_row['returncode'] == 0, 'dmesg capture failed')
    logs = log_row['stdout']
    required = ['GA414 NOAUX: gate=1 cpu=0x8c pci=8086:9a49 subsystem=103c:8716 build=25G83',
                'GA414 NOAUX: preflight first=1 original=1 patched=0 expected=1/0',
                'GA414 NOAUX: postflight original=0 patched=1 verified=1 expected=0/1',
                'XeNG NOAUX: fillSurfaceStateAuxInfo sempre AUX_NONE: aplicado',
                'XE-NOCCS3: IntelAccelerator::submitCCSResolve -> retorno imediato: aplicado',
                'HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80',
                'HP-R6: real TGL/Tahoe upstream pool sizing/alignment enabled=1']
    require(all(x in logs for x in required), 'missing actual runtime patch/topology evidence')
    require('GA414 NOAUX: ERROR' not in logs and 'GA414 NOAUX: DISABLED' not in logs, 'NOAUX invalid')
    health_row = json.loads((WORK / 'commands/runtime-health-pre.json').read_text())
    health = json.loads(health_row['stdout'])
    require(health_row['returncode'] == 0 and health['status'] == 'HEALTH_GATE_PASS' and health['session'] == SESSION, 'pre-health failed')
    normal_ssh.configure(); remote.ROOT = ROOT / 'ga414'
    for name, digest in HASHES.items():
        path = ROOT / 'ga412/private/native-build-v2' / name
        require(sha(path) == digest, 'sealed GA412 binary changed: ' + name)
        if not options.resume_preflight_unsigned_original:
            remote.upload(path, BASE + '/' + name, timeout=20)
    if options.resume_preflight_unsigned_original:
        failed = json.loads((WORK / 'commands/runtime-immediate-preflight.json').read_text())
        require(failed['returncode'] == 1 and 'code object is not signed at all' in failed['stderr'], 'unexpected preflight failure')
        require(not (WORK / 'commands/runtime-r8-once-execution.json').exists(), 'GPU already attempted')
    command = f'''set -eu
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = {SESSION}
/bin/chmod 700 {BASE}/managed-rt-probe {BASE}/trace-managed-cpu.dylib
/usr/bin/shasum -a 256 {BASE}/managed-rt-probe {BASE}/trace-managed-cpu.dylib
/usr/bin/python3 {BASE}/health.py
'''
    prep = remote.run('runtime-immediate-preflight-original-binaries', command, timeout=60)
    require(all(d in prep['stdout'] for d in HASHES.values()) and 'HEALTH_GATE_PASS' in prep['stdout'], 'immediate preflight failed')
    script = f'''set -eu
BASE={BASE}
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = {SESSION}
umask 077
mkdir "$BASE/once-execution-claim"
printf 'ONCE_CLAIM_CREATED\\n'
set +e
GA411_TRACE_DYLIB="$BASE/trace-managed-cpu.dylib" "$BASE/managed-rt-probe" R8 legacy "$BASE/r8-legacy-capture" > >(/usr/bin/tee "$BASE/probe.stdout") 2> >(/usr/bin/tee "$BASE/probe.stderr" >&2)
rc=$?
printf '%s\\n' "$rc" >"$BASE/probe.exit"
printf 'PROBE_EXIT=%s\\n' "$rc"
exit "$rc"
'''
    save(WORK / 'r8-once-started.json', {'goal_id': 'REDACTED-SESSION-ID',
         'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'maximum_execution_attempts': 1,
         'binary_sha256': HASHES, 'session': SESSION, 'remote_script': script,
         'runtime_log': record(WORK / 'commands/runtime-current-dmesg.json'),
         'pre_health': record(WORK / 'commands/runtime-health-pre.json')})
    # Any timeout/failure is terminal for GPU attempts; no loop or retry.
    remote.run('runtime-r8-once-execution', '/bin/bash -c ' + shlex.quote(script), timeout=100, check=False)
    remote.run('runtime-health-post', '/usr/bin/python3 ' + BASE + '/health.py', timeout=60, check=False)
    capture = WORK / 'r8-legacy-capture'; capture.mkdir()
    for name in ('input.bin', 'expected.bin', 'gpu.bin', 'cpu.bin', 'result.json', 'command.json'):
        remote.download(BASE + '/r8-legacy-capture/' + name, capture / name, timeout=20)
    for name in ('probe.stdout', 'probe.stderr', 'probe.exit'):
        remote.download(BASE + '/' + name, capture / name, timeout=20)
    remote.run('runtime-capture-remote-hashes', '/usr/bin/shasum -a 256 ' + BASE + '/r8-legacy-capture/* ' + BASE + '/probe.stdout ' + BASE + '/probe.stderr ' + BASE + '/probe.exit', timeout=25)


if __name__ == '__main__':
    main()
