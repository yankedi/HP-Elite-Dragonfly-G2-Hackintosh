#!/usr/bin/env python3
"""Compare module imports to exact Apple KDK KPI pseudoextensions and IOPCI.

Pseudoextensions intentionally carry undefined external names: those are the
kernel's exported KPI lists, not executable implementations. IOPCIFamily is
an implementation: only its defined external names may act as providers.
This check does not validate C++ object/vtable layout or KernelCollection load.
"""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('kdk', type=Path)
p.add_argument('module', type=Path)
p.add_argument('out', type=Path)
p.add_argument('--nm', required=True)
a = p.parse_args()
a.out.mkdir()
version = plistlib.loads((a.kdk/'System/Library/CoreServices/SystemVersion.plist').read_bytes())
if version.get('ProductBuildVersion') != '25G83': raise SystemExit('exact KDK build required')
declared = plistlib.loads((ROOT/'i915-xnu/native/Info.plist').read_bytes())['OSBundleLibraries']
def names(path, defined=False):
    args = [a.nm, '-arch', 'x86_64', '-g', '-j']
    if defined: args += ['--defined-only']
    return set(subprocess.check_output([*args, str(path)], text=True).splitlines())
providers = {}
inputs = []
base = a.kdk/'System/Library/Extensions'
for info_path in sorted((base/'System.kext/PlugIns').glob('*.kext/Info.plist')):
    info = plistlib.loads(info_path.read_bytes())
    if not info.get('CFBundleIdentifier', '').startswith('com.apple.kpi.'): continue
    binary = info_path.parent/info.get('CFBundleExecutable', '')
    if not binary.is_file(): continue
    for name in names(binary): providers.setdefault(name, []).append(info['CFBundleIdentifier'])
    inputs += [info_path, binary]
info_path = base/'IOPCIFamily.kext/Contents/Info.plist'
info = plistlib.loads(info_path.read_bytes())
binary = info_path.parent/'MacOS'/info['CFBundleExecutable']
for name in names(binary, True): providers.setdefault(name, []).append(info['CFBundleIdentifier'])
inputs += [info_path, binary]
imports = sorted(set(subprocess.check_output([a.nm, '-u', str(a.module)], text=True).splitlines()))
rows = [{'name': n, 'KDK_providers': providers.get(n, []),
         'declared_providers': [v for v in providers.get(n, []) if v in declared]} for n in imports]
result = {
    'build': version['ProductBuildVersion'], 'module': str(a.module),
    'import_count': len(imports), 'declared_dependencies': list(declared), 'symbols': rows,
    'not_in_declared_KPI': [r['name'] for r in rows if not r['declared_providers']],
    'not_in_any_KDK_provider': [r['name'] for r in rows if not r['KDK_providers']],
    'CXX_ABI': 'NOT_VERIFIED', 'kernel_collection': 'NOT_TESTED', 'runtime': 'NOT_TESTED',
    'scope': 'Exact KDK KPI-name contract, not vtable/layout/load compatibility or public API stability',
}
(a.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
with (a.out/'inputs.sha256').open('xb') as f:
    subprocess.run(['sha256sum', str(a.module), *map(str, inputs)], stdout=f, check=True)
print(json.dumps({k: v for k, v in result.items() if k != 'symbols'}, indent=2))
