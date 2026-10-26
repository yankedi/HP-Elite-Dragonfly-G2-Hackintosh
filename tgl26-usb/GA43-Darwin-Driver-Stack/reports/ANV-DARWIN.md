# GA42 ANV Darwin integration

Date: 2026-10-21
Mesa input: `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2` (Mesa 26.2.3,
GA40 sealed source; source remained clean)

## Scope and result

This unit adds a local, opt-in patch layer for the pinned Mesa ANV source. It
does not modify GA40, does not repeat the Linux ICD build, does not access a
device, and does not claim a runnable macOS driver. The patch layer applies
cleanly to a fresh copy and is source-only until a real Apple user SDK and
Darwin linker are supplied.

Full patch/tool commits:

| Commit | Unit |
|---|---|
| `a4fba6bee40ccb5e44cb40ed30de4eec1f2dadfb` | opt-in Meson Darwin conditions and public libdrm dependency contract |
| `bf92a3ec3ddf5d00ececcd5fd3f1814a42a3bd39` | Darwin `intel_ioctl` → public `drmIoctl`; remove Linux-only test syscall includes |
| `f3c63871a1c237b94d9276c42a5ad128aa836d8a` | Mach-O Vulkan loader export list |
| `5144499e502f8060ece2460a7e58d356c5551768` | bounded patched Darwin configure/TU attempt |
| `b992acfde83595337b7525fa843047dac8835d73` | fix Meson `pre_args` ordering before the fixed retry |

The SDK inventory is `anv/sdk-inventory.json` (ignored) and raw invocation
`logs/anv-002-sdk-inventory/{command.json,stdout.txt,stderr.txt}`. It found:

* no local Apple user SDK candidate;
* clang 21.1.8 targeting Linux, GNU ld 2.46, and no `xcrun`, `xcode-select`,
  `otool`, or `lipo`;
* the public GA41 MacKernelSDK path exists but is explicitly rejected as a
  user SDK.

## Patch layer

1. `anv/patches/0001-meson-intel-darwin.patch` adds `-Dintel-darwin=true`,
   validates a Darwin host and `-Dvulkan-drivers=intel`, enters the Intel
   source subtree, preserves CLC requirements, and requires either a
   `pkg-config` `libdrm` public dependency or an explicitly staged prefix and
   library name. It never substitutes Linux libdrm.
2. `anv/patches/0002-anv-darwin-syscalls.patch` routes Mesa's common
   `intel_ioctl()` through public `drmIoctl()` on `__APPLE__`; Linux remains on
   `ioctl()`. It removes unused Linux `sys/syscall.h` includes from ANV test
   stubs.
3. `anv/patches/0003-anv-darwin-exports.patch` adds the Darwin ld
   `-exported_symbols_list` integration with exactly the three loader-facing
   symbols: `vk_icdGetInstanceProcAddr`,
   `vk_icdGetPhysicalDeviceProcAddr`, and
   `vk_icdNegotiateLoaderICDInterfaceVersion`.

`logs/anv-055-verify-meson-order` is the successful fixed patch-layer
check: all three patches applied to a fresh copy of the pinned clean source,
all assertions passed, and no Mach-O or ELF artifact was emitted.

## Actual Darwin attempt

The bounded attempt is `tools/anv-darwin-attempt.py`; the fixed-layer retry's
raw stdout/stderr are preserved at
`logs/anv-065-darwin-build-attempt/{stdout.txt,stderr.txt}` and the receipt is
in the ignored attempt work directory:

`anv/work/darwin-attempt-20261021T053905Z-126483/attempt.json`

The exact patched Meson cross configure reached project startup but failed at
the host toolchain linker probe:

```text
ERROR: Unable to detect linker for compiler ... -target x86_64-apple-macos26 -isysroot /nonexistent
ld.bfd: unrecognised emulation mode: llvm
Supported emulations: elf_x86_64 elf_i386 elf32_x86_64 elf_iamcu
```

The last raw failure from a real pinned Mesa translation unit was:

```text
src/intel/compiler/brw/brw_eu.c:9:10: fatal error: 'sys/stat.h' file not found
```

The attempt used `/nonexistent` only as an explicit missing-SDK sentinel. No
Apple SDK headers were fabricated, and no object was emitted. Artifact kind:
**none**; consequently there is no Mach-O and no ELF result to inspect.

## Checks and remaining blockers

* Source-layer apply/inspection: PASS (`anv-035` raw log, exit 0).
* Darwin configure attempt: BLOCKED by absent Apple user SDK plus the Linux
  Nix wrapper/GNU linker not being a Darwin linker (`anv-065`, exit 1).
* Real Mesa Darwin TU: BLOCKED at missing SDK `sys/stat.h` (`anv-065`, exit 1).
* A Linux-only Meson parse probe (`anv-040`) passed but unexpectedly allowed
  Meson's fallback zlib/expat retrieval during dependency discovery. It is not
  acceptance evidence, must not be repeated under GA42 offline rules, and is
  retained as a raw negative record.

Required before a legitimate native build attempt can continue: a locally
available Apple user SDK/sysroot, an Apple-compatible Darwin linker/toolchain,
and a staged Darwin libdrm-compatible public dependency exposing the APIs used
by ANV. Even after those are present, this patch layer would establish build
integration only; it does not establish ANV initialization, i915/Xe ioctl
compatibility, Vulkan enumeration, GPU submission, or acceleration on macOS.
