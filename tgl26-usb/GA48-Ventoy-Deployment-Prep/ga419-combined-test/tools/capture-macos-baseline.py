#!/usr/bin/env python3
"""Read-only, boot-pinned peripheral baseline; evidence stays on the development host."""
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

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT.parent
sys.path.insert(0, str(PREP / 'ga410/tools'))
import normal_ssh
import remote

normal_ssh.configure()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--session', required=True)
args = parser.parse_args()
BOOT = str(uuid.UUID(args.session)).upper()
label = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
work = ROOT / 'private/macos-live' / ('baseline-' + label)
work.mkdir(parents=True, mode=0o700)
code = r'''
import base64,datetime,json,subprocess
expected='__BOOT_SESSION_UUID__'
def boot():return subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
assert boot()==expected
commands=[
 ('os',['/usr/bin/sw_vers']),
 ('boot',['/usr/sbin/sysctl','kern.bootsessionuuid','kern.boottime','kern.bootargs']),
 ('chosen',['/usr/sbin/ioreg','-p','IODeviceTree','-n','chosen','-r','-l']),
 ('kexts',['/usr/bin/kmutil','showloaded']),
 ('dmesg',['/sbin/dmesg']),
 ('ioreg-service',['/usr/sbin/ioreg','-a','-l','-p','IOService']),
 ('ioreg-usb',['/usr/sbin/ioreg','-a','-l','-p','IOUSB']),
 ('hid',['/usr/bin/hidutil','list']),
 ('battery',['/usr/sbin/ioreg','-r','-c','AppleSmartBattery','-l']),
 ('power',['/usr/bin/pmset','-g','batt']),
 ('displays',['/usr/sbin/ioreg','-r','-c','AppleBacklightDisplay','-l']),
 ('bluetooth',['/usr/sbin/system_profiler','SPBluetoothDataType','-json']),
 ('camera',['/usr/sbin/system_profiler','SPCameraDataType','-json']),
 ('audio',['/usr/sbin/system_profiler','SPAudioDataType','-json']),
 ('network',['/sbin/ifconfig']),
 ('processes',['/bin/ps','-axo','pid,etime,command']),
 ('diagnostics',['/bin/ls','-lt','/Library/Logs/DiagnosticReports'])]
result={'boot':expected,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':[]}
for name,argv in commands:
 try:
  p=subprocess.run(argv,capture_output=True,timeout=40)
  result['commands'].append({'name':name,'argv':argv,'returncode':p.returncode,
   'stdout_b64':base64.b64encode(p.stdout).decode(),'stderr':p.stderr.decode(errors='replace')})
 except subprocess.TimeoutExpired as e:
  result['commands'].append({'name':name,'argv':argv,'returncode':None,'timeout':True,
   'stdout_b64':base64.b64encode(e.stdout or b'').decode(),'stderr':(e.stderr or b'').decode(errors='replace')})
assert boot()==expected
result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
print(json.dumps(result))
'''
code = code.replace("expected='__BOOT_SESSION_UUID__'", 'expected=' + repr(BOOT))
password = os.environ['GA410_SUDO_PASSWORD'] + '\n'
command = 'sudo -S -p "" /usr/bin/python3 -c ' + shlex.quote(code)
p = subprocess.run(remote.SSH + [command], input=password.encode(), capture_output=True, timeout=420)
receipt = {'boot': BOOT, 'utc': label, 'returncode': p.returncode,
           'remote_script_sha256': hashlib.sha256(code.encode()).hexdigest(),
           'stdout_sha256': hashlib.sha256(p.stdout).hexdigest(), 'stderr': p.stderr.decode(errors='replace')}
(work / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
(work / 'response.json').write_bytes(p.stdout)
assert p.returncode == 0, receipt
data = json.loads(p.stdout)
import base64
for row in data['commands']:
    (work / (row['name'] + '.stdout')).write_bytes(base64.b64decode(row['stdout_b64']))
print(json.dumps({'baseline': str(work), 'boot': data['boot'],
    'commands': [{'name': c['name'], 'returncode': c['returncode']} for c in data['commands']]}, indent=2))
