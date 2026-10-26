#!/usr/bin/env python3
"""Build our private C adapter against a fixed, directly loaded software ICD."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HEADERS = Path(os.environ.get('VULKAN_HEADERS_DIR', ''))
LVP = Path(os.environ.get('VULKAN_LVP_LIBRARY', ''))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if not os.environ.get('VULKAN_HEADERS_DIR') or not os.environ.get('VULKAN_LVP_LIBRARY'):
        raise SystemExit('Set VULKAN_HEADERS_DIR and VULKAN_LVP_LIBRARY for local build dependencies')
    variant = sys.argv[1] if len(sys.argv)>1 else 'release'
    if variant not in {'release','sanitize'}: raise SystemExit('unknown build variant')
    output=ROOT/'build'/('backend-'+variant)
    output.mkdir(exist_ok=False)
    src=['metal/backend-adapter/nm_backend.c','prototype/api/metal_like.c','prototype/tests/backend_test.c']
    command=['clang','-std=c11','-Wall','-Wextra','-Werror','-g','-O2',
             '-I'+str(HEADERS/'include'),'-Isources/nullmoth/plugin',
             '-Imetal/backend-adapter','-Iprototype/api',f'-DNM_LVP_PATH="{LVP}"']
    if variant=='sanitize': command+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
    command+=src+['-pthread','-ldl','-lm','-o',str(output/'backend-test')]
    p=subprocess.run(command,cwd=ROOT,capture_output=True)
    (output/'compiler.stdout').write_bytes(p.stdout); (output/'compiler.stderr').write_bytes(p.stderr)
    files=src+['metal/backend-adapter/nm_backend.h','prototype/api/metal_like.h',
               'sources/nullmoth/plugin/nvmtl_tex_upload.h','sources/nullmoth/plugin/nvmtl_sample_positions.h']
    receipt={'command':command,'exit':p.returncode,'source_sha256':{f:sha(ROOT/f) for f in files},
             'software_icd':{'path':str(LVP),'sha256':sha(LVP)},
             'vulkan_headers':{'path':str(HEADERS/'include/vulkan/vulkan_core.h'),
                               'sha256':sha(HEADERS/'include/vulkan/vulkan_core.h')},
             'scope':'Linux CPU model and explicitly fixed software Vulkan only; no macOS Metal ABI'}
    if not p.returncode: receipt['binary_sha256']=sha(output/'backend-test')
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    sys.stdout.buffer.write(p.stdout); sys.stderr.buffer.write(p.stderr)
    print(json.dumps({'exit':p.returncode,'output':str(output)})); return p.returncode
if __name__=='__main__': raise SystemExit(main())
