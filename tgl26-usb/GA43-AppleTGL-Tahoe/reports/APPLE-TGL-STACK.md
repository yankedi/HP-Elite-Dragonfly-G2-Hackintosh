# Apple Tiger Lake 原生驱动栈（任务 A）

状态标记：`VERIFIED_SOURCE` 表示已读固定 commit 的源码；`VERIFIED_BINARY`
表示已对本地 16.0.32 二进制做 Mach-O 符号/字节检查；`VERIFIED_CPU_TEST`
表示本机 CPU 测试通过；`NEEDS_TARGET_BINARY` 表示必须用 25G83 原始文件复核；
`BLOCKED_SDK` 表示缺 macOS SDK/链接器；`NOT_TESTED` 表示未实机验证；
`UNSAFE_FOR_TARGET` 表示当前证据下不应在目标机启用。

## 0. 结论摘要

1. **可以复用 Apple 已有的 GPU 内存管理、调度器、上下文和任务提交。**
   `AppleIntelTGLGraphics.kext` 的 Mach-O 导出符号中实际存在
   `IntelAccelerator`、`IGPagePool`、`IGScheduler3/4/5`、
   `IGHardwareCommandStreamer5`、`IGHardwareRingBuffer`、
   `IGHardwareContext`、`IGAccelResource`、`IGAccelTask` 等类。它们不是
   NootedGreen 自己实现的；NootedGreen 只是 hook/route/byte-patch 这些 Apple
   代码。因此“必须先从零移植 i915/XNU 才能让 GPU 执行”不是本路线的必要前提。
   `VERIFIED_BINARY`。

2. **Apple TGL 16.0.32 是 Big Sur 时代的旧二进制，不是 Tahoe 原生构建。**
   NootedGreen 固定树内的 donor：
   `AppleIntelTGLGraphics` 的 `CFBundleShortVersionString=16.0.32`，
   `version.plist` 的 `SourceVersion=16000032000000`，framebuffer 的
   `BuildMachineOSBuild=20A2313`；MTL driver 的 `LC_BUILD_VERSION` 为
   `minos 10.16.0 / sdk 10.16.0`。所以“复用 Apple TGL 驱动”实际是
   **把旧 TGL 用户态/内核态驱动接到 Tahoe 的 Metal/IOAF2 上**，不是直接使用
   Tahoe 自带的 TGL 栈。`VERIFIED_BINARY`。

3. **真正的不兼容主要在用户态 Metal ABI、IOSurface 偏移、编译器接口和
   IOAcceleratorFamily2 行为；不是 Gen12 指令集本身。**
   `libxedrv.m`、`compiler-adapter.cpp`、`llvm-bridge.cpp` 和
   `patch-mtl17.py` 处理这些差异。`VERIFIED_SOURCE`；25G83 的具体二进制
   仍需复核（`NEEDS_TARGET_BINARY`）。

4. **9A49 的 `isRealTGL` 为真。** NootedGreen 用 CPUID family 6 model
   `0x8C/0x8D` 判定真 TGL；i5-1135G7 属于 TGL-U，应为 `0x8C`。
   因此 RPL/ADL 专属分支应跳过。**但参考实现把部分 Tahoe 布局修复
   （XE-FMT、XE-PLANES2）也放进了 `if (!isRealTGL)` 块，真 TGL 反而不会执行。**
   这是本阶段最重要的代码级发现之一。`VERIFIED_SOURCE`。

5. **Metal 加速的“最后一公里”不是内核驱动，而是签名/加载策略。**
   参考项目要求 `amfi_get_out_of_my_way=1`，本任务明令禁止。没有等价的
   合法签名/加载路径时，方案 A 只能做离线分析和受控构建，不能部署。
   `UNSAFE_FOR_TARGET`（就当前约束而言）。

6. **Mesa ANV / i915-XNU 不是方案 A 的必要组件。** 它们仍是方案 B 的主体；
   在方案 A 中最多作为诊断/回退路径，不应与 Apple 加速器同时接管 GPU。

## 1. 组件、版本与来源

固定输入（完整哈希见 `docs/provenance.json` 与
`docs/provenance/*-SHA256SUMS`）：

| 组件 | 版本/来源 | SHA-256（关键文件） | 证据 |
|---|---|---|---|
| `AppleIntelTGLGraphics.kext`（原始 `sle/`） | GPUDriversIntel 16.0.32，NootedGreen 固定 commit `95f8189` | `890735a93a19d3ddda24ff31bda3075dbd145fb7b26c11769f33c4564a8027ac` | `VERIFIED_BINARY` |
| 同上，`le/` 改名/重签副本 | `com.xxxxx.driver.AppleIntelTGLGraphics`，同一 UUID `ba3aa1c0…` | `1b2f5aa3131f9b909fe984877e41d5ebcdb2837572b45e1e901a72a6271515a2` | `VERIFIED_BINARY`；与 `sle/` 字节不同，不能混用哈希 |
| `AppleIntelTGLGraphicsFramebuffer.kext`（`le/`） | 16.0.32，UUID `b96a8448…` | `285ee7a9c3d6c9a9647013f44fb40f312b1cb42879974ef0542544cf049442b5` | `VERIFIED_BINARY` |
| 同上（`lep/` 变体） | 16.0.32，UUID `b6078743…`，体积更小 | `a562cff08e08bda3eab6f4f550368f46d50155f2c6341af460377be6b2444f56` | `VERIFIED_BINARY`；与 `le/` 不是同一二进制 |
| `AppleIntelTGLGraphicsMTLDriver` | 16.0.32，LC_BUILD_VERSION minos 10.16.0 | `e21a8d127c83877599c6e52cc0a8bdb81a968db75ab98345079bf367d2b17d3f` | `VERIFIED_BINARY` |
| `libigc.dylib` | 16.0.32 | `9ff8b3b36f0b27707d861d17ee1e251ef59f22154e709e5e513151b0c0b0dee8` | `VERIFIED_BINARY` |
| `libMTLIGCCompilerPlugin.dylib` | 16.0.32，LLVM 3902 | `477083cb773da4dc814d97fa1a64611194c6ecf4bb7b98c3d4ea31094c1df667` | `VERIFIED_BINARY` |
| 25G83 `AppleIntelTGLGraphics`（目标哈希） | IntelIGPU-Tahoe `docs/DEPLOY-SAME-HARDWARE.md` 声明 | `ae99582bd5a945494ee684d339ac1abd0526828bcd3ea981239c0fd38f794d47` | `NEEDS_TARGET_BINARY`（本机无文件） |
| 25G83 `AppleIntelTGLGraphicsMTLDriver`（目标哈希） | 同上 | `4c161bc54a3038c1e7539545175f5c928ee2fe50bda12bf833d7057337f1fecf` | `NEEDS_TARGET_BINARY`（本机无文件） |

**来源说明。** 这些 Apple 二进制是 `sgiammori/NootedGreen` 固定 commit 的
`sle_Internal/` 内容，不是本阶段另行下载的 Apple 驱动。仓库只记录哈希，
不复制/再分发它们；`inputs/upstream/` 也被 Git 忽略。参考项目作者明确说
donor 来自该 NootedGreen 集合（`docs/HISTORY.md`、`macos/build-all.sh`）。

**版本差异。** NootedGreen 的 `sle_Internal/sle/` 与 25G83 的原始文件哈希不同，
这证明“同一 16.0.32 版本号”不等于“同一字节”。`patch-mtl17.py` 的固定
文件偏移必须在目标文件上重新核对，不能把 25G241 的 donor 补丁直接套到
25G83。`NEEDS_TARGET_BINARY`。

## 2. 完整调用链

```text
macOS Metal.framework / 应用 / WindowServer
        │  MTLDevice / MTLCommandQueue / MTLRenderPipelineState
        ▼
AppleIntelTGLGraphicsMTLDriver.bundle
  MTLIGAccelDevice / Buffer / Texture / CommandQueue / encoders
        │  IOAccelerator.framework 用户态 API
        │  IOAccelDeviceGetConnect / IOAccelResource* / IOSurface*
        ▼
IOAcceleratorFamily2 (IOAF2)
  IOAccelDevice / IOAccelResource2 / IOAccelSysMemory /
  IOAccelCommandBufferPool2 / IOAccelDisplayPipeTransaction2
        │  IOConnect / shared memory / user client
        ▼
AppleIntelTGLGraphics.kext
  IntelAccelerator
  IGScheduler3/4/5, IGHardwareCommandStreamer5,
  IGHardwareRingBuffer, IGHardwareContext, IGPagePool,
  IGAccelResource, IGAccelTask, resolves, display pipe
        │  MMIO / GGTT / PPGTT / batch buffer / interrupts
        ▼
Intel Iris Xe (Gen12 Xe-LP): RCS / BCS / VCS, EUs, L3, display engine
```

### 2.1 Metal → MTL driver

`AppleIntelTGLGraphicsMTLDriver` 是用户态 dylib，Mach-O 中定义了
`MTLIGAccelDevice`、`MTLIGAccelBuffer`、`MTLIGAccelTexture`、
`MTLIGAccelCommandQueue`、`MTLIGAccelCommandBuffer`、
`MTLIGAccelRenderCommandEncoder`、`MTLIGAccelComputeCommandEncoder`、
`MTLIGAccelBlitCommandEncoder`、`MTLIGRenderPipelineState` 等类。
它动态链接：

- `Metal.framework`
- `IOAccelerator.framework`
- `IOSurface.framework`
- `IOKit.framework`
- `CoreFoundation` / `Foundation` / `libobjc` / `libc++`

未定义符号包括 `IOAccelDeviceGetConnect`、`IOAccelResourceFinishEvent`、
`IOAccelResourceGetClientSharedPrivate`、`IOAccelResourceListAddResource`、
`IOAccelResourcePageoff`、`IOAccelSharedGetConnect`、`IOSurfaceGetBaseAddress`、
`IOSurfaceLock` 等。这些符号把 Metal 对象接到 IOAF2 的用户客户端和
IOSurface 共享内存。`VERIFIED_BINARY`（`llvm-nm -u` / `--dylibs-used`）。

### 2.2 MTL driver → IOAF2

MTL driver 本身不直接写 GPU MMIO。它通过 IOAF2 的 `IOAccelDevice` 用户客户端
创建/提交 `IOAccelResource2`、`IOAccelCommandQueue`、`IOAccelEvent` 和
`IOAccelDisplayPipeTransaction2`。参考项目在 `kern_green.cpp` 里 hook 的
IOAF2 方法也印证了这条边界：

- `IOAccelCommandBufferPool2::init` / `getBufferPtrNoInc`
- `IOAccelOrphanedMemoryPool::getMemory`
- `IOAccelSysMemory::lockForCPUAccess` / `unlockForCPUAccess`
- `IOAccelDisplayPipe::transaction_interrupt_gated` /
  `completeTransaction` / `transaction_queue_gated`
- `IOAccelEventMachine2::waitForStamp`
- `IOAccelLegacySurface::set_id_mode`

这些 hook 是 NootedGreen 对 IOAF2 的适配/诊断，不是 Apple TGL kext 的实现。
`VERIFIED_SOURCE`。

### 2.3 IOAF2 → Apple TGL 内核加速器

`AppleIntelTGLGraphics.kext` 是内核 kext（`MH_KEXT_BUNDLE`），导出 3026 个
全局符号。与本链路直接相关的类包括：

| 类/符号 | 作用 |
|---|---|
| `IntelAccelerator` | 加速器主体；`start`/`stop`、GPU 信息、显示 pipe、resolve、命令提交入口 |
| `IGScheduler3` / `IGScheduler4` / `IGScheduler5` | GuC / 主机调度器；`waitForGpuIdle`、`push`、`notify`、`pause`、`resume` |
| `IGHardwareCommandStreamer5` | RCS/BCS/VCS 命令流；`submitExecList`、`prepareExecListAndSubmit`、`setGTFrequencyMMIO` |
| `IGHardwareRingBuffer` | ring 提交、stamp、semaphore wait、reset |
| `IGHardwareContext` | 上下文创建、`restoreFromSafeImage`、LRCA |
| `IGPagePool` | GPU 页池、分配/回收/prune |
| `IGAccelResource` / `IGAccelResource2` | surface/纹理/缓冲资源、plane 表、pageon/pageoff、resolve |
| `IGAccelTask` | 用户任务、Blit2D/3D 上下文、stamp |
| `IGAccelCommandQueue` | 命令队列、coalesced segment、barrier |
| `IGAccelDisplayPipe` | flip、transaction、display stamp |
| `resolve_ccs` / `resolve_hiz_g7` | 压缩/ HiZ resolve |

因此 **GPU 内存管理（GGTT/PPGTT、页池、资源生命周期）、上下文、ring、
调度、提交、中断、reset 和显示 pipe 都已由 Apple kext 提供**。NootedGreen
不需要重新实现这些；它只需要让这些代码在目标硬件/系统上正确运行。
`VERIFIED_BINARY`（符号）＋`VERIFIED_SOURCE`（hook 名称和调用关系）。

### 2.4 Framebuffer

`AppleIntelTGLGraphicsFramebuffer.kext` 负责：

- 显示模式/时序：`AppleIntelFramebuffer`、
  `AppleIntelBaseController::hwCRTCToIODetailedTimingInformation`
- plane 编程：`PLANE_CTL/STRIDE/SURF/SIZE/POS/OFFSET`
- display pipe / transcoder / DDI / eDP link
- DMC、电源、背光、panel power
- `performTransaction`：把 IOAF2 的 flip 事务变成显示引擎寄存器写入

参考项目对 framebuffer 的修改主要是显示 13（ADL-P/RPL-P）的 DPT、DBUF S1、
gamma、boot timing、brightness 和 DPMS；这些不应默认用于 TGL display 12。
`VERIFIED_SOURCE`；具体寄存器行为仍需目标硬件验证。

### 2.5 GPU 硬件边界

内核 kext 通过 BAR0 MMIO 和 GGTT/PPGTT 操作 Gen12：

- ring：RCS0（render）、BCS0（blit）、VCS0（video）
- 上下文：LRCA、PPHWSP、safe image、execlist / GuC
- 内存：GGTT PTEs（`0x800000` 基址）、PPGTT、stolen memory、page pool
- 提交：MI_BATCH_BUFFER_START、MI_LRI、PIPE_CONTROL、semaphore、stamp
- 中断/错误：GT_INTR、CSB、ERROR_GEN6、RING_FAULT、reset

这些是 Apple 驱动的内部实现，不是公开 API；本阶段只做静态符号/反汇编级确认，
没有执行 MMIO 或 batch。`NOT_TESTED`。

## 3. NootedGreen 到底改了什么

NootedGreen 是 Lilu 插件，不是驱动本体。按层次分：

### 3.1 加载与身份

- `kern_start.cpp` 把最大内核版本从 `Sequoia` 改为 `Tahoe`；否则插件在
  macOS 26 不加载。`VERIFIED_SOURCE`（相对 upstream 的唯一差异）。
- `kern_green.cpp` 用 CPUID family/model 判定 `isRealTGL`：
  model `0x8C`（TGL-U）或 `0x8D`（TGL-H）。i5-1135G7 为 `0x8C`。
- 通过 PCI config read hook 和 IORegistry 属性把设备表现为 `9A49`；
  参考项目本身是 RPL `A7A0`，所以必须伪装；本机是原生 `9A49`，不需要
  GPU 拓扑伪装，但仍需要让 Apple kext 的 bundle/personality 匹配。
- `-ngreentglwithgfx` 选择同时加载 TGL framebuffer 和 TGL hardware kext；
  `-ngreentglfb` 只加载 framebuffer。Gen11+ 的 DBUF 分配在 HW kext 侧，
  FB-only 会留下未编程的 DBUF。`VERIFIED_SOURCE`（README/源码）。

### 3.2 内核 hook / route

- 通过 Lilu `KernelPatcher::routeMultiple` 替换符号实现（如
  `IntelAccelerator::start`、`SafeForceWakeMultithreaded`、
  `IGScheduler5::waitForGpuIdle`、`submitBlit` 等）。
- 通过 `LookupPatchPlus` 做字节 find/replace（如 V46 deviceStart bypass、
  V52 拓扑、XE-FMT、XE-PLANES2、XE-NOCCS3 等）。
- 通过 `SolveRequestPlus` 解析符号（如 `pmap_find_phys`、
  `IGSharedMappedBuffer::getVirtualAddress`）。
- 通过 IOAF2 hook 修命令缓冲池、orphan pool、display pipe 计数等。

### 3.3 用户态

- `libxedrv.m`：注入 MTL driver，转换 Tahoe 的 pipeline descriptor 到
  16.0.32 旧布局，补 selector，禁用不支持的特性，处理 no-copy 纹理和
  blit 排序。
- `patch-mtl17.py`：固定偏移修改 MTL driver 的 Mach-O header、编译器路径和
  若干 GPU 行为字节。
- `compiler-adapter.cpp`：把 Tahoe 的
  `MTLCompilerBuildRequestWithSerializedBitcode` 映射到旧插件的
  `MTLCompilerBuildRequestWithOptions`。
- `llvm-bridge.cpp`：把旧插件（LLVM 3902）的少数符号接到 Tahoe
  `libLLVM`（LLVM 32023），并提供 `getSerializedModule` 的签名扫描。
- `build-shader-compiler.sh`：组装 `xe.bundle`，路径放在
  `/System/Library/Caches/xe.bundle` 以绕过 `MTLCompilerService` 的
  sandbox/前缀规则。

### 3.4 参考项目的“成功”证据边界

参考项目的 `docs/STATUS.md` 声称 Metal 桌面、WindowServer、Dock/Finder、
Mission Control、视频解码等可用；`docs/HISTORY.md` 有大量实验记录。
但这些是**上游作者的机器/系统上的报告和源码注释**，本仓库没有其原始日志、
panic 文件或可复现实验脚本。它们不能直接证明 9A49/25G83 可用。
本报告只把“源码中存在相应实现”标为 `VERIFIED_SOURCE`，把“在该机器上成功”
标为上游声明，不当作本机证据。

## 4. Tahoe Metal ABI 不兼容点

`libxedrv.m` 的注释和代码给出了最具体的差异。以下数字是源码声明，已与
25G83 独立项目的 `pipeline_descriptor_compat.m` 交叉核对：

### 4.1 Pipeline descriptor

- 旧 driver 期望的 `MTLRenderPipelineDescriptorPrivate` 布局约 `0x2e0` 字节；
  Tahoe 的 `_private` 结构更大，`_descriptorPrivate` 返回的指针偏移发生变化。
- `libxedrv` 在 `pd_wrapper` 中复制：
  - `0x00..0xa8` 原样；
  - 旧 `0xa8..0x108` ← 新 `0xb8..0x118`（跳过 `shaderValidation` /
    `shaderValidationState` / `textureWriteRoundingMode`）；
  - 旧 `0xd0` 的 `misc` 位域 ← 新 `0xe0`，通过 21 项 `MISC[]` 表逐位重排；
  - 旧 `0x108..0x128` ← 新 `0x198..0x1b8`；
  - 旧 `0x128..0x148` ← 新 `0x1c0..0x1e0`；
  - 旧 `0x148..0x160` ← 新 `0x1e0..0x1f8`。
- 颜色附件：旧 driver 读取的 bitfield 把
  `blendingEnabled@0`、`rgbBlendOperation@1`、`alphaBlendOperation@4`、
  `sourceRGB@7`、`sourceAlpha@12`、`destRGB@17`、`destAlpha@22`、
  `writeMask@27`、`logicOp@31`、`pixelFormat@36` 等打包；`libxedrv`
  用 `att_wrapper` 重新构造。
- 25G83 独立源码 `pipeline_descriptor_compat.m` 给出同一类布局：
  `MTLRenderPipelineDescriptorInternal` size `0x338`，`_private` offset
  `0x30`；颜色附件 size `0x10`，`_private` offset `0x8`；动态探针
  `rasterSampleCount@0xb8`、`vertexDescriptor@0x110`；`logicOp` 新位 32、
  旧位 27。`VERIFIED_SOURCE`（25G83 项目）；这支持“25G83 的 descriptor
  布局与 25G241 同形”，但仍需目标二进制/运行时探针。

**关键风险：** `libxedrv` 的 `check_layout()` 目前只检查 Objective-C type
encoding 和两个动态探针，不检查 `class_getInstanceSize == 0x338` 或
`_private` offset `0x30`。25G83 项目会检查这些。建议在 TGL/25G83 适配中
补上，避免布局变化时静默转换。`NEEDS_SOURCE_PORT`。

### 4.2 新 selector / 新 API

旧 driver 缺少 Tahoe Metal 使用的 selector。`libxedrv` 做了两类处理：

- 补实现：带 `resourceIndex` 的 texture view 初始化、`newBufferWithDescriptor:`、
  `getGlobalMemoryBuffer` 等。
- 明确拒绝：dynamic libraries、binary archives、mesh shaders、部分 ICB、
  显式 resource index。拒绝时返回 `NSError`/`nil`，不伪造成功。

这不是“完整支持 Tahoe Metal”，而是把 16.0.32 driver 的能力边界如实暴露。
`VERIFIED_SOURCE`。

### 4.3 IOSurface 偏移

参考项目的内核补丁给出：

- `IOSurface+0xa4`：旧 driver 的 `performTransaction+0x81361` 直接读它；
  Tahoe 布局变化后该字段为 0。反汇编确认 16.0.32 在文件偏移 `0x81361`
  执行 `movl 0xa4(%rbx), %eax`，随后比较 `'420x'/'420v'`。
- `IOSurface+0x80`：25G241 的 `getPixelFormat()` 读取位置（源码注释）。
- `IOSurface+0x98`：25G241 的 `getPlaneCount()` 读取位置；16.0.32 的
  `calculateIOSurfaceDeviceCacheVRAMBytes` 在 `0x7287d` 仍读 `+0xb0`。
- 25G83 独立源码 `intel_framebuffer.cpp` 明确写到：
  `TGL 16.0 performTransaction+0x81361 reads IOSurface+0xa4 inline,
  overwriting its default BGRA with zero on 25G83`。这与上面的反汇编一致，
  说明 **25G83 也需要处理这个 stale offset**。`VERIFIED_SOURCE`（25G83
  项目）＋`VERIFIED_BINARY`（16.0.32）。

**但 `+0x98` 不能直接当作 25G83 的 plane count。** 25G83 项目使用导出的
`IOSurface::getPlaneCount()` 方法，而不是假设固定 offset；这是更安全的
策略。`NEEDS_TARGET_BINARY`。

### 4.4 压缩、fast clear、stencil

参考项目的 MTL13–17 和 XE-NOCCS/NOAUX/NOCCS3/NODEPTH 主要是 RPL 的
AUX table / render compression / fast clear / stencil 问题。原生 TGL 支持
这些功能，Apple driver 也应在 TGL 上正常运行；把这些补丁默认套到 9A49
会关闭硬件特性，甚至掩盖真实 bug。`A 类`/`UNSAFE_FOR_TARGET`，默认关闭。

### 4.5 其他 ABI

- `MTLCompilerService` 的插件路径/sandbox 规则：25G241 上需要用
  `/System/Library/PrivateFrameworks/../Caches/xe.bundle/...` 形式；
  25G83 项目使用 `/Library/GPUBundles` 的 GPU bundle principal class，
  但没有使用同一 `xe.bundle` 编译器桥。该路径是否在 25G83 仍成立，
  必须用目标系统的 `MTLCompilerService` 验证。`NEEDS_TARGET_BINARY`。
- `IOAcceleratorFamily2` 的符号/内部偏移：NootedGreen 使用若干固定 offset
  （如 `IOAccelResource2+0xe0`、`+0xf8`、`+0xfc`）。25G83 项目尽量使用
  导出方法，避免 offset。两者不能互相证明；必须在 25G83 二进制/符号上
  重新核对。`NEEDS_TARGET_BINARY`。

## 5. Shader Compiler 桥

### 5.1 新旧入口

- Tahoe 的 `MTLCompiler` 调用
  `MTLCompilerBuildRequestWithSerializedBitcode(compiler, input, rdx, flags,
  bitcode, size, stack...)`，bitcode 为 LLVM 32023 格式。
- 旧 TGL 插件只导出
  `MTLCompilerBuildRequestWithOptions(compiler, input, rdx, flags, Module*,
  stack...)`，链接 LLVM 3902。
- `compiler-adapter.cpp` 提供新入口，把 `bitcode/size` 解析为 LLVM Module，
  再调用旧入口。其注释说明参数映射：旧 `r9` = 新 `stack[0x10]`；旧
  `stack[0x10..0x38]` = 新 `stack[0x18..0x40]`。
- `llvm-bridge.cpp` 重新导出 Tahoe `libLLVM`，并补旧插件需要的
  `WriteBitcodeToFile`、`raw_string_ostream` 析构、`parseIRFile`、
  `getNamedMetadata`、`Value::setName` 等符号；其中
  `getSerializedModule` 通过签名扫描定位，而不是固定 offset（v2）。

### 5.2 为什么需要桥

旧插件不能直接吃 Tahoe 的 LLVM 32023 bitcode；Tahoe 的 `libigc` 又没有
Gen12LP。参考项目的做法是：

1. 保留 Apple 16.0.32 的 `libigc.dylib` + `libMTLIGCCompilerPlugin.dylib`
   （唯一 Gen12LP 编译器）。
2. 用 adapter 把新 API 降到旧 API。
3. 用 bridge 把旧插件的 LLVM 3902 符号接到 Tahoe 的 LLVM 32023。
4. 把整个 `xe.bundle` 放到 `MTLCompilerService` 能读的路径。

`VERIFIED_SOURCE`。**未验证：** 25G83 的 `MTLCompiler` 是否仍有相同的
`getSerializedModule` 签名；`GPUCompiler 32023` 路径是否存在；bridge 的
Twine/`raw_string_ostream` 布局是否仍匹配。`NEEDS_TARGET_BINARY`。

## 6. 复用判断（对应任务 A 的六个问题）

### Q1：能否复用 Apple 已有的 GPU 内存管理和任务提交？

**能。** `AppleIntelTGLGraphics.kext` 已包含 `IGPagePool`、GGTT/PPGTT、
`IGAccelResource`、`IGHardwareContext`、`IGScheduler*`、
`IGHardwareCommandStreamer5`、`IGHardwareRingBuffer`、`IGAccelTask` 等。
方案 A 的核心价值就是复用这些，而不是重写 i915 GEM/提交。`VERIFIED_BINARY`。

### Q2：哪些功能已经由 Apple TGL 驱动完成？

- 显示模式/时序/plane/transcoder/DDI/eDP（framebuffer kext）
- 显示 pipe flip/transaction（`IGAccelDisplayPipe`）
- GPU 页池、资源、GGTT/PPGTT、stolen memory
- 上下文、LRCA、safe image、execlist/GuC 调度
- ring、batch、semaphore、stamp、中断、错误/reset
- 频率/电源/RC6/GuC（真 TGL 上）
- resolve（CCS/HiZ）、blit 2D/3D
- Metal 用户态对象/命令编码（MTL driver）
- IGC Gen12LP shader 编译（旧 `libigc`）

这些是“已实现”，不等于“在本机已正确工作”；后者需要目标验证。

### Q3：NootedGreen 具体修改了什么？

见第 3 节。概括：加载/身份、CPU 检测、kext personality、符号 hook、
字节 patch、IOAF2 hook、显示/调度/内存/压缩修复、用户态 ABI adapter、
编译器桥。它不是驱动本体。

### Q4：Tahoe 的 Metal ABI 哪里与旧 TGL 驱动不兼容？

- pipeline descriptor 的 `_private` 布局、`misc` 位域、颜色附件 bitfield
- 新 selector/resourceIndex、dynamic library/binary archive 能力
- `_descriptorPrivate` 返回结构的偏移/大小
- IOSurface 的 pixel format/plane count 偏移
- `MTLCompilerService` 的入口、LLVM 版本、插件路径/sandbox
- IOAF2 的 transaction option 语义、命令缓冲池/orphan pool 行为
- no-copy 纹理 offset、2D/3D blit 排序、Stencil8 对齐

前四项有源码/二进制证据；后几项有参考项目实验记录，但仍需 25G83 复核。

### Q5：Shader Compiler 的新旧 LLVM 接口如何连接？

adapter + bridge + 旧插件 + 旧 `libigc`，见第 5 节。关键风险是
`getSerializedModule` 签名扫描和 Twine 布局；这两项在 25G83 上未验证。

### Q6：是否仍需要 Mesa ANV 或 i915/XNU？

**方案 A 的主路径不需要。** Apple kext 已提供内核内存/提交/调度；Mesa ANV
是方案 B 的用户态 Vulkan 栈，i915/XNU 是方案 B 的内核后端。把它们混入
方案 A 会增加复杂度，并可能与 Apple 加速器争夺 PCI/MMIO/上下文。
Mesa/ANV 可以保留为诊断或未来回退，但不应作为方案 A 的前置条件。

## 7. 本阶段未证明 / 下一步必须取证

| 项目 | 状态 | 需要的证据 |
|---|---|---|
| 25G83 `AppleIntelTGLGraphics` 原始文件 | `NEEDS_TARGET_BINARY` | 目标系统只读复制 + SHA-256；确认 `ae995…` 是否为该文件 |
| 25G83 `AppleIntelTGLGraphicsMTLDriver` | `NEEDS_TARGET_BINARY` | 同上；确认 `4c161…`、Mach-O UUID、LC_BUILD_VERSION、header 布局 |
| 25G83 `Info.plist` 16.0.32 | `NEEDS_TARGET_BINARY` | `CFBundleShortVersionString`/`CFBundleVersion`/personality |
| 25G83 `IOAcceleratorFamily2` 符号/偏移 | `NEEDS_TARGET_BINARY` | 符号表（`nm`/`kcsyms`）与目标 IOAF2 二进制 |
| 25G83 `MTLCompiler` / `GPUCompiler` | `NEEDS_TARGET_BINARY` | `dyld_info -exports`、`getSerializedModule` 签名、LLVM 版本 |
| 25G83 Metal descriptor 布局 | `VERIFIED_SOURCE`（独立项目） | 运行时 `class_getInstanceSize`/ivar offset/探针；目标机日志 |
| 9A49 上 Apple TGL 驱动原生加载 | `NOT_TESTED` | 一次受控启动日志；仍受签名/AMFI 限制 |
| 9A49 Metal 桌面/WindowServer | `NOT_TESTED` | 实际 GPU 提交、flip、像素证据；不能以 framebuffer 输出代替 |
| 签名/AMFI 合法路径 | `UNSAFE_FOR_TARGET` | 当前禁止 `amfi_get_out_of_my_way=1`；需要合法签名/加载方案或新授权 |

**结论：** 方案 A 在架构上比从零移植 i915 更接近目标：它复用了 Apple 的
内核 GPU 管理和提交，只需要解决旧驱动的 Tahoe 用户态 ABI、少量 OS 布局
补丁和加载/签名问题。但它不是“复制 EFI 即可”，而且当前参考实现依赖
被禁止的 AMFI 绕过；在本阶段只能继续离线适配和取证，不能部署。
