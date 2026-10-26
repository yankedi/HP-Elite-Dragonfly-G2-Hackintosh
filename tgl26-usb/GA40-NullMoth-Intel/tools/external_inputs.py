#!/usr/bin/env python3
"""Record locally available external tools, headers, software ICD and ELF deps.

This is a reproducibility receipt, not permission to download/modify a store.
Only runs ldd on known local build artifacts and the fixed software ICD.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'reference/external-inputs.json'
if out.exists(): raise SystemExit('External input receipt already exists')
paths=set(); reasons={}; missing=[]


def add(path,why):
    p=Path(path)
    if not p.is_file(): return
    p=p.resolve()
    if ROOT in p.parents: return
    paths.add(p); reasons.setdefault(str(p),set()).add(why)


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


for tool in ['python3','clang','clang++','cc','cmake','ninja','pkg-config','git','curl','cargo','rustc','ld','ldd']:
    value=shutil.which(tool)
    if value: add(value,'available tool '+tool)

for folder in ['tools','logs','intel','metal/translator-prototype','reference/intel-build','reference/translator-build']:
    for file in (ROOT/folder).rglob('*'):
        if not file.is_file() or file.suffix not in {'.py','.json','.txt','.sh','.md','.log'}: continue
        if file.stat().st_size>4*1024*1024: continue
        text=file.read_text(errors='replace')
        for path in re.findall(r'/nix/store/[a-z0-9]{32}-[^\s\"\'<>;,(){}\[\]]+',text):
            p=Path(path.rstrip(':'))
            if p.is_file(): add(p,'recorded in '+str(file.relative_to(ROOT)))
            elif p.is_dir() and ('include' in p.parts or p.name in {'bin','site-packages','pkgconfig'}):
                for child in p.rglob('*'):
                    if child.is_file(): add(child,'recorded include/bin directory '+str(p))

# Explicit complete Vulkan include tree and fixed software ICD from executed build.
receipt=json.loads((ROOT/'build/backend-release/receipt.json').read_text())
core=Path(receipt['vulkan_headers']['path'])
for file in core.parent.parent.rglob('*'):
    if file.is_file(): add(file,'complete executed Vulkan include tree')
lvp=Path(receipt['software_icd']['path']); add(lvp,'direct fixed software ICD')
intel_manifest=json.loads((ROOT/'reference/intel-build/manifest.json').read_text())
add(intel_manifest['toolchain']['iga']['path'],'read-only historical IGA used for actual native shader decoding')

# Dynamic runtime closure. e_type excludes relocatable objects; no executable runs.
candidates=[lvp]
for file in (ROOT/'build').rglob('*'):
    if not file.is_file() or file.is_symlink() or file.suffix in {'.gz','.a','.rlib','.rmeta'}: continue
    with file.open('rb') as f: header=f.read(18)
    if len(header)==18 and header[:4]==b'\x7fELF' and int.from_bytes(header[16:18],'little') in {2,3}:
        candidates.append(file)
ldd_rows=[]
seen=set()
while candidates:
    file=candidates.pop().resolve()
    if file in seen: continue
    seen.add(file)
    result=subprocess.run(['ldd',str(file)],capture_output=True,text=True,timeout=15)
    ldd_rows.append({'path':str(file),'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    for dependency in re.findall(r'(/nix/store/[^\s()]+)',result.stdout):
        p=Path(dependency)
        add(p,'ELF dependency of '+str(file))
        if p not in seen: candidates.append(p)
    if 'not found' in result.stdout: missing.append(str(file))

rows=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p),'reasons':sorted(reasons[str(p)])} for p in sorted(paths)]
result={'scope':'Existing host tools/recorded external inputs and dynamic runtime closure; source/build bytes remain local GA40 artifacts',
        'limitation':'Not an exported Nix store closure or an SDK licence grant. Private migration requires compatible runtime and all listed files; unknown external Apple AIR payloads are not included.',
        'files':rows,'ldd':ldd_rows,'missing_dynamic_dependencies':missing,'hardware_access':False}
assert not missing,missing
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'external_files':len(rows),'elf_scans':len(ldd_rows),'missing_dynamic_dependencies':missing,'receipt_sha256':sha(out)}))
