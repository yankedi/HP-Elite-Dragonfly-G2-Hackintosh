#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from build_backend import ROOT, HEADERS, LVP

out=ROOT/'build/cross-component'
out.mkdir(exist_ok=False)
source=['metal/backend-adapter/nm_backend.c','prototype/api/metal_like.c','prototype/api/pipeline.c']
command=['clang','-std=c11','-Wall','-Wextra','-Werror','-O2','-g','-I'+str(HEADERS/'include'),
         '-Isources/nullmoth/plugin','-Imetal/backend-adapter','-Iprototype/api',f'-DNM_LVP_PATH="{LVP}"']
command+=source+['-pthread','-ldl','-lm','-o',str(out/'metal-like-pipeline')]
p=subprocess.run(command,cwd=ROOT,capture_output=True)
(out/'compiler.stdout').write_bytes(p.stdout); (out/'compiler.stderr').write_bytes(p.stderr)
row={'command':command,'exit':p.returncode,'source_sha256':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in source}}
if not p.returncode: row['binary_sha256']=hashlib.sha256((out/'metal-like-pipeline').read_bytes()).hexdigest()
(out/'receipt.json').write_text(json.dumps(row,indent=2)+'\n')
sys.stderr.buffer.write(p.stderr); print(json.dumps(row)); raise SystemExit(p.returncode)
