#!/usr/bin/env python3
"""Private local delivery manifest, original-input and pinned-source verification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DEP=ROOT.parent/'GA32-ISA-Lab/tools/mesa-eu/source'
PIN='863338275d915e867319c3690ffd3272b06303c3'
EXCLUDE={'manifest.json','manifest.sha256','logs/manifest-verification.txt'}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def selected():
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or str(rel) in EXCLUDE:continue
        if any(x in {'__pycache__','.git','.pytest_cache'} for x in rel.parts):continue
        # Keep native executable/log result hashes, omit intermediates.
        if p.suffix in {'.o','.obj','.pyc'}:continue
        yield p

def originals():
    receipt=json.loads((ROOT/'inputs/provenance.json').read_text())
    for item in receipt['files']:
        p=Path(item['original']);q=ROOT/item['copy']
        if sha(p)!=item['sha256'] or sha(q)!=item['sha256']:
            raise ValueError('Original/copy differs: '+str(p))
    head=subprocess.check_output(['git','-C',str(DEP),'rev-parse','HEAD'],text=True).strip()
    if head!=PIN or subprocess.check_output(['git','-C',str(DEP),'status','--porcelain'],text=True):
        raise ValueError('Mesa dependency changed')
    return receipt

def create():
    originals()
    data={'schema':1,'scope':'private GA3.4 local CPU-only engineering; no hardware execution',
          'dependency':{'path':str(DEP),'commit':PIN,'clean':True},
          'exclusions':sorted(EXCLUDE)+['.git','__pycache__','.pytest_cache','*.o','*.obj','*.pyc'],
          'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in selected()]}
    (ROOT/'manifest.json').write_text(json.dumps(data,indent=2)+'\n')
    (ROOT/'manifest.sha256').write_text(sha(ROOT/'manifest.json')+'  manifest.json\n')

def verify():
    originals();manifest=json.loads((ROOT/'manifest.json').read_text())
    if (ROOT/'manifest.sha256').read_text().split()[0]!=sha(ROOT/'manifest.json'):raise ValueError('Manifest checksum mismatch')
    expected={f['path'] for f in manifest['files']};actual={str(p.relative_to(ROOT)) for p in selected()}
    if actual!=expected:raise ValueError({'missing':sorted(expected-actual),'unlisted':sorted(actual-expected)})
    for item in manifest['files']:
        p=ROOT/item['path']
        if p.is_symlink() or p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:raise ValueError('File differs '+item['path'])
    print('Verified',len(expected),'local files; original inputs unchanged; Mesa pin clean')
    print('manifest SHA256',sha(ROOT/'manifest.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--create',action='store_true');args=p.parse_args()
    if args.create:create()
    verify()
