#!/usr/bin/env python3
"""Private byte seal. verify is strictly read-only; create never runs experiments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'manifest.json','manifest.sha256','logs/manifest-verification.txt'}
HISTORIES=['GA32-ISA-Lab','GA33-research','GA34-Offline-Lab','GA35-Driver-Reversing','GA36-Fault-Safety']

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def local_files():
    files=[]
    for p in sorted(ROOT.rglob('*')):
        # Preserve malicious-path test fixtures as links, never follow them.
        # Path.rglob does not recurse through directory symlinks by default.
        if (p.is_symlink() or p.is_file()) and str(p.relative_to(ROOT)) not in EXCLUDED:files.append(p)
    return files

def local_entry(path):
    row={'path':str(path.relative_to(ROOT))}
    if path.is_symlink():
        target=os.readlink(path);encoded=os.fsencode(target)
        row.update(kind='symlink',target=target,bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest())
    else:
        row.update(kind='file',bytes=path.stat().st_size,sha256=digest(path))
    return row

def inputs():
    paths=set()
    index=json.loads((ROOT/'track-e/evidence/INPUTS.json').read_text())
    for row in index['files']:
        p=Path(row['path']);assert digest(p)==row['sha256'];paths.add(p)
    frozen=json.loads((ROOT/'reference/ga36-source-freeze.json').read_text())
    for row in frozen:
        p=Path(row['source']);assert digest(p)==row['sha256'];paths.add(p)
    for name in HISTORIES:
        p=ROOT.parent/name/'manifest.json';paths.add(p)
        q=p.with_suffix('.sha256')
        if q.exists():paths.add(q)
    return sorted(paths)

def historical_verify():
    counts={}
    for name in HISTORIES:
        directory=ROOT.parent/name;manifest=directory/'manifest.json';data=json.loads(manifest.read_text())
        selfhash=directory/'manifest.sha256'
        if selfhash.exists():assert selfhash.read_text().split()[0]==digest(manifest),name+' selfhash'
        for row in data['files']:
            p=Path(row['path']);p=p if p.is_absolute() else directory/p
            assert p.is_file() and digest(p)==row['sha256'],str(p)
            expected=row.get('size',row.get('bytes'))
            if expected is not None:assert p.stat().st_size==expected,str(p)
        counts[name]=len(data['files'])
    # GA36 also seals selected external history inputs. Its schema uses an
    # absolute path (current schema) or a project-root-relative path, never GA37.
    olddir=ROOT.parent/'GA36-Fault-Safety'
    old=json.loads((olddir/'manifest.json').read_text())
    external=old.get('historical_sources',[])
    for row in external:
        p=Path(row['path']);p=p if p.is_absolute() else ROOT.parent/p
        assert digest(p)==row['sha256'],str(p)
    return counts,len(external)

def create():
    assert not (ROOT/'manifest.json').exists(),'already sealed; do not overwrite a delivery seal'
    historical_verify()
    rows=[local_entry(p) for p in local_files()]
    external=[{'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)} for p in inputs()]
    data={'schema':'ga37-private-seal/v1','scope':'Private local engineering evidence, includes historical derived data; never publish Apple proprietary inputs or derived analysis. No IMG/hardware delivery.','exclusions':sorted(EXCLUDED),'files':rows,'external_sources':external}
    manifest=ROOT/'manifest.json';manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'manifest.sha256').write_text(digest(manifest)+'  manifest.json\n')
    print('SEALED',len(rows),'local files;',len(external),'external sources; manifest SHA256',digest(manifest))

def verify():
    manifest=ROOT/'manifest.json';data=json.loads(manifest.read_text());assert (ROOT/'manifest.sha256').read_text().split()[0]==digest(manifest)
    assert sorted(data['exclusions'])==sorted(EXCLUDED)
    assert {row['path'] for row in data['files']}=={str(p.relative_to(ROOT)) for p in local_files()},'local files added or removed'
    for row in data['files']:
        p=ROOT/row['path'];assert local_entry(p)==row,str(p)
    for row in data['external_sources']:
        p=Path(row['path'])
        assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],str(p)
    counts,external=historical_verify()
    print('VERIFY_PASS',len(data['files']),'local;',len(data['external_sources']),'external; historical=',counts,'GA36 external=',external)
    print('manifest SHA256',digest(manifest))
    print('Read-only verification; source/result IMG none, backend none, hardware approval NO.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['create','verify']);args=parser.parse_args()
    (create if args.action=='create' else verify)()
