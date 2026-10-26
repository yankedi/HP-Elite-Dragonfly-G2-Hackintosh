#!/usr/bin/env python3
"""One bounded, read-only SSH snapshot; writes receipts only on developer host."""
import datetime
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / 'private' / 'linux-readonly.json'
if out.exists():
    raise FileExistsError(out)
remote = r'''
import glob, json, os, pathlib, subprocess
def read(path, limit=120000):
    try:
        with open(path, 'r', errors='replace') as f: return f.read(limit)
    except OSError as e: return {'error': str(e)}
def cmd(args):
    try:
        p=subprocess.run(args, capture_output=True, text=True, timeout=15)
        return {'argv':args,'rc':p.returncode,'stdout':p.stdout[:120000],'stderr':p.stderr[:4000]}
    except Exception as e: return {'argv':args,'error':str(e)}
r={'os':os.uname().sysname,
   'uptime':read('/proc/uptime'), 'commands':[], 'sysfs':{}}
if r['os']!='Linux': raise RuntimeError('Expected Linux')
for a in [['systemctl','show','ga417-awake.service','-p','ActiveState','-p','SubState','-p','MainPID','-p','Transient'],
          ['systemd-inhibit','--list','--no-pager'],['lspci','-nnk'],['lsusb'],['lsusb','-t']]:
    r['commands'].append(cmd(a))
for path in ['/proc/interrupts','/sys/bus/acpi/devices/INT34C5:00/status','/sys/bus/acpi/devices/INTC1055:00/status']:
    r['sysfs'][path]=read(path)
for pattern, names in [('/sys/bus/i2c/devices/i2c-SYNA*',['name','modalias','irq']),
                       ('/sys/bus/i2c/devices/i2c-WACF*',['name','modalias','irq']),
                       ('/sys/bus/acpi/devices/SYNA*',['hid','path','status','modalias']),
                       ('/sys/bus/acpi/devices/INT34*',['hid','path','status','modalias']),
                       ('/sys/bus/acpi/devices/INTC105*',['hid','path','status','modalias']),
                       ('/sys/class/thunderbolt/domain*',['security','iommu_dma_protection','boot_acl']),
                       ('/sys/class/thunderbolt/[0-9]*',['device_name','vendor_name','authorized','generation']),
                       ('/sys/class/backlight/*',['type','max_brightness','brightness','actual_brightness']),
                       ('/sys/class/video4linux/video*',['name','index'])]:
    for base in sorted(glob.glob(pattern)):
        r['sysfs'][base]={'realpath':os.path.realpath(base), **{n:read(base+'/'+n) for n in names}}
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
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
p = subprocess.run(ssh, input=remote, capture_output=True, text=True, timeout=150)
out.parent.mkdir(parents=True, exist_ok=True)
row = {'started_utc':start,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'argv':ssh,'remote_script_sha256':hashlib.sha256(remote.encode()).hexdigest(),
       'returncode':p.returncode,'stderr':p.stderr}
if p.returncode == 0:
    row['snapshot'] = json.loads(p.stdout)
else:
    row['stdout'] = p.stdout
out.write_text(json.dumps(row, indent=2) + '\n')
print(json.dumps(row, indent=2))
raise SystemExit(p.returncode)
