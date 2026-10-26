#!/usr/bin/env python3
"""Strict final link of Mesa objects, resolving only absent optional table slots.

ELF weak undefineds become NULL at static link. Mach-O LLD instead errors.
Use absolute-zero PRIVATE symbols only for generated VK_ENTRY_WEAK references
with no definition anywhere in the exact link inputs. Never generate code,
public API implementations, or fallbacks for strong unresolved references.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

from darwin_link_inputs import dynamic_definitions


def symbols(nm, inputs):
    text = subprocess.check_output([nm, '-m', *map(str, inputs)], text=True)
    defined, weak, strong = set(), set(), set()
    for line in text.splitlines():
        m = re.search(r'\b(_[A-Za-z0-9_]+)$', line)
        if not m:
            continue
        if '(undefined)' not in line:
            defined.add(m[1])
        elif '(undefined) weak external ' in line:
            weak.add(m[1])
        else:
            strong.add(m[1])
    return defined, weak - strong, text


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('build', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    build, out = a.build.resolve(), a.out.resolve()
    out.mkdir()  # exclusive new evidence; never alter the failed Meson output
    target = 'src/intel/vulkan/libvulkan_intel.dylib'
    commands = subprocess.check_output(['ninja', '-C', str(build), '-t', 'commands', target], text=True)
    command = shlex.split(commands.splitlines()[-1])
    if command[command.index('-o')+1] != target:
        raise SystemExit('not the expected final ANV link command')
    if any(x in ' '.join(command) for x in ('dynamic_lookup', '-undefined,suppress', '-flat_namespace')):
        raise SystemExit('loose linker policy refused')
    # Portable output colocates its explicit custom DRM dependency. Only rpath
    # changes; all object/framework/library choices remain from the real build.
    command = [x for x in command if not x.startswith('-Wl,-rpath,')]
    command += ['-Wl,-rpath,@loader_path']
    driver = subprocess.run(command+['-###'], cwd=build, text=True, capture_output=True, check=True)
    (out/'driver-command.txt').write_text(driver.stderr)
    ld_command = shlex.split(driver.stderr.splitlines()[-1])
    if Path(ld_command[0]).resolve() != Path(os.environ['DARWIN_LD']).resolve():
        raise SystemExit('unexpected actual linker in Clang driver')
    inputs = [build/x for x in command if x.endswith(('.a', '.o'))]
    if not inputs or not all(x.is_file() for x in inputs):
        raise SystemExit('actual complete object/archive inputs required')
    nm = str(Path(os.environ['DARWIN_LLVM_BIN'])/'llvm-nm')
    defined, weak, text = symbols(nm, inputs)
    dynamic, dynamic_inputs = dynamic_definitions(ld_command, build, nm)
    defined.update(dynamic)
    (out/'input-symbols.txt').write_text(text)
    candidates = set()
    for header in build.rglob('*entrypoints*.h'):
        candidates.update('_'+n for n in re.findall(
            r'\b([A-Za-z_]\w*)\([^;{}]*\)\s+VK_ENTRY_WEAK\s+VK_ENTRY_HIDDEN;', header.read_text()))
    missing = sorted((weak - defined) & candidates)
    if not missing:
        raise SystemExit('no generated optional NULL slots found')
    # Actual implementations always win because we never define their names.
    # A future source change recomputes this set from the new exact archives.
    fallback = out/'optional-null.s'
    fallback.write_text('# Generated NULL addresses, NOT function stubs.\n' + ''.join(
        f'.globl {n}\n.private_extern {n}\n{n} = 0\n' for n in missing))
    obj = out/'optional-null.o'
    subprocess.run([os.environ['DARWIN_CC'], '-target', 'x86_64-apple-macos26',
                    '-c', str(fallback), '-o', str(obj)], check=True)
    command[command.index('-o')+1] = str(out/'libvulkan_intel.dylib')
    command += [str(obj), '-Wl,-undefined,error', '-Wl,--error-limit=0']
    (out/'contract.json').write_text(json.dumps({
        'build': str(build), 'inputs': list(map(str, inputs)),
        'defined_count': len(defined), 'missing_optional_null': missing,
        'dynamic_inputs': list(map(str, dynamic_inputs)), 'dynamic_export_count': len(dynamic),
        'missing_strong_policy': 'never resolved by this tool; strict linker errors',
        'argv': command, 'cwd': str(build),
        'scope': 'static link only; no Vulkan initialization/runtime/GPU'}, indent=2)+'\n')
    subprocess.run(['sha256sum', *map(str, inputs+dynamic_inputs), str(fallback), str(obj)],
                   stdout=(out/'inputs.sha256').open('xb'), check=True)
    print(f'{len(missing)} generated optional slots explicitly NULL; strong imports remain strict', flush=True)
    result = subprocess.run(command, cwd=build, check=False)
    inspect_exit = None
    if result.returncode == 0:
        expected = [
            '/usr/lib/libSystem.B.dylib', '@rpath/libdrm.dylib', '/usr/lib/libz.1.dylib',
            '/usr/lib/libobjc.A.dylib', '/usr/lib/libexpat.1.dylib', '/usr/lib/libc++.1.dylib',
            *[f'/System/Library/Frameworks/{n}.framework/Versions/A/{n}'
              for n in ('QuartzCore', 'Metal', 'CoreFoundation', 'CoreGraphics')],
        ]
        inspector = [sys.executable, '-B', str(Path(__file__).parent/'inspect-darwin-probe.py'),
            str(out/'libvulkan_intel.dylib'), '--kind', 'dylib', '--id', '@rpath/libvulkan_intel.dylib',
            '--rpath', '@loader_path']
        for dependency in expected: inspector += ['--allow', dependency, '--require', dependency]
        for name in ('GetInstanceProcAddr', 'GetPhysicalDeviceProcAddr', 'NegotiateLoaderICDInterfaceVersion'):
            inspector += ['--export', '_vk_icd'+name]
        with (out/'output-contract.json').open('xb') as f:
            inspect_exit = subprocess.run(inspector, stdout=f, check=False).returncode
    (out/'link-exit.json').write_text(json.dumps({
        'link_exit': result.returncode, 'inspection_exit': inspect_exit,
        'strict_artifact_pass': result.returncode == 0 and inspect_exit == 0})+'\n')
    return result.returncode or inspect_exit or 0


if __name__ == '__main__':
    raise SystemExit(main())
