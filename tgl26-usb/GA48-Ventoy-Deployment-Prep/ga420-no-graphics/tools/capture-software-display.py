#!/usr/bin/env python3
"""Boot-pinned complete rendering baseline, transferred before any local filtering."""
import argparse
import base64
import datetime
import os
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

WORK = Path(__file__).resolve().parents[1]
PREP = WORK.parent
sys.path.insert(0, str(PREP / 'ga410/tools'))
import normal_ssh
import remote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--boot', required=True)
args = parser.parse_args()
boot = str(uuid.UUID(args.boot)).upper()
normal_ssh.configure()
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out = WORK / 'private/macos-live' / ('software-baseline-' + stamp)
out.mkdir(mode=0o700)
code = 'EXPECTED = ' + repr(boot) + '\n' + r'''
import base64,datetime,json,subprocess
def boot():return subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
assert boot()==EXPECTED
result={'boot':EXPECTED,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':[]}
commands=[
 ('boot',['/usr/sbin/sysctl','kern.bootsessionuuid','kern.boottime','kern.bootargs']),
 ('kexts',['/usr/bin/kmutil','showloaded']),
 ('ioreg-service',['/usr/sbin/ioreg','-a','-l','-p','IOService']),
 ('graphics',['/usr/sbin/system_profiler','SPDisplaysDataType','-json']),
 ('dmesg',['/sbin/dmesg']),
 ('processes',['/bin/ps','-axo','pid,ppid,%cpu,rss,etime,command']),
 ('chosen',['/usr/sbin/ioreg','-a','-l','-p','IODeviceTree']),
 ('vm',['/usr/bin/vm_stat']),
 ('os',['/usr/bin/sw_vers']),
 ('network',['/sbin/ifconfig']),
 ('power',['/usr/bin/pmset','-g','batt']),
 ('diagnostics',['/bin/ls','-lt','/Library/Logs/DiagnosticReports'])]
for name,argv in commands:
 try:
  p=subprocess.run(argv,capture_output=True,timeout=40)
  row={'name':name,'argv':argv,'returncode':p.returncode,'stdout_base64':base64.b64encode(p.stdout).decode(),'stderr_base64':base64.b64encode(p.stderr).decode()}
 except (OSError,subprocess.TimeoutExpired) as e:
  row={'name':name,'argv':argv,'returncode':None,'error':str(e),'stdout_base64':base64.b64encode(getattr(e,'stdout',None) or b'').decode(),'stderr_base64':base64.b64encode(getattr(e,'stderr',None) or b'').decode()}
 result['commands'].append(row)
assert boot()==EXPECTED
result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
print(json.dumps(result))
'''
(out / 'remote-script.py').write_text(code)
password = os.environ['GA410_SUDO_PASSWORD'] + '\n'
p = subprocess.run(remote.SSH + ['sudo -S -p "" /usr/bin/python3 -c ' + shlex.quote(code)],
                   input=password.encode(), capture_output=True, timeout=540)
(out / 'response.json').write_bytes(p.stdout)
(out / 'receipt.json').write_text(json.dumps({'boot': boot, 'returncode': p.returncode,
    'stdout_sha256': hashlib.sha256(p.stdout).hexdigest(), 'stderr': p.stderr.decode(errors='replace'),
    'remote_script_sha256': hashlib.sha256(code.encode()).hexdigest()}, indent=2) + '\n')
assert p.returncode == 0, p.stderr.decode(errors='replace')
data = json.loads(p.stdout)
for row in data['commands']:
    (out / (row['name'] + '.stdout')).write_bytes(base64.b64decode(row['stdout_base64'], validate=True))
    (out / (row['name'] + '.stderr')).write_bytes(base64.b64decode(row['stderr_base64'], validate=True))
print(json.dumps({'baseline': str(out), 'boot': boot,
    'commands': [{'name': r['name'], 'returncode': r['returncode']} for r in data['commands']]}, indent=2))
