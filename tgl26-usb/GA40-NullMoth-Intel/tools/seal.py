#!/usr/bin/env python3
"""Private GA40 byte seal; verify is strictly read-only and never replays tests."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'manifest.json','manifest.sha256','logs/seal-verification.json','logs/seal-verification.txt'}


def sha_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def entries():
    result=[]
    for parent,dirs,files in os.walk(ROOT,followlinks=False):
        parent=Path(parent)
        # Include directory symlinks themselves, never traverse their targets.
        links=[d for d in dirs if (parent/d).is_symlink()]
        dirs[:]=[d for d in dirs if d not in links]
        for name in files+links:
            path=parent/name; relative=path.relative_to(ROOT).as_posix()
            if relative in EXCLUDED: continue
            info=path.lstat()
            if stat.S_ISLNK(info.st_mode):
                target=os.readlink(path); data=os.fsencode(target)
                row={'path':relative,'kind':'symlink','target':target,
                     'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            elif stat.S_ISREG(info.st_mode):
                row={'path':relative,'kind':'file','bytes':info.st_size,'sha256':sha_file(path)}
            else: raise ValueError('Unsupported special artifact: '+relative)
            row['mode']=stat.S_IMODE(info.st_mode)
            result.append(row)
    return sorted(result,key=lambda row:row['path'])


def external_verify():
    receipt=ROOT/'reference/external-inputs.json'
    if not receipt.exists(): raise ValueError('Missing external dependency receipt')
    rows=json.loads(receipt.read_text())['files']
    for row in rows:
        path=Path(row['path'])
        if not path.is_absolute() or ROOT in path.parents:
            raise ValueError('Invalid external path')
        if path.stat().st_size!=row['bytes'] or sha_file(path)!=row['sha256']:
            raise ValueError('External input mismatch: '+str(path))
    return len(rows)


def main():
    if len(sys.argv)!=2 or sys.argv[1] not in {'create','verify'}:
        raise SystemExit('Usage: python3 -B tools/seal.py create|verify')
    manifest=ROOT/'manifest.json'; checksum=ROOT/'manifest.sha256'
    if sys.argv[1]=='create':
        if manifest.exists() or checksum.exists(): raise ValueError('Existing seal must never be overwritten')
        count=external_verify()
        data={'schema':'ga40-private-seal-v1','scope':'Offline artifacts only; no GPU/macOS acceleration claim',
              'excluded_exact_paths':sorted(EXCLUDED),'external_files':count,'entries':entries()}
        with manifest.open('x') as out: json.dump(data,out,indent=2); out.write('\n')
        with checksum.open('x') as out: out.write(sha_file(manifest)+'  manifest.json\n')
    recorded=json.loads(manifest.read_text())
    assert recorded['schema']=='ga40-private-seal-v1'
    assert recorded['excluded_exact_paths']==sorted(EXCLUDED)
    assert checksum.read_text()==sha_file(manifest)+'  manifest.json\n'
    assert recorded['entries']==entries(),'Added/deleted/changed artifacts after sealing'
    count=external_verify(); assert count==recorded['external_files']
    print(json.dumps({'status':'PASS','mode':sys.argv[1],'local_entries':len(recorded['entries']),
                      'external_files':count,'manifest_sha256':sha_file(manifest),
                      'hardware_approval':'NO'}))


if __name__=='__main__': main()
