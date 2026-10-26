# NullMoth Vulkan backend audit (static, M1)

Scope: `plugin/nvmtl_vk.c`, `plugin/nvmtl_vk.h`, the four Metal-side files
(`NVMTLDevice.m`, `NVMTLObjects.[hm]`, `NVMTLEventSync.m`,
`NVMTLLibraryLoad.m`) and the pinned translator. Source commit
`47f818b11cef59acb480210afdf9065fdd44e356`.

This is a **static audit**, not a runtime qualification. No Vulkan device,
GPU, driver, macOS install, `/dev/dri`, ioctl or SSH was touched. No build was
run. A clean compile is not evidence of correctness; a valid `VkResult` is not
evidence of Metal semantics.

## 1. Backend shape

- One `VkInstance`, one `VkPhysicalDevice` (index 0), one `VkDevice`, one
  graphics+compute `VkQueue` per process (`nvmtl_vk.c:121-133`, `:752`,
  `:766-768`, `:1066`).
- Initialization is `pthread_once` (`:1073-1078`); the first Metal device in
  the process owns the backend.
- The ICD is opened **directly** with `dlopen` (`:705`), not through the
  Vulkan loader. The loader is only a fallback (`:727-733`).
- `nvmtl_vk.c` is included into `NVMTLDevice.m:2121`, so it shares the
  Objective-C TU and global state.
- The backend is tightly coupled to NVK's private exports and Apple's
  accelerator/IOSurface/WindowServer stack.

## 2. Findings

### F1 — Presentation is not Vulkan (critical for portability)

There is no `VK_KHR_swapchain`, `VkSwapchainKHR`, `VkPresentInfoKHR` or
`vkQueuePresentKHR` in the plugin. `presentDrawable:` records an Apple
drawable and marks its IOSurface (`NVMTLObjects.m:5013-5023`, `:4965-5010`);
the display swap is done by WindowServer/NVAccel. `commitAndWaitUntilSubmitted`
(`:5031`) waits for the plugin's GPU work in WindowServer when the kernel-side
wait is unavailable.

Consequence: this is not a portable Vulkan presenter. A Linux backend must
supply its own swapchain/presentation path; the NullMoth code offers no
reusable implementation.

### F2 — IOSurface import is an NVK private escape, not standard external memory (critical)

`nvmtl_vk_surface_vram` (`nvmtl_vk.c:1938-1971`) creates a `VkDeviceMemory`
using `VkImportMemoryFdInfoKHR` with an opaque fd whose number comes from
`open("/dev/null")` (`:1946`). NVK is expected to replace the allocation with
the IOSurface's real VRAM using the private `nvmtl_nvk_stage_import` record
(`:1951`). Without that hook, the import is refused and the code falls back to
a private image plus copy-in/copy-out.

Consequence: the “zero-copy IOSurface” claim is conditional on the patched NVK
and NVAccel. It cannot be reproduced with a standard Vulkan driver (ANV, RADV,
or a Linux loader) and must not be used as evidence of portable external
memory support.

### F3 — Metal events are CPU synchronization, not GPU timeline semaphores (high)

There is no `VkSemaphore`, `vkCreateSemaphore`, timeline semaphore extension,
or semaphore array in `VkSubmitInfo` (`:5730`). `MTLEvent`/`MTLSharedEvent`
hold an `NSCondition` and a `uint64_t` (`NVMTLObjects.h:154-155`).

A wait splits the command buffer; the wait part is only released after the CPU
reads `signaledValue` (`NVMTLEventSync.m:346-363`, `:620-627`). A signal is
published on the CPU after the part's fence wait (`:640-673`). Cross-process
shared events return `nil` (`NVMTLDevice.m:1759`,
`NVMTLObjects.m:5215`).

Consequences:

- Metal event ordering is coarser and more CPU-coupled than a Vulkan timeline
  semaphore.
- Any test that assumes GPU-side event waits or shared-event IPC is invalid.
- Performance measurements that include event waits measure CPU/fence
  behavior, not GPU scheduling.

### F4 — Vendor identity is accelerator-class based; Intel is not stock ANV (high for GA40)

`nvmtl_vk_vendor()` (`:90-100`) returns `0x10de` for `NVAccel`, reads a PCI
vendor for `NMXAccel` (only AMD/Intel), and defaults to NVIDIA for anything
else. The Intel branch is reached only through NullMoth's `NMXAccel`
accelerator. There is no evidence in the tree of a stock macOS Intel
accelerator, a Linux i915/AGX path, or Intel hardware validation.

Consequence: GA40's Intel/i915 route cannot reuse the vendor selection as-is.
The existence of `libvulkan_intel.dylib` in a string does not prove ANV
support.

### F5 — WindowServer completion is a private kernel handshake (high)

`NVMTLEventSync.m:79-114` and `nvmtl_vk.c:1920-1936` implement pending/ready
surface marks through `NVAccel` (`nvmtl_nvk_surface_dirty`,
`NVAccelSurfaceWait`, `nvSurfGpuEscape`). The code depends on an accelerator
that understands these marks; older accelerators fall back to waiting for each
composite.

Consequence: the display path cannot be ported to Linux and is not a generic
Vulkan queue-present ordering mechanism.

### F6 — One queue, no queue-family selection beyond graphics+compute (medium/high)

The backend picks the first queue family with both graphics and compute
(`:766-768`) and creates one queue at index 0 (`:1066`). There is no dedicated
transfer queue, async compute queue, or queue-family capability negotiation.

Consequence: workloads that expect async compute/transfer overlap get the
single-queue serialization of this backend. The translator's exact-dispatch
and submit-ahead logic can hide some latency, but not provide hardware queue
parallelism.

### F7 — Fixed descriptor ABI and SPIR-V rewriting (high)

Descriptor bands are fixed:

```text
buffers 0..31, textures 32..159, samplers 160..191, colors 192..199,
storage textures 480..607, address table 640
```

Source: `nvmtl_vk.c:1977-1990`. The plugin rewrites/retargets SPIR-V sets and
binding numbers (`nvmtl_spirv_retarget_set`, `:2727`), and the translator's
documented ABI uses the same base bands (`translator/docs/ARCHITECTURE.md`).

Consequence: this is a closed ABI between the translator, plugin and NVK
patches. A different shader producer or a stock Vulkan pipeline layout cannot
be substituted without changing both sides.

### F8 — Pipeline cache is absent; shader modules are destroyed after pipeline creation (medium)

`vkCreateGraphicsPipelines` and `vkCreateComputePipelines` are called with
`VK_NULL_HANDLE` as the cache (`:4169`, `:4355`). The only persistent cache is
Mesa's shader disk cache (`MESA_SHADER_CACHE_DIR`, `:692-703`). Shader modules
are destroyed after pipeline creation (`:4170-4180`), which is legal Vulkan.

Consequence: pipeline creation cost is paid per process/pipeline; no
application-controlled `VkPipelineCache` is exposed. This is a performance
limitation, not a correctness bug.

### F9 — Render passes and framebuffers, not dynamic rendering (medium)

Passes are built from `vkCreateRenderPass` (`:3580`) and
`vkCreateFramebuffer` (`:4880`); begin uses `vkCmdBeginRenderPass` (`:4923`).
Pass variants are cached by shape. There is no `VK_KHR_dynamic_rendering`.

Consequence: the backend carries a large render-pass/framebuffer compatibility
matrix. It is a legitimate Vulkan 1.0-style design, but not the modern
dynamic-rendering path and not easily portable to a simplified backend.

### F10 — Hard-coded memory budgets and heuristics (medium)

Default constants:

- `NVMTL_VRAM_NONIMAGE = 2655 MiB` (`:174`)
- default headroom `1024 MiB` (`:175`)
- buffer park 256 MiB total, 64 MiB per buffer (`:1146-1148`)
- shared-in-VRAM is **off by default**; opt-in `NVMTL_SHARED_VRAM=1`
  (`:1116-1121`)
- VRAM budget falls back to 70% of the largest device-local heap when
  `VK_EXT_memory_budget` is absent (`:1597`)

Consequence: these numbers were tuned for an RTX 5060/NVK. On Intel they can
cause over- or under-commit. They are policy, not Vulkan requirements.

### F11 — Device loss disables the backend permanently (medium)

On `vkQueueSubmit` failure or fence failure, `g_state = -1` and later calls
are refused (`:5740-5741`, `:5786-5787`). There is no `VK_ERROR_DEVICE_LOST`
recovery, device re-creation, or queue reset.

Consequence: a single GPU hang can turn into a process-wide “Vulkan down”
state. The code intentionally avoids retiring uncertain in-flight resources;
that is safer for memory but leaves the process unable to continue GPU work.

### F12 — Optional NVIDIA-only paths bypass Vulkan (medium, conditional)

- Raw SASS dispatch: `NVMTLObjects.m:4508-4511`, `NVMTLSass.m`,
  `nvmtl_nvk_dispatch_sass_v*` (`nvmtl_vk.c:4400`,
  `NVMTLSass.m:115`). If SASS runs, no VkPipeline is built.
- NVVM/`NVIDIAShared.bundle` AIR→SASS: `NVMTLVendorCompiler.m:114-178`.
- NVDEC/NVENC VideoToolbox registration: `NVMTLDevice.m:250-460`.

Consequence: “Metal on Vulkan” is not universally true; some workloads take
NVIDIA compiler/machine-code paths. These paths are irrelevant to a
non-NVIDIA route and must be excluded from reuse claims.

### F13 — Direct ICD load bypasses the Vulkan loader (medium)

Normal path: `dlopen("/Library/GPUBundles/nvmtl/libvulkan_nouveau.dylib")`
(`:705`). The loader (`libvulkan.dylib`) is only used if direct loading fails
(`:727-733`). Consequently, loader layers, implicit validation, and loader ICD
discovery do not apply in the normal path. The code compensates with its own
debug-utils/validation-loader diagnostic path (`:581-681`), but that is not
equivalent to a standard loader environment.

### F14 — Extension availability is feature-gated, but some features are mandatory (low/medium)

The want list (`:774-780`) is intersected with enumerated device extensions.
Missing optional extensions disable features with a log line. However,
`shaderInt64` is mandatory (`:943`); no device → no Metal device. RT requires
three extensions and all entry points (`:815-817`, `:1011-1016`). Sparse is
conditional on the NVK export and `sparseBinding` (`:966`).

Consequence: the backend is more robust than a hard-coded extension list, but
the mandatory `shaderInt64` and NVK export dependencies still narrow the
usable device set.

## 3. Positive controls worth preserving

These are genuine engineering strengths, independent of portability:

1. **Standard Vulkan core resource path.** Buffers, images, views, samplers,
   render passes, framebuffers, graphics/compute pipelines and command buffers
   use ordinary Vulkan 1.0/1.1/1.2 calls. The call graph is traceable
   (`metal/API-DEPENDENCY.md` §4).
2. **Explicit feature queries.** Capabilities are queried and copied into
   `VkPhysicalDevice*Features` only when supported (`:818-940`).
3. **SPIR-V preflight and validation.** `nvmtl_spirv_ok` (`:485`) checks the
   module header/capabilities; the translator validates with external
   `spirv-val` (`translator/translator/src/tools.rs:310`). Unsupported modules fail
   visibly rather than silently producing invalid SPIR-V.
4. **Fence-based lifetime discipline.** The plugin keeps resources alive
   until the part's fence completes, and explicitly declines to retire
   uncertain in-flight resources on device loss (`:5786-5800`).
5. **Bounded queues and submit-ahead.** The command queue enforces capacity
   (`NVMTLObjects.m:5147-5155`) and submission parts are capped
   (`NVMTLEventSync.m:467-473`).
6. **Deterministic sample-position model.** `nvmtl_sample_positions.h` is
   pure C, validates/quantizes patterns and is unit-testable without a GPU.
7. **Pure-C contract headers.** `nvmtl_physical_bounds.h`,
   `nvmtl_sampler_desc.h`, `nvmtl_sampler_state.h`, `nvmtl_tex_upload.h` and
   `nvmtl_sample_positions.h` are reusable on Linux under their licence.

## 4. Claim audit

| Claim | Audit result |
|---|---|
| “Vulkan backend” | True for the core resource/pipeline/command path; false as a complete portable Vulkan implementation because presentation, surface sharing and events are Apple/NVK-private. |
| “Metal 3” | Partly. Tier-2 argument buffers are reported; many Metal features are emulated or refused. No full conformance suite is present. |
| “Ray tracing” | Conditional emulation on NVK's software BVH, not hardware RT. |
| “Mesh shaders” | Lowered by the translator; no `VK_EXT_mesh_shader`. |
| “Zero-copy IOSurface” | Conditional on NVK + NVAccel private hooks; otherwise copy path. |
| “Open source” | Source-available PolyForm Noncommercial; not OSI. |
| macOS 15 Sequoia | Upstream-tested claim; GA40 did not run it. |
| macOS 26 Tahoe | Changelog claims fixes; README scopes to 15; EVENT-WAIT explicitly disclaims general Tahoe support. **Untested for this pin in GA40.** |
| Intel/AMD | Code branches exist; no hardware evidence. Intel is via `NMXAccel`, not stock ANV. |

## 5. Unresolved / not audited

- Runtime correctness on any GPU, including the RTX 5060 used upstream.
- Thread-safety of all encoder/resource paths under concurrent command
  buffers. The code has locks and comments about past races; no dynamic race
  detector was run.
- Exact NVK patch ↔ plugin ABI compatibility beyond symbol names. The plugin
  dlsyms optional symbols and degrades, but structure layouts are shared by
  convention.
- `VK_EXT_memory_budget` accuracy on NVK.
- Whether `vkCreateDevice` result `-8` (feature not present) is handled
  gracefully in every path; it is logged and the device is refused.
- Apple superclass behavior for shared textures.
- Translator semantic equivalence to Metal; `spirv-val` only proves structural
  validity.
- Tahoe, Intel, AMD, and Linux behavior. No evidence exists here.

## 6. Audit conclusion (bounded)

The backend is a real, substantial Vulkan 1.0/1.1/1.2-style implementation
with a clear core call graph, but it is **not** a portable Vulkan backend. Its
reusable value for GA40 is:

1. the pure-C contract headers (direct reuse under PolyForm),
2. the translator as a separate LGPL component (with its external LLVM/SPIR-V
   tool dependencies),
3. the documented Metal→Vulkan contract patterns and failure modes as
   reference material.

It is **not** evidence that Metal works on Intel, that Tahoe works, that
IOSurface sharing is portable, or that Metal events are Vulkan timeline
semaphores. Do not promote any of those to a GA40 result without new,
independent evidence.
