# Reuse matrix — corrected source assessment (GA40)

Status: bounded source assessment, corrected after independent G1 review.
The original draft and exact failing recipes remain in
`reference/repairs/api-license-001/` and `audit/api-license/negative/`.
This is not a legal clearance or whole-plugin runtime qualification.

Source: `sources/nullmoth` @ `47f818b11cef59acb480210afdf9065fdd44e356`
(`v2.4.3`). Static reading only; no build, GPU, install or runtime test.

## 1. What is in the tree

| Area | Files | Lines | Bytes | Character |
|---|---:|---:|---:|---|
| `plugin/` | 33 | 28,932 | 1,898,300 | Objective-C/C Metal plugin + C Vulkan backend |
| `translator/` | 381 | 314,831 | 11,527,811 | Rust AIR/LLVM→SPIR-V, LGPL |
| `kexts/` | 97 | 23,169 | 1,470,250 | NVIDIA r610 port, display/accelerator kexts |
| `tools/` | 95 | 9,302 | 495,910 | tests/benchmarks/oracles |
| `docs/` | 8 | 2,022 | 85,414 | claims and field notes |
| `nvk/` | 3 | 12,313 | 461,512 | Mesa patch + pin + note |
| `build/`, `package/` | 10 | 759 | 56,976 | build/install scripts |

The plugin is one translation unit (`NVMTLDevice.m:2112-2122`), and
`nvmtl_vk.c` is `#include`d into it. This matters for reuse: copying one `.m`
file does not produce a standalone component.

## 2. Classification

| Class | Meaning |
|---|---|
| **Direct** | Small, self-contained code with no Darwin/Metal/Apple-private dependency; can be copied verbatim into a Linux C/C++ build after adding the licence and a compile check. |
| **Limited** | Useful contract/algorithm, but depends on Vulkan runtime, Objective-C, a fixed ABI, or an external tool; requires adaptation or a separate process/library. |
| **NVIDIA-specific** | Meaningful only with NVK/NVRM/NVAccel/NVIDIA compiler or NVIDIA hardware. Must not be presented as portable. |
| **Unknown** | No source or no evidence for the claimed behavior; treat as unproven. |

## 3. Matrix

| Component / file | Class | Reuse value for GA40 | Blocking facts | Licence |
|---|---|---|---|---|
| `plugin/nvmtl_sampler_desc.h` (16 L) | **Direct** | Metal-like sampler descriptor struct | none (stdint only) | PolyForm NC |
| `plugin/nvmtl_sampler_state.h` (66 L) | **Direct** | Maps descriptor → `VkSamplerCreateInfo` | caller must include Vulkan headers first; no Darwin | PolyForm NC |
| `plugin/nvmtl_sample_positions.h` (70 L) | **Direct** | 1/2/4/8 sample patterns, validation, quantization | none (C math) | PolyForm NC |
| `plugin/nvmtl_physical_bounds.h` (38 L) | **Direct** | SPIR-V physical-storage in-bounds access-chain rewrite helper | marks pointer types in storage class5349, rewrites op66→65/70→67; not decorations or general SPIR-V validation | PolyForm NC |
| `plugin/nvmtl_tex_upload.h` (61 L) | **Direct** | one-in-flight async upload state machine | caller supplies fence handles | PolyForm NC |
| `plugin/nvmtl_sample_depth_contract.h` (14 L) | **Direct but NVK-meaning** | contract bit constants | useful only if matching NVK's sample-depth contract | PolyForm NC |
| `plugin/nvmtl_log_failure.h` (34 L) | **Direct** | release-log classifier | not core; plugin-specific wording | PolyForm NC |
| `plugin/nvmtl_cmd_refusal.h` (42 L) | **Direct** | refusal reasons/strings | diagnostic only; plugin-specific | PolyForm NC |
| `plugin/nvmtl_vk.h` (361 L) | **Limited** | backend ABI/state structs, useful as a contract reference | embeds Vulkan handles as `void *`, assumes `nvk_*` layout, no public ownership rules | PolyForm NC |
| `plugin/nvmtl_vk.c` (7,881 L) | **Limited / NVIDIA-specific** | standard Vulkan resource/pipeline patterns; feature gating | one-TU, Darwin headers, NVK dlsyms, IOSurface, no semaphores, one queue, fixed descriptor ABI | PolyForm NC |
| `plugin/NVMTLDevice.m` + `NVMTLDevice_contract.m` | **Limited** | Metal device/pixel-format/feature contract | `MTLIOAccelDevice`, IOKit, VideoToolbox, `MTLDeviceSPI`; not portable | PolyForm NC |
| `plugin/NVMTLObjects.[hm]` | **Limited** | Metal object/command-buffer state machine, lifetime patterns | Objective-C, IOSurface, Apple private classes, 5,710 + 323 L | PolyForm NC |
| `plugin/NVMTLEventSync.m` | **NVIDIA-specific** | submission partitioning and event semantics reference | no Vulkan semaphores; NVAccel surface marks; CPU waits | PolyForm NC |
| `plugin/NVMTLLibraryLoad.m` | **Limited / Unknown** | metallib indexing, AIR text, caching | depends on external `air-opt`/`air-runtime/libLLVM.dylib`; AIR version unknown | PolyForm NC |
| `plugin/NVMTLVendorCompiler.m`, `NVMTLSass*.m` | **NVIDIA-specific** | NVVM/SASS path reference | `NVIDIAShared.bundle`, `MTLCompiler`, NVK SASS hook; not needed for SPIR-V | PolyForm NC |
| `plugin/NVMTLGL*.m` | **NVIDIA/macOS-specific** | Apple GL-on-Metal integration | Apple OpenGL/CA private APIs | PolyForm NC |
| `translator/` (Rust) | **Limited (substantial)** | real AIR/LLVM→SPIR-V translator, reflection, mesh/tess lowering | LGPL; external `llvm-dis`/`spirv-val`; needs LLVM IR, not Metal API | LGPL-3.0-or-later |
| `translator/wrapper/` | **Limited** | address/linearization helpers used by translator | same LGPL/runtime constraints | LGPL-3.0-or-later |
| `nvk/nvk-macos.patch` | **Limited / NVIDIA-specific** | evidence of the exact NVK ABI the plugin expects | Mesa patch for macOS/NVRM; not portable to Linux ANV | MIT (Mesa) |
| `kexts/NVRM`, `kexts/NVRMFB`, `kexts/NVRMAGDC`, `kexts/NVAccel` | **NVIDIA-specific** | kernel/display architecture reference | NVIDIA r610 + macOS IOKit + GSP; outside GA40 CPU scope | PolyForm NC + upstream NVIDIA terms; see licence map |
| `kexts/NMDRM`, `kexts/NMIntelFB`, `kexts/NM*` | **Unknown / limited** | Intel/DRM-shaped artifacts for a different route | no evidence they drive GA40's Intel target; generated/derived data | PolyForm NC + MIT facts |
| `docs/`, `README`, `CHANGELOG` | **Limited (evidence)** | claims, failure modes, test ideas | claims vs tested distinction; see `claims-vs-evidence.json` | ambiguous (root default) |
| `tools/` | **Limited** | CPU tests/oracles/bench patterns | mostly macOS-specific or benchmark-only; not a backend | mostly ambiguous |
| Apple private ABI reconstructions (`kexts/NVRM/accel/{iofam,re}`) | **Unknown** | interface facts only | no Apple licence/header; copyright status untested | PolyForm header + unknown Apple facts |

## 4. Recommended exact extraction: Bundle A (pure C, 5 files, 251 lines)

Do **not** rewrite the Metal API. Extract only the standalone contract helpers:

| File | Lines | SHA-256 | Why |
|---|---:|---|---|
| `plugin/nvmtl_sampler_desc.h` | 16 | `4cac887dab4f5e1bbf1b8792ed4a3a26a7042f13fb509f82150308a5a249f00c` | stable descriptor struct |
| `plugin/nvmtl_sampler_state.h` | 66 | `223f23b62c4549529acb6a1f76ea6f878a33886f8f05d6f0581c2495a038f8a9` | descriptor → `VkSamplerCreateInfo`, with LOD/border/anisotropy rules |
| `plugin/nvmtl_sample_positions.h` | 70 | `ac3d8d6d7e0de5c569b2561fc63244f325df8f12ceb437f14e47cb4b5939c4e1` | deterministic sample patterns and quantization |
| `plugin/nvmtl_physical_bounds.h` | 38 | `bf3afe460229160d82b6948531d65c6f0f8f53662969f7414646f3c4ab552b5a` | physical-pointer in-bounds access-chain opcode rewrite, not decoration rewriting |
| `plugin/nvmtl_tex_upload.h` | 61 | `3c46589d1578c9782ccd720bdbae50e16de580a404aa8116c40ae6ab0b4f9c11` | async upload lifetime invariants |

Optional sixth: `plugin/nvmtl_sample_depth_contract.h` (14 L,
`faf44f6839bfa95c0919c82b31acb451d05bf5583f1f84da69f0fab354576e49`) only if
the adapter intentionally mirrors NVK's sample-depth contract. It is constants,
not an implementation.

Machine-readable manifest:
`reference/nullmoth-api-inventory/reuse-slice.json` (265 lines / 11,801 bytes
with the optional file).

### Why this set

- All five are C99/C11 headers without Objective-C, Darwin, IOKit,
  IOSurface or Metal includes. Some contain `static inline` functions;
  `nvmtl_physical_bounds.h` has a non-inline `static int` function which must
  be called in an include-and-call TU to avoid unused-function warnings.
- `nvmtl_sampler_state.h` needs `VkSamplerCreateInfo`, `VkSamplerAddressMode`,
  `VkBorderColor`, `VkCompareOp`, `VkFilter`, `VkSamplerMipmapMode`; include
  `vulkan/vulkan.h` before it. It does **not** create a device or call Vulkan.
- `nvmtl_physical_bounds.h` only uses `stdint.h`, `stdlib.h`, `stddef.h` and
  manipulates a SPIR-V word array. Its literal behavior must be tested against
  a known module; do not assume general SPIR-V validity.
- `nvmtl_tex_upload.h` is decision logic only. The caller owns the fence and
  the `uint64_t` in-flight handle.
- Together they cover four small, real contracts that recur in any
  Metal→Vulkan adapter: sampler state, sample positions, a SPIR-V rewrite, and
  upload lifetime.

The original M1 compile claim was overstated. Independent G1 reproduced
failure of the exact `-Wall -Wextra -Werror` recipe on sampler initialization
and unused non-inline physical-bounds helper; the original failures are retained.
Vulkan headers do exist at
`/nix/store/70gg5639vl0vrh52jc4ivb18rab3z5hq-vulkan-headers-1.4.357.0/include`.
The include-and-call probe `audit/api-license/probe_helpers.c` passes 106 CPU
checks with the explicitly documented `-Wno-missing-field-initializers` below.
This probe creates no Vulkan device. GA40's actual two-header adapter and
CPU/Lavapipe results are separately described in `metal/backend-adapter/README.md`.

### What Bundle A is not

- It is not a Metal API implementation, a command buffer, a device, a
  swapchain, or a Vulkan backend.
- It does not include `nvmtl_vk.c`, `NVMTLObjects.m`, IOSurface, events, NVK
  hooks or NVIDIA compiler code.
- It does not make GA40's Intel path work. It only avoids re-deriving a few
  well-tested small rules.

### Corrected integration recipe (bounded CPU check executed by G1)

1. Create a dedicated directory (for example `metal/backend-adapter/reuse/` in
   a later milestone) and copy the five files verbatim.
2. Preserve existing SPDX/copyright notices and the archived PolyForm licence
   plus `Required Notice: Copyright (c) 2026 NullMoth Systems
   (https://nullmothsystems.com)`. `nvmtl_tex_upload.h` has **no SPDX header**;
   a separately extracted copy should add an explanatory PolyForm SPDX/notice
   based on the plugin's governing terms. Never claim it already had that line
   or edit the pinned upstream file. Directory notice in the actual GA40 glue:
   `metal/backend-adapter/NOTICE.md`.
3. Add a `reuse_compile_check.c` that:
   - includes `vulkan/vulkan.h` then `nvmtl_sampler_state.h`;
   - builds a `nvmtl_sampler_desc` and checks a few expected
     `VkSamplerCreateInfo` fields (address modes, border color, LOD clamp);
   - calls `nvmtl_sample_default`, `nvmtl_sample_pattern_valid`,
     `nvmtl_sample_pattern_quantize` for 1/2/4/8;
   - runs `nvmtl_relax_physical_bounds` on a tiny synthetic SPIR-V word array;
   - exercises `nvmtl_up_before_upload` / `nvmtl_up_before_consume` /
     `nvmtl_up_set` / `nvmtl_up_clear`.
4. Compile with a CPU-only command such as
    `cc -std=c11 -Wall -Wextra -Werror -Wno-missing-field-initializers -I<vulkan-include> -Ireuse reuse_compile_check.c -lm`.
    Add `-Wno-missing-field-initializers` for the upstream sampler initializer,
    and use an include-and-call TU for the non-inline helper. An actual command:

    ```sh
    clang -std=c11 -Wall -Wextra -Werror -Wno-missing-field-initializers -O2 \
      -I/nix/store/70gg5639vl0vrh52jc4ivb18rab3z5hq-vulkan-headers-1.4.357.0/include \
      -Isources/nullmoth/plugin audit/api-license/probe_helpers.c -lm \
      -o build/reuse-helper-probe
    build/reuse-helper-probe
    ```

    This is a compile/unit check, not a GPU test; original exact flags remain
    negative controls, not silently rewritten as a previous pass.
5. Record the copied-file SHA-256 values and keep them pinned. If the upstream
   commit changes, re-run the extraction and re-check the diffs.

## 5. Translator reuse (Bundle B, not a header copy)

The translator is the only large component that is plausibly reusable as a
separate component, but it is **not** a small pure-C extraction.

- 381 tracked files, 314,831 lines, Rust, LGPL-3.0-or-later.
- It consumes **LLVM IR text**, not Metal API calls. For `.air` it invokes
  `llvm-dis`; the plugin's macOS front end uses `air-opt`/`libLLVM.dylib`,
  which are not in the repo.
- It runs `spirv-val --target-env vulkan1.2` as a final backstop.
- It emits SPIR-V with a fixed descriptor ABI (buffers 0..32, textures
  32..160, samplers 160..192, colors 192..200, storage textures 480..608).
- It contains native Rust passes for CFG structurization, access lowering,
  resources, stage I/O, mesh lowering, reflection and function constants.

Recommended use: build it as an **unmodified shared library or CLI** and call
it over a stable boundary; do not copy its source into a proprietary binary.
If modified, comply with LGPL source/relink obligations. A Linux build needs a
Rust toolchain plus `llvm-dis` and `spirv-val`; the actual Metal AIR front end
is still missing.

## 6. What to avoid

| Avoid | Reason |
|---|---|
| Copying `nvmtl_vk.c` wholesale | one-TU Darwin code, NVK dlsyms, IOSurface, no semaphores, fixed ABI |
| Copying `NVMTLObjects.m` / `NVMTLDevice.m` | Objective-C + Apple private classes; not portable |
| Reusing the NVK patch on Linux ANV | patch targets Mesa macOS/NVRM and private `nvmtl_nvk_*` exports |
| Treating IOSurface import as VK external memory | fake `/dev/null` fd + NVK staging record |
| Treating Metal events as timeline semaphores | CPU `NSCondition` + fence waits; cross-process events return nil |
| Reusing NVIDIA SASS/NVVM paths | `NVIDIAShared.bundle`/`MTLCompiler`/NVK hooks; NVIDIA-only |
| Calling the repository “MIT” | root is PolyForm NC; only `nvk/` patch is MIT; translator is LGPL |
| Claiming Tahoe/Intel validation | no evidence in this pin; see `claims-vs-evidence.json` |

## 7. Verification plan for M1→M2

Bounded and CPU-only:

1. **Static hash check** — re-run SHA-256 on Bundle A and compare with
   `reuse-slice.json`.
2. **Compile check** — compile `reuse_compile_check.c` with host Vulkan headers;
   no device, no loader, no GPU.
3. **Unit checks** — sampler fields, sample patterns (valid/invalid/quantize),
   upload state transitions, physical-bounds rewrite on a hand-built module.
4. **Licence check** — preserve existing SPDX/copyright where present; the
   original tex-upload header has no SPDX. New extraction must identify the
   governing PolyForm licence and Required Notice, without changing the
   pinned origin; no MIT/Apache relicensing.
5. **Translator (optional, separate)** — `cargo build --release` on Linux, then
   translate a checked-in `.ll` fixture with `spirv-val`; do not run GPU code.
6. **No hardware** — do not enumerate `/dev/dri`, load a driver, install, or
   use SSH. This matrix remains a source-reuse assessment, not an integration
   result.

## 8. Decision summary

- **Recommended now:** Bundle A (5 pure-C headers) as a pinned, noncommercial
  extraction with the exact hashes above.
- **Recommended as a separate track:** translator (LGPL) as an unmodified
  library/CLI, with its external toolchain documented.
- **Reference only:** `nvmtl_vk.c` core call graph, feature gates and failure
  modes; Metal objects; docs.
- **Do not reuse:** IOSurface/WindowServer path, NVK private hooks, NVIDIA
  SASS/NVVM path, kexts, Apple private ABI reconstructions.
- **Unknown, needs evidence:** Intel/ANV behavior, Tahoe, cross-process
  textures/events, AIR bitcode front end, actual runtime correctness.
