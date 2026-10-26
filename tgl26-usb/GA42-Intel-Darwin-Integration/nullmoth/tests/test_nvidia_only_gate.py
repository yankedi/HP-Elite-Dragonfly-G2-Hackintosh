#!/usr/bin/env python3
"""Apply and execute the corrected NullMoth vendor/ICD policy.

The test applies the patch to the real GA40 checkout, extracts the original C
functions (including the original I/O-registry vendor helper), and compiles a
small registry model. It positively exercises Intel ANV, AMD RADV, NVIDIA NVK,
explicit multi-GPU binding, and unknown fail-closed behavior.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import re
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
SOURCE = ROOT.parent / "GA40-NullMoth-Intel" / "sources" / "nullmoth"
PATCH = ROOT / "nullmoth" / "patches" / "0001-nvidia-only-accelerator-gate.patch"
PATCHES = sorted(PATCH.parent.glob("*.patch"))


def function(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"unterminated {signature}")


def run() -> None:
    assert SOURCE.is_dir(), SOURCE
    assert subprocess.check_output(
        ["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True
    ).strip() == "47f818b11cef59acb480210afdf9065fdd44e356"
    with tempfile.TemporaryDirectory(prefix="nm-gate-") as td:
        work = Path(td) / "nullmoth"
        shutil.copytree(SOURCE, work, ignore=shutil.ignore_patterns(".git", "build"))
        for patch in PATCHES:
            applied = subprocess.run(
                ["patch", "-p1", "--fuzz=0", "--forward", "--batch", "-i", str(patch)],
                cwd=work, check=False, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True,
            )
            print(applied.stdout, end="")
            applied.check_returncode()
        vk = (work / "plugin/nvmtl_vk.c").read_text()
        device = (work / "plugin/NVMTLDevice.m").read_text()
        initializer = function(vk, "static int nvmtl_vk_initialize(void)")
        assert initializer.index("nvmtl_vk_freeze_vendor();") < initializer.index("dlopen(")
        guard_end = initializer.index('    if (!getenv("NVRM_FLUSH_TIMEOUT_MS"))')
        startup_guard = initializer[:guard_end] + "    return 0;\n}"
        assert 'if (!selected_lib || !selected_json)' in startup_guard
        assert 'dlopen(selected_lib,' in initializer
        assert 'setenv("VK_ICD_FILENAMES", selected_json,' in initializer
        assert initializer.index("nvmtl_vk_loader_env_matches(selected_json)") < initializer.index("dlopen(NVMTL_LOADER")
        vendor = (work / "plugin/NVMTLVendorCompiler.m").read_text()
        sass = (work / "plugin/NVMTLSass.m").read_text()
        assert 'IOObjectConformsTo(accel, "NMXAccel")' in vk
        assert 'IOServiceMatching("NMXAccel")' in vk
        assert 'case 0x8086: return "/Library/GPUBundles/nvmtl/intel_icd.json"' in vk
        assert 'case 0x8086: return "/Library/GPUBundles/nvmtl/libvulkan_intel.dylib"' in vk
        assert "if (!mine || !live || mine != live)" in device
        assert 'mine && mine != live' not in device
        assert 'live == 0x8086 ? "Intel, ANV"' in device
        assert 'nvmtl_vk_vendor() == 0x10de' in vendor
        assert 'nvmtl_vk_vendor() != 0x10de' in sass
        gate = re.search(
            r"if \((!mine \|\| !live \|\| mine != live)\) \{", device
        )
        assert gate, "patched NVMTLDevice binding gate was not found"
        device_gate = gate.group(1)

        funcs = "\n\n".join(
            [
                function(vk, "static uint16_t nvmtl_pci_vendor_of"),
                function(vk, "uint16_t nvmtl_vk_set_accelerator"),
                function(vk, "static uint16_t nvmtl_vk_vendor_locked"),
                function(vk, "uint16_t nvmtl_vk_vendor(void)"),
                function(vk, "static void nvmtl_vk_freeze_vendor"),
                function(vk, "static const char *nvmtl_vk_icd_json"),
                function(vk, "static inline const char *nvmtl_icd_lib_path"),
                function(vk, "static int nvmtl_vk_loader_env_matches"),
            ]
        )
        harness = f"""
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#define R_OK 4
typedef unsigned char UInt8;
typedef unsigned long mach_port_t;
typedef unsigned long io_service_t;
typedef unsigned long io_registry_entry_t;
typedef void *CFTypeRef;
typedef void *CFDataRef;
typedef unsigned long CFTypeID;
#define CFSTR(x) x
#define kCFAllocatorDefault 0
enum {{ kIOMainPortDefault = 1, kIOServicePlane = 0, KERN_SUCCESS = 0 }};
static int has_nv_service, has_nmx_service;
static uint16_t nmx_vendor;
struct fake_data {{ UInt8 b[2]; }};
static struct fake_data data;
static void *IOServiceMatching(const char *name) {{ return (void *)name; }}
static io_service_t IOServiceGetMatchingService(int port, void *matching) {{
    (void)port;
    if (!strcmp((const char *)matching, "NVAccel")) return has_nv_service ? 7 : 0;
    if (!strcmp((const char *)matching, "NMXAccel")) return has_nmx_service ? 9 : 0;
    return 0;
}}
static int IOObjectConformsTo(mach_port_t object, const char *name) {{
    return (object == 7 && !strcmp(name, "NVAccel")) ||
           (object == 9 && !strcmp(name, "NMXAccel"));
}}
static int IORegistryEntryGetParentEntry(io_registry_entry_t entry, int plane, io_registry_entry_t *parent) {{
    (void)plane; if (!entry) return 1; *parent = 1; return KERN_SUCCESS;
}}
static CFTypeRef IORegistryEntryCreateCFProperty(io_registry_entry_t entry, const char *key, void *alloc, int opts) {{
    (void)entry; (void)alloc; (void)opts;
    if (strcmp(key, "vendor-id")) return NULL;
    data.b[0] = (UInt8)(nmx_vendor & 0xff); data.b[1] = (UInt8)(nmx_vendor >> 8);
    return nmx_vendor ? (CFTypeRef)&data : NULL;
}}
static CFTypeID CFGetTypeID(CFTypeRef value) {{ (void)value; return 1; }}
static CFTypeID CFDataGetTypeID(void) {{ return 1; }}
static long CFDataGetLength(CFDataRef value) {{ return value ? 2 : 0; }}
static const UInt8 *CFDataGetBytePtr(CFDataRef value) {{ return ((struct fake_data *)value)->b; }}
static void CFRelease(CFTypeRef value) {{ (void)value; }}
static void IOObjectRelease(io_service_t object) {{ (void)object; }}
static int access(const char *path, int mode) {{ (void)path; (void)mode; return 0; }}
static uint16_t g_vendor;
static int g_accelerator_bound;
static int g_vendor_frozen;
static pthread_mutex_t g_vendor_lock = PTHREAD_MUTEX_INITIALIZER;
{funcs}
static int g_state;
static void nvlog(const char *fmt, ...) {{ (void)fmt; }}
{startup_guard}
static void reset(void) {{
    g_vendor = 0; g_accelerator_bound = 0; g_vendor_frozen = 0;
    has_nv_service = 0; has_nmx_service = 0; nmx_vendor = 0; g_state = 0;
    unsetenv("NVMTL_ICD_LIB");
    unsetenv("VK_DRIVER_FILES"); unsetenv("VK_ICD_FILENAMES"); unsetenv("VK_ADD_DRIVER_FILES");
}}
static int check(int got, int want, const char *what) {{
    if (got != want) {{ fprintf(stderr, "FAIL %s: got %d want %d\\n", what, got, want); return 1; }}
    return 0;
}}
static int nvmtl_device_binding_allowed(uint16_t mine, uint16_t live) {{
    if ({device_gate}) return 0;
    return 1;
}}
static void *bind_accelerator(void *p) {{
    (void)nvmtl_vk_set_accelerator((mach_port_t)(uintptr_t)p);
    return NULL;
}}
int main(void) {{
    int failures = 0;
    reset();
    failures += check(nvmtl_vk_vendor(), 0, "no accelerator has no vendor");
    failures += check(nvmtl_vk_icd_json() == NULL, 1, "no accelerator has no ICD json");
    failures += check(nvmtl_icd_lib_path() == NULL, 1, "no accelerator has no ICD library");
    nvmtl_vk_freeze_vendor(); has_nv_service = 1;
    failures += check(nvmtl_vk_vendor(), 0, "unknown frozen startup never rediscovers");

    reset();
    failures += check(nvmtl_vk_initialize(), -1, "unknown startup rejected before loader calls");
    failures += check(nvmtl_vk_initialize(), -1, "unknown startup stays failed on repeated init");
    reset(); has_nv_service = 1;
    (void)nvmtl_vk_set_accelerator(11);
    failures += check(nvmtl_vk_initialize(), -1, "explicit unknown cannot fall back to discovered NVIDIA");
    reset(); nmx_vendor = 0x8086; (void)nvmtl_vk_set_accelerator(9);
    failures += check(nvmtl_vk_initialize(), 0, "Intel passes real pre-loader startup guard");
    const char *json = nvmtl_vk_icd_json();
    failures += check(nvmtl_vk_loader_env_matches(json), 1, "Intel fallback unconfigured environment");
    setenv("VK_ICD_FILENAMES", "/unrelated/nvidia.json", 1);
    failures += check(nvmtl_vk_loader_env_matches(json), 0, "reject unrelated legacy ICD");
    setenv("VK_ICD_FILENAMES", json, 1);
    failures += check(nvmtl_vk_loader_env_matches(json), 1, "allow exact selected legacy ICD");
    setenv("VK_DRIVER_FILES", "/unrelated/nvidia.json", 1);
    failures += check(nvmtl_vk_loader_env_matches(json), 0, "modern override cannot bypass legacy guard");
    setenv("VK_DRIVER_FILES", json, 1);
    failures += check(nvmtl_vk_loader_env_matches(json), 1, "allow matching modern and legacy ICDs");
    setenv("VK_ADD_DRIVER_FILES", "/extra/nvidia.json", 1);
    failures += check(nvmtl_vk_loader_env_matches(json), 0, "reject additional ambient drivers");

    reset(); has_nmx_service = 1; nmx_vendor = 0x8086;
    failures += check(nvmtl_vk_vendor(), 0x8086, "unbound Intel NMXAccel discovery");
    failures += check(strstr(nvmtl_vk_icd_json(), "intel_icd.json") != NULL, 1, "Intel ANV ICD json");
    failures += check(strstr(nvmtl_icd_lib_path(), "libvulkan_intel.dylib") != NULL, 1, "Intel ANV ICD library");

    reset(); has_nv_service = 1; has_nmx_service = 1; nmx_vendor = 0x8086;
    failures += check(nvmtl_vk_set_accelerator(9), 0x8086, "authenticated Intel NMXAccel binding");
    failures += check(nvmtl_vk_vendor(), 0x8086, "explicit Intel binding beats system NVIDIA");
    failures += check(strstr(nvmtl_vk_icd_json(), "intel_icd.json") != NULL, 1, "explicit Intel selects ANV ICD");
    failures += check(strstr(nvmtl_icd_lib_path(), "libvulkan_intel.dylib") != NULL, 1, "explicit Intel selects ANV library");
    failures += check(nvmtl_device_binding_allowed(0x8086, 0x8086), 1, "Intel NVMTLDevice binding is accepted");
    failures += check(nvmtl_device_binding_allowed(0x8086, 0x10de), 0, "cross-vendor NVMTLDevice binding is refused");
    failures += check(nvmtl_device_binding_allowed(0, 0x8086), 0, "unknown NVMTLDevice binding is refused");
    setenv("NVMTL_ICD_LIB", "/tmp/private-nvk.dylib", 1);
    failures += check(strstr(nvmtl_icd_lib_path(), "libvulkan_intel.dylib") != NULL, 1, "Intel ignores private ICD override");

    reset(); has_nv_service = 1; has_nmx_service = 1; nmx_vendor = 0x1234;
    failures += check(nvmtl_vk_set_accelerator(9), 0, "unknown NMX binding refused");
    failures += check(nvmtl_vk_vendor(), 0, "unknown binding does not fall back to NVIDIA");
    failures += check(nvmtl_vk_icd_json() == NULL, 1, "unknown binding has no ICD json");

    reset(); has_nv_service = 1;
    failures += check(nvmtl_vk_vendor(), 0x10de, "unbound NVIDIA discovery");
    failures += check(strstr(nvmtl_vk_icd_json(), "nvk_icd.json") != NULL, 1, "NVIDIA NVK ICD json");
    failures += check(strstr(nvmtl_icd_lib_path(), "libvulkan_nouveau.dylib") != NULL, 1, "NVIDIA NVK library");

    reset();
    failures += check(nvmtl_vk_set_accelerator(7), 0x10de, "NVAccel accepted");
    failures += check(nvmtl_vk_vendor(), 0x10de, "explicit NVIDIA identity");

    reset(); nmx_vendor = 0x8086;
    failures += check(nvmtl_vk_set_accelerator(9), 0x8086, "first explicit Intel binding");
    failures += check(nvmtl_vk_set_accelerator(7), 0x10de, "second binding reports its own vendor");
    failures += check(nvmtl_vk_vendor(), 0x8086, "second binding cannot mutate Intel backend");
    nvmtl_vk_freeze_vendor();
    failures += check(nvmtl_vk_set_accelerator(7), 0x10de, "late NVIDIA bind identifies mismatch");
    failures += check(nvmtl_vk_vendor(), 0x8086, "initialized Intel identity is frozen");
    failures += check(nvmtl_device_binding_allowed(0x10de, nvmtl_vk_vendor()), 0, "late NVIDIA device rejected");

    reset(); has_nv_service = 1; nmx_vendor = 0x8086;
    nvmtl_vk_freeze_vendor(); /* Vulkan before any explicit Metal binding */
    failures += check(nvmtl_vk_set_accelerator(9), 0x8086, "late Intel reports its own vendor");
    failures += check(nvmtl_vk_vendor(), 0x10de, "initialized discovery cannot switch to Intel");
    failures += check(nvmtl_device_binding_allowed(0x8086, nvmtl_vk_vendor()), 0, "late Intel device rejected");

    reset(); has_nv_service = 1; nmx_vendor = 0x8086;
    (void)nvmtl_vk_vendor(); /* discovery alone is not initialization */
    (void)nvmtl_vk_set_accelerator(9);
    failures += check(nvmtl_vk_vendor(), 0x8086, "explicit binding may override discovery before init");

    for (int i = 0; i < 100; i++) {{
        reset(); nmx_vendor = 0x8086;
        pthread_t intel, nvidia;
        if (pthread_create(&intel, NULL, bind_accelerator, (void *)(uintptr_t)9) ||
            pthread_create(&nvidia, NULL, bind_accelerator, (void *)(uintptr_t)7)) abort();
        if (pthread_join(intel, NULL) || pthread_join(nvidia, NULL)) abort();
        uint16_t selected = nvmtl_vk_vendor();
        nvmtl_vk_freeze_vendor();
        (void)nvmtl_vk_set_accelerator(9); (void)nvmtl_vk_set_accelerator(7);
        failures += check(nvmtl_vk_vendor(), selected, "concurrent first binding stays stable");
    }}

    puts(failures ? "FAIL corrected vendor/ICD policy" : "PASS corrected vendor/ICD policy");
    return failures != 0;
}}
"""
        c = Path(td) / "gate.c"
        exe = Path(td) / "gate"
        c.write_text(harness)
        subprocess.run(
            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pthread", str(c), "-o", str(exe)],
            check=True,
        )
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    run()
