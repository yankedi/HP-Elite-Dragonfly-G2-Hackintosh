#!/usr/bin/env python3
"""Collect verified offline artifacts into a private immutable-by-convention set.

No deploy/install layout or runtime success is implied. SDK and Apple bytes
remain in ignored staging, while public reports carry hashes and statuses.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
check=Path(sys.argv[1]).resolve();dest=Path(sys.argv[2]).absolute()
assert (ROOT/'logs').resolve() in check.parents
assert (ROOT/'staging').resolve() in dest.resolve().parents and not dest.exists()
assert (check.parent/(check.name+'.log')).read_text().rstrip().endswith('GA46 required offline checks PASS; target/GPU never executed')
subprocess.run(['python3',str(ROOT/'tools/verify-donor-stage.py'),str(ROOT/'staging/donor-native-001')],check=True,stdout=sys.stderr)
dest.mkdir()
shutil.copytree(check/'kernel/NootedGreen.kext',dest/'NootedGreen.kext')
shutil.copytree(ROOT/'staging/donor-native-001',dest/'donor',symlinks=True)
for name in ['libxedrv.dylib','libMTLIGCCompilerPlugin.dylib','libLLVMbridge.dylib','metal-abi-probe','compiler-runtime-probe']:
    shutil.copy2(check/'userspace'/name,dest/name)
files=[]
for p in sorted(dest.rglob('*')):
    if p.is_symlink():
        # Record links; never dereference an inherited donor resource link.
        files.append(dict(path=str(p.relative_to(dest)),symlink=str(p.readlink())))
    elif p.is_file():
        with p.open('rb') as f:d=hashlib.file_digest(f,'sha256').hexdigest()
        files.append(dict(path=str(p.relative_to(dest)),bytes=p.stat().st_size,sha256=d))
k=json.loads((check/'kernel/structure.json').read_text())
u=json.loads((check/'userspace-audit.json').read_text())
hashes={f['path']:f.get('sha256') for f in files}
assert hashes['NootedGreen.kext/Contents/MacOS/NootedGreen']==k['sha256']
assert all(hashes[c['name']]==c['sha256'] for c in u['components'])
manifest=dict(schema=1,artifact_root=str(dest),check_root=str(check),
              source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              kext_sha256=k['sha256'],kext_status=['KEXT_FILETYPE_VALID','KEXT_RELOCATIONS_VALID','KERNEL_SYMBOLS_AUDITED','KEXT_LINKED'],
              userland=u['components'],files=files,
              runtime=['RUNTIME_SYMBOL_UNVERIFIED','ABI_UNVERIFIED','DEPLOYMENT_BLOCKED','GPU_NOT_TESTED'],
              target_modified=False,target_new_binaries_executed=False,source_img=None,result_img=None,
              not_deployable_reasons=['native kext only routes audited observation/staging paths',
                 'compiler request/reply contract and LLVM3902 provider missing',
                 'Metal private schema unapproved; quarantine dylib refuses device',
                 'modified Apple signature invalid; host acceptance unproved'],
              preserved_baseline='GA45 971c2a1 read-only')
(dest/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
