# NullMoth Metal → Vulkan API dependency map (M1, pinned source)

Status: bounded static inventory. No GPU, `/dev/dri`, ioctl, SSH, build,
installation or driver load was performed. No source file was edited.

## 1. Pin and evidence

| Item | Value |
|---|---|
| Repository | `https://github.com/nullmoth/nvidia-macos-driver.git` |
| Commit | `47f818b11cef59acb480210afdf9065fdd44e356` |
| Tag | `v2.4.3` (same commit) |
| Tree | `5c3425d8764ca9fa2217c76bb2b79099128474f5` |
| Clone | **shallow**; single snapshot, no parent history |
| Tracked files | 639 (626 regular, 13 executable, 0 symlinks) |
| Working tree | clean at inventory time |
| Machine-readable records | `reference/nullmoth-api-inventory/source-pin.json`, `source-files.json`, `api-map.json`, `file-provenance.json`, `claims-vs-evidence.json` |

Full SHA/tag/tree checks passed locally. The clone is shallow, so the commit
is verified as an object and as `v2.4.3`, but its ancestry is not present.

Primary source files:

- `plugin/NVMTLDevice.m` 2,122 lines
- `plugin/NVMTLObjects.h` 323 lines
- `plugin/NVMTLObjects.m` 5,710 lines
- `plugin/NVMTLEventSync.m` 832 lines
- `plugin/NVMTLLibraryLoad.m` 2,917 lines
- `plugin/nvmtl_vk.c` 7,881 lines
- `plugin/nvmtl_vk.h` 361 lines
- translator: 381 tracked files (`translator/`), 370 files under the crate
- docs: README, HOW-IT-WORKS, CARD-SUPPORT, TROUBLESHOOTING, CHANGELOG

## 2. Build shape: the plugin is one Objective-C translation unit

`plugin/NVMTLDevice.m` is not just the device class. At its end it imports
every other plugin implementation and **includes the C backend source**:

```text
NVMTLDevice.m:2112  #import "NVMTLDevice_contract.m"
NVMTLDevice.m:2114  #import "NVMTLObjects.m"
NVMTLDevice.m:2115  #import "NVMTLForward.m"
NVMTLDevice.m:2116  #import "NVMTLLibraryLoad.m"
NVMTLDevice.m:2117  #import "NVMTLGL.m"
NVMTLDevice.m:2118  #import "NVMTLGLVBlank.m"
NVMTLDevice.m:2119  #import "NVMTLEmbedded.m"
NVMTLDevice.m:2120  #import "NVMTLVendorCompiler.m"
NVMTLDevice.m:2121  #include "nvmtl_vk.c"
NVMTLDevice.m:2122  #import "NVMTLSass.m"
```

Consequences:

- `nvmtl_vk.c` is compiled as C inside an Objective-C TU. It is not a clean
  standalone library and cannot be linked on Linux as-is.
- Internal symbols are shared through the TU; many `nvmtl_*` prototypes are
  declared ad hoc in `.m` files, not in a public header.
- `NVMTLObjects.h` declares the Metal object graph and embeds `nvk_buffer`,
  `nvk_image`, `nvk_pipeline`, `nvk_cmdbuf` state by value.

## 3. Metal surface implemented by this plugin

`plugin/NVMTLObjects.h` (line numbers are declarations):

| Metal protocol/class | Implementation | Backing state |
|---|---|---|
| `MTLDevice` / `MTLDeviceSPI` | `NVMTLDevice : MTLIOAccelDevice` (`NVMTLDevice.m:141-144`, `:557`) | one process-wide `VkDevice` |
| `MTLBuffer` | `NVMTLBuffer` (`Objects.h:20`) | `nvk_buffer` + optional managed shadow |
| `MTLTexture` | `NVMTLTexture` (`Objects.h:35`) | `nvk_image`, optional `IOSurfaceRef`, optional VRAM alias |
| `MTLHeap` | `NVMTLHeap` (`Objects.h:156`) | `nvk_heap` placement allocation |
| `MTLLibrary`, `MTLFunction` | `NVMTLLibrary`, `NVMTLFunction` (`Objects.h:61,104`) | function name → SPIR-V bytes + AIR text |
| `MTLRenderPipelineState` | `NVMTLRenderPipelineState` (`Objects.h:106`) | `nvk_pipeline` |
| `MTLComputePipelineState` | `NVMTLComputePipelineState` (`Objects.h:164`) | `nvk_pipeline` or optional SASS |
| `MTLCommandQueue` | `NVMTLCommandQueue` (`Objects.h:109`) | one `nvk_queue` |
| `MTLCommandBuffer` | `NVMTLCommandBuffer` (`Objects.h:112`) | `nvk_cmdbuf` plus submission parts |
| `MTLRenderCommandEncoder` | `NVMTLObjects.m:2652` | render pass + framebuffer |
| `MTLComputeCommandEncoder` | `NVMTLObjects.m:4272` | compute pipeline + descriptors |
| `MTLBlitCommandEncoder` | `NVMTLObjects.m:4652` | transfer commands |
| `MTLParallelRenderCommandEncoder` | `NVMTLObjects.m:5394` | deferred encoders |
| `MTLAccelerationStructure` / encoder | `Objects.h:190-191`, `Objects.m:5542` | `VkAccelerationStructureKHR` (NVK software BVH) |
| `MTLDepthStencilState` | `Objects.h:149` | fixed compare/write/stencil state |
| `MTLSamplerState` | `Objects.h:151` | `nvk_sampler` |
| `MTLEvent` / `MTLSharedEvent` | `Objects.h:154-155` | `NSCondition` + `uint64_t`; **not Vulkan semaphores** |
| `MTLIndirectCommandBuffer` | `Objects.h:179` | CPU-side command list/emulation |
| `MTLBinaryArchive` / dynamic library | `NVMTLLibraryLoad.m:1888,2446` | cache/reflection records |
| `MTLCounterSampleBuffer` | `Objects.h:232` | query pool / timestamps |

Not implemented or explicitly refused (examples):

- `newSharedEventWithHandle:` → `nil` (`NVMTLDevice.m:1759`)
- `newSharedEventHandle` → `nil` (`NVMTLObjects.m:5215`)
- `newBufferWithDescriptor:`, `newBufferWithIOSurface:` → `nil`
  (`NVMTLDevice_contract.m:71-72`)
- `newVisibleFunctionTableWithDescriptor:` → `nil` in the contract
  (`NVMTLDevice_contract.m:77`); visible-function tables are implemented
  elsewhere in `NVMTLLibraryLoad.m`, so this specific selector is a gap.

## 4. Line-linked Metal → Vulkan call graph

Each row is a real call chain in the pinned tree. `→` means a direct call or
an immediately inlined wrapper. Line numbers are exact for this commit.

### 4.1 Device and queue bring-up

```text
-[NVMTLDevice initWithAcceleratorPort:]        NVMTLDevice.m:557
  → nvmtl_vk_set_accelerator                   nvmtl_vk.c:81
  → nvmtl_vk_vendor                            nvmtl_vk.c:90
  → nvmtl_vk_init                              nvmtl_vk.c:1075
  → nvmtl_vk_initialize                        nvmtl_vk.c:683
      → dlopen(NVMTL_ICD_LIB)                  nvmtl_vk.c:705
      → vkCreateInstance                       nvmtl_vk.c:740
      → vkEnumeratePhysicalDevices             nvmtl_vk.c:744/752
      → vkGetPhysicalDeviceProperties(2)       nvmtl_vk.c:753/758
      → vkEnumerateDeviceExtensionProperties   nvmtl_vk.c:784/786
      → vkGetPhysicalDeviceFeatures(2)         nvmtl_vk.c:942/868
      → vkCreateDevice                         nvmtl_vk.c:971
      → vkGetDeviceProcAddr                    nvmtl_vk.c:973
      → vkGetDeviceQueue                       nvmtl_vk.c:1066
```

`-[NVMTLDevice newCommandQueueWithMaxCommandBufferCount:]`
(`NVMTLDevice.m:632`) → `nvmtl_vk_queue_create` (`nvmtl_vk.c:4524`). The
actual `vkCreateCommandPool` is deferred to each command buffer begin
(`nvmtl_vk.c:4651`).

### 4.2 Buffers

```text
-[NVMTLDevice newBufferWithLength:options:]    NVMTLDevice.m:642
  → nvmtl_vk_buffer_create                     nvmtl_vk.c:1290
  → nvmtl_vk_buffer_create_body                nvmtl_vk.c:1307
      → vkGetBufferMemoryRequirements          nvmtl_vk.c:1324
      → vkAllocateMemory                       nvmtl_vk.c:1332/1365
      → vkMapMemory                            nvmtl_vk.c:1333/1369
      → vkBindBufferMemory                     nvmtl_vk.c:1334/1368
```

Private buffers may use the sparse path (`nvmtl_vk_buffer_create_sparse`,
`nvmtl_vk.c:1255`), which uses `vkCreateBuffer` (`:1262`), `vkAllocateMemory`
(`:1270/1272`) and later `vkQueueBindSparse` (`:1240`).

### 4.3 Textures and IOSurfaces

```text
-[NVMTLDevice newTextureWithDescriptor:]       NVMTLDevice.m:821
  → nvmtl_vk_image_create_typed                nvmtl_vk.c:1833
  → ..._lifetime_body                          nvmtl_vk.c:1841
      → nvmtl_opaque_CreateImage               nvmtl_vk.c:377
          → nvmtl_typed_CreateImage            nvmtl_vk.c:355
              → vkCreateImage                  nvmtl_vk.c:363
      → vkGetImageMemoryRequirements           nvmtl_vk.c:1860
      → vkAllocateMemory                       nvmtl_vk.c:1861
      → vkBindImageMemory                      nvmtl_vk.c:1863
      → vkCreateImageView                      nvmtl_vk.c:1870
```

IOSurface path:

```text
-[NVMTLDevice newTextureWithDescriptor:iosurface:plane:]   NVMTLDevice.m:941
  → nvmtlNewSurfaceTexture                                  NVMTLDevice.m:949
  → nvmtl_surface_image_create                              NVMTLDevice.m:903
      if shareable: nvmtl_vk_surface_vram                   nvmtl_vk.c:1938
          → NVK nvmtl_nvk_stage_import                      nvmtl_vk.c:1951
          → vkAllocateMemory (opaque-fd import)             nvmtl_vk.c:1952
          → vkCreateBuffer / vkBindBufferMemory             nvmtl_vk.c:1963
          → nvmtl_vk_image_create_buffer_alias             NVMTLDevice.m:911
      else: nvmtl_vk_image_create_typed                     NVMTLDevice.m:937
  CPU synchronization:
      nvmtlSurfaceIn   NVMTLObjects.m:1215 → nvmtl_vk_image_write  :1231
      nvmtlSurfaceOut  NVMTLObjects.m:1270 → nvmtl_vk_image_read   :1292
```

The “shared VRAM” import is not standard Vulkan external memory. It passes a
synthetic open file descriptor (`open("/dev/null")`, `nvmtl_vk.c:1946`) plus
NVK's private `nvmtl_nvk_stage_import` record so NVK can substitute the
IOSurface's real allocation. A portable Vulkan backend cannot copy this.

### 4.4 Render pipeline

```text
-[NVMTLDevice newRenderPipelineStateWithDescriptor:error:]  NVMTLDevice.m:1439
  → nvmtl_vk_pipeline_create_rt                              nvmtl_vk.c:3981
  → nvmtl_vk_pipeline_create_impl                            nvmtl_vk.c:3970
      → vkCreateShaderModule                                 :4075
      → vkCreatePipelineLayout                               :4113
      → vkCreateRenderPass                                   :3580
      → vkCreateGraphicsPipelines                            :4169
      → vkDestroyShaderModule                                :4170
```

Render pass and framebuffer are created per pass/pipeline variant. There is
no `VK_KHR_dynamic_rendering`. `VkPipelineCache` is `VK_NULL_HANDLE`
(`nvmtl_vk.c:4169`); compilation caching relies on Mesa's shader cache
(`MESA_SHADER_CACHE_DIR`, `nvmtl_vk.c:692-703`).

### 4.5 Compute pipeline and dispatch

```text
-[NVMTLDevice newComputePipelineStateWithFunction:error:]  NVMTLDevice.m:1820
  → nvmtl_vk_compute_pipeline_create                         nvmtl_vk.c:4235
  → nvmtl_vk_compute_pipeline_create_g                       nvmtl_vk.c:4237
      → vkCreateShaderModule                                 :4274
      → vkCreatePipelineLayout                               :4279
      → vkCreateComputePipelines                             :4355

-[NVMTLComputeCommandEncoder dispatchThreadgroups:...]       NVMTLObjects.m:4507
  → nvmtl_vk_cmd_dispatch_threads                            nvmtl_vk.c:4437
      → vkCmdBindPipeline :4459 / vkCmdBindDescriptorSets :4460 /
        vkCmdPushConstants :4480 / vkCmdDispatch :4481
```

The encoder runs an optional raw-SASS path first
(`NVMTLObjects.m:4508-4511`, `NVMTLSass.m`). If it succeeds, no Vulkan
pipeline is built or dispatched. The SASS path is NVIDIA/NVK-specific.

### 4.6 Command buffer, render encoder, submission

```text
-[NVMTLCommandQueue commandBuffer]              NVMTLObjects.m:5147
  → nvmtl_vk_cmd_begin                          nvmtl_vk.c:4642
      → vkCreateCommandPool                     :4651
      → vkBeginCommandBuffer                    :4660
      → vkCreateQueryPool                       :4665

-[NVMTLRenderCommandEncoder drawPrimitives:...]  NVMTLObjects.m:3106
  → nvmtl_vk_cmd_draw                            nvmtl_vk.c:5378
      → vkCmdDraw                               :5385

-[NVMTLRenderCommandEncoder drawIndexedPrimitives:...] NVMTLObjects.m:3359
  → nvmtl_vk_cmd_draw_indexed                    nvmtl_vk.c:5449
      → vkCmdBindIndexBuffer                    :5453
      → vkCmdDrawIndexed                        :5459

-[NVMTLRenderCommandEncoder endEncoding]         NVMTLObjects.m:3234
  → nvmtl_vk_cmd_end_render                      nvmtl_vk.c:5518
      → vkCmdEndRenderPass                      :5519

-[NVMTLCommandBuffer commit]                     NVMTLObjects.m:5039
  → nvmtlSubmitWithEvents                        NVMTLEventSync.m:689
  → nvmtlSealPartWithSignal                      NVMTLEventSync.m:314
  → nvmtlAdvancePart                             NVMTLEventSync.m:613
      → nvmtl_vk_submit_begin                    NVMTLEventSync.m:576
          → nvmtl_vk_submit_begin_at             nvmtl_vk.c:5680
              → vkCreateFence                    :5703
              → vkQueueSubmit                    :5735
      → nvmtl_vk_submit_finish                   NVMTLEventSync.m:33
          → nvmtl_vk_submit_finish               nvmtl_vk.c:5747
              → vkWaitForFences                  :5764
```

`VkSubmitInfo` is built with zero wait and zero signal semaphores
(`nvmtl_vk.c:5730`). Ordering comes from the single queue, fence waits, and
CPU-side event checks. Submit-ahead is capped (default 16 parts,
`NVMTLEventSync.m:467-473`).

On submit or fence failure the backend sets `g_state = -1` and refuses later
work rather than attempting device recovery (`nvmtl_vk.c:5740-5741`,
`:5786-5787`).

## 5. Dependency categories

The machine-readable `api-map.json` uses the labels `standard_vk`,
`extension_vk`, `nvk`, `nvidia`, `macos_private` and `unknown`, with a
`dependency_categories` block that also names `NVRM` explicitly.

### 5.1 Standard Vulkan (core / 1.1 / 1.2 / 1.3)

The backend loads this fixed core list via
`INSTANCE_FNS`/`DEVICE_FNS` (`nvmtl_vk.c:199-209`):

- instance/device: enumerate physical devices, properties/features, memory
  properties, queue families, `vkCreateDevice`, `vkGetDeviceProcAddr`
- buffers/images: create, memory requirements, allocate/map/bind, image views
- descriptors: set layouts, pools, sets, updates, bind
- pipelines: shader modules, layouts, graphics/compute pipelines
- render: render passes, framebuffers, begin/end, draw, indexed draw
- transfers: copy buffer/image, blit, fill
- queries/timestamps: query pools, reset/begin/end/copy/get
- synchronization: fences (create/wait/reset/destroy), barriers, queue submit
- dynamic state: viewport, scissor, topology, cull, front face, depth/stencil,
  blend constants, depth bias, line width
- sparse: `vkQueueBindSparse` only when the NVK sparse hook is present

Vulkan API version requested: 1.3 (`nvmtl_vk.c:738`). Vulkan 1.1/1.2
features are queried and copied only when supported (`:818-940`):
buffer device address, descriptor indexing/bindless, 16-bit storage,
float16/int8, Vulkan memory model, 64-bit atomics, host query reset,
scalar block layout, shader draw parameters, cube arrays, robust buffer
access, tessellation, geometry-less vertex stores, independent blend,
alpha-to-one, dual-source blend, wide lines, sample-rate shading, precise
occlusion queries.

Not used anywhere in `nvmtl_vk.c`:

- `VK_KHR_swapchain` (presentation is IOSurface/WindowServer)
- `VK_KHR_dynamic_rendering`
- `VK_KHR_synchronization2`
- `VK_KHR_timeline_semaphore` / `VkSemaphore`
- `VK_EXT_mesh_shader`
- `VK_EXT_descriptor_buffer`
- any `VK_KHR_maintenance*`

### 5.2 Vulkan extensions requested (hard-coded want list)

`nvmtl_vk.c:774-780` requests each extension only if the ICD enumerates it.
Missing extensions degrade features rather than failing device creation
(except features required unconditionally, e.g. `shaderInt64` at `:943`).

| Extension | Why it is used | Exact anchor |
|---|---|---|
| `VK_EXT_extended_dynamic_state3` | polygon mode, provoking vertex, depth clip, unrestricted topology | `:774`, fields `:829-846`, commands `:1042-1053` |
| `VK_EXT_depth_clip_enable` | Metal depth clip mode | `:775`, `:826-828`, `:1051` |
| `VK_EXT_memory_budget` | measured VRAM budget/usage | `:775`, query `:1585-1607` |
| `VK_KHR_acceleration_structure` | ray tracing | `:775`, `:815-817`, `:1011-1016` |
| `VK_KHR_ray_query` | inline ray queries | `:775`, `:815-817` |
| `VK_KHR_deferred_host_operations` | RT prerequisite | `:775` |
| `VK_EXT_external_memory_host` | `newBufferWithBytesNoCopy` zero-copy import | `:776`, `:1406-1449` |
| `VK_EXT_image_drm_format_modifier` | explicit row pitch for buffer textures | `:777`, `:7374` |
| `VK_KHR_external_memory_fd` | IOSurface opaque-fd allocation record | `:778`, `:1946` |
| `VK_EXT_mutable_descriptor_type` | texture/storage bands share descriptors | `:779`, `:1508` |
| `VK_KHR_cooperative_matrix` | MPS/simdgroup matrix paths | `:779`, `:892-915` |
| `VK_EXT_calibrated_timestamps` | GPU clock correlation | `:779`, `:995-1008` |
| `VK_EXT_sample_locations` | programmable sample positions | `:779`, `:793-802`, `:978-994` |
| `VK_KHR_pipeline_executable_properties` | optional `NVMTL_PSTAT=1` statistics | `:779`, `:807`, `:973-976` |
| `VK_EXT_provoking_vertex` | Apple GL `setProvokingVertexMode:` | `:780`, `:832-845`, `:1046` |
| `VK_KHR_vertex_attribute_divisor` | per-instance step rates | `:780`, `:849-865` |
| `VK_EXT_debug_utils` | NVK messages to the plugin log | `:630`, `:659-681` |
| `VK_EXT_layer_settings`, `VK_EXT_validation_features` | validation-loader diagnostic path | `:642-643` |

### 5.3 NVIDIA / NVK-specific

These are not Vulkan extensions; they are exported symbols from the patched
NVK dylib, found with `dlsym` after opening the ICD directly:

| Symbol | Anchor | Role |
|---|---|---|
| `nvmtl_nvk_stage_import` | `nvmtl_vk.c:717` | stage a surface VRAM allocation record for the next `vkAllocateMemory` |
| `nvmtl_nvk_surface_dirty` | `nvmtl_vk.c:718` | mark IOSurface VRAM newest/GPU-pending/ready; page-off handshake |
| `nvmtl_nvk_sample_depth_contract_v1` | `nvmtl_vk.c:719` | sample-depth capability contract; also `vkNVMTLGetSampleDepthContractV1` |
| `nvmtl_nvk_sample_depth_image_v1` | `nvmtl_vk.c:720` | verify an image against the contract; also `vkNVMTLVerifySampleDepthImageV1` |
| `nvmtl_nvk_sparse_bind_v1` | `nvmtl_vk.c:721` | enables the sparse buffer path |
| `nvmtl_nvk_dispatch_sass_v1` | `nvmtl_vk.c:4400` | optional raw SASS dispatch |
| `nvmtl_nvk_dispatch_sass_v3` | `NVMTLSass.m:115` | optional raw SASS dispatch |
| `nvmtl_nvk_sass_image_handle_v1`, `..._sampler_handle_v1` | `NVMTLSassResolve.m:64,72` | NVK-owned descriptor indices for SASS |
| `nvkmd_nvrm_gsub_stats` | `nvmtl_vk.c:5645` | NVRM/NVK submission statistics |

The patch file `nvk/nvk-macos.patch` adds the matching exports:
`nvmtl_nvk_stage_import` at patch line 9647, `nvmtl_nvk_surface_dirty` at
4338, `nvmtl_nvk_sparse_bind_v1` at 9416-9417, and the SASS dispatcher at
11997-12004. These are NullMoth/Mesa-patch interfaces, not public Vulkan.

Also NVIDIA-specific, but outside Vulkan:

- `VkPhysicalDeviceShaderSMBuiltinsPropertiesNV` for SM count
  (`nvmtl_vk.c:756-761`)
- NVDEC/NVENC VideoToolbox registration (`NVMTLDevice.m:250-460`)
- optional NVVM/`NVIDIAShared.bundle` AIR→SASS compiler
  (`NVMTLVendorCompiler.m:114-178`)
- NVRM/NVAccel/NVRMFB/NVRMAGDC kext path (outside `plugin/`)
- GSP firmware `610.57.04` (external, not in repo)

### 5.3b NVRM (kernel/runtime dependency, not a Vulkan API)

The plugin does not call NVRM ioctls directly. NVRM enters through the patched
NVK ICD and the kernel kexts:

| NVRM dependency | Evidence | Boundary |
|---|---|---|
| `NVRM.kext`, `NVAccel.kext`, `NVRMFB.kext`, `NVRMAGDC.kext` | `README.md:40-44`, `docs/HOW-IT-WORKS.md:28-60` | outside `plugin/`; macOS IOKit kexts |
| NVIDIA r610 open GPU kernel modules | `README.md:155`, `NOTICE` | external tag `610.57.04` |
| GSP firmware `610.57.04` | `README.md:41`, `docs/HOW-IT-WORKS.md:25` | external `/Users/Shared/nvfw/nvidia/610.57.04` |
| NVK macOS patch against NVRM instead of Linux DRM | `nvk/nvk-macos.patch`, `nvk/2.0.5/README.md` | the ICD the plugin loads |
| `nvkmd_nvrm_gsub_stats` | `plugin/nvmtl_vk.c:5645` | optional NVRM/NVK statistics |
| `NVRM_FLUSH_TIMEOUT_MS` / wait behavior | `plugin/nvmtl_vk.c:142-151`, `:687-690` | inherited by NVK submissions |
| NVDEC/NVENC engines reached through NVRM | `plugin/NVMTLDevice.m:250-460` | VideoToolbox registration, outside Vulkan |

Consequence: the Vulkan backend is only the user-space adapter. The GPU
submission path continues into NVK → NVRM → GSP. Reusing the plugin on Intel
does not reuse this stack; it would need a different kernel/ICD path.

### 5.4 macOS-private dependencies

| Dependency | Anchor | Why it blocks portable reuse |
|---|---|---|
| `MTLIOAccelDevice` superclass / `MTLDeviceSPI` | `NVMTLDevice.m:141-144`, `:560` | The plugin is a subclass of an Apple private accelerator device. There is no Linux equivalent. |
| Accelerator Mach port / IOKit vendor lookup | `nvmtl_vk.c:66-100` | Device selection comes from `NVAccel`/`NMXAccel` IORegistry objects, not an enumerable Vulkan loader device. |
| `IOSurface` API | `NVMTLDevice.m:903-937`, `NVMTLObjects.m:1172-1300` | Texture sharing, scan-out, CPU copy-in/out and seed/lock semantics. |
| WindowServer / NVAccel completion marks | `NVMTLEventSync.m:79-114`, `nvmtl_vk.c:1920-1936` | Uses `NVAccelSurfaceWait` and NVK's `nvSurfGpuEscape` path. |
| `MTLIOAccelResourcePool`, `setHwResourcePool:count:` | `NVMTLDevice.m:540-554` | Private Metal resource pool ABI; arguments are filled by offset. |
| `MTLSharedTextureHandle` superclass implementation | `NVMTLDevice.m:1752-1756` | Sharing is delegated to Apple's `MTLIOAccelDevice`, not implemented in Vulkan. |
| Mach-O symbol rebinding (`_sysconf`, `_open`) | `nvmtl_vk.c:265-319`, `:713-716` | Rewrites the NVK dylib's import pointers in-process so sandboxed apps can allocate. This is a macOS-specific hack. |
| `sysctlbyname("debug.nvaccel_headless")` | `nvmtl_vk.c:1884` | Selects copy-out behavior for headless/other-GPU display. |
| `MTLArchitecture` private ivar | `NVMTLDevice.m:2076-2100` | Answers Metal architecture by setting a private ivar. |
| `air-opt` external binary | `NVMTLLibraryLoad.m:25`, `:441-468` | Converts AIR bitcode to LLVM text; not in repository. |
| `air-runtime/libLLVM.dylib` external dylib | `NVMTLLibraryLoad.m:556-585` | In-process bitcode reader/unroll; not in repository. |
| `MTLCompiler` / `NVIDIAShared.bundle` | `NVMTLVendorCompiler.m:114-178` | Optional NVIDIA AIR→SASS path; not in repository. |
| Apple GL-on-Metal / CoreAnimation private hooks | `NVMTLGL.m`, `NVMTLGLVBlank.m` | OpenGL/vblank claims depend on Apple frameworks. |

### 5.5 Unknown / unverified

- Exact AIR bitcode producer/LLVM version accepted by the external
  `air-opt`/`libLLVM` pair. The source only checks wrapper magic
  `DE C0 17 0B` (`NVMTLLibraryLoad.m:901`) and an `MTLB` container header
  (`:917`).
- Behavior of Apple's superclass `newSharedTextureWithHandle:`; no source.
- Whether `VK_EXT_memory_budget` values from NVK match NVRM's real budget;
  the fallback is 70% of the largest device-local heap (`nvmtl_vk.c:1597`).
- Whether the single physical device index 0 is always the intended GPU
  (`nvmtl_vk.c:752`).
- Runtime correctness of any of the above on Intel/ANV, AMD/RADV or non-NVK
  drivers. No such evidence exists in this tree.

## 6. Vendor selection and hard-coded paths

`nvmtl_vk_vendor()` (`nvmtl_vk.c:90-100`):

1. If a Metal device was created, `nvmtl_vk_set_accelerator()`
   (`:81-88`) reads the accelerator port:
   - `NVAccel` → NVIDIA `0x10de`
   - `NMXAccel` → read the parent PCI `vendor-id`; accept only
     `0x1002` (AMD) or `0x8086` (Intel)
2. Otherwise, match `NVAccel` in the I/O registry; if present → `0x10de`.
3. Otherwise, match `NMXAccel`; accept AMD/Intel vendor id; **default to
   `0x10de`** for anything else (`:98`).

ICD selection (`:101-117`):

| Vendor | ICD JSON | Direct dylib |
|---|---|---|
| NVIDIA | `/Library/GPUBundles/nvmtl/nvk_icd.json` | `/Library/GPUBundles/nvmtl/libvulkan_nouveau.dylib` |
| AMD | `/Library/GPUBundles/nvmtl/radeon_icd.json` | `/Library/GPUBundles/nvmtl/libvulkan_radeon.dylib` |
| Intel | `/Library/GPUBundles/nvmtl/intel_icd.json` | `/Library/GPUBundles/nvmtl/libvulkan_intel.dylib` |

`NVMTL_ICD_LIB` can override the direct dylib with any readable path
(`:110`). If direct loading fails, it sets `VK_ICD_FILENAMES` and loads
`/Library/GPUBundles/nvmtl/libvulkan.dylib` (`:727-733`).

Important for GA40's Intel route: the Intel branch is reached **only** through
NullMoth's `NMXAccel` accelerator, not through a stock macOS i915/AGX
accelerator and not through a normal Linux Vulkan loader. The default and all
validated evidence are NVIDIA/NVK. There is no Intel hardware evidence in the
tree.

Other hard-coded choices:

- one physical device, index 0 (`:752`)
- first queue family with graphics+compute (`:766-768`)
- `VK_API_VERSION_1_3` (`:738`)
- descriptor bands `0..640` (`:1977-1990`)
- `NVMTL_VRAM_NONIMAGE` 2,655 MiB and 1,024 MiB headroom defaults
  (`:174-175`)
- buffer park 256 MiB / 64 MiB max per buffer (`:1146-1148`)
- 128 MiB translation/texture caches (`NVMTLLibraryLoad.m:1152`)
- sample-position push ABI offset 96, 64 bytes
  (`nvmtl_sample_positions.h:15-17`)

## 7. IOSurface, WindowServer and external host memory

### IOSurface

Two modes:

1. **Familyshared VRAM (NVK only).** If `nvmtl_vk_surface_share_on()`
   (`nvmtl_vk.c:1888`) is true, the surface is single-plane, the row is a
   multiple of 32 bytes and the image fits, `nvmtl_vk_surface_vram` allocates a
   `VkDeviceMemory` by importing an opaque fd record. The fd is `/dev/null`;
   NVK swaps in the IOSurface's real allocation using the private
   `nvmtl_nvk_stage_import` record. The image is then a buffer alias
   (`NVMTLDevice.m:906-921`).
2. **Private image plus copies.** Otherwise a normal `VkImage` is created and
   `nvmtlSurfaceIn`/`nvmtlSurfaceOut` copy the whole plane through
   `vkCmdCopyBufferToImage`/`vkCmdCopyImageToBuffer` (via
   `nvmtl_vk_image_write/read`). This is the fallback when the NVK escape is
   absent, the row is not 32-byte aligned, the texture is multi-planar, or the
   GPU is headless/other-vendor.

### WindowServer

`NVMTLEventSync.m:79-114` and `nvmtl_vk.c:1920-1936` implement a kernel
completion handshake with `NVAccel`:

- On commit, `nvmtl_ws_mark_pending` (`NVMTLEventSync.m:193`) marks each
  written IOSurface pending and (when the accelerator supports it) marks its
  shared VRAM newest.
- On completion, `nvmtl_ws_release` (`:153`) releases the mark and publishes
  deferred textures.
- `nvmtl_vk_accel_surface_wait()` (`nvmtl_vk.c:1927`) reads the
  `NVAccelSurfaceWait` IORegistry property to decide whether a page-off waits
  for the GPU.
- `-[NVMTLCommandBuffer commitAndWaitUntilSubmitted]`
  (`NVMTLObjects.m:5031`) waits for completion in WindowServer when the
  kernel-side wait is unavailable.

There is no `VK_KHR_swapchain`, `VkSwapchainKHR`, `VkPresentInfoKHR` or
`vkQueuePresentKHR` anywhere in the plugin. Presentation is entirely
Apple `MTLDrawable`/`IOSurface` + NVAccel.

### External host memory

`nvmtl_vk_buffer_import_host` (`nvmtl_vk.c:1406-1449`) is the only standard
external-memory path:

- requires `VK_EXT_external_memory_host` and a power-of-two
  `minImportedHostPointerAlignment` (`:1026-1031`)
- requires pointer and size to be multiples of that alignment (`:1411`)
- queries `vkGetMemoryHostPointerPropertiesEXT` with
  `VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT` (`:1417`)
- creates a buffer with `VkExternalMemoryBufferCreateInfo`, allocates with
  `VkImportMemoryHostPointerInfoEXT`, binds it (`:1420-1445`)
- on any failure, `newBufferWithBytesNoCopy` falls back to a private/shared
  copy and resyncs at submission (`NVMTLDevice_contract.m:56-67`)

This path is portable in principle, but the current code is compiled into the
macOS plugin and uses Apple allocator semantics. It is not a standalone Linux
import API.

## 8. Timeline and shared-event architecture

There are **no Vulkan semaphores** in the backend. The extension list has no
timeline semaphore; `DEVICE_FNS` has no `vkCreateSemaphore`; `VkSubmitInfo`
has no wait/signal arrays (`nvmtl_vk.c:5730`).

Metal events are emulated as follows:

- `NVMTLEvent`/`NVMTLSharedEvent` hold `uint64_t _value` and an
  `NSCondition` (`NVMTLObjects.h:154-155`).
- `encodeWaitForEvent:value:` records a boundary
  (`NVMTLObjects.m:5026` → `NVMTLEventSync.m:346`). The command buffer is
  split into parts; the part with the wait is held until
  `signaledValue >= value` is observed on the CPU (`NVMTLEventSync.m:620-627`).
- `encodeSignalEvent:value:` records a signal part
  (`NVMTLObjects.m:5025` → `NVMTLEventSync.m:365`). The CPU calls
  `setSignaledValue:` only after `nvmtl_vk_submit_finish` has waited for that
  part's fence (`NVMTLEventSync.m:640-673`).
- `NVMTLSharedEvent` notifications use `MTLSharedEventListener.dispatchQueue`
  and are fired from the CPU after the signal (`NVMTLEventSync.m:797-821`).
- Cross-process shared events are explicitly not built:
  `newSharedEventWithHandle:` → `nil` (`NVMTLDevice.m:1759`);
  `newSharedEventHandle` → `nil` (`NVMTLObjects.m:5215`).

Therefore:

- A Metal event is not a GPU timeline semaphore. GPU work can be split and
  serialized by CPU waits; latency is higher and ordering is coarser.
- “Wait already satisfied/ promised” may be folded into the channel
  (`NVMTLEventSync.m:485-492`, `:549-552`), which is an optimization, not a
  GPU wait.
- Any analysis that assumes Vulkan timeline semaphores or cross-process
  event sharing is wrong for this source.

## 9. AIR → SPIR-V architecture

### 9.1 Container and conversion

1. A metallib is scanned for bitcode wrapper magic `DE C0 17 0B`
   (`NVMTLLibraryLoad.m:901`). `off`/`size` fields are read from the wrapper
   (`:902-906`).
2. `nvmtl_air_to_text` (`:632`) turns the AIR blob into LLVM IR text:
   - in-process: `air-runtime/libLLVM.dylib`, `LLVMParseBitcodeInContext2` +
     `LLVMPrintModuleToString` (`:600-630`)
   - out-of-process fallback: `/Library/GPUBundles/nvmtl/air-opt -S`
     (`:441-468`)
   - result cached by SHA-256 of the blob (`:432-438`)
3. `nvmtl_index_metallib_uncached` (`:894`) maps function names to AIR and
   stage metadata, including `MTLB` dynamic-library exports (`:917-925`).
4. `nvmtl_compile_library_entry` (`:850`) calls the translator:
   `xlate(ll, stage, ...)` (`:862`), writes/reads the SPIR-V cache, and
   returns `NSData` of SPIR-V.
5. `nvmtl_translate_metallib_k` (`:1125`) memoizes function dictionaries and
   manages the 128 MiB budget (`:1152`).

Everything above is Objective-C/macOS-specific and depends on external Apple
or NVIDIA LLVM tooling. The executable bitcode path is not reproducible from
this repository alone.

### 9.2 Translator pipeline

The translator is a Rust crate (`metal2vulkan`, LGPL-3.0-or-later), not an
NVK or NVIDIA component. It consumes **LLVM IR text**, not Metal API calls.

```text
translate                          translator/translator/src/lib.rs:61
  → translate_with_options         :65
  → air_to_sanitized_ll            src/tools.rs:131
      → llvm-dis for .air, or read .ll
      → target triple := spirv-unknown-vulkan1.2
  → parse stage metadata           !air.vertex/!air.fragment/!air.kernel
  → typed LLVM/AIR parse + native  emitter
  → owned SpirvModule + passes
  → finish_module                  src/lib.rs:1043
  → spirv-val --target-env vulkan1.2   src/tools.rs:310
```

Key contracts from the translator's own docs:

- Output target is SPIR-V for Vulkan 1.2 (`VULKAN_TARGET_ENV`,
  `src/tools.rs:128`).
- Descriptor ABI: buffers 0..32, sampled textures 32..160, samplers 160..192,
  colors 192..200, storage textures 480..608, all set 0
  (`docs/ARCHITECTURE.md`, “Layout and interfaces”). The plugin uses the same
  bands, plus specialized sets for vertex/bindless/address tables.
- Unsupported inputs fail visibly; `spirv-val` is a backstop, not a repair
  loop (`docs/ARCHITECTURE.md`).
- It requires external `llvm-dis` and `spirv-val`; these are not vendored.
- It does **not** use NVIDIA NVVM/PTX on the product path.

### 9.3 Optional NVIDIA compiler path

`plugin/NVMTLVendorCompiler.m` can compile AIR through
`NVIDIAShared.bundle`/`MTLCompiler`/`NVSCompileAIRText` into SASS, and
`NVMTLSass.m` can dispatch that SASS through NVK's private hook. This path is
optional and NVIDIA-specific. It is not needed for the Vulkan/SPIR-V route and
must not be conflated with the translator.

## 10. Claims vs tested reality

| Claim | Source | Reality in this pin |
|---|---|---|
| macOS 15 Sequoia tested | `README.md:3,24` | Upstream claims 15.7.x/15.8.1; `docs/CARD-SUPPORT.md:65` reports RTX 5060/15.8.1 tests. GA40 did not run it. |
| macOS 26 Tahoe | CHANGELOG and TROUBLESHOOTING describe fixes | README still scopes the product to macOS 15. `docs/EVENT-WAIT.md:33-39` explicitly says the Tahoe run used a locally repaired plugin/NVAccel and “does not qualify macOS 26 support generally.” Treat Tahoe as **unvalidated for 2.4.3**. |
| Metal 3 / argument buffers tier 2 | README | `argumentBuffersSupport` returns Tier 2 (`NVMTLDevice.m:1934`); actual support depends on the translator and fixed descriptor ABI. |
| Ray tracing | README | Enabled only when NVK exposes AS + ray query; the log itself calls it “NVK's software BVH” (`nvmtl_vk.c:1018`). Not hardware RT. |
| Mesh shaders | README | Translators lower mesh/object stages (`translator/translator/src/mesh_lower.rs`); the plugin has no `VK_EXT_mesh_shader` request. Not native Vulkan mesh shaders. |
| Turing+ / 245 IDs | README, CARD-SUPPORT | Device table is broad; physical validation is RTX 5060 automated, 5070/5080 user reports, Turing/Ampere/Ada “Pending” (`docs/CARD-SUPPORT.md:11-16`). |
| OpenGL/OpenCL/Core Image/Core ML | README | Depends on Apple frameworks and NVIDIAShared; not validated in GA40 and not part of the Metal→Vulkan backend. |
| “Open source” | README | Source-available under PolyForm Noncommercial 1.0.0, not OSI open source; translator LGPL; NVK patch MIT. See `reference/licenses/LICENSES.md`. |
| Intel/AMD support | vendor code | Code path exists only through `NMXAccel`; no evidence for Intel hardware, stock i915/ANV, or GA40's target. |
| Cross-process shared events | none | Explicitly returns nil. |
| IOSurface sharing | README/HOW-IT-WORKS | NVK-private escape; not portable Vulkan external memory. |

## 11. What this means for GA40

- The **Metal API layer** is a large Objective-C reimplementation coupled to
  Apple's private `MTLIOAccelDevice`, IOSurface, WindowServer and IOKit. It is
  not a reusable cross-platform Metal implementation.
- The **translator** is the most separable substantial component: pure Rust
  CPU code, LGPL, SPIR-V 1.2 output, with external `llvm-dis`/`spirv-val`.
  It still depends on a macOS AIR→LLVM-text front end that is not in the repo.
- The **Vulkan backend** (`nvmtl_vk.c`) is mostly standard Vulkan core plus a
  long list of optional extensions, but its presentation, IOSurface, event and
  SASS paths are NVIDIA/NVK/Apple-specific. It is a reference for contracts,
  not a drop-in Linux backend.
- A small set of **pure-C headers** is directly usable on Linux; see
  `reports/REUSE-MATRIX.md` for the exact files, sizes and licence terms.

## 12. Evidence limits

- Static source reading only; no compilation, no `ocvalidate`, no `cargo
  build`, no macOS run, no GPU enumeration, no driver load.
- Line numbers are from commit `47f818b`; they will drift on any other commit.
- The clone is shallow, so history-based provenance (which commit introduced a
  line) is unavailable.
- “Tested” statements above are upstream claims unless explicitly marked as a
  GA40 check. GA40 has not validated Metal, Vulkan, Intel, Tahoe or any
  hardware path.
