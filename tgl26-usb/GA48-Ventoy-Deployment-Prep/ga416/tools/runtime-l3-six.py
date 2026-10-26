#!/usr/bin/env python3
"""First GA416 boot: staged screenshots, then an explicitly claimed single R8."""
import argparse
import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tarfile
import uuid

ROOT=Path(__file__).resolve().parents[2]
GA=ROOT/'ga416'
WORK=GA/'private/l3-six-runtime'
BASE='/private/tmp/ga416-l3-six'
SESSION=os.environ.get('GA416_EXPECTED_BOOT_SESSION')
CONSOLE_USER=os.environ.get('GA416_CONSOLE_USER')
CONSOLE_UID=os.environ.get('GA416_CONSOLE_UID')
try:
    SESSION=str(uuid.UUID(SESSION)).upper()
except (ValueError, TypeError, AttributeError):
    SESSION=''
if not SESSION or not CONSOLE_USER or not CONSOLE_UID or not CONSOLE_UID.isdigit():
    raise SystemExit('Set GA416_EXPECTED_BOOT_SESSION, GA416_CONSOLE_USER and GA416_CONSOLE_UID')
HASHES={'managed-rt-probe':'b324901b7c4dd8b62f812fb08b0e98950eb303c160a2bc9764302178d930db37',
        'trace-managed-cpu.dylib':'642fc8a409b198253fdca4fb9f32b6f980bf119573d2f868794aafdc234648e9'}
sys.path.insert(0,str(ROOT/'ga410/tools'))
import normal_ssh
import remote


def configure():
    normal_ssh.configure();remote.ROOT=GA
    if not os.environ.get('GA410_SUDO_PASSWORD'):
        raise SystemExit('Set GA410_SUDO_PASSWORD in the caller environment')
    WORK.mkdir(parents=True,exist_ok=True)


def run(name,command,**kw):
    with contextlib.redirect_stdout(io.StringIO()):row=remote.run('l3six-'+name,command,**kw)
    print(name,'rc=',row['returncode'],flush=True)
    return row


def health(name):
    row=run(name,'/usr/bin/python3 '+BASE+'/health-l3-six.py',sudo=True,timeout=70)
    data=json.loads(row['stdout']);assert data['status']=='HEALTH_GATE_PASS'
    initial=json.loads(json.loads((GA/'private/commands/l3six-initial-runtime-health.json').read_text())['stdout'])
    assert {x['path']:x['sha256'] for x in data['diagnostics']}=={x['path']:x['sha256'] for x in initial['diagnostics']}
    return data


def stage():
    initial=json.loads(json.loads((GA/'private/commands/l3six-initial-runtime-health.json').read_text())['stdout'])
    assert not initial['kernel_fault_lines']
    assert not any(d['mtime_since_boot'] or d['current_session_in_content'] for d in initial['diagnostics'])
    for marker in ['HP-GA416: L3 override 0 -> 6','HP-GA416: effective L3BankCount = 6',
                   'HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80 L3Banks=6',
                   'GA414 NOAUX: postflight original=0 patched=1 verified=1',
                   'XE-NOCCS3: IntelAccelerator::submitCCSResolve -> retorno imediato: aplicado',
                   'XeNG PLANES2: calculateIOSurfaceDeviceCacheVRAMBytes planos de IOSurface+0x98: aplicado']:
        assert marker in initial['dmesg']['stdout']
    archive=WORK/'l3six-tools.tar.gz'
    with tarfile.open(archive,'x:gz') as t:
        for name in HASHES:
            p=ROOT/'ga412/private/native-build-v2'/name
            assert hashlib.sha256(p.read_bytes()).hexdigest()==HASHES[name]
            t.add(p,arcname=name)
        t.add(ROOT/'ga415/private/cpu-build-v2/build-v2/desktop-capture',arcname='desktop-capture')
        for name in ['health-l3-six.py','capture-l3-six.command']:t.add(GA/'tools'/name,arcname=name)
        t.add(GA/'private/l3-six/build/product/NootedGreen.kext',arcname='candidate/NootedGreen.kext')
    run('stage-directory',f'set -eu\ntest "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = {SESSION}\numask 077\nmkdir {BASE}',timeout=15)
    with contextlib.redirect_stdout(io.StringIO()):remote.upload(archive,BASE+'/l3six-tools.tar.gz',timeout=35)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    run('stage-extract',f'''set -eu
test "$(/usr/bin/shasum -a 256 {BASE}/l3six-tools.tar.gz | /usr/bin/awk '{{print $1}}')" = {digest}
/usr/bin/tar -xpf {BASE}/l3six-tools.tar.gz -C {BASE}
/bin/chmod 700 {BASE}/capture-l3-six.command {BASE}/managed-rt-probe
''',timeout=25)
    sig=run('native-signature',f'''set -eu
/usr/bin/codesign --verify --strict --deep --verbose=4 {BASE}/candidate/NootedGreen.kext
/usr/bin/codesign --display --verbose=4 {BASE}/candidate/NootedGreen.kext
/usr/bin/dwarfdump --uuid {BASE}/candidate/NootedGreen.kext/Contents/MacOS/NootedGreen
/usr/bin/shasum -a 256 {BASE}/candidate/NootedGreen.kext/Contents/MacOS/NootedGreen
''',timeout=30,check=False)
    print(sig['stdout'],sig['stderr'])
    health('health-before-desktop')
    run('ioreg-counters',"set -o pipefail\n/usr/sbin/ioreg -rc IntelAccelerator -d1 | /usr/bin/grep -E 'xe-topo|xe-blitfix|xe-rec'",check=False,timeout=20)


def capture():
    health('health-immediate-pre-desktop')
    row=run('desktop-gui',f'''set -eu
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = {SESSION}
/bin/launchctl asuser {CONSOLE_UID} /usr/bin/sudo -u {shlex.quote(CONSOLE_USER)} /usr/bin/open -a Terminal {BASE}/capture-l3-six.command
/bin/sleep 15
/bin/cat {BASE}/desktop/run.stdout {BASE}/desktop/run.stderr {BASE}/desktop/exit
''',sudo=True,timeout=45,check=False)
    print(row['stdout'],row['stderr'])
    health('health-after-desktop')
    row=run('desktop-archive',f'set -eu\n/usr/bin/tar -czf {BASE}/l3six-desktop.tar.gz -C {BASE} desktop\n/usr/bin/shasum -a 256 {BASE}/l3six-desktop.tar.gz',timeout=35)
    archive=WORK/'l3six-desktop.tar.gz'
    with contextlib.redirect_stdout(io.StringIO()):remote.download(BASE+'/l3six-desktop.tar.gz',archive,timeout=35)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in row['stdout']
    with tarfile.open(archive) as t:t.extractall(WORK/'captures',filter='data')


def r8():
    assert (WORK/'desktop-reviewed.json').is_file(),'Desktop must be reviewed before R8'
    assert json.loads((WORK/'desktop-reviewed.json').read_text())['status']=='PREVIOUS_DESKTOP_ARTIFACTS_NOT_OBSERVED'
    claim_path=WORK/'r8-once-authorized.json'
    assert not claim_path.exists(),'Claim exists; never retry'
    health('r8-health-immediate-pre')
    preflight=f'''/usr/bin/python3 - <<'PY'
import hashlib,subprocess,os
from pathlib import Path
base=Path({BASE!r})
assert subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()=={SESSION!r}
for name,digest in {HASHES!r}.items():assert hashlib.sha256((base/name).read_bytes()).hexdigest()==digest,name
assert os.access(base/'managed-rt-probe',os.X_OK),'Probe must be executable before claiming the attempt'
assert not (base/'r8-once-claim').exists() and not (base/'r8-capture').exists()
print('EXACT_BINARIES_AND_FRESH_CLAIM_PASS')
PY'''
    run('r8-sealed-preflight',preflight,timeout=25)
    script=f'''set -eu
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = {SESSION}
umask 077
mkdir {BASE}/r8-once-claim
set +e
GA411_TRACE_DYLIB={BASE}/trace-managed-cpu.dylib {BASE}/managed-rt-probe R8 legacy {BASE}/r8-capture > {BASE}/r8.stdout 2> {BASE}/r8.stderr
rc=$?
printf '%s\\n' "$rc" > {BASE}/r8.exit
printf 'R8_EXIT=%s\\n' "$rc"
exit "$rc"
'''
    claim={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'session':SESSION,
           'authorization':'此前用户要求新IMG桌面正常后验证一次R8；本轮用户报告新IMG成功启动且原花屏消失，在场；先完成桌面截图/身份/健康后执行。',
           'maximum_execution_attempts':1,'explicit_command_buffers':1,'automatic_retry':False,
           'binaries':HASHES,'script':script}
    with claim_path.open('x') as f:json.dump(claim,f,ensure_ascii=False,indent=2)
    attempt=run('r8-execute-ONCE','/bin/bash -c '+shlex.quote(script),timeout=90,check=False)
    # No further GPU submission regardless of return/health outcome.
    post=run('r8-health-post','/usr/bin/python3 '+BASE+'/health-l3-six.py',sudo=True,timeout=70,check=False)
    if attempt['returncode']!=0 or post['returncode']!=0:
        (WORK/'STOP-GPU.json').write_text(json.dumps({'attempt_rc':attempt['returncode'],'health_rc':post['returncode'],'no_retry':True})+'\n')
    row=run('r8-archive',f'set -eu\n/usr/bin/tar -czf {BASE}/l3six-r8.tar.gz -C {BASE} r8-capture r8.stdout r8.stderr r8.exit r8-once-claim\n/usr/bin/shasum -a 256 {BASE}/l3six-r8.tar.gz',timeout=30)
    archive=WORK/'l3six-r8.tar.gz'
    with contextlib.redirect_stdout(io.StringIO()):remote.download(BASE+'/l3six-r8.tar.gz',archive,timeout=30)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in row['stdout']
    with tarfile.open(archive) as t:t.extractall(WORK/'captures',filter='data')
    print(json.dumps({'GPU_attempts':1,'execution_rc':attempt['returncode'],'post_health_rc':post['returncode'],
                      'pixel_result':'PENDING_INDEPENDENT_AUDIT'}))


def permission_recovery():
    # New user instruction explicitly authorizes fixing permissions and continuing.
    # Preserve the failed claim, STOP record and every original stdout/stderr.
    original=json.loads((GA/'private/commands/l3six-r8-execute-ONCE.json').read_text())
    assert original['returncode']==126
    assert 'Permission denied' in (WORK/'captures/r8.stderr').read_text()
    assert (WORK/'captures/r8.stdout').stat().st_size==0
    assert not (WORK/'captures/r8-capture').exists()
    claim_path=WORK/'r8-permission-recovery-authorized.json'
    assert not claim_path.exists(),'Recovery already claimed; never retry'
    health('recovery-health-before-permission-fix')
    code=f'''/usr/bin/python3 - <<'PY'
import os,hashlib,subprocess,json
from pathlib import Path
base=Path({BASE!r});probe=base/'managed-rt-probe'
assert subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()=={SESSION!r}
before=hashlib.sha256(probe.read_bytes()).hexdigest()
assert before=={HASHES['managed-rt-probe']!r}
before_mode=oct(probe.stat().st_mode & 0o777)
os.chmod(probe,0o700)
assert hashlib.sha256(probe.read_bytes()).hexdigest()==before
print(json.dumps({{'before_mode':before_mode,'after_mode':oct(probe.stat().st_mode & 0o777),'binary_sha256_unchanged':before}}))
PY'''
    print(run('recovery-fix-executable-permission',code,sudo=True,timeout=25)['stdout'])
    health('recovery-health-immediate-pre')
    preflight=f'''/usr/bin/python3 - <<'PY'
import os,hashlib,subprocess
from pathlib import Path
base=Path({BASE!r})
assert subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()=={SESSION!r}
for name,digest in {HASHES!r}.items():assert hashlib.sha256((base/name).read_bytes()).hexdigest()==digest,name
assert os.access(base/'managed-rt-probe',os.X_OK)
assert (base/'r8.stderr').read_text().endswith('Permission denied\\n')
assert not (base/'r8-recovery-claim').exists() and not (base/'r8-recovery-capture').exists()
print('EXACT_BINARIES_EXECUTABLE_FRESH_RECOVERY_CLAIM_PASS')
PY'''
    run('recovery-sealed-preflight',preflight,timeout=25)
    script=f'''set -eu
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = {SESSION}
umask 077
mkdir {BASE}/r8-recovery-claim
set +e
GA411_TRACE_DYLIB={BASE}/trace-managed-cpu.dylib {BASE}/managed-rt-probe R8 legacy {BASE}/r8-recovery-capture > {BASE}/r8-recovery.stdout 2> {BASE}/r8-recovery.stderr
rc=$?
printf '%s\\n' "$rc" > {BASE}/r8-recovery.exit
printf 'R8_RECOVERY_EXIT=%s\\n' "$rc"
exit "$rc"
'''
    with claim_path.open('x') as f:
        json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'session':SESSION,
                   'authorization':'用户新指示：没权限你提权啊我给你root密码了。仅修复测试程序执行位后继续一次R8。',
                   'prior_launch_result':'exec rejected126, program never started; priorGPUsubmissions=0',
                   'maximum_new_GPU_attempts':1,'automatic_retry':False,'binaries':HASHES,'script':script},f,ensure_ascii=False,indent=2)
    attempt=run('recovery-r8-execute-ONCE','/bin/bash -c '+shlex.quote(script),timeout=90,check=False)
    post=run('recovery-health-post','/usr/bin/python3 '+BASE+'/health-l3-six.py',sudo=True,timeout=70,check=False)
    if attempt['returncode']!=0 or post['returncode']!=0:
        (WORK/'STOP-GPU-RECOVERY.json').write_text(json.dumps({'attempt_rc':attempt['returncode'],'health_rc':post['returncode'],'no_retry':True})+'\n')
    row=run('recovery-r8-archive',f'set -eu\n/usr/bin/tar -czf {BASE}/l3six-r8-recovery.tar.gz -C {BASE} r8-recovery-capture r8-recovery.stdout r8-recovery.stderr r8-recovery.exit r8-recovery-claim\n/usr/bin/shasum -a 256 {BASE}/l3six-r8-recovery.tar.gz',timeout=30)
    archive=WORK/'l3six-r8-recovery.tar.gz'
    with contextlib.redirect_stdout(io.StringIO()):remote.download(BASE+'/l3six-r8-recovery.tar.gz',archive,timeout=30)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in row['stdout']
    with tarfile.open(archive) as t:t.extractall(WORK/'captures',filter='data')
    print(json.dumps({'new_GPU_attempts':1,'execution_rc':attempt['returncode'],'post_health_rc':post['returncode'],
                      'pixel_result':'PENDING_INDEPENDENT_AUDIT'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['stage','capture','r8','permission-recovery'])
    args=p.parse_args();configure()
    {'stage':stage,'capture':capture,'r8':r8,'permission-recovery':permission_recovery}[args.phase]()
