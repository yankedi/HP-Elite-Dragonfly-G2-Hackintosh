#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'build'/(sys.argv[1] if len(sys.argv)>1 else 'uapi-layout-v2')
out.mkdir(exist_ok=False)
command=['clang','-std=c11','-Wall','-Wextra','-Werror','-Isources/mesa/include/drm-uapi',
         'drm/mock/layout_probe.c','-o',str(out/'layout-probe')]
p=subprocess.run(command,cwd=ROOT,capture_output=True)
(out/'compiler.stdout').write_bytes(p.stdout); (out/'compiler.stderr').write_bytes(p.stderr)
row={'command':command,'exit':p.returncode}
if not p.returncode:
    run=subprocess.run([str(out/'layout-probe')],capture_output=True)
    row['probe_exit']=run.returncode
    (out/'abi.json').write_bytes(run.stdout)
    (out/'probe.stderr').write_bytes(run.stderr)
    assert run.returncode==0 and json.loads(run.stdout)['pointer_size']==8
row['inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
               [ROOT/'drm/mock/layout_probe.c',ROOT/'sources/mesa/include/drm-uapi/drm.h',ROOT/'sources/mesa/include/drm-uapi/i915_drm.h']}
(out/'receipt.json').write_text(json.dumps(row,indent=2)+'\n')
sys.stderr.buffer.write(p.stderr)
print(json.dumps(row)); raise SystemExit(p.returncode)
