#!/usr/bin/env python3
"""Verify actual linked files and two-level dependency metadata, never execute."""
import importlib.util
import json
from pathlib import Path
import sys
r=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('macho',r/'tools/macho-audit.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
out=Path(sys.argv[1]);items=[]
for name in ['libxedrv.dylib','libMTLIGCCompilerPlugin.dylib','libLLVMbridge.dylib','metal-abi-probe','compiler-runtime-probe']:
    x=m.inspect(out/name)
    assert x['header']['filetype']==(6 if name.endswith('.dylib') else 2)
    assert x['header']['flags']&1,'NOUNDEFS missing'
    imports=[s for s in x['symbols'] if s['undefined']]
    assert all(s['descriptor']>>8 not in (0,0xfe,0xff) for s in imports),'flat/dynamic lookup import'
    deps=[l['name'] for l in x['libraries'] if l['command']!=0xd]
    assert all(p.startswith(('/usr/lib/','/System/Library/')) for p in deps),'unexpected runtime dependency'
    items.append(dict(name=name,sha256=x['sha256'],filetype=x['header']['filetype'],imports=len(imports),
                      dependencies=deps,status='USERSPACE_DYLIB_LINKED' if name.endswith('.dylib') else 'PROBE_LINKED_NOT_EXECUTED',
                      runtime='ABI_UNVERIFIED',signature='UNSIGNED'))
print(json.dumps(dict(components=items,target_executed=False,gpu='GPU_NOT_TESTED'),indent=2))
