#!/usr/bin/env python3
"""Offline five-stage Darwin probes. No guessed SDK, downloads or execution.

Each invocation requires a fresh label. Object/link/inspection subprocesses
have separate exclusive logs. An export-name fixture is never an actual ICD.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

if not __debug__:
    raise SystemExit('Evidence contracts require Python assertions; optimized Python is rejected')

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('label')
p.add_argument('--clang', type=Path, required=True)
p.add_argument('--lld', type=Path, required=True)
p.add_argument('--readobj', type=Path, required=True)
p.add_argument('--sdk', type=Path)
p.add_argument('--legacy-lld', action='store_true', help='old Android LLD Darwin flavor, not current ld64.lld')
a = p.parse_args()
if a.sdk:
    a.sdk = a.sdk.resolve()
for name in ('clang', 'lld', 'readobj'):
    setattr(a, name, getattr(a, name).resolve())
root = Path(__file__).resolve().parents[1]
assert a.label and '/' not in a.label
out = root / 'artifacts' / a.label
logs = root / 'logs' / a.label
assert not out.exists() and not logs.exists(), 'never overwrite a probe'
out.mkdir(parents=True)
logs.mkdir(parents=True)
src = root / 'toolchain/probes'
env = os.environ.copy()
# Never allow a Nix host wrapper or ambient C include/library paths to
# silently turn missing Darwin dependencies into Linux header contamination.
for name in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH',
             'SDKROOT', 'MACOSX_DEPLOYMENT_TARGET'):
    env.pop(name, None)
def run(name, args):
    d = logs / name
    d.mkdir()
    args = list(map(str, args))
    rec = {'argv': args, 'cwd': str(root), 'started': datetime.now(timezone.utc).isoformat()}
    (d/'command.json').write_text(json.dumps(rec, indent=2)+'\n')
    with (d/'stdout.txt').open('xb') as stdout, (d/'stderr.txt').open('xb') as stderr:
        try:
            r = subprocess.run(args, cwd=root, env=env, stdout=stdout, stderr=stderr, check=False)
            code = r.returncode
        except OSError as e:
            stderr.write(str(e).encode())
            code = 127
    rec.update(exit_code=code, ended=datetime.now(timezone.utc).isoformat())
    (d/'command.json').write_text(json.dumps(rec, indent=2)+'\n')
    print(name, code)
    return code

cc = [a.clang, '--target=x86_64-apple-macos26.0', '-Werror', '-fno-ident']
if a.sdk:
    if not (a.sdk/'SDKSettings.json').is_file() or not (a.sdk/'usr/include/stdlib.h').is_file():
        p.error('SDK must be a complete user SDK, not kernel headers')
    cc += ['-isysroot', a.sdk.resolve()]
link = [a.lld, '-flavor', 'darwin', '-arch', 'x86_64', '-platform_version',
        'macos', '26.0', '26.0', '-dylib']
if a.legacy_lld:
    link = [a.lld, '-flavor', 'darwin', '-arch', 'x86_64',
             '-macosx_version_min', '26.0', '-sdk_version', '26.0', '-dylib']
link += ['-undefined', 'error']
stage = {
    'compiler_version': run('compiler-version', [a.clang, '--version']),
    'compiler_targets': run('compiler-targets', [a.clang, '-print-targets']),
    'linker_help': run('linker-help', [a.lld, '-flavor', 'darwin', '-help']),
}
tool_identity_valid = (all(v == 0 for v in stage.values()) and
    'clang version' in (logs/'compiler-version/stdout.txt').read_text(errors='replace') and
    'x86-64' in (logs/'compiler-targets/stdout.txt').read_text(errors='replace') and
    bool((logs/'linker-help/stdout.txt').read_text(errors='replace').strip()))
stage['c_object'] = run('01-c-object', cc+['-ffreestanding', '-c', src/'minimal.c', '-o', out/'minimal.o'])
syslib = ['-syslibroot', a.sdk, '-lSystem'] if a.sdk else []
stage['minimal_dylib'] = run('02-minimal-dylib', link+syslib+['-install_name', '@rpath/libga43_probe.dylib',
    '-rpath', '@loader_path', '-o', out/'libga43_probe.dylib', out/'minimal.o'])
if stage['minimal_dylib'] and a.legacy_lld:
    # Diagnostic salvage only: old LLD synthesizes dyld_stub_binder even for
    # freestanding arithmetic. Unresolved imports remain explicitly visible.
    # Never use this policy to link ANV or the native driver.
    stage['minimal_dynamic_lookup_diagnostic'] = run('02-dynamic-lookup-diagnostic', link+
        ['-undefined', 'dynamic_lookup', '-install_name', '@rpath/DIAGNOSTIC_ONLY.dylib',
         '-rpath', '@loader_path', '-o', out/'DIAGNOSTIC_ONLY.dylib', out/'minimal.o'])
stage['libcxx_object'] = run('03-libcxx-object', cc+['-stdlib=libc++', '-c', src/'libcxx.cpp', '-o', out/'libcxx.o'])
# Even when compilation fails, perform a separate actual linker dependency
# resolution probe with the valid C object, explicitly not C++ program success.
syslib = ['-syslibroot', a.sdk.resolve()] if a.sdk else []
stage['libcxx_link'] = run('03-libcxx-link', link+syslib+['-lc++', '-lSystem', '-o', out/'libcxx-probe.dylib',
    out/('libcxx.o' if stage['libcxx_object'] == 0 else 'minimal.o')])
stage['libsystem_object'] = run('04-system-object', cc+['-c', src/'libsystem.c', '-o', out/'libsystem.o'])
stage['libsystem_link'] = run('04-system-link', link+syslib+['-lSystem', '-o', out/'libsystem-probe.dylib',
    out/('libsystem.o' if stage['libsystem_object'] == 0 else 'minimal.o')])
stage['icd_names_object'] = run('05-icd-names-object', cc+['-ffreestanding', '-c', src/'icd-symbols.c', '-o', out/'icd-names.o'])
stage['icd_names_link'] = run('05-icd-names-link', link+syslib+(['-lSystem'] if a.sdk else [])+['-install_name', '@rpath/NOT_AN_ICD.dylib',
    '-exported_symbols_list', src/'icd.exports', '-o', out/'NOT_AN_ICD.dylib', out/'icd-names.o'])
inspections = {}
for f in sorted(out.iterdir()):
    inspections[f.name] = [run('inspect-'+f.name, [a.readobj, '--file-headers', '--symbols', '--needed-libs', '--macho-version-min', f]),
                          run('loadcommands-'+f.name, [a.readobj.parent/'llvm-objdump', '--macho', '--private-headers', f])]
contracts = {
    'c_object': ('minimal.o', 'object', []),
    'libcxx_object': ('libcxx.o', 'object', []),
    'libsystem_object': ('libsystem.o', 'object', []),
    'icd_names_object': ('icd-names.o', 'object', []),
    'minimal_dylib': ('libga43_probe.dylib', 'dylib', ['--id', '@rpath/libga43_probe.dylib', '--rpath', '@loader_path', '--export', '_ga43_checked_add']),
    'libcxx_link': ('libcxx-probe.dylib', 'dylib', ['--require', '/usr/lib/libc++.1.dylib', '--require', '/usr/lib/libSystem.B.dylib']),
    'libsystem_link': ('libsystem-probe.dylib', 'dylib', ['--require', '/usr/lib/libSystem.B.dylib']),
    'icd_names_link': ('NOT_AN_ICD.dylib', 'dylib', ['--id', '@rpath/NOT_AN_ICD.dylib', *sum((['--export', n] for n in (src/'icd.exports').read_text().split()), [])]),
}
validated = {}
for name, (file, kind, options) in contracts.items():
    if stage[name] != 0:
        validated[name] = False
        continue
    allow = ['/usr/lib/libSystem.B.dylib', '/usr/lib/libc++.1.dylib', '/usr/lib/libc++abi.dylib'] if a.sdk else []
    code = run('contract-'+name, [sys.executable, '-B', root/'tools/inspect-darwin-probe.py',
        out/file, '--kind', kind, *sum((['--allow', n] for n in allow), []), *options])
    validated[name] = code == 0 and inspections.get(file) == [0, 0]
hash_exit = run('sha256', ['sha256sum', a.clang, a.lld, a.readobj,
    a.readobj.parent/'llvm-objdump', root/'tools/darwin-probes.py', root/'tools/inspect-darwin-probe.py',
    *sorted(src.iterdir()), *sorted(out.iterdir())])
result = {'stages': stage, 'sdk': str(a.sdk) if a.sdk else None,
          'schema': 'ga43-enforced-probes-v2', 'validated': validated,
          'tool_identity_valid': tool_identity_valid,
          'strict_pass': all(validated.values()) and hash_exit == 0 and tool_identity_valid,
          'minimal_dylib_scope': 'strict link result above; diagnostic fallback retains undefined runtime imports, not SDK success',
          'icd_names_scope': 'data export-name fixture, not Vulkan ABI or ANV; never load',
          'system_link_fallback_scope': 'if source failed: dependency-resolution probe only',
          'runtime': 'NOT_TESTED', 'gpu': 'NOT_TESTED'}
(logs/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
