# GA41 ANV Linux ICD build report

Date: 2026-10-21

## Result

**PASS: actual Mesa ANV Linux ICD built.** The build used the sealed GA40 Mesa
tree at commit `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2` (Mesa 26.2.3), without
modifying that tree. After a bounded interrupted/resumed build, the final
Ninja invocation completed its 308 remaining targets at `[308/308]`.

Artifacts are local to GA41:

* `anv/artifacts/lib/libvulkan_intel.so` (27,514,976 bytes)
  * SHA-256 `e8c99be081ec15eeae6b7fdc5178c2c1871f5d1c79a5e5dd7dff50e69e15fe5a`
* `anv/artifacts/share/vulkan/icd.d/intel_icd.x86_64.json` (182 bytes)
  * SHA-256 `f29074f09b7e0b5283a7b842f07ecf8b79395908b0c7b382084d695c3fb27736`

The JSON is valid and declares API version `1.4.354`, 64-bit library, and the
standard installed path `/usr/local/lib/libvulkan_intel.so`. It is not a claim
that the artifact has been installed anywhere.

## Exact build inputs

| Input | Version/path |
|---|---|
| Mesa source | GA40 sealed tree, commit `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2` |
| Meson | 1.12.1, GA40 read-only wheel extraction |
| Ninja | 1.13.2 |
| Clang | 21.1.8, Nix wrapper and `clang-21.1.8-dev` |
| LLVM | 21.1.8 (`llvm-config` development output plus runtime libraries) |
| SPIRV-LLVM-Translator | 21.1.0; `LLVMSPIRVLib.pc` 21.1.0.0 |
| SPIR-V Tools | Nix 1.4.357.0; `SPIRV-Tools.pc` 2026.3.1 |
| glslang | GA40 read-only `glslangValidator` 16.6.0 |
| libdrm | 2.4.134 development/runtime outputs |
| Vulkan headers/loader pc | 1.4.357 |
| zlib / expat | 1.3.2 / 2.8.5 |

Dependency retrieval was bounded to the Nix paths requested by the build:
`nix build --no-link --print-out-paths` fetched 58.1 MiB and unpacked 198.7
MiB for LLVM/translator/SPIR-V/glslang inputs; SPIR-V Tools development outputs
added 3.8 MiB download and 17.9 MiB unpacked. Retrieval logs are
`logs/anv-deps-dry-run.txt`, `logs/anv-deps-fetch.txt`,
`logs/anv-spirv-tools-dev-dry-run.txt`, and
`logs/anv-spirv-tools-dev-fetch.txt`.

## Meson configuration

The standalone command is `anv/build_anv.sh`; it invokes Meson against the
sealed source and writes only to GA41. Important options were:

```text
--buildtype=release
-Dplatforms=
-Dgallium-drivers=
-Dvulkan-drivers=intel
-Dopengl=false -Dglx=disabled -Degl=disabled -Dgbm=disabled
-Dllvm=enabled -Dspirv-tools=enabled -Dmesa-clc=enabled
-Dintel-elk=false -Dwerror=false -Dbuild-tests=false
-Dtools= -Dvideo-codecs=
```

The final Meson introspection confirms Vulkan driver `intel`, LLVM enabled at
21.1.8, SPIR-V Tools enabled, Mesa CLC enabled, and no Gallium/OpenGL/GLX/EGL/
GBM drivers. Raw configure output is `logs/anv-003-configure.stdout.txt`, with
`logs/anv-003-configure.rc` recording success.

## Fixes during this build

1. The old GA40 attempt stopped before compilation because CLC requires LLVM.
   GA41 fetched the necessary open LLVM development, translator, and SPIR-V
   development outputs rather than disabling required shader compilation.
2. Nix separates LLVM and Clang outputs. Meson searched the LLVM `--libdir`
   for `clangBasic`; GA41 now uses `anv/llvm-config-wrapper.sh` and a private
   symlink directory containing the read-only clang archives. No large archive
   was copied and `/nix/store` remained read-only.
3. The CLC helper then exposed the missing `clang/Config/config.h` include.
   The script pins `clang-21.1.8-dev` and adds its include directory to
   `CFLAGS`/`CXXFLAGS`. Details, including the observed failure, are retained
   in `logs/anv-010-repair-notes.txt`.

## Static artifact checks

The built `mesa_clc` and all eight Intel shader SPIR-V outputs are present in
the build tree; this confirms required CLC shader generation was built rather
than disabled. The source/tree check is retained in
`logs/anv-011-source-integrity.txt`. `logs/anv-005-readelf-header.txt` confirms
an ELF64 x86-64 shared object.
`logs/anv-006-readelf-dynamic.txt` records the dependencies and SONAME
`libvulkan_intel.so`; the final run has no RPATH ambiguity and has a Nix
RUNPATH for libdrm, expat, glibc, libstdc++, and libgcc. `logs/anv-007-ldd.txt`
resolved every listed dependency. The exported ICD entry points are:

```text
vk_icdGetInstanceProcAddr
vk_icdGetPhysicalDeviceProcAddr
vk_icdNegotiateLoaderICDInterfaceVersion
```

These are the expected loader-facing symbols; ordinary Vulkan entry points are
resolved through the ICD dispatch mechanism and are not expected as direct
global exports. The exact exported-symbol check is in
`logs/anv-012-exported-symbols.txt`; artifact hashes are in
`logs/anv-008-artifact-sha256.txt`.

## Explicit limits

This is a **Linux** ANV ELF build only. No Apple SDK was available and no
Darwin-native build was attempted or implied. ANV remains a Linux DRM/i915 or
Xe userspace driver; macOS has no `/dev/dri` ABI for it. No Vulkan loader
enumeration, GPU open, target SSH, hardware command, kernel module, firmware,
MMIO, or GPU submission was performed. Therefore this report claims build and
static ELF/ICD validity only, not device initialization, enumeration, runtime,
macOS compatibility, or acceleration.
