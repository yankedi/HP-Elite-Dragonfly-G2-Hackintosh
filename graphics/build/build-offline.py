#!/usr/bin/env python3
"""Cross-build NootedGreen or HookCase without installation or target execution.

This is a publication copy of the GA47 cross-build helper. Set all tool and
dependency paths explicitly; this source-only snapshot deliberately does not
bundle Apple donor binaries, firmware headers, SDKs, toolchains, or signatures.
The original tested invocation also built from additional private external
inputs and is not claimed reproducible from this snapshot alone.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OLD = Path(os.environ['NG_BUILD_INPUTS']).expanduser()
SDK = Path(os.environ['SDKROOT']).expanduser()
CC = os.environ['CLANG_APPLE']
LD = os.environ['LD64_LLD']
LLVM_BIN = Path(os.environ.get('LLVM_BIN', '')).expanduser()
FIRMWARE_HEADERS_RAW = os.environ.get('NG_FIRMWARE_HEADERS', '')
FIRMWARE_HEADERS = Path(FIRMWARE_HEADERS_RAW).expanduser() if FIRMWARE_HEADERS_RAW else None
OUT = Path(os.environ.get('GRAPHICS_BUILD_OUT', str(ROOT / 'build/output'))).expanduser()
BUILD = OUT / 'hp'
SIGN = Path(os.environ['RCODESIGN']).expanduser()
# The original helper encoded one host's target install names and SDK version.
# Keep those userland-only inputs external and explicit in this publication copy.
USERLAND_INSTALL_NAME_DIR = os.environ.get('GRAPHICS_USERLAND_INSTALL_NAME_DIR')
XEDRV_INSTALL_NAME = os.environ.get('GRAPHICS_XEDRV_INSTALL_NAME')
GPUCOMPILER_PLUGIN_LLVM_INSTALL_NAME = os.environ.get('GRAPHICS_PLUGIN_LLVM_INSTALL_NAME')
TBD_RAW = os.environ.get('GRAPHICS_GPUCOMPILER_TBD')
TBD = Path(TBD_RAW).expanduser() if TBD_RAW else None


def run(*args, **kw):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kw)


def sign(path):
    run(SIGN, 'sign', '--config-file', '/dev/null', '--timestamp-url', 'none', path)


def remove_signature(path):
    """codesign --remove-signature equivalent for the thin x86_64 old plugin.

    Retain file offsets and unused trailing bytes; compact only load commands.
    install_name_tool and the upstream JSON then see the same header padding.
    """
    b = bytearray(path.read_bytes())
    assert b[:4] == bytes.fromhex('cffaedfe'), 'expected thin MH_MAGIC_64'
    count, size = struct.unpack_from('<II', b, 16)
    commands, p = [], 32
    for _ in range(count):
        cmd, n = struct.unpack_from('<II', b, p)
        assert n >= 8 and p + n <= 32 + size
        if cmd != 0x1d:
            commands.append(b[p:p+n])
        p += n
    assert p == 32 + size
    new = b''.join(commands)
    b[32:32+size] = new + bytes(size - len(new))
    struct.pack_into('<II', b, 16, len(commands), len(new))
    path.write_bytes(b)


def patch(path, table):
    b = bytearray(path.read_bytes())
    for x in json.loads(table.read_text()):
        off, old, new = x['off'], bytes.fromhex(x['old']), bytes.fromhex(x['new'])
        assert len(old) == len(new)
        assert b[off:off+len(old)] == old, f'{table.name}: original bytes mismatch at {off:#x}'
        b[off:off+len(new)] = new
    path.write_bytes(b)


def kext(name):
    src = ROOT / 'src' / name
    b = BUILD / (name + '.kext')
    obj = OUT / 'objects' / BUILD.name / name
    obj.mkdir(parents=True, exist_ok=True)
    (b / 'Contents/MacOS').mkdir(parents=True, exist_ok=True)
    hook = name == 'HookCase'
    bid, ver = ('org.smichaud.HookCase', '8.0.1') if hook else ('com.StezzaPilot.NootedGreen', '1.0.0')
    text = (src / 'Info.plist').read_text()
    for k, v in {'EXECUTABLE_NAME': name, 'PRODUCT_BUNDLE_IDENTIFIER': bid,
                 'PRODUCT_NAME': name, 'PRODUCT_NAME:rfc1034identifier': name,
                 'MODULE_VERSION': ver, 'CURRENT_PROJECT_VERSION': ver,
                 'DEVELOPMENT_LANGUAGE': 'en', 'MODULE_NAME': bid}.items():
        text = text.replace('$(' + k + ')', v)
    assert '$(' not in text
    info = plistlib.loads(text.encode())
    if hook:
        info.pop('IOKitPersonalities', None)
    (b / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    flags = ['-target', 'x86_64-apple-macos13.0', '-mkernel', '-nostdinc',
             '-fno-builtin', '-fno-common', '-fno-stack-protector', '-mmmx', '-msse', '-msse2',
             '-DKERNEL', '-DKERNEL_PRIVATE', '-DDRIVER_PRIVATE', '-DAPPLE', '-DNeXT', '-DDEBUG=1',
             '-isystem', str(OLD / 'MacKernelSDK/Headers'), '-I' + str(src),
             '-O0' if hook else '-O2', '-g',
             '-fno-use-cxa-atexit', '-fno-register-global-dtors-with-atexit',
             '-mllvm', '-disable-atexit-based-global-dtor-lowering',
             '-fno-asynchronous-unwind-tables']
    if hook:
        flags += ['-D__null_terminated=', '-D__stateful_pure=']
    else:
        if FIRMWARE_HEADERS is None:
            raise SystemExit('Set NG_FIRMWARE_HEADERS to the externally obtained pinned upstream NootedGreen directory; firmware headers are not redistributed here.')
        flags += ['-I' + str(FIRMWARE_HEADERS)]
        flags += ['-DAPPLE_KEXT_ASSERTIONS=1', '-DPRODUCT_NAME=' + name, '-DMODULE_VERSION=' + ver,
                  '-I' + str(OLD / 'Lilu.kext/Contents/Resources')]
    # Exact upstream direct-entry KMOD metadata, not the prior native-only variant.
    metadata = obj / 'info.c'
    metadata.write_text(f'''#include <mach/mach_types.h>
extern kern_return_t {name}_kern_start(kmod_info_t *, void *);
extern kern_return_t {name}_kern_stop(kmod_info_t *, void *);
__attribute__((visibility("default"))) KMOD_EXPLICIT_DECL({bid}, "{ver}", {name}_kern_start, {name}_kern_stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
__private_extern__ int _kext_apple_cc = __APPLE_CC__;
''')
    run(CC, *flags, '-c', metadata, '-o', obj / 'info.o')
    sources = [src / 'HookCase.cpp'] if hook else [src / (s + '.cpp') for s in
        'DisplayMergeNub DYLDPatches Firmware FirmwareADLP HDMI IntelDPLinkTraining kern_gen11 kern_genx kern_green kern_patcherplus kern_start'.split()]
    if hook:
        run(CC, *flags, '-c', src / 'HookCase.s', '-o', obj / 'HookCase_s.o')
    else:
        sources.append(OLD / 'Lilu.kext/Contents/Resources/Library/plugin_start.cpp')
    for s in sources:
        run(CC, *flags, '-std=gnu++14' if hook else '-std=gnu++17', '-nostdinc++',
            '-fno-exceptions', '-fno-rtti', '-fapple-kext', '-Wno-deprecated-declarations',
            '-Wno-inconsistent-missing-override', '-Wno-unused-parameter', '-c', s, '-o', obj / (s.stem + '.o'))
    run(LD, '-kext', '-arch', 'x86_64', '-platform_version', 'macos', '13.0', '26.5',
        '-export_dynamic', '-o', b / 'Contents/MacOS' / name,
        *sorted(obj.glob('*.o')), OLD / 'MacKernelSDK/Library/x86_64/libkmod.a')
    sign(b)


def dylib(source, target, install, *libs):
    obj = OUT / 'objects' / (source.stem + '.o')
    obj.parent.mkdir(parents=True, exist_ok=True)
    opts = ['-fno-objc-arc'] if source.suffix == '.m' else ['-std=c++17', '-isystem', str(SDK / 'usr/include/c++/v1')]
    run(CC, '-target', 'x86_64-apple-macos15.0', '-isysroot', SDK, '-O2',
        *opts, '-c', source, '-o', obj)
    run(LD, '-dylib', '-arch', 'x86_64', '-platform_version', 'macos', '15.0', '26.5',
        '-syslibroot', SDK, '-install_name', install, '-o', target, obj, '-lSystem', *libs)


def userland():
    required = {
        'GRAPHICS_USERLAND_INSTALL_NAME_DIR': USERLAND_INSTALL_NAME_DIR,
        'GRAPHICS_XEDRV_INSTALL_NAME': XEDRV_INSTALL_NAME,
        'GRAPHICS_PLUGIN_LLVM_INSTALL_NAME': GPUCOMPILER_PLUGIN_LLVM_INSTALL_NAME,
        'GRAPHICS_GPUCOMPILER_TBD': TBD,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit('Set userland-only external inputs: ' + ', '.join(missing))
    out = BUILD
    out.mkdir(parents=True, exist_ok=True)
    sle = OLD / 'sle_Internal/sle'
    sh, mtl = sle / 'AppleIntelGraphicsShared.bundle/Contents', sle / 'AppleIntelTGLGraphicsMTLDriver.bundle/Contents'
    lib = out / 'libxedrv.dylib'
    dylib(ROOT / 'macos/src/libxedrv.m', lib,
          XEDRV_INSTALL_NAME,
          '-framework', 'Foundation', '-framework', 'Metal', '-framework', 'IOSurface', '-lobjc')
    sign(lib)
    # Import and execute the unchanged upstream patcher. Translate only its
    # absolute macOS host-tool calls (PATH cannot override /usr/bin/plutil).
    def host_tool(argv, **kwargs):
        if argv[0] == '/usr/bin/plutil':
            assert argv[1:6] == ['-replace', 'Development.PoshDisable', '-integer', '1', argv[-1]]
            p = Path(argv[-1])
            d = plistlib.loads(p.read_bytes())
            d.setdefault('Development', {})['PoshDisable'] = 1
            p.write_bytes(plistlib.dumps(d))
        elif argv[0] == '/usr/bin/codesign':
            assert argv[1:4] == ['-f', '-s', '-']
            sign(argv[-1])
        elif argv[0] == '/bin/rm':
            assert argv[1:2] == ['-rf'] and Path(argv[-1]).parent == out
            shutil.rmtree(argv[-1])
        else:
            raise ValueError('unexpected upstream host command: ' + repr(argv))
        return subprocess.CompletedProcess(argv, 0)
    spec = importlib.util.spec_from_file_location('upstream_mtl17', ROOT / 'macos/patch-mtl17.py')
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    module.subprocess = SimpleNamespace(run=host_tool)
    saved_argv = sys.argv
    try:
        sys.argv = [str(spec.origin), str(sle / 'AppleIntelTGLGraphicsMTLDriver.bundle'), str(lib), str(out)]
        module.main()
    finally:
        sys.argv = saved_argv
    b = out / 'xe.bundle/Contents'
    b.mkdir(parents=True, exist_ok=True)
    for name in ['MacOS', 'Resources']:
        (b / name).mkdir(exist_ok=True)
    for name in ['Info.plist', 'PkgInfo', 'version.plist']:
        shutil.copy2(sh / name, b / name)
    for f in (sh / 'Resources').iterdir():
        shutil.copy2(f, b / 'Resources' / f.name)
    shutil.copy2(mtl / 'Resources/runtime.gpuencode.split', b / 'Resources')
    for name in ['libigc.dylib', 'libigcHSW.dylib', 'libIGIL-Metal.dylib', 'libISAProfilerDyn.dylib']:
        shutil.copy2(sh / 'MacOS' / name, b / 'MacOS' / name)
    dylib(ROOT / 'macos/src/llvm-bridge.cpp', b / 'MacOS/libLLVMbridge.dylib', USERLAND_INSTALL_NAME_DIR + '/libLLVMbridge.dylib',
          '-lc++', '-compatibility_version', '1.0.0', '-current_version', '3902.30.1', '-reexport_library', TBD)
    p = b / 'MacOS/libMTLIGCCompilerPluginOld.dylib'
    shutil.copy2(sh / 'MacOS/libMTLIGCCompilerPlugin.dylib', p)
    remove_signature(p)
    run(LLVM_BIN / 'llvm-install-name-tool', '-id', USERLAND_INSTALL_NAME_DIR + '/' + p.name,
        '-change', GPUCOMPILER_PLUGIN_LLVM_INSTALL_NAME, USERLAND_INSTALL_NAME_DIR + '/libLLVMbridge.dylib', p)
    patch(p, ROOT / 'macos/plugin-old-patches.json')
    dylib(ROOT / 'macos/src/compiler-adapter.cpp', b / 'MacOS/libMTLIGCCompilerPlugin.dylib',
          USERLAND_INSTALL_NAME_DIR + '/libMTLIGCCompilerPlugin.dylib', '-lc++', TBD, '-reexport_library', p)
    for f in sorted((b / 'MacOS').glob('*.dylib')):
        sign(f)
    sign(b.parent)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=['NootedGreen', 'HookCase'])
    parser.add_argument('--output-set', choices=['hp'], default='hp')
    args = parser.parse_args()
    BUILD = OUT / args.output_set
    if args.output_set == 'upstream':
        run('git', 'diff', '--exit-code', 'UPSTREAM_BASE', '--', 'src', 'macos', cwd=ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    kext(args.component)
