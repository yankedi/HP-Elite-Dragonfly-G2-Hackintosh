#!/usr/bin/env python3
"""Owned-source and JSON hygiene plus frozen-input/dependency verification."""
import ast
import json
from pathlib import Path
import archive

ROOT=Path(__file__).resolve().parents[1]
def main():
    scripts=[]
    for folder in ('tools','track-a','track-b/diagnostic-src','track-c'):
        for path in (ROOT/folder).rglob('*.py'):
            if any(x in ('build','__pycache__','ga33-base') for x in path.parts):continue
            ast.parse(path.read_text(),filename=str(path));scripts.append(path)
    records=list(ROOT.rglob('*.json'))
    for path in records:json.loads(path.read_text())
    archive.originals()
    spec=json.loads((ROOT/'track-a/spec-diff.json').read_text())
    names={x['name'] for x in spec['commands']}
    assert {'3DSTATE_STENCIL_BUFFER','3DPRIMITIVE','RENDER_SURFACE_STATE','SAMPLER_STATE','STATE_BASE_ADDRESS'}<=names
    audit=json.loads((ROOT/'track-a/packet-audit.json').read_text())
    assert audit['packet_count']==166==sum(audit['classifications'].values())
    assert not audit['complete_gpu_semantics_validated']
    print('PASS',len(scripts),'owned Python AST;',len(records),'JSON; frozen original inputs and clean Mesa pin;166 audited packets')
if __name__=='__main__':main()
