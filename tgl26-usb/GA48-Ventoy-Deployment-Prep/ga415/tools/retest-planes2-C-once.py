#!/usr/bin/env python3
"""One newly authorized C repetition on the pinned, healthy PLANES2 boot only."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga415'
WORK = GA / 'private/planes2-C-retest'
BASE = '/private/tmp/ga415-planes2-C-retest'
SESSION = 'REDACTED-SESSION-ID'
UUID = '4C4C44E9-5555-3144-A1E4-CB51FF5A72E6'
BINARY_SHA = '207cbd59630de9c84c96e2871417a2ac14f23a9207f6635657172635a5adb3ca'
SOURCE_SHA = 'f962b7dff955cdf6fe9bafd1a4a151a7acd1f831394f9e40d8b33b20edce9789'
sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--user-present', action='store_true', required=True)
    p.add_argument('--approved', action='store_true', required=True)
    args = p.parse_args()
    assert args.user_present and args.approved
    assert not (GA / 'private/STOP-GPU.json').exists(), 'Existing stop condition requires review'
    assert hashlib.sha256((GA / 'tools/iosurface-pixel-probe.m').read_bytes()).hexdigest() == SOURCE_SHA
    # Local claim is created before any attempt. Existing attempts are never removed/reused.
    WORK.mkdir(mode=0o700)
    claim = {'case': 'C', 'width': 642, 'height': 100, 'pattern': 'affine', 'bpr': 'align16',
             'new_user_authorization': '在场，批准 C 一次', 'user_present': True, 'hands_off_requested': True,
             'hands_off_independently_observed': False,
             'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'session': SESSION,
             'NG_UUID': UUID, 'binary_sha256': BINARY_SHA, 'source_sha256': SOURCE_SHA,
             'maximum_explicit_command_buffers': 1, 'automatic_retry': False}
    (WORK / 'authorization.json').write_text(json.dumps(claim, ensure_ascii=False, indent=2) + '\n')
    normal_ssh.configure(); remote.ROOT = GA
    if not os.environ.get('GA410_SUDO_PASSWORD'):
        raise SystemExit('Set GA410_SUDO_PASSWORD in the caller environment')
    try:
        # Reuse only the read-only collector, not the old GPU launch claims.
        command = "/usr/bin/python3 /private/tmp/ga415-avatar-repro/collect-planes2-state.py"
        before = json.loads(remote.run('planes2-C-retest-health-before', command, sudo=True, timeout=75)['stdout'])
        old = json.loads(json.loads((GA / 'private/commands/blitobs-delivery-final-health.json').read_text())['stdout'])
        assert before['session']['stdout'].strip() == SESSION == old['session']['stdout'].strip()
        assert {r['path']: r['sha256'] for r in before['diagnostics']} == {r['path']: r['sha256'] for r in old['diagnostics']}
        import re
        assert before['dmesg']['returncode'] == 0
        assert not re.search(r'GPU.*(?:hang|reset|restart)|gpuRestart|PIPE_CONTROL|panic\(cpu', before['dmesg']['stdout'], re.I)
        assert len([s for s in before['processes']['stdout'].splitlines() if '/WindowServer' in s and s.split()[0] == '197']) == 1
        protected = json.loads(json.loads((GA / 'private/commands/blitobs-protected-after.json').read_text())['stdout'])
        installed = {path: record['sha256'] for path, record in protected['installed_files'].items()
                     if path in ['/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics',
                                 '/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver',
                                 '/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib']}
        assert len(installed) == 3
        preflight = r'''/usr/bin/python3 - <<'REMOTE'
import hashlib,json,subprocess
from pathlib import Path
def call(argv):return subprocess.check_output(argv,text=True,timeout=25)
assert call(['/usr/sbin/sysctl','-n','kern.bootsessionuuid']).strip()==SESSION
loaded=call(['/usr/bin/kmutil','showloaded']);assert UUID in next(s for s in loaded.splitlines() if 'com.StezzaPilot.NootedGreen ' in s)
args=call(['/usr/sbin/sysctl','-n','kern.bootargs']).split()
assert '-ngreentgltahoe' in args and not set(args)&{'-ngreennoplanesfix','-ngreen415obs','-ngreenxefix','-ngreenccs'}
paths=INSTALLED
for path,digest in paths.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
binary=Path('/private/tmp/ga415-runtime/build-v2/iosurface-pixel-probe')
assert hashlib.sha256(binary.read_bytes()).hexdigest()==BINARY_SHA
subprocess.run(['/usr/bin/codesign','--verify','--strict',str(binary)],check=True,timeout=20)
assert not Path(BASE).exists()
print(json.dumps({'status':'PINNED_PLANES2_RETEST_PREFLIGHT_PASS','session':SESSION,'NG_id':UUID,'binary_sha256':BINARY_SHA,'installed_hashes':paths}))
REMOTE'''
        preflight = preflight.replace('SESSION', repr(SESSION)).replace('UUID', repr(UUID)).replace('BINARY_SHA', repr(BINARY_SHA)).replace('INSTALLED', repr(installed)).replace('BASE', repr(BASE))
        remote.run('planes2-C-retest-pinned-preflight', preflight, timeout=100)
        # Exactly one subprocess.run of the GPU binary; no case list, retries or callback re-entry.
        launch = r'''/usr/bin/python3 - <<'REMOTE'
import hashlib,json,subprocess
from pathlib import Path
assert subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()==SESSION
binary=Path('/private/tmp/ga415-runtime/build-v2/iosurface-pixel-probe')
assert hashlib.sha256(binary.read_bytes()).hexdigest()==BINARY_SHA
root=Path(BASE);root.mkdir(mode=0o700)
with (root/'gpu-C.stdout').open('xb') as o,(root/'gpu-C.stderr').open('xb') as e:
 r=subprocess.run([str(binary),'--execute-once','--case','C','--bpr','align16','--pattern','affine','--output',str(root/'gpu-C'),'--claim-path',str(root/'GPU-ONCE-C')],stdout=o,stderr=e,timeout=60)
with (root/'gpu-C.exit').open('x') as stream:stream.write(str(r.returncode)+'\n')
print(json.dumps({'returncode':r.returncode,'stdout':(root/'gpu-C.stdout').read_text(),'stderr':(root/'gpu-C.stderr').read_text()}))
raise SystemExit(0 if r.returncode==0 else 3)
REMOTE'''
        launch = launch.replace('SESSION', repr(SESSION)).replace('BINARY_SHA', repr(BINARY_SHA)).replace('BASE', repr(BASE))
        run = remote.run('planes2-C-retest-GPU-ONCE', launch, timeout=90, check=False)
        assert run['returncode'] == 0, 'Single GPU attempt failed; do not retry'
        after = json.loads(remote.run('planes2-C-retest-health-after', command, sudo=True, timeout=75)['stdout'])
        assert after['session']['stdout'] == before['session']['stdout']
        assert {r['path']: r['sha256'] for r in after['diagnostics']} == {r['path']: r['sha256'] for r in before['diagnostics']}
        assert after['dmesg']['returncode'] == 0
        assert not re.search(r'GPU.*(?:hang|reset|restart)|gpuRestart|PIPE_CONTROL|panic\(cpu', after['dmesg']['stdout'], re.I)
        assert len([s for s in after['processes']['stdout'].splitlines() if '/WindowServer' in s and s.split()[0] == '197']) == 1
        receipt = remote.run('planes2-C-retest-archive', f"set -eu\n/usr/bin/tar -cf {BASE}/capture.tar -C {BASE} gpu-C gpu-C.stdout gpu-C.stderr gpu-C.exit GPU-ONCE-C\n/usr/bin/shasum -a 256 {BASE}/capture.tar", timeout=30)
        archive = WORK / 'capture.tar'; remote.download(BASE + '/capture.tar', archive, timeout=45)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest(); assert digest in receipt['stdout']
        with tarfile.open(archive) as stream: stream.extractall(WORK / 'capture', filter='data')
        summary = {'status': 'ONE_NEW_C_CAPTURED_HEALTH_PASS_PIXEL_VERIFICATION_REQUIRED', 'authorization': claim,
                   'archive_sha256': digest, 'before_utc': before['utc'], 'after_utc': after['utc'],
                   'WindowServer_PID': 197, 'diagnostics_unchanged': True, 'diagnostic_count': len(after['diagnostics']),
                   'new_explicit_GPU_command_buffers': 1, 'automatic_retry': False, 'root_cause': 'ROOT_CAUSE_UNVERIFIED'}
        (WORK / 'execution.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'status': summary['status'], 'capture': str(WORK / 'capture/gpu-C'), 'GPU_attempts': 1}))
    except BaseException as exc:
        (WORK / 'STOP.json').write_text(json.dumps({'reason': str(exc), 'completion_unknown_if_timeout': True, 'no_retry': True}, indent=2) + '\n')
        raise


if __name__ == '__main__':
    main()
