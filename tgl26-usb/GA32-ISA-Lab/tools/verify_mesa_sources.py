#!/usr/bin/env python3
"""Explicit pristine-vs-standalone-adapter source audit."""
from pathlib import Path
import difflib
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]

def main():
    adapter=ROOT/'tools/mesa-eu/adapter'
    source=ROOT/'tools/mesa-eu/source/src/intel/compiler'
    rows=[]
    for p in sorted((adapter/'eu').glob('*')):
        if p.suffix not in {'.c','.h'}:continue
        q=source/p.name
        row={'adapter':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
             'upstream_exists':q.exists()}
        if q.exists():
            row['pristine_sha256']=hashlib.sha256(q.read_bytes()).hexdigest()
            row['same_as_pristine']=p.read_bytes()==q.read_bytes()
            if not row['same_as_pristine']:
                row['diff']=''.join(difflib.unified_diff(q.read_text().splitlines(True),p.read_text().splitlines(True),
                                                      fromfile='pristine/'+q.name,tofile='adapter/'+p.name))
        rows.append(row)
    for p in sorted(adapter.glob('*')):
        if p.suffix in {'.c','.h','.patch'}:
            rows.append({'adapter':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                         'origin':'isolated reference support copy; see reference/PROVENANCE.json'})
    changed={Path(x['adapter']).name for x in rows if x.get('same_as_pristine') is False}
    assert changed=={'brw_compiler.h','brw_shader.h','brw_eu_emit.c'}, changed
    (ROOT/'analysis/mesa-adapter-provenance.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(len(rows),'sources checked; pristine differences:',sorted(changed))
if __name__=='__main__':main()
