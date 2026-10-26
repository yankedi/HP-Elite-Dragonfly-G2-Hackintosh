#!/usr/bin/env python3
"""Backfill all available unified-log levels for this boot, without a predicate."""
import datetime
import os
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT.parent
sys.path.insert(0, str(PREP / 'ga410/tools'))
import normal_ssh
import remote

normal_ssh.configure()
work = ROOT / 'private/macos-live'
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
stem = work / ('boot-backfill-' + stamp)
code = r'''
import datetime,json,re,subprocess,sys
boot=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()
assert boot
raw=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.boottime'],text=True)
epoch=int(re.search(r'sec = (\d+)',raw).group(1))
start=datetime.datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')
end=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
argv=['/usr/bin/log','show','--start',start,'--end',end,'--style','ndjson','--info','--debug','--source','--backtrace','--signpost']
print('BACKFILL_SPEC '+json.dumps({'boot':boot,'argv':argv,'predicate':None,'all_available_levels':True,'note':'Historical store may not retain every debug event; this is not proof of lossless pre-stream capture.'}),file=sys.stderr,flush=True)
p=subprocess.run(argv)
assert subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True).strip()==boot
sys.exit(p.returncode)
'''
command = 'sudo -S -p "" /usr/bin/python3 -c ' + shlex.quote(code)
password = os.environ['GA410_SUDO_PASSWORD'] + '\n'
sha = hashlib.sha256()
count = 0
target = Path(str(stem) + '.ndjson.gz')
error_path = Path(str(stem) + '.stderr')
with error_path.open('xb') as err, target.open('xb') as raw:
    p = subprocess.Popen(remote.SSH + [command], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
    p.stdin.write(password.encode())
    p.stdin.close()
    with gzip.GzipFile(filename='', fileobj=raw, mode='wb', compresslevel=1) as out:
        while True:
            chunk = p.stdout.read(262144)
            if not chunk:
                break
            count += len(chunk)
            sha.update(chunk)
            out.write(chunk)
    p.stdout.close()
    rc = p.wait()
with target.open('rb') as f:
    packed_hash = hashlib.file_digest(f, 'sha256').hexdigest()
verify = hashlib.sha256()
verified = 0
with gzip.open(target, 'rb') as f:
    for block in iter(lambda: f.read(1048576), b''):
        verified += len(block)
        verify.update(block)
assert count == verified and sha.hexdigest() == verify.hexdigest()
receipt = {'status': 'COMPLETE' if rc == 0 else 'FAILED_PRESERVED', 'returncode': rc,
    'boot': boot, 'predicate': None,
    'process_filter': None, 'sampling_or_discard': False, 'uncompressed_bytes': count,
    'uncompressed_sha256': sha.hexdigest(), 'compressed_sha256': packed_hash,
    'compressed_bytes': target.stat().st_size, 'gzip_roundtrip_verified': True,
    'path': str(target), 'stderr': error_path.read_text(),
    'limitation': 'All available persisted events; unavailable historical debug events cannot be recovered.'}
Path(str(stem) + '.result.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
raise SystemExit(rc)
