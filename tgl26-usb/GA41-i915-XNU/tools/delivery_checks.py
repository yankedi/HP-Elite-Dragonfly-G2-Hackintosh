#!/usr/bin/env python3
"""Audit actual deliverables without loading an ICD, opening a GPU or building."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess

R = Path(__file__).resolve().parents[1]
checks = []

def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def check(name, condition):
    if not condition:
        raise RuntimeError(name)
    checks.append(name)

icd = R / "anv/artifacts/lib/libvulkan_intel.so"
header = icd.read_bytes()[:64]
check("actual Linux ELF64 x86_64 shared ICD", header[:5] == b"\x7fELF\x02" and
      struct.unpack_from("<HH", header, 16) == (3, 62))
check("Linux ICD pinned successful artifact hash", digest(icd) ==
      "e8c99be081ec15eeae6b7fdc5178c2c1871f5d1c79a5e5dd7dff50e69e15fe5a")
symbol_text = subprocess.run(["nm", "-D", "--defined-only", str(icd)],
                             check=True, capture_output=True, text=True).stdout
check("3 Vulkan ICD loader symbols", all(s in symbol_text for s in
      ("vk_icdGetInstanceProcAddr", "vk_icdGetPhysicalDeviceProcAddr",
       "vk_icdNegotiateLoaderICDInterfaceVersion")))
json_path = R / "anv/artifacts/share/vulkan/icd.d/intel_icd.x86_64.json"
check("ICD JSON exact hash and version", digest(json_path) ==
      "f29074f09b7e0b5283a7b842f07ecf8b79395908b0c7b382084d695c3fb27736" and
      json.loads(json_path.read_text())["ICD"]["api_version"] == "1.4.354")
check("required mesa_clc exists", (R / "anv/build/mesa-anv/src/compiler/clc/mesa_clc").is_file())
spv = list((R / "anv/build/mesa-anv/src/intel/shaders").rglob("*.spv"))
check("8 generated internal shader SPIRV binaries", len(spv) == 8 and
      all(p.read_bytes()[:4] == b"\x03\x02\x23\x07" for p in spv))
for name in ("gx_gem", "gx_ioctl", "xnu_copy", "xnu_memory", "abi_compile"):
    b = (R / "build/xnu-final" / (name + ".o")).read_bytes()
    check("native MachO relocatable " + name,
          struct.unpack_from("<I", b)[0] == 0xFEEDFACF and
          struct.unpack_from("<I", b, 4)[0] == 0x01000007 and
          struct.unpack_from("<I", b, 12)[0] == 1)
reuse = json.loads((R / "sources/i915-function-reuse.json").read_text())
generated = (R / "i915-xnu/gem/upstream_create.inc").read_text()
for row in reuse:
    source = (R / row["source"]).read_text()
    a = source.index("static int i915_gem_publish(" if row["function"] == "i915_gem_publish"
                     else "int\ni915_gem_create_ioctl(")
    b = source.index("{", a) + 1
    depth = 1
    while depth:
        depth += (source[b] == "{") - (source[b] == "}")
        b += 1
    body = source[a:b] + "\n"
    check("verbatim upstream function " + row["function"], body in generated and
          hashlib.sha256(body.encode()).hexdigest() == row["sha256"])
record = json.loads((R / "logs/reviewed-tests-001/command.json").read_text())
check("actual final CPU tests exit0 with sanitizer options", record["exit_code"] == 0 and
      "ASAN_OPTIONS=detect_leaks=1:abort_on_error=1" in record["argv"] and
      "100% tests passed" in (R / "logs/reviewed-tests-001/stdout.txt").read_text())
check("GA40 independent readonly verification passed", '"status": "PASS"' in
      (R / "logs/ga40-readonly-verify-001/stdout.txt").read_text())
check("failure retention gap disclosed, not falsely passed", "不满足" in
      (R / "FINAL-REPORT.md").read_text())
check("complete original review and regression preserved",
      (R / "audit/review-001/repro_fd_path_swap.log").read_text().startswith("observed success"))
print(json.dumps({"status": "PASS", "checks": checks, "count": len(checks),
                  "meaning": "artifact and evidence audit; strict raw-log-retention remains UNMET",
                  "hardware_approval": "NO"}, ensure_ascii=False, indent=2))
