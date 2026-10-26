#!/usr/bin/env python3
"""Execute exact pinned framebuffer patch logic on a fake register bank on Linux."""

import hashlib
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from check_framebuffer_sources import safe_extract_archive
from build_framebuffer import verified_input

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = {
    "init": "void IGFX::TigerLakeRegisterMap::init()",
    "processKernel": "void IGFX::TigerLakeRegisterMap::processKernel(",
    "shouldLog": "bool IGFX::TigerLakeRegisterMap::shouldLog(",
    "mapAddress": "uint32_t IGFX::TigerLakeRegisterMap::mapAddress(",
    "record": "void IGFX::TigerLakeRegisterMap::record(",
    "publish": "void IGFX::TigerLakeRegisterMap::publish(",
    "snapshot": "void IGFX::TigerLakeRegisterMap::snapshot(",
    "takeSnapshot": "void IGFX::TigerLakeRegisterMap::takeSnapshot(",
    "prepareTranscoderA": "void IGFX::TigerLakeRegisterMap::prepareTranscoderA(",
    "read": "uint32_t IGFX::TigerLakeRegisterMap::read(",
    "write": "void IGFX::TigerLakeRegisterMap::write(",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def block(text, marker):
    """Extract a balanced C++ block without treating comments/strings as braces."""
    if text.count(marker) != 1:
        raise ValueError(f"Ambiguous source marker: {marker}")
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 0
    tokens = r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]'
    for match in re.finditer(tokens, text[opening:]):
        if match.group() == "{":
            depth += 1
        elif match.group() == "}":
            depth -= 1
            if depth == 0:
                end = opening + match.end()
                return text[start:end], {"start_line": text.count("\n", 0, start) + 1,
                                          "end_line": text.count("\n", 0, end) + 1}
    raise ValueError(f"Unterminated C++ block: {marker}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutations", action="store_true", help="also prove that two representative injected regressions are detected")
    args = parser.parse_args()
    root = ROOT / ".local/nonboot-graphics"
    root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    pins = json.loads((ROOT / "manifests/framebuffer-patch-check.json").read_text())
    source = safe_extract_archive(verified_input(pins["source_archive"]).read_bytes(), run / "source")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    for item in pins["patch_source"]["patches"]:
        patch = verified_input(item)
        subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)], check=True)
        subprocess.run(["git", "-C", str(source), "apply", str(patch)], check=True)
    cpp = (source / "WhateverGreen/kern_igfx.cpp").read_text()
    hpp = (source / "WhateverGreen/kern_igfx.hpp").read_text()
    selected = {}
    subject, location = block(hpp, "class TigerLakeRegisterMap: public PatchSubmodule")
    selected["class"] = {**location, "sha256": sha(subject.encode())}
    # Accessibility only: all enum values, fields, initializers and inline logic retained.
    subject = subject.replace("private:", "public:")
    pieces = ['#include "nonboot_graphics_host.hpp"', "struct IGFX { ReadSupport modMMIORegistersReadSupport; WriteSupport modMMIORegistersWriteSupport;",
              subject + " modTigerLakeRegisterMap; };", "static IGFX *callbackIGFX = nullptr;"]
    for name, marker in {"TGLReg": "namespace TGLReg {", "snapshotRegisters": "static const uint32_t tglSnapshotRegisters[] =", **FUNCTIONS}.items():
        text, location = block(cpp, marker)
        selected[name] = {**location, "sha256": sha(text.encode())}
        pieces.append(text + (";" if name == "snapshotRegisters" else ""))
    pieces.extend([
        "void IGFX::TigerLakeRegisterMap::lateCheck(void *) {}",
        "void IGFX::TigerLakeRegisterMap::publishThread(void *, void *) {}",
        "void IGFX::TigerLakeRegisterMap::traceThread(void *, void *) {}",
        "void IGFX::TigerLakeRegisterMap::traceArm(uint32_t) {}",
        "void IGFX::TigerLakeRegisterMap::traceNote(uint32_t, uint32_t, bool) {}",
        '#include "nonboot_graphics_cases.cpp"',
    ])
    translation = run / "subject.cpp"
    translation.write_text("\n".join(pieces) + "\n")
    compiler = shutil.which("clang++")
    if not compiler:
        raise SystemExit("clang++ required")
    command = [compiler, "-std=c++17", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
               "-I", str(ROOT / "tests"), str(translation), "-o", str(run / "subject-tests")]
    build = subprocess.run(command, capture_output=True, timeout=120)
    (run / "compile.stdout").write_bytes(build.stdout)
    (run / "compile.stderr").write_bytes(build.stderr)
    execution = None
    if build.returncode == 0:
        execution = subprocess.run([str(run / "subject-tests")], capture_output=True, timeout=30)
        (run / "test.stdout").write_bytes(execution.stdout)
        (run / "test.stderr").write_bytes(execution.stderr)
    result = json.loads(execution.stdout) if execution and execution.returncode == 0 else None
    mutations = []
    if result and args.mutations:
        faults = [
            ("wrong-dp-target", "return address - 0x64040 + 0x60540;", "return address - 0x64040 + 0x60544;", "golden write map"),
            ("drop-zero-duty", "if (out != 0 || address != 0xC8254)", "if (out != 0)", "zero duty actually reaches hardware model"),
        ]
        original = translation.read_text()
        for name, before, after, expected_failure in faults:
            if original.count(before) != 1:
                raise ValueError(f"Ambiguous mutation site: {name}")
            mutant = run / (name + ".cpp")
            mutant.write_text(original.replace(before, after))
            mutant_command = [str(mutant) if x == str(translation) else x for x in command]
            mutant_command[-1] = str(run / name)
            compiled = subprocess.run(mutant_command, capture_output=True, timeout=120)
            tested = subprocess.run([str(run / name)], capture_output=True, timeout=30) if compiled.returncode == 0 else None
            detected = tested is not None and tested.returncode == 1 and expected_failure in tested.stderr.decode(errors="replace")
            (run / (name + ".stderr")).write_bytes(tested.stderr if tested else compiled.stderr)
            mutations.append({"name": name, "compile_exit_code": compiled.returncode,
                              "test_exit_code": tested.returncode if tested else None,
                              "detected_at_expected_assertion": detected})
    report = {
        "schema_version": 1, "status": "passed" if result and all(x["detected_at_expected_assertion"] for x in mutations) else "failed",
        "source_commit": pins["source_archive"]["commit"], "patch_commit": pins["patch_source"]["commit"],
        "source_archive_sha256": pins["source_archive"]["sha256"],
        "patches": [{"name": x["name"], "sha256": x["sha256"]} for x in pins["patch_source"]["patches"]],
        "patched_cpp_sha256": sha(cpp.encode()), "patched_hpp_sha256": sha(hpp.encode()), "extracted_blocks": selected,
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "test_sources": {p.name: sha(p.read_bytes()) for p in sorted((ROOT / "tests").glob("nonboot_graphics*"))},
        "compile_command": command, "compiler_version": subprocess.check_output([compiler, "--version"], text=True),
        "compile_exit_code": build.returncode, "test_exit_code": execution.returncode if execution else None,
        "sanitizers": ["address", "undefined"], "result": result,
        "injected_regression_detection": mutations,
        "substitutions": ["PatchSubmodule/boot arguments/CPU info", "MMIO callbacks backed by std::map", "in-memory IORegistry/NVRAM counters",
                          "no-op async thread/trace/lateCheck paths; no concurrency coverage", "private to public for test access; no method-body changes"],
        "hardware_accessed": False, "macos_booted": False, "kext_loaded": False,
        "proves": "Selected original C++ logic executes correctly for tested synthetic vectors on Linux; not a hardware model or Apple driver/ABI validation",
    }
    for path in run.glob("*.std*"):
        report.setdefault("log_sha256", {})[path.name] = sha(path.read_bytes())
    (run / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (root / "latest.json").write_text(json.dumps({"report": str((run / "report.json").relative_to(ROOT))}) + "\n")
    print(json.dumps({"status": report["status"], "result": result, "report": str((run / "report.json").relative_to(ROOT))}))
    if report["status"] != "passed":
        print((build.stderr if build.returncode else execution.stderr).decode(errors="replace"))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
