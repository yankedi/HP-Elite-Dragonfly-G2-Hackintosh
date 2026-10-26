#!/usr/bin/env python3
"""Attempt an isolated Linux cross-build of the pinned framebuffer study.

Uses cached, hash-verified community inputs; never deploys an EFI or kext.
The original Latitude CLI recipe is a reference, not executed by this script.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile

from build_vesa_prototype import extract
from check_framebuffer_sources import safe_extract_archive

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".local"
# Fixed recipe date, not an inferred upstream timestamp. Prevents __DATE__ drift.
SOURCE_DATE_EPOCH = "1792022400"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_record(name):
    return json.loads((ROOT / name).read_text())


def verified_input(record, path_key="local_path", hash_key="sha256"):
    path = (ROOT / record[path_key]).resolve(strict=True)
    if not path.is_relative_to(PRIVATE) or not path.is_file():
        raise ValueError("Build input must be a cached private file")
    if digest(path) != record[hash_key]:
        raise ValueError(f"Input digest mismatch: {record[path_key]}")
    return path


def stage_source(run, patch_report, readiness):
    archive = verified_input(patch_report["source_archive"])
    source = safe_extract_archive(archive.read_bytes(), run / "weg")
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    for record in patch_report["patch_source"]["patches"]:
        patch = verified_input(record)
        subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)], check=True)
        subprocess.run(["git", "-C", str(source), "apply", str(patch)], check=True)
    inputs = readiness["external_inputs"]
    lilu = verified_input(inputs["lilu_resources"], "private_copy")
    extract(lilu, "Lilu.kext/", source / "Lilu.kext")
    sdk_archive = verified_input(inputs["mackernelsdk_candidate"], "private_copy", "archive_sha256")
    sdk = safe_extract_archive(sdk_archive.read_bytes(), run / "sdk")
    shutil.move(str(sdk), source / "MacKernelSDK")
    return source


def compile_sources(source, out, clang, run_command):
    obj_dir = out / "obj"
    obj_dir.mkdir()
    project = (source / "WhateverGreen.xcodeproj/project.pbxproj").read_text()
    version = re.search(r"MODULE_VERSION = ([0-9.]+);", project).group(1)
    sdk = source / "MacKernelSDK"
    resources = source / "Lilu.kext/Contents/Resources"
    common = [
        "-target", "x86_64-apple-macos10.6", "-O3", "-nostdinc", "-fno-builtin", "-fno-common",
        "-mkernel", "-fvisibility=hidden", "-fstrict-aliasing", "-mmmx", "-msse", "-msse2",
        "-msse3", "-mfpmath=sse", "-mssse3", "-ftree-vectorize", "-fno-non-call-exceptions",
        "-fno-asynchronous-unwind-tables", "-DKERNEL", "-DKERNEL_PRIVATE", "-DDRIVER_PRIVATE",
        "-DAPPLE", "-DNeXT", f"-DMODULE_VERSION={version}", "-DPRODUCT_NAME=WhateverGreen",
        "-I" + str(sdk / "Headers"), "-I" + str(resources), "-I" + str(resources / "Headers"),
        "-I" + str(source / "WhateverGreen"), "-I" + str(obj_dir), "-Wno-unknown-warning-option",
        "-ffile-prefix-map=" + str(source) + "=WhateverGreen",
        "-Wno-ossharedptr-misuse", "-Wno-vla", "-Wno-deprecated-declarations",
        "-Wno-inconsistent-missing-override", "-Wno-format",
    ]
    cpp_flags = ["-x", "c++", "-std=c++17", "-fno-rtti", "-fno-exceptions", "-fapple-kext", "-fcheck-new",
                 "-mllvm", "-disable-atexit-based-global-dtor-lowering"]
    sources = [(p, cpp_flags) for p in sorted((source / "WhateverGreen").glob("*.cpp"))]
    sources += [(resources / "Library/plugin_start.cpp", cpp_flags)]
    sources += [(p, []) for p in sorted((source / "WhateverGreen").glob("*.S"))]
    module = obj_dir / "WhateverGreen_info.c"
    module.write_text(
        '#include <mach/mach_types.h>\n'
        'extern kern_return_t _start(kmod_info_t *ki, void *data);\n'
        'extern kern_return_t _stop(kmod_info_t *ki, void *data);\n'
        '__private_extern__ kern_return_t WhateverGreen_kern_start(kmod_info_t *ki, void *data);\n'
        '__private_extern__ kern_return_t WhateverGreen_kern_stop(kmod_info_t *ki, void *data);\n'
        '__attribute__((visibility("default"))) '
        f'KMOD_EXPLICIT_DECL(as.vit9696.WhateverGreen, "{version}", _start, _stop)\n'
        '__private_extern__ kmod_start_func_t *_realmain = WhateverGreen_kern_start;\n'
        '__private_extern__ kmod_stop_func_t *_antimain = WhateverGreen_kern_stop;\n'
        '__private_extern__ int _kext_apple_cc = __APPLE_CC__;\n'
    )
    sources.append((module, ["-x", "c", "-std=c11"]))
    objects = []
    for path, flags in sources:
        obj = obj_dir / (path.stem + ".o")
        run_command("compile-" + path.stem, [clang, *flags, *common, "-c", str(path), "-o", str(obj)])
        magic, cpu, _, filetype = struct.unpack_from("<4I", obj.read_bytes())
        if (magic, cpu, filetype) != (0xFEEDFACF, 0x1000007, 1):
            raise ValueError(f"Not an x86_64 Mach-O object: {obj.name}")
        objects.append(obj)
    return version, objects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", default="clang")
    parser.add_argument("--linker", help="Mach-O ld64 supporting -kext (LLVM 21 lld does not)")
    parser.add_argument("--llvm-bin", required=True, help="directory containing llvm-nm and llvm-readobj")
    parser.add_argument("--compile-only", action="store_true", help="generate and compile objects without linking")
    args = parser.parse_args()
    if not args.compile_only and not args.linker:
        parser.error("--linker is required unless --compile-only is selected")
    root = PRIVATE / "framebuffer-build"
    root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    (run / "logs").mkdir()
    out = run / "out"
    out.mkdir()
    report = {"schema_version": 1, "status": "started", "run_directory": str(run.relative_to(ROOT)),
              "commands": [], "hp_boot_tested": False, "metal_tested": False, "deployed": False,
              "source_date_epoch": SOURCE_DATE_EPOCH, "resource_converter_native_comparison": False}

    def command(label, argv):
        result = subprocess.run([str(x) for x in argv], capture_output=True, timeout=180,
                                env={**os.environ, "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH, "LC_ALL": "C"})
        (run / "logs" / (label + ".stdout")).write_bytes(result.stdout)
        (run / "logs" / (label + ".stderr")).write_bytes(result.stderr)
        report["commands"].append({"label": label, "argv": [str(x) for x in argv], "exit_code": result.returncode})
        if result.returncode:
            raise RuntimeError(f"{label} failed (exit {result.returncode}): {result.stderr.decode(errors='replace')[-4000:]}")
        return result.stdout

    try:
        linker = Path(args.linker).resolve(strict=True) if args.linker else None
        clang = shutil.which(args.clang)
        if not clang:
            raise ValueError("clang executable not found")
        llvm = Path(args.llvm_bin).resolve(strict=True)
        report["tools"] = {"clang_version": command("clang-version", [clang, "--version"]).decode(),
                           "linker_path": str(linker) if linker else None,
                           "linker_sha256": digest(linker) if linker else None,
                           "llvm_nm_sha256": digest(llvm / "llvm-nm")}
        pins = read_record("manifests/framebuffer-patch-check.json")
        readiness = read_record("manifests/framebuffer-build-readiness.json")
        report["source_commit"] = pins["source_archive"]["commit"]
        report["latitude_commit"] = pins["patch_source"]["commit"]
        report["input_pins"] = {
            "source_archive": pins["source_archive"]["sha256"],
            "patches": [{"name": p["name"], "sha256": p["sha256"]} for p in pins["patch_source"]["patches"]],
            "lilu_debug": readiness["external_inputs"]["lilu_resources"]["sha256"],
            "mackernelsdk": readiness["external_inputs"]["mackernelsdk_candidate"]["archive_sha256"],
            "builder_sha256": digest(Path(__file__)),
            "resource_generator_sha256": digest(ROOT / "scripts/generate_weg_resources.py"),
        }
        source = stage_source(run, pins, readiness)
        # Pure-Python resource converter checks its pinned upstream inputs itself.
        command("resources", [sys.executable, str(ROOT / "scripts/generate_weg_resources.py"), str(source)])
        version, objects = compile_sources(source, out, clang, command)
        report["objects"] = [{"name": p.name, "sha256": digest(p)} for p in objects]
        if args.compile_only:
            imports = set()
            for obj in objects:
                symbols = command("imports-" + obj.stem, [llvm / "llvm-nm", "-u", obj]).decode().splitlines()
                imports.update(s.strip() for s in symbols)
            forbidden = {"___cxa_atexit", "___dso_handle", "_atexit", "_main"} & imports
            if forbidden:
                raise ValueError(f"Unexpected userspace runtime imports: {sorted(forbidden)}")
            report.update(status="compiled-objects-only", version=version, kext_linked=False,
                          userspace_atexit_imports_absent=True)
            print(f"Compiled {len(objects)} Mach-O objects; not linked: {(run / 'report.json').relative_to(ROOT)}")
            return 0
        sdk = source / "MacKernelSDK"
        # libkmodc++ is a universal archive in this SDK, not in Library/x86_64.
        # No empty libcc_kext stub: link with actual available inputs and inspect imports.
        libraries = [sdk / "Library/universal/libkmodc++.a", sdk / "Library/x86_64/libkmod.a"]
        report["libraries"] = [{"path": str(p.relative_to(source)), "sha256": digest(p)} for p in libraries]
        kext = out / "WhateverGreen.kext"
        binary = kext / "Contents/MacOS/WhateverGreen"
        binary.parent.mkdir(parents=True)
        command("link", [linker, "-arch", "x86_64", "-macosx_version_min", "10.6", "-kext", "-static",
                         "-dead_strip", *objects, *libraries, "-o", binary])
        magic, cpu, _, filetype = struct.unpack_from("<4I", binary.read_bytes())
        if (magic, cpu, filetype) != (0xFEEDFACF, 0x1000007, 11):
            raise ValueError("Linker output is not MH_KEXT_BUNDLE x86_64; refusing a mislabelled dylib/executable")
        text = (source / "WhateverGreen/Info.plist").read_text()
        for name, value in {"MODULE_VERSION": version, "EXECUTABLE_NAME": "WhateverGreen",
                            "PRODUCT_BUNDLE_IDENTIFIER": "as.vit9696.WhateverGreen",
                            "PRODUCT_NAME": "WhateverGreen", "PRODUCT_NAME:rfc1034identifier": "WhateverGreen"}.items():
            text = text.replace("$(" + name + ")", value)
        if "$(" in text:
            raise ValueError("Unexpanded Info.plist variable")
        info = plistlib.loads(text.encode())
        (kext / "Contents/Info.plist").write_bytes(plistlib.dumps(info, sort_keys=False))
        (out / "Licenses").mkdir()
        shutil.copyfile(source / "LICENSE.txt", out / "Licenses/WhateverGreen.txt")
        lilu_commit = readiness["external_inputs"]["lilu_resources"]["resolved_commit"]
        shutil.copyfile(ROOT / ".cache/licenses/Lilu" / (lilu_commit + ".txt"), out / "Licenses/Lilu.txt")
        symbols = command("undefined-symbols", [llvm / "llvm-nm", "-u", binary]).decode().splitlines()
        forbidden = {"___cxa_atexit", "___dso_handle", "_atexit", "_main"} & {s.strip() for s in symbols}
        if forbidden:
            raise ValueError(f"Unexpected userspace C++ runtime imports in kext: {sorted(forbidden)}")
        command("mach-header", [llvm / "llvm-readobj", "--file-headers", "--macho-version-min", binary])
        report.update(status="linked-experimental-kext", version=version, filetype=filetype,
                      binary_sha256=digest(binary), undefined_symbols=symbols,
                      signed=False, stripped=False,
                      scope="Linux cross-link only. Kernel/Lilu imports require macOS linker validation; no runtime or loading proof.")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report.update(status="blocked", blocker=str(error))
        print(str(error), file=sys.stderr)
    finally:
        (run / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        (root / "latest.json").write_text(json.dumps({"report": str((run / "report.json").relative_to(ROOT))}, indent=2) + "\n")
    print(f"{report['status']}: {(run / 'report.json').relative_to(ROOT)}")
    return 0 if report["status"] == "linked-experimental-kext" else 1


if __name__ == "__main__":
    raise SystemExit(main())
