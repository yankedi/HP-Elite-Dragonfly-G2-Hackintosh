#!/usr/bin/env python3
"""Copy a fixed allowlist of ordinary readable files over SSH, never remote writes."""
import hashlib
import json
import pathlib
import shlex
import subprocess
import sys
import time
from collect_readonly import ROOT, SSH

FILES = [
    '/System/Library/KernelCollections/BootKernelExtensions.kc',
    '/System/Library/KernelCollections/SystemKernelExtensions.kc',
    '/Library/KernelCollections/AuxiliaryKernelExtensions.kc',
    '/System/Library/Extensions/AppleIntelICLGraphics.kext/Contents/Info.plist',
    '/System/Library/Extensions/AppleIntelICLLPGraphicsFramebuffer.kext/Contents/Info.plist',
    '/System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/Info.plist',
    '/System/Library/CoreServices/SystemVersion.plist',
]


def main():
    out = ROOT / 'inputs' / 'macos-readonly'
    out.mkdir(parents=True, exist_ok=True)
    receipts = []
    resume = '--resume' in sys.argv
    receipt = ROOT / 'logs' / ('fetch-resume-receipt.json' if resume else 'fetch-receipt.json')
    if receipt.exists():
        raise SystemExit('refuse overwrite receipt')
    for remote in FILES:
        local = out / remote.lstrip('/')
        if local.exists():
            old = json.loads((ROOT/'logs'/'fetch-receipt.json').read_text()) if resume else []
            trusted = next((r for r in old if r['remote']==remote and r.get('verified')), None)
            digest = hashlib.file_digest(local.open('rb'),'sha256').hexdigest()
            if trusted and trusted['sha256']==digest:
                receipts.append(dict(trusted, reused_verified_input=True))
                continue
            if not resume:
                raise SystemExit('refuse overwrite input')
            partial = local.with_suffix(local.suffix+'.partial-first-timeout')
            if partial.exists():
                raise SystemExit('refuse overwrite partial')
            local.rename(partial)
            receipts.append({'remote':remote,'partial_local':str(partial.relative_to(ROOT)),
                             'partial_bytes':partial.stat().st_size,'partial_sha256':digest,
                             'verified':False,'reason':'first outer shell timeout; preserved, not usable binary'})
        local.parent.mkdir(parents=True, exist_ok=True)
        started = time.time()
        before = subprocess.run(SSH + ['shasum -a 256 ' + shlex.quote(remote)], capture_output=True, timeout=90)
        record = {'remote': remote, 'local': str(local.relative_to(ROOT)), 'before_exit': before.returncode,
                  'before_stdout': before.stdout.decode(), 'before_stderr': before.stderr.decode(),
                  'started_unix': started}
        if before.returncode == 0:
            with local.open('xb') as f:
                p = subprocess.run(SSH[:1] + ['-C'] + SSH[1:] + ['cat ' + shlex.quote(remote)], stdout=f, stderr=subprocess.PIPE, timeout=600)
            after = subprocess.run(SSH + ['shasum -a 256 ' + shlex.quote(remote)], capture_output=True, timeout=90)
            digest = hashlib.file_digest(local.open('rb'), 'sha256').hexdigest()
            record.update(copy_exit=p.returncode, copy_stderr=p.stderr.decode(), after_exit=after.returncode,
                          after_stdout=after.stdout.decode(), after_stderr=after.stderr.decode(),
                          sha256=digest, bytes=local.stat().st_size,
                          verified=p.returncode == 0 and after.returncode == 0 and
                          before.stdout.split()[0].decode() == digest == after.stdout.split()[0].decode())
        record['elapsed'] = time.time()-started
        receipts.append(record)
        receipt.write_text(json.dumps(receipts, indent=2)+'\n')
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
