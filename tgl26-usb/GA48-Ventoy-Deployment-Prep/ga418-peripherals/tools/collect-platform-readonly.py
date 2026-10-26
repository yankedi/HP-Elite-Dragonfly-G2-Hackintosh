#!/usr/bin/env python3
"""Bounded same-boot sysfs/proc platform snapshot, no device streaming or writes."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
name = sys.argv[1] if len(sys.argv) == 2 else 'linux-platform.json'
if len(sys.argv) > 2 or Path(name).name != name or not name.endswith('.json'):
    raise ValueError('Use a new local JSON basename')
OUT = ROOT / 'private' / name
if OUT.exists():
    raise FileExistsError(OUT)
REMOTE = r'''
import glob,json,os,pathlib,subprocess
def read(p,limit=90000):
    try:
        with open(p,'r',errors='replace') as f:return f.read(limit)
    except OSError as e:return {'error':str(e)}
boot=read('/proc/sys/kernel/random/boot_id').strip()
if os.uname().sysname!='Linux' or boot!='REDACTED-MACHINE-ID':
    raise RuntimeError('Not the expected unattended Linux boot; no further collection')
r={'boot_before':boot,'files':{},'commands':[]}
for argv in [['systemctl','show','ga417-awake.service','-p','ActiveState','-p','SubState','-p','MainPID','-p','Transient'],
             ['systemd-inhibit','--list','--no-pager']]:
    p=subprocess.run(argv,capture_output=True,text=True,timeout=12)
    r['commands'].append({'argv':argv,'rc':p.returncode,'stdout':p.stdout[:20000],'stderr':p.stderr[:2000]})
for pattern in ['/proc/asound/cards','/proc/asound/pcm','/proc/asound/card*/codec*',
                '/sys/class/drm/card*-eDP-*/privacy_screen*',
                '/sys/class/thunderbolt/domain*/security',
                '/sys/class/thunderbolt/domain*/iommu_dma_protection',
                '/sys/class/thunderbolt/*/generation',
                '/sys/class/thunderbolt/*/usb4_version',
                '/sys/class/thunderbolt/*/nvm_version',
                '/sys/class/thunderbolt/*/authorized',
                '/sys/class/thunderbolt/*/rx_speed','/sys/class/thunderbolt/*/tx_speed',
                '/sys/bus/thunderbolt/devices/domain*/security',
                '/sys/bus/thunderbolt/devices/domain*/iommu_dma_protection',
                '/sys/bus/thunderbolt/devices/*/generation',
                '/sys/bus/thunderbolt/devices/*/usb4_version',
                '/sys/bus/thunderbolt/devices/*/nvm_version',
                '/sys/bus/thunderbolt/devices/*/authorized',
                '/sys/bus/thunderbolt/devices/*/rx_speed',
                '/sys/bus/thunderbolt/devices/*/tx_speed',
                '/sys/bus/iio/devices/iio:device*/name',
                '/sys/class/nvme/nvme*/model',
                '/sys/class/nvme/nvme*/firmware_rev',
                '/sys/bus/usb/devices/usb*/maxchild',
                '/sys/bus/usb/devices/usb*/speed',
                '/sys/bus/usb/devices/usb*/bcdUSB',
                '/sys/bus/pci/devices/0000:00:07.*/device',
                '/sys/bus/pci/devices/0000:00:0d.*/device',
                '/sys/bus/pci/devices/0000:00:14.*/device',
                '/sys/bus/pci/devices/0000:00:1f.3/device',
                '/sys/bus/pci/devices/0000:00:*/power/runtime_status']:
    for p in sorted(glob.glob(pattern))[:40]:
        if pathlib.Path(p).is_file():r['files'][p]=read(p)
for pattern in ['/sys/class/sound/card*/device','/sys/bus/iio/devices/iio:device*',
                '/sys/class/nvme/nvme*/device','/sys/bus/usb/devices/usb*',
                '/sys/bus/pci/devices/0000:00:0d.*/driver',
                '/sys/bus/pci/devices/0000:00:14.*/driver']:
    for p in sorted(glob.glob(pattern))[:40]:r['files'][p]={'realpath':os.path.realpath(p)}
r['boot_after']=read('/proc/sys/kernel/random/boot_id').strip()
if r['boot_after']!=boot:raise RuntimeError('Boot changed during collection')
print(json.dumps(r))
'''
prior = json.loads((ROOT / 'private/linux-readonly.json').read_text())
argv = prior['argv']
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
p = subprocess.run(argv, input=REMOTE, text=True, capture_output=True, timeout=90)
row = {'started_utc': started, 'finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'remote_script_sha256': hashlib.sha256(REMOTE.encode()).hexdigest(), 'argv': argv,
       'returncode': p.returncode, 'stderr': p.stderr}
if p.returncode == 0:
    row['snapshot'] = json.loads(p.stdout)
else:
    row['stdout'] = p.stdout
OUT.write_text(json.dumps(row, indent=2) + '\n')
print(str(OUT), 'SSH exit', p.returncode)
raise SystemExit(p.returncode)
