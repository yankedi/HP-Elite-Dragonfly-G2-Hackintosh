#!/usr/bin/env python3
"""Read existing GPIO/USB descriptor/EDID files, without opening camera streams."""
import datetime
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'private' / 'linux-resources.json'
if out.exists():
    raise FileExistsError(out)
remote = r'''
import glob, json, os, subprocess
boot='/proc/sys/kernel/random/boot_id'
def read(path,binary=False):
    try:
        with open(path,'rb') as f: b=f.read(200000)
        return b.hex() if binary else b.decode(errors='replace')
    except OSError as e: return {'error':str(e)}
assert os.uname().sysname=='Linux'
boot_before=read(boot).strip()
r={'files':{},'commands':[]}
for base in sorted(glob.glob('/sys/bus/usb/devices/*')):
    vid=read(base+'/idVendor'); pid=read(base+'/idProduct')
    if (vid,pid) not in [('0408\n','5349\n'),('8087\n','0026\n')]: continue
    for name in ['idVendor','idProduct','bcdDevice','product','speed','bNumInterfaces','power/control','power/runtime_status','descriptors']:
        r['files'][base+'/'+name]=read(base+'/'+name,name=='descriptors')
for f in sorted(glob.glob('/sys/class/drm/card*-eDP-*/edid')):
    r['files'][f]=read(f,True)
for path in ['/sys/kernel/debug/gpio','/sys/kernel/debug/pinctrl/INT34C5:00/gpio-ranges',
             '/sys/kernel/debug/pinctrl/INT34C5:00/pinmux-pins',
             '/sys/kernel/debug/pinctrl/INT34C5:00/pins']:
    p=subprocess.run(['sudo','-n','cat',path],capture_output=True,text=True,timeout=12)
    r['commands'].append({'path':path,'rc':p.returncode,'stdout':p.stdout[:200000],'stderr':p.stderr[:3000]})
boot_after=read(boot).strip()
assert boot_before and boot_after==boot_before
r['boot_stable']=True
print(json.dumps(r))
'''
target = os.environ.get('GA418_SSH_TARGET', '')
if not re.fullmatch(r'(?:[A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9][A-Za-z0-9._:-]*', target):
    raise SystemExit('Set GA418_SSH_TARGET to an authorized user@host or host')
remote_python = os.environ.get('GA418_REMOTE_PYTHON', 'python3')
if not re.fullmatch(r'[A-Za-z0-9_./+-]+', remote_python):
    raise SystemExit('GA418_REMOTE_PYTHON must be a simple executable path')
ssh = ['ssh','-o','ConnectTimeout=8','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
       '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',target,
       shlex.quote(remote_python) + ' -']
p=subprocess.run(ssh,input=remote,capture_output=True,text=True,timeout=100)
row={'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'returncode':p.returncode,'stderr':p.stderr,
     'script_sha256':hashlib.sha256(remote.encode()).hexdigest(),
     'snapshot':json.loads(p.stdout) if p.returncode==0 else p.stdout}
out.write_text(json.dumps(row,indent=2)+'\n')
print('Saved',out,'SSH rc',p.returncode)
if p.returncode==0:
    for c in row['snapshot']['commands']:
        print(c['path'],'rc',c['rc'],c['stderr'])
        if c['path'].endswith('gpio') or c['path'].endswith('gpio-ranges'): print(c['stdout'])
raise SystemExit(p.returncode)
