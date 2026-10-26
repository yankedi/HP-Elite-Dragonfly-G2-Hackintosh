#!/usr/bin/env python3
"""Offline inspectable kext package; no target exports, signing or installation."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('module', type=Path)
p.add_argument('out', type=Path)
a = p.parse_args()
out, module = a.out.resolve(), a.module.resolve()
out.mkdir()
llvm = Path(os.environ['GA43_LLVM_BIN'])
def llvm_run(tool, *args):
    return subprocess.check_output([str(llvm/tool), *map(str, args)], text=True)
header = llvm_run('llvm-readobj', '--file-headers', module)
if 'FileType: KextBundle' not in header or 'Arch: x86_64' not in header:
    raise SystemExit('required real x86_64 MH_KEXT_BUNDLE')
imports = sorted(set(llvm_run('llvm-nm', '-u', module).splitlines()))
if any(n.startswith(('_gx_', '_i915_')) for n in imports):
    raise SystemExit('project-internal imports unresolved')
symbols = llvm_run('llvm-nm', module)
for required in ('_kmod_info', '__realmain', '__antimain', '__start', '__stop'):
    if not any(line.endswith(' '+required) and ' U ' not in line for line in symbols.splitlines()):
        raise SystemExit('missing kmod entry: '+required)
relocations = llvm_run('llvm-readobj', '--relocations', module)
info = plistlib.loads((ROOT/'i915-xnu/native/Info.plist').read_bytes())
bundle = out/'GX43IntelGEM.kext'/'Contents'
(bundle/'MacOS').mkdir(parents=True)
shutil.copy2(module, bundle/'MacOS'/info['CFBundleExecutable'])
(bundle/'Info.plist').write_bytes(plistlib.dumps(info))
(out/'header.txt').write_text(header)
(out/'symbols.txt').write_text(symbols)
(out/'relocations.txt').write_text(relocations)
(out/'imports.txt').write_text('\n'.join(imports)+'\n')
result = {
    'module': str(module), 'package': str(bundle.parent), 'filetype': 'MH_KEXT_BUNDLE',
    'arch': 'x86_64', 'project_symbols_resolved': True,
    'kernel_import_count': len(imports), 'target_25G83_exports': 'NOT_VERIFIED',
    'public_KPI_and_CXX_ABI': 'NOT_VERIFIED', 'kernel_collection': 'NOT_TESTED',
    'signature': 'UNSIGNED', 'installed': False, 'runtime': 'NOT_TESTED',
    'gpu': 'NOT_TESTED',
    'scope': 'Actual kext link and relocations, not target kernel symbol resolution or load acceptance',
}
(out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
files = sorted(x for x in out.rglob('*') if x.is_file())
with (out/'SHA256SUMS').open('xb') as f:
    subprocess.run(['sha256sum', *map(str, files)], stdout=f, check=True)
print(json.dumps(result, indent=2))
