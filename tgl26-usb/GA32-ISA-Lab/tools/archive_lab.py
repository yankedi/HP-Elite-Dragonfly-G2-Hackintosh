#!/usr/bin/env python3
"""Create/verify evidence manifest; caches/build trees excluded explicitly, key binaries included."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BINARIES=['tools/iga/build/IGAExe/iga64','tools/iga/build-gcc/IGAExe/iga64',
          'tools/iga/build-sanitize/IGAExe/iga64','tools/mesa-eu/adapter/build/g11to12',
          'tools/mesa-eu/adapter/build-sanitize/g11to12',
          'tools/mesa-eu/adapter/build-gcc/g11to12']
SOURCES={'tools/iga/source':'c36a504a4e6c68030c3302646aa396b8b59b22cb',
         'tools/mesa-eu/source':'863338275d915e867319c3690ffd3272b06303c3'}
ANCHORS=['tools/mesa-eu/source/src/intel/genxml/gen11.xml',
         'tools/mesa-eu/source/src/intel/genxml/gen12.xml',
         'tools/mesa-eu/source/src/intel/compiler/brw_inst.h',
         'tools/mesa-eu/source/src/intel/compiler/brw_eu_validate.c',
         'tools/iga/source/visa/iga/IGAJSONv2.md']
EXTERNAL=[ROOT.parent/'GA32/capture/tgl-hang-GA32b-crash-20261018.bin',
          ROOT.parent/'GA32b-offline-analysis.zip']

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def excluded(p):
    r=str(p.relative_to(ROOT))
    if r in BINARIES or r in ANCHORS:return False
    if r in {'manifest.json','manifest.sha256','logs/manifest-verification.txt'}:return True
    if any(x in p.parts for x in ['.git','__pycache__']):return True
    if any(r.startswith(s+'/') for s in SOURCES):return True
    if any(x.startswith('build') and x not in {'build.sh','build-adapter.sh'} for x in p.relative_to(ROOT).parts[:-1]):return True
    return False

def selected():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not excluded(p))

def record(p,local=True):
    return {'path':str(p.relative_to(ROOT)) if local else str(p),
            'bytes':p.stat().st_size,'sha256':sha(p)}

def create():
    deps=[]
    for s,pin in SOURCES.items():
        commit=subprocess.check_output(['git','-C',str(ROOT/s),'rev-parse','HEAD'],text=True).strip()
        status=subprocess.check_output(['git','-C',str(ROOT/s),'status','--porcelain'],text=True)
        if commit!=pin or status:raise ValueError('dependency pin/clean check failed: '+s)
        deps.append({'path':s,'commit':commit,'clean':True,'per_file_scope':'critical anchors only; repository commit pins full source'})
    manifest={'schema':1,'date':'2026-10-18','scope':'private offline GA32-ISA-Lab; no GPU execution',
              'exclusions':['.git','__pycache__','third-party source trees except critical anchors',
                            'build intermediates except named native binaries','manifest self/hash/verifier log'],
              'dependencies':deps,'external_inputs':[record(p,False) for p in EXTERNAL],
              'files':[record(p) for p in selected()]}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT/'manifest.sha256').write_text(sha(ROOT/'manifest.json')+'  manifest.json\n')

def verify():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    expected={x['path'] for x in manifest['files']}
    actual={str(p.relative_to(ROOT)) for p in selected()}
    if expected!=actual:raise ValueError({'missing':sorted(expected-actual),'unlisted':sorted(actual-expected)})
    for scope,entries in [(True,manifest['files']),(False,manifest['external_inputs'])]:
        for e in entries:
            p=ROOT/e['path'] if scope else Path(e['path'])
            if p.is_symlink():raise ValueError('symlink not allowed: '+str(p))
            if p.stat().st_size!=e['bytes'] or sha(p)!=e['sha256']:raise ValueError('hash mismatch: '+str(p))
    for dep in manifest['dependencies']:
        path=ROOT/dep['path']
        if subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()!=dep['commit']:
            raise ValueError('dependency commit mismatch')
        if subprocess.check_output(['git','-C',str(path),'status','--porcelain'],text=True):
            raise ValueError('dependency dirty')
    print('verified',len(expected),'local files;',len(manifest['external_inputs']),'external inputs; two clean pinned source trees')
    print('manifest SHA256',sha(ROOT/'manifest.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--create',action='store_true');a=p.parse_args()
    if a.create:create()
    verify()
