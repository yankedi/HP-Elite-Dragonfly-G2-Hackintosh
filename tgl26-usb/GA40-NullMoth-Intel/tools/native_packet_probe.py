#!/usr/bin/env python3
"""Exercise unchanged Mesa genxml packer offline, with independent word oracle."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'build/native-packet-probe'
out.mkdir(exist_ok=False)
source=ROOT/'sources/mesa'
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
generator=['python3','-B',str(source/'src/intel/genxml/gen_pack_header.py'),
           str(source/'src/intel/genxml/gen120.xml'),'--include-symbols','MI_NOOP,MI_BATCH_BUFFER_END']
p=subprocess.run(generator,capture_output=True,env=env)
(out/'generator.stderr').write_bytes(p.stderr)
(out/'gen120_minimal_pack.h').write_bytes(p.stdout)
row={'generator':generator,'generator_exit':p.returncode,'scope':'NOT_FOR_HARDWARE, CPU packing only, no dispatch/pipeline/ANV device'}
if not p.returncode:
    command=['clang','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
             '-I'+str(out),'-I'+str(source/'src'),'-I'+str(source/'include'),
             '-I'+str(source/'src/intel/genxml'),'-DHAVE_ENDIAN_H','-DHAVE_STRUCT_TIMESPEC',
             'prototype/vulkan/native_packet_probe.c','-lm','-o',str(out/'native-packet-probe')]
    c=subprocess.run(command,capture_output=True,cwd=ROOT,env=env)
    (out/'compiler.stdout').write_bytes(c.stdout); (out/'compiler.stderr').write_bytes(c.stderr)
    row.update(command=command,compiler_exit=c.returncode)
    if not c.returncode:
        r=subprocess.run([str(out/'native-packet-probe')],capture_output=True,env=env)
        (out/'result.json').write_bytes(r.stdout); (out/'run.stderr').write_bytes(r.stderr)
        row['run_exit']=r.returncode
        if not r.returncode:
            result=json.loads(r.stdout)
            assert result['words']==[0,0x05000000] and result['bytes']==8 and not result['submitted']
row['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
    source/'src/intel/genxml/gen_pack_header.py',source/'src/intel/genxml/gen120.xml',
    ROOT/'prototype/vulkan/native_packet_probe.c']}
(out/'receipt.json').write_text(json.dumps(row,indent=2)+'\n')
print(json.dumps(row,indent=2))
raise SystemExit(row.get('run_exit',row.get('compiler_exit',row['generator_exit'])))
