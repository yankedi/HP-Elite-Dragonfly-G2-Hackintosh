#!/usr/bin/env python3
"""Record tracked-byte identities of pristine third-party inputs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'nullmoth':'47f818b11cef59acb480210afdf9065fdd44e356',
            'mesa':'31e9a6b2e95e30d84bf3177d1f497d063e59b6b2'}
out = ROOT/'sources/provenance.json'
if out.exists(): raise SystemExit('Source receipts are immutable')
sources={}
for name,pin in EXPECTED.items():
    path=ROOT/'sources'/name
    def git(*args): return subprocess.check_output(['git','-C',str(path),*args])
    assert git('rev-parse','HEAD').decode().strip()==pin
    assert not git('status','--porcelain','--untracked-files=no').strip()
    rows=[]
    for raw in git('ls-files','-z').split(b'\0'):
        if not raw: continue
        relative=os.fsdecode(raw); p=path/relative
        data=os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()
        rows.append({'path':relative,'kind':'symlink' if p.is_symlink() else 'file',
                     'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    manifest=ROOT/'sources'/(name+'-tracked-manifest.json')
    manifest.write_text(json.dumps(rows,indent=2)+'\n')
    sources[name]={'commit':pin,'origin':git('remote','get-url','origin').decode().strip(),
                   'tracked_files':len(rows),'tracked_manifest':str(manifest.relative_to(ROOT)),
                   'tracked_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
                   'pristine':True}
sources['mesa']['tag']='mesa-26.2.3'
sources['mesa']['official_tag_evidence']='logs/mesa-upstream-pin-012/stdout.txt'
sources['mesa']['mirror_tag_evidence']='logs/mesa-pin-002/stdout.txt'
assert (ROOT/'logs/mesa-upstream-pin-012/stdout.txt').read_bytes()==(ROOT/'logs/mesa-pin-002/stdout.txt').read_bytes()
sources['nullmoth']['declared_mesa_base']=(ROOT/'sources/nullmoth/nvk/MESA_BASE').read_text().strip()
sources['nullmoth']['declared_mesa_base_is_selected_mesa']=False
result={'sources':sources,'scope':'Tracked source bytes, not a claim that these drivers execute on macOS',
        'hardware_validated':False,'historical_ga39_verification':'logs/ga39-entry-verify.json'}
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k: {'commit':v['commit'],'files':v['tracked_files']} for k,v in sources.items()}))
