#!/usr/bin/env python3
"""Offline fixed-source ANV attempt, gated on actual Darwin link probes.

GA43 requires a genuine SDK and successful runtime dependency probes before
copying/configuring Mesa. Never repeat GA42's sentinel-sysroot Meson attempts.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import io
import tarfile


ROOT = Path(__file__).resolve().parents[1]
GA40_ROOT = Path(os.environ.get("GA40_ROOT", str(ROOT.parent / "GA40-NullMoth-Intel"))).resolve()
SOURCE = Path(os.environ.get("MESA_SOURCE", str(GA40_ROOT / "sources/mesa"))).resolve()
EXPECTED = "31e9a6b2e95e30d84bf3177d1f497d063e59b6b2"
PATCHES = sorted((ROOT / "anv/patches").glob("*.patch"))


def checked_output(argv: list[str]) -> str:
    return subprocess.check_output(argv, text=True).strip()


def unwrapped_compiler(name: str) -> str:
    candidate = os.environ.get('DARWIN_CC' if name == 'clang' else 'DARWIN_CXX') or shutil.which(name)
    if not candidate:
        raise SystemExit(f'{name} is absent')
    path = Path(candidate).resolve()
    # Nix wrappers inject Linux include and linker choices even for -target.
    # Discover the same genuine binary used by the existing native build.
    if 'wrapper' in str(path):
        text = path.read_text()
        suffix = r'\+\+' if name == 'clang++' else ''
        match = re.search(r'/nix/store/[^\s\"\x27]+/bin/clang' + suffix + r'(?=[\s\"\x27])', text)
        if not match:
            raise SystemExit(f'cannot unwrap {path}; supply DARWIN_CC/DARWIN_CXX')
        path = Path(match.group(0))
    if not path.is_file():
        raise SystemExit(f'compiler is absent: {path}')
    return str(path)


def main() -> int:
    sdk = os.environ.get('DARWIN_SDK')
    linker = os.environ.get('DARWIN_LD')
    if not sdk or not linker:
        print('BLOCKED: provide legal complete DARWIN_SDK, modern DARWIN_LD and '
              'DARWIN_LLVM_BIN; fresh strict probes run inside gate; no Meson run', file=sys.stderr)
        return 2
    sysroot = Path(sdk).resolve()
    required = ['SDKSettings.json', 'usr/include/stdlib.h', 'usr/include/c++/v1/string',
                'usr/lib/libSystem.tbd']
    missing = [s for s in required if not (sysroot/s).is_file()]
    if missing:
        print('BLOCKED: incomplete user SDK: '+', '.join(missing), file=sys.stderr)
        return 2
    if not Path(linker).is_file() or not os.access(linker, os.X_OK):
        print('BLOCKED: Darwin linker is not executable', file=sys.stderr)
        return 2
    llvm_bin = Path(os.environ.get('DARWIN_LLVM_BIN', '')).resolve()
    if not all((llvm_bin / n).is_file() for n in ('llvm-ar', 'llvm-strip', 'llvm-readobj', 'llvm-objdump')):
        print('BLOCKED: DARWIN_LLVM_BIN must contain Mach-O archive/strip/inspection tools', file=sys.stderr)
        return 2
    clang = unwrapped_compiler('clang')
    clangxx = unwrapped_compiler('clang++')
    compiler_hashes = [line.split()[0] for line in checked_output(['sha256sum', clang, clangxx]).splitlines()]
    if compiler_hashes[0] != compiler_hashes[1] or checked_output([clang, '-print-resource-dir']) != checked_output([clangxx, '-print-resource-dir']):
        print('BLOCKED: C/C++ must have matching Clang binary hash/resource identity', file=sys.stderr)
        return 2
    # Never trust caller-supplied/stale probe JSON. Run current sources and
    # current tool/SDK paths immediately before the Mesa copy/configure.
    label = f"anv-gate-{time.time_ns()}-{os.getpid()}"
    probe_command = [sys.executable, '-B', str(ROOT/'tools/darwin-probes.py'), label,
                     '--clang', clang, '--lld', str(Path(linker).resolve()),
                     '--readobj', str(llvm_bin/'llvm-readobj'), '--sdk', str(sysroot)]
    probe_run = subprocess.run(probe_command, cwd=ROOT, check=False)
    if probe_run.returncode:
        print('BLOCKED: fresh strict probe process failed; no Meson run', file=sys.stderr)
        return 2
    probe = json.loads((ROOT/'logs'/label/'result.json').read_text())
    if probe.get('schema') != 'ga43-enforced-probes-v2' or probe.get('sdk') != str(sysroot) or probe.get('strict_pass') is not True:
        print('BLOCKED: fresh output/import/LLVM contracts failed; no Meson run', file=sys.stderr)
        return 2
    sdk_status = 'explicit legal user SDK; strict probes passed (not runtime)'

    actual = checked_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"])
    if actual != EXPECTED:
        raise SystemExit(f"Mesa pin mismatch: expected {EXPECTED}, got {actual}")
    if checked_output(["git", "--no-optional-locks", "-C", str(SOURCE), "status", "--porcelain"]):
        raise SystemExit("pinned Mesa source is not clean")

    run_id = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}"
    work = ROOT / "anv/work" / f"darwin-attempt-{run_id}"
    if work.exists():
        raise SystemExit(f"refusing existing attempt path: {work}")
    # Export only pinned tracked files, never inherited ignored wrap caches.
    work.mkdir(parents=True)
    archive = subprocess.check_output(['git', '-C', str(SOURCE), 'archive', EXPECTED])
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:
        t.extractall(work, filter='data')
    for patch in PATCHES:
        subprocess.run(
            ["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(patch)],
            cwd=work,
            check=True,
        )

    resource_dir = checked_output([clang, "-print-resource-dir"])
    sdk_version = json.loads((sysroot/'SDKSettings.json').read_text())['Version']
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,2}', sdk_version):
        raise SystemExit('invalid SDK version')
    platform_link = f'-Wl,-platform_version,macos,26.0,{sdk_version}'
    cross = work / "darwin-cross.ini"
    sysroot_arg = str(sysroot)
    cross.write_text(
        "[binaries]\n"
        f"c = '{clang}'\n"
        f"cpp = '{clangxx}'\n"
        f"objc = '{clang}'\n"
        f"ar = '{llvm_bin / 'llvm-ar'}'\n"
        f"strip = '{llvm_bin / 'llvm-strip'}'\n"
        "\n[built-in options]\n"
        f"c_args = ['-target', 'x86_64-apple-macos26', '-isysroot', '{sysroot_arg}', '-resource-dir', '{resource_dir}']\n"
        f"cpp_args = ['-target', 'x86_64-apple-macos26', '-isysroot', '{sysroot_arg}', '-stdlib=libc++']\n"
        f"objc_args = ['-target', 'x86_64-apple-macos26', '-isysroot', '{sysroot_arg}']\n"
        f"c_link_args = ['-target', 'x86_64-apple-macos26', '-isysroot', '{sysroot_arg}', '--ld-path={linker}', '{platform_link}']\n"
        f"cpp_link_args = ['-target', 'x86_64-apple-macos26', '-isysroot', '{sysroot_arg}', '-stdlib=libc++', '--ld-path={linker}', '{platform_link}']\n"
        f"objc_link_args = ['-target', 'x86_64-apple-macos26', '-isysroot', '{sysroot_arg}', '--ld-path={linker}', '{platform_link}']\n"
        "\n[host_machine]\n"
        "system = 'darwin'\n"
        "cpu_family = 'x86_64'\n"
        "cpu = 'x86_64'\n"
        "endian = 'little'\n"
        "\n[properties]\n"
        "needs_exe_wrapper = true\n"
        f"sys_root = '{sysroot_arg}'\n"
        f"pkg_config_libdir = {os.environ.get('DARWIN_PKG_CONFIG_LIBDIR', '').split(':') if os.environ.get('DARWIN_PKG_CONFIG_LIBDIR') else []!r}\n"
    )
    build = work / "build"
    meson = [sys.executable, "-B", "-m", "mesonbuild.mesonmain"]
    configure = meson + [
        "setup",
        str(build),
        str(work),
        "--cross-file",
        str(cross),
        "--buildtype=release",
        "--wrap-mode=nodownload",
        "--force-fallback-for=",
        "-Dplatforms=macos",
        "-Dgallium-drivers=",
        "-Dvulkan-drivers=intel",
        "-Dopengl=false",
        "-Dglx=disabled",
        "-Degl=disabled",
        "-Dgbm=disabled",
        "-Dllvm=enabled",
        "-Dmesa-clc=enabled",
        "-Dintel-elk=false",
        "-Dintel-darwin=true",
        "-Dwerror=false",
        "-Dbuild-tests=false",
        "-Dtools=",
        "-Dvideo-codecs=",
    ]
    if os.environ.get('DARWIN_REUSE_PINNED_CLC') == '1':
        # Mesa's supported system mode runs the already sealed SAME-SOURCE
        # Linux build tools on the build machine. It does not disable CLC,
        # ship ELF in the ICD, or replace ANV's Intel compiler.
        old = Path(os.environ.get("GA41_ANV_COMPILER_BUILD", str(ROOT.parent / "GA41-i915-XNU/anv/build/mesa-anv/src/compiler"))).resolve()
        tools = {
            old/'clc/mesa_clc': '6e95a3e12526fb93d0eff06ef6d395e6be0865dd47c52f6939b6dc86f289c231',
            old/'spirv/vtn_bindgen2': '74d418aeb5cad82bd30d358fd8233f7cb5baa0bc0001d398d985481ef2f7fb44',
        }
        for program, expected_hash in tools.items():
            if checked_output(['sha256sum', str(program)]).split()[0] != expected_hash:
                raise SystemExit('pinned native CLC tool changed: ' + str(program))
        configure = [x for x in configure if x not in ('-Dllvm=enabled', '-Dmesa-clc=enabled')]
        configure += ['-Dllvm=auto', '-Dmesa-clc=system']
    if os.environ.get('DARWIN_LIBDRM_PREFIX'):
        configure += ['-Dintel-darwin-libdrm-prefix=' +
                      str(Path(os.environ['DARWIN_LIBDRM_PREFIX']).resolve())]
    print(f"SDK_STATUS: {sdk_status}")
    print(f"MESA_COMMIT: {actual}")
    print(f"PATCHES: {', '.join(p.name for p in PATCHES)}")
    print("DARWIN_CONFIGURE_COMMAND:")
    print(" ".join(configure))
    meson_env = os.environ.copy()
    if os.environ.get("DARWIN_MESON_PYTHONPATH"):
        meson_env["PYTHONPATH"] = os.environ["DARWIN_MESON_PYTHONPATH"]
    if os.environ.get('DARWIN_REUSE_PINNED_CLC') == '1':
        meson_env['PATH'] = str(old/'clc') + ':' + str(old/'spirv') + ':' + meson_env['PATH']
    configure_result = subprocess.run(configure, cwd=ROOT, env=meson_env, check=False)

    # Meson owns generated headers, platform defines and native CLC commands.
    # Do not scatter-compile an unconfigured TU with missing generated inputs.
    build_exit = None
    if configure_result.returncode == 0:
        build_exit = subprocess.run(['ninja', '-C', str(build), '-j4'],
                                    cwd=ROOT, env=meson_env, check=False).returncode
    final_link_exit = None
    final_dir = work/'strict-final-link'
    if configure_result.returncode == 0 and (build/'src/intel/vulkan/libvulkan_intel.dylib.p/anv_gem.c.o').is_file():
        # Preserve Ninja's actual failure. A separate strict final link handles
        # ELF optional-NULL semantics without changing the original build log.
        # Missing real input archives/strong imports still fail closed.
        final_link_exit = subprocess.run([sys.executable, '-B', str(ROOT/'tools/link-darwin-anv.py'),
            str(build), str(final_dir)], cwd=ROOT, env=meson_env, check=False).returncode
    tu_object = build/'src/intel/compiler/brw/libintel_compiler.a.p/brw_eu.c.o'
    tu_inspect_exit = None
    if tu_object.is_file():
        tu_inspect_exit = subprocess.run([sys.executable, '-B', str(ROOT/'tools/inspect-darwin-probe.py'),
            str(tu_object), '--kind', 'object'], cwd=ROOT, check=False).returncode

    receipt = {
        "schema": "ga43-anv-darwin-attempt-v2",
        "fresh_probe_log": str(ROOT/'logs'/label),
        "mesa_commit": actual,
        "patches": [p.name for p in PATCHES],
        "work": str(work),
        "sdk_status": sdk_status,
        "sysroot": sysroot_arg,
        "configure_exit": configure_result.returncode,
        "build_exit": build_exit,
        "strict_final_link_exit": final_link_exit,
        "strict_final_artifact": str(final_dir/'libvulkan_intel.dylib'),
        "real_mesa_tu_inspect_exit": tu_inspect_exit,
        "artifact": {
            "path": str(tu_object),
            "exists": tu_object.exists(),
            "kind": "x86_64 Mach-O object" if tu_inspect_exit == 0 else "unverified or absent",
        },
        "dependency_downloads": "disabled by --wrap-mode=nodownload",
        "network_observation": "not monitored; no fetch command requested",
        "device_access": "not used",
    }
    (work / "attempt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    if configure_result.returncode: return configure_result.returncode
    if final_link_exit is not None: return final_link_exit or tu_inspect_exit or 0
    return build_exit or tu_inspect_exit or 0


if __name__ == "__main__":
    sys.exit(main())
