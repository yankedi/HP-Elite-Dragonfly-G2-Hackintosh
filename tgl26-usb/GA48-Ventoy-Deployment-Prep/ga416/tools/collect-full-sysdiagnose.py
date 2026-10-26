#!/usr/bin/env python3
"""Run one complete native sysdiagnose and copy every resulting archive off-target."""
import contextlib
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote


def main():
    normal_ssh.configure()
    remote.ROOT = ROOT / 'ga416'
    if not os.environ.get('GA410_SUDO_PASSWORD'):
        raise SystemExit('Set GA410_SUDO_PASSWORD in the caller environment')
    work = ROOT / 'ga416/private/crash-series'
    label = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name = 'full-sysdiagnose-' + label
    target = '/Users/Shared/' + name
    expected = os.environ.get('GA416_EXPECTED_BOOT_SESSION')
    if not expected:
        raise SystemExit('Set GA416_EXPECTED_BOOT_SESSION for the authorized capture')
    code = f'''
import subprocess,json,time,hashlib
from pathlib import Path
boot=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
assert boot=={expected!r},'Boot changed'
p=Path({target!r});p.mkdir(mode=0o700)
out={{'boot':boot,'target':str(p),'started_epoch':time.time(),'command':['/usr/bin/sysdiagnose','-u','-b','-f',str(p)],'reduced_collection_flags':False}}
r=subprocess.run(out['command'],capture_output=True,text=True)
out.update({{'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'finished_epoch':time.time()}})
out['files']=[]
for f in p.iterdir():
 if not f.is_file():continue
 h=hashlib.sha256()
 with f.open('rb') as fd:
  for block in iter(lambda:fd.read(1048576),b''):h.update(block)
 out['files'].append({{'path':str(f),'bytes':f.stat().st_size,'sha256':h.hexdigest()}})
print(json.dumps(out))
'''
    command = '/usr/bin/python3 -c ' + shlex.quote(code)
    print('Starting complete sysdiagnose for ' + expected, flush=True)
    with contextlib.redirect_stdout(io.StringIO()):
        receipt = remote.run(name, command, sudo=True, timeout=None, check=False)
    if receipt['returncode'] != 0:
        print('SSH/sysdiagnose wrapper failed; original receipt retained: ' + name)
        raise SystemExit(1)
    result = json.loads(receipt['stdout'])
    result['downloads'] = []
    for row in result['files']:
        local = work / (name + '-' + Path(row['path']).name)
        with contextlib.redirect_stdout(io.StringIO()):
            remote.download(row['path'], local, sudo=True, timeout=None)
        h = hashlib.sha256()
        with local.open('rb') as f:
            for block in iter(lambda: f.read(1048576), b''):
                h.update(block)
        assert local.stat().st_size == row['bytes']
        assert h.hexdigest() == row['sha256']
        result['downloads'].append({'path': str(local.relative_to(ROOT)), 'sha256': h.hexdigest(),
                                    'bytes': local.stat().st_size, 'verified': True})
    (work / (name + '.result.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
