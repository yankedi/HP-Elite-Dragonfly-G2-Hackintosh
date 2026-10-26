# GA4.3 — Apple Tiger Lake 原生 Metal 驱动适配：第一阶段报告

日期：2026-10-22
目标：HP Elite Dragonfly G2，i5-1135G7，Tiger Lake-U `8086:9A49`，
macOS Tahoe 26.6.2 / 25G83，x86_64。

**结论：第一阶段（源码验证、补丁分类、25G83 兼容分析、目标配置、只读预检、
受控构建检查）已交付；严格整体目标“在 9A49/25G83 上实际启用 Metal 硬件加速”
仍是 UNMET。** 本阶段没有安装/加载任何驱动，没有改 EFI/NVRAM/SIP/SSV/AMFI，
没有 SSH 目标 macOS，没有 GPU MMIO/batch。所有“成功”只指本报告明确标注的
源码、二进制、CPU 测试或对象编译层级。

## 一、最重要的发现

1. **Apple 原生 TGL 栈的内核下半身是可复用的。**
   `AppleIntelTGLGraphics.kext` 实际导出 `IntelAccelerator`、`IGScheduler3/4/5`、
   `IGHardwareCommandStreamer5`、`IGHardwareContext`、`IGPagePool`、
   `IGAccelResource`、`IGAccelTask`、`IGHardwareRingBuffer` 等类；GPU 内存、
   上下文、ring、调度、提交、中断/复位和显示 pipe 都已存在。
   `VERIFIED_BINARY`。这意味着方案 A 不需要先从零移植 i915/XNU 才能开始。

2. **参考项目复用的是 Big Sur 时代的 16.0.32 驱动，不是 Tahoe 原生驱动。**
   donor MTL driver 的 `LC_BUILD_VERSION` 是 `minos 10.16.0`，framebuffer 的
   `BuildMachineOSBuild` 是 `20A2313`。Tahoe 适配主要发生在用户态 Metal ABI、
   IOSurface 布局、IOAF2 行为和 shader compiler 桥，而不是 Gen12 指令集。
   `VERIFIED_BINARY`。

3. **`isRealTGL` 在 9A49 上为真，但参考实现把两个 Tahoe 修复放错了分支。**
   NootedGreen 用 CPUID model `0x8C/0x8D` 判定真 TGL；i5-1135G7 是 TGL-U，
   应走真 TGL 分支。可是 `XE-FMT`（IOSurface 格式）和 `XE-PLANES2`
   （plane count）被放在 `if (!isRealTGL)` 块内，真 TGL 反而不会执行。
   这两个修的是 Tahoe 对象布局，不是 RPL 硬件特性。`VERIFIED_SOURCE`。

4. **`-ngreenxefix` 不是 Tiger Lake 兼容开关。**
   它把 display 13（ADL-P/RPL-P）寄存器过滤、BLR、FBDPMS、命令池、
   NOORPHAN 和整套 RPL CSB/ELSQ hook 一起打开；其中多项没有 `isRealTGL`
   保护。真 TGL 上直接使用会改变 display 12/原生调度/电源路径。
   `VERIFIED_SOURCE`。必须拆成 TGL 专用 profile。

5. **真正的部署阻塞是签名/AMFI，不是代码编译。**
   参考实现要求 `amfi_get_out_of_my_way=1`；本任务明令禁止。没有合法
   签名/加载路径时，即使所有离线代码都通过，也不能在目标机部署。
   `UNSAFE_FOR_TARGET`（当前约束）。

6. **25G83 与 25G241 的 ABI 形状有独立源码证据，但目标二进制仍缺失。**
   25G83 的 IntelIGPU-Tahoe 源码确认：pipeline descriptor 的
   size/offset/bit 位置与 25G241 适配器同形；`performTransaction+0x81361`
   仍读 `IOSurface+0xa4` 并得到 0；GPU bundle 机制存在。但所有固定偏移的
   MTL patch、IOAF2 符号/内部结构、`+0x98` plane count、MTLCompiler/LLVM
   路径都必须用 25G83 原始文件复核。`NEEDS_TARGET_BINARY`。

## 二、交付物与状态

| 交付物 | 路径 | 状态 |
|---|---|---|
| 中文最终报告 | `FINAL-REPORT.md` | 本文件 |
| 逐补丁矩阵 | `reports/TGL-PATCH-MATRIX.md` | `VERIFIED_SOURCE` + 二进制复核 |
| 25G83 兼容性 | `reports/TAHOE-25G83-COMPAT.md` | 源码级 `[1]/[2]`；二进制 `[3]/[4]` |
| 原生驱动栈 | `reports/APPLE-TGL-STACK.md` | `VERIFIED_SOURCE` + `VERIFIED_BINARY` |
| 目标配置 | `configs/tgl-9a49-25G83.json` | `ANALYSIS_ONLY`，部署禁止 |
| 只读预检工具 | `tools/check-tgl-compat.py` | `VERIFIED_CPU_TEST` |
| 单元测试 | `tests/test_check_tgl_compat.py` | 14/14 通过 |
| 构建检查 | `reports/BUILD-VALIDATION.md` + `logs/build/` | 12 对象 `COMPILED`；完整 kext `BLOCKED_SDK` |
| 提交台账 | `reports/GIT-COMMITS.md` | 9 个单元 + 交付提交 |
| 下一阶段计划 | `reports/NEXT-STEPS.md` | 最小 P0–P5 |

状态图例：`VERIFIED_SOURCE`（源码已读）、`VERIFIED_BINARY`（Mach-O 符号/
字节已查）、`VERIFIED_CPU_TEST`（CPU 测试通过）、`COMPILED`（对象/组件编译
通过）、`NEEDS_TARGET_BINARY`（缺 25G83 原始文件）、`BLOCKED_SDK`（缺 macOS
SDK/链接器）、`NOT_TESTED`（未实机）、`UNSAFE_FOR_TARGET`（当前证据/约束下
不应启用）。

## 三、任务 A：Apple TGL 栈到底实现了什么

完整分析见 `reports/APPLE-TGL-STACK.md`，这里只列结论：

### 1. 调用链

```text
Metal / WindowServer
  → AppleIntelTGLGraphicsMTLDriver（MTLIGAccel*，用户态命令编码）
  → IOAcceleratorFamily2（IOAccelDevice/Resource/CommandQueue/DisplayPipe）
  → AppleIntelTGLGraphics.kext（IntelAccelerator/IGScheduler/IGHardware*/IGPagePool）
  → Intel Iris Xe Gen12（RCS/BCS/VCS、GGTT/PPGTT、EU、display）
```

### 2. 哪些已由 Apple 完成

- GPU 页池、GGTT/PPGTT、资源生命周期；
- 上下文/LRCA/safe image、execlist/GuC、ring、batch、semaphore、stamp；
- 中断、错误、reset、频率/电源/RC6（真 TGL 上）；
- 显示模式/时序/plane/transcoder/DDI/DPMS；
- 2D/3D blit、CCS/HiZ resolve；
- Metal 用户态对象/命令编码；
- IGC Gen12LP shader 编译（旧 `libigc`）。

### 3. NootedGreen 改了什么

加载/身份、CPUID 检测、kext personality、符号 route、字节 patch、IOAF2 hook、
显示/调度/内存/压缩修复、用户态 `libxedrv`、编译器 adapter/bridge。
它不是驱动本体；它让旧 Apple 驱动在非原生系统/硬件上工作。

### 4. 关键不兼容

- `MTLRenderPipelineDescriptorPrivate` 的 `_private` 布局、`misc` 位域、
  颜色附件 bitfield；
- 新 selector/resourceIndex、dynamic libraries/binary archives；
- `IOSurface+0xa4` 的 stale format、`+0x98` 的 plane count；
- `MTLCompilerService` 的入口/LLVM 版本/插件路径/sandbox；
- IOAF2 transaction option 与命令池/orphan 池行为；
- no-copy 纹理 offset、2D/3D blit 排序、Stencil8 对齐。

### 5. 是否还需要 Mesa ANV / i915-XNU？

**方案 A 主路径不需要。** 它们属于方案 B；混入会与 Apple 加速器争夺
PCI/MMIO/上下文。可保留为诊断/回退，不作为方案 A 前置条件。

## 四、任务 B：TGL / RPL 补丁分类

完整矩阵见 `reports/TGL-PATCH-MATRIX.md`。分类结果：

- **A 类（RPL/ADL 专属，TGL 不需要）：** V52 拓扑硬编码、V46 deviceStart、
  V54/V65/V507 中断/execlist、V57/V71 错误风暴、V111 deviceStart force、
  V132/V148/V165 Blit3D、V212 idle、V509 LRCA、V99R/V99G、V193、
  display 13 xefix（DPT/DBUF S1/GAMMA）、BLR、FBDPMS、GTFREQ、IDLEBOUND、
  CSBGUARD/CSBRESYNC、SAMETAIL/ELSQ/POSH、MTL13–18、PoshDisable。
- **B 类（TGL 也需要的 Tahoe 修复）：** `kern_start` Tahoe、`isRealTGL`
  检测、`-ngreentglwithgfx` 加载、`XE-VALD`、`XE-FMT`、`XE-PLANES2`、
  `XE-POOLALIGN`（需拆出）、`libxedrv` descriptor/selector、compiler
  adapter/bridge。注意 `XE-FMT`/`XE-PLANES2` 当前被 `!isRealTGL` 挡住。
- **C 类（通用稳定性）：** `XE-PAGESYNC`、`XE-RESFREE`、`XE-NOORPHAN`、
  `libxedrv` v15/v16/v17（需 TGL 重测）。
- **D 类（未知/危险）：** `XE-NOCCS3`、`XE-NODEPTH`、`XE-BLITALIGN`、
  `V40`、`V221`、`forceWake` 替换、`HANGCHECK`、`V204 ccont`、
  `XE-BOOTHOLD`、`PSMI` 在 TGL 上的必要性未证明。

### 守卫审计的关键结论

- 在 `-ngreenxefix` 下但没有 `isRealTGL` 保护：display 13 过滤、BLR、
  FBDPMS、POOL/POOLALIGN、NOORPHAN、ringDiag/flipDiag、BLITSCRATCH2
  等。真 TGL 不能整体打开 xefix。
- 被 `!isRealTGL` 挡住但其实是 B 类：`XE-FMT`、`XE-PLANES2`（以及可能
  部分 `XE-NOCCS3/NODEPTH` 的 Tahoe pool 问题，但后者仍归 D）。
- 完全无条件：`XE-VALD`、`V40`、`V221`、`XE-RESFREE`、`XE-GTFREQ`、
  `XE-IDLEBOUND`、`forceWake`、`HANGCHECK`。其中 GTFREQ/IDLEBOUND/
  forceWake/HANGCHECK 在真 TGL 上应禁止或显式 gate。

## 五、任务 C：25G83 兼容性

完整表格见 `reports/TAHOE-25G83-COMPAT.md`。四类结论：

### `[1]` 源码可确认与 OS 构建号无关

- `kern_start` 的 `KernelVersion::Tahoe`；
- `isRealTGL` 的 CPUID 判定；
- `MTLCompilerBuildRequestWithSerializedBitcode` 入口名（源码级）；
- NootedGreen 的 pattern（不是 offset）本身。

### `[2]` 有充分源码证据可兼容 25G83

- pipeline descriptor：`MTLRenderPipelineDescriptorInternal` size `0x338`、
  `_private@0x30`；颜色附件 size `0x10`、`_private@0x8`；`logicOp` 新位 32/
  旧位 27；动态探针 `@0xb8/@0x110`。来自 25G83 独立项目源码。
- `performTransaction+0x81361` 读 `IOSurface+0xa4` 并得到 0；25G83 源码明确
  记录同一问题。
- GPU bundle 位置/`MetalPluginName`/`MetalPluginClassName` 机制。
- 25G83 参考项目确实有 WindowServer/Metal 桌面路径的源码和声明；但这是
  ADL 46A3，不是 9A49，不能当本机运行证据。

### `[3]` 依赖具体二进制，需要比对

- 25G83 `AppleIntelTGLGraphics` / `AppleIntelTGLGraphicsMTLDriver` 哈希；
- framebuffer 目标文件（同系统参考未公布哈希）；
- `patch-mtl17.py` 的全部固定 offset（header 16/4224、path 0xa2e7b、代码
  0x18c28/0x1c7c0/0x1c7cf/0x49cfe/0x65f12/0x67c27/0x67c5c）；
- NootedGreen 的 kernel/FB pattern 在目标文件中的存在/唯一性；
- IOAF2 符号/内部 offset；
- `+0x98` plane count（25G241 证据，25G83 未证明）；
- `MTLCompiler`/`GPUCompiler`/`libLLVM` 路径与版本。

### `[4]` 当前无法确认

- 9A49 + 25G83 的实际 Metal/WindowServer；
- 25G83 的 `MTLCompiler` `getSerializedModule` 签名；
- 25G83 的 `xe.bundle` sandbox/路径是否仍可用；
- 合法签名/AMFI 路径；
- GuC/固件在 9A49 上的实际行为；
- 25G83 的 IOAF2 orphan/pool 行为。

### `patch-mtl17.py` / `mtl17-patches.json`

- 当前 JSON 有 10 条；脚本无条件应用全部 10 条 + `PoshDisable=1`。
- 其中的 header 两条（16/4224）和 plugin path（0xa2e7b）是 TGL 可能需要的；
  其余 7 条是 RPL/AUX/fast-clear 相关，TGL 默认不应使用。
- 脚本只检查固定 offset 的旧字节，不检查目标 SHA-256/OS build/版本/UUID。
- donor 16.0.32 上 10 条旧字节全部匹配（`logs/tool/donor-audit-003-all-patches.json`）；
  25G83 目标未提供，全部 `NEEDS_TARGET_BINARY`。
- **不能直接运行 `patch-mtl17.py` 做 TGL 输出**；它会带入 RPL 补丁和
  PoshDisable。应使用 `configs/tgl-9a49-25G83.json` 的选中子集，先生成
  受控清单，再离线构建。

## 六、任务 D：实际代码与构建

### D1 配置

`configs/tgl-9a49-25G83.json`：

- 目标身份：i5-1135G7 / `8086:9A49` / 26.6.2 / 25G83 / x86_64；
- `deployment_allowed=false`，`amfi_bypass_allowed=false`；
- 选中的 boot args：`-ngreentglwithgfx`、`-allow3d`、`-ngreenkeepefi`
  （均标 `NOT_TESTED`/`VERIFIED_SOURCE`，不是运行证明）；
- 排除：`-ngreenxefix`、`-disablegfxfirmware`、`ngreen-dmc=adlp`、
  `ngreenSched=4`、`-ngreenfixbootmode`、`-ngreenfixbootpatch`、
  `-ngreenV69ForceOriginalUnsafe`、`amfi_get_out_of_my_way=1` 等；
- 二进制项：TGL kext / MTL driver / framebuffer，均含 donor + 目标哈希
  （framebuffer 目标哈希未公布，标 `NEEDS_TARGET_BINARY`）；
- 所有 kernel patch `selected=false`；MTL 只选 3 条（header 两条 + compiler
  path），其余 7 条明确排除。

### D2 只读预检工具

`tools/check-tgl-compat.py`：

- 只读打开，不写目标文件；检查读取前后 size/mtime；
- SHA-256、thin Mach-O 架构/文件类型、`LC_BUILD_VERSION`、UUID、
  `Info.plist` 版本；
- offset patch 的原始字节、pattern patch 的精确出现次数；
- 重复 patch ID、重叠写、冲突替换；
- 缺文件/哈希不符/架构错误/字节不符/冲突均拒绝，退出码 2–7；
- `--allow-donor` 只输出 `DONOR_ONLY`，不是目标通过；
- `--allow-fixture` 只输出 `FIXTURE_ONLY`，`--strict` 拒绝；
- `--audit-unselected` 对未选中 patch 做软审计，不把不匹配当目标失败。

测试：14/14 通过（`logs/tool/tests-001.log` 保留首次失败，
`tests-002.log` 为最终成功）。Donor 审计：10 条 MTL + 8 条 kernel/FB
pattern 全部匹配 16.0.32 donor；这不是 25G83 目标结果。

### D3 受控构建

见 `reports/BUILD-VALIDATION.md`：

- 12 个 NootedGreen/Lilu 对象 **`COMPILED`**（x86_64 Mach-O object）；
- 完整 kext：`BLOCKED_SDK`/`NOT_TESTED`。GNU ld 不能链接 Mach-O；
  ld64.lld 18 的 `-kext` 输出是 `MH_EXECUTE` 而非 `MH_KEXT_BUNDLE`；
  缺 `libcc_kext.a`；
- `libxedrv.m`：`BLOCKED_SDK`（缺 Foundation/Metal/IOSurface/用户 SDK）；
- `compiler-adapter.cpp`/`llvm-bridge.cpp`：`BLOCKED_SDK`（宿主 glibc 不能
  冒充 Darwin libc++/libSystem）；
- `xe.bundle` / MTL 输出：未执行 macOS 脚本，`NOT_TESTED`。

## 七、任务 E：方案 A vs 方案 B

| 维度 | 方案 A：Apple TGL + NootedGreen + Tahoe ABI | 方案 B：NullMoth + Vulkan/ANV + i915/XNU |
|---|---|---|
| 与原生 TGL 匹配度 | **高**：Apple 的 TGL 驱动就是为 Gen12/Xe-LP 写的；9A49 原生，不需要 GPU 拓扑伪装 | 中：i915/ANV 支持 TGL，但 Darwin 后端需重写；NullMoth 是 Metal 前端，不提供内核 GPU 管理 |
| 已有实际 GPU 执行证据 | 参考项目在 RPL 25G241 上报告 Metal 桌面；本机 9A49/25G83 **无** | GA40–GA42 只有 CPU/对象/编译证据；**无** GPU 执行、无 Darwin ANV ICD、无链接 kext |
| 25G83 兼容性 | 需要目标 TGL/MTL/FB/IOAF2/MTLCompiler 文件；结构上差异集中在 ABI/offset，工作量可控 | 需要精确 KDK、完整 Darwin ANV/DRM/GEM/VM/提交/IRQ；25G83 兼容面更大且更未知 |
| 内核驱动工作量 | **低–中**：复用 Apple 加速器，只做加载/少量 hook/补丁 | **极高**：GEM、GPU VA/PTE、context、submit、fence、IRQ、reset、电源，全部要自建/移植 |
| Metal 用户态工作量 | **中**：descriptor/selector 适配、compiler bridge、MTL 子集补丁 | **极高**：Darwin ANV ICD + NullMoth Metal 前端 + IOSurface/WindowServer 集成 |
| WindowServer/IOSurface | 中：旧 driver 的 IOSurface offset、flip/transaction、签名 | 极高：需要自己实现 Metal/NMX/IOSurface 共享，且没有已验证路径 |
| 风险 | 高：专有二进制、AMFI/签名、内核 panic、旧驱动 ABI；但路径短 | 高：工程量大、无 GPU 证据、驱动/用户态双重未知；失败模式更分散 |
| 源码/专有依赖 | Apple 16.0.32 专有二进制 + NootedGreen 开源 + Tahoe 私有 ABI | Mesa/ANV/i915/NullMoth 开源 + Apple Metal/IOAF2 私有 ABI |
| 后续验证 | 目标二进制预检 → 合法签名 → 一次受控启动 → Metal/WindowServer | 完整 SDK/KDK → GEM/VM/提交 → Darwin ANV → Metal/NMX，周期长 |

### 结论

**方案 A 更值得优先，但只能作为“离线可行性主线”，不能直接部署。**
可验证的理由：

1. 它复用了 Apple 已有的 GPU 内存/调度/提交，避免了方案 B 最大的内核工作量；
2. 参考项目已经给出可审阅的 NootedGreen/libxedrv/compiler 代码，且我们能
   在 16.0.32 donor 上复核所有字节/符号；
3. 25G83 的独立源码证据支持 descriptor/IOSurface 的关键形状；
4. 方案 B 经过 GA40–GA42 仍没有 GPU 执行、没有 Darwin ANV ICD、没有
   可加载 kext，短期内不可能替代 A。

但方案 A 有两个硬门槛：

- **25G83 目标二进制**：没有它，所有固定 offset/patch 都只是 donor 证据；
- **合法签名/加载路径**：参考实现依赖 `amfi_get_out_of_my_way=1`，当前禁止。
  没有替代方案，A 不能进入实机。

因此不建议现在把主路线改成 B；建议继续 A 的离线取证/适配，直到上述门槛
给出明确结论。若目标二进制或签名路径被证明不可行，再回到 B 评估。

## 八、最终回答

**问：对原生 Tiger Lake 9A49，在 Tahoe 25G83 上复用 Apple TGL Metal 驱动，
哪些代码已可直接使用，哪些补丁需要移植，哪些条件仍必须从真实系统取证？**

### 1. 已可直接使用（源码/二进制层面，不是运行层面）

- Apple 16.0.32 的 `AppleIntelTGLGraphics.kext` 内核加速器：GPU 页池、
  GGTT/PPGTT、context、scheduler、ring、提交、IRQ/reset、display pipe；
- `AppleIntelTGLGraphicsFramebuffer.kext` 的显示模式/时序/plane/DDI/DPMS；
- `AppleIntelTGLGraphicsMTLDriver` 的 Metal 对象/命令编码；
- NootedGreen 的 `kern_start` Tahoe 版本、`isRealTGL` 检测、
  `-ngreentglwithgfx` 加载策略（需目标 personality 核对）；
- `libxedrv` 的 descriptor/selector 适配骨架；
- `compiler-adapter.cpp` / `llvm-bridge.cpp` 的新旧 LLVM 桥骨架；
- 25G83 独立项目已证明的 descriptor 形状、IOSurface `+0xa4` stale 读取、
  GPU bundle 加载机制（源码级）。

### 2. 需要移植/改造的补丁

- **必须从 `!isRealTGL` 移出：** `XE-FMT`、`XE-PLANES2`；
- **保留但加目标校验：** `XE-VALD`（当前无条件应用，目标是 framebuffer，
  不是 HW kext）；
- **从 xefix 拆出、单独测试：** `XE-POOLALIGN`、`XE-PAGESYNC`、
  `XE-NOORPHAN`、`XE-RESFREE`；
- **增加 TGL gate：** `V40`、`V221`、`forceWake` 替换、`HANGCHECK`；
- **MTL：** 只保留 header 两条 + compiler path；其余 7 条默认排除；
- **libxedrv：** 补 class size/`_private` offset 检查；TGL 默认保留压缩；
- **compiler bridge：** 目标 `getSerializedModule` 签名/`GPUCompiler` 路径
  检查，不能写死 25G241 的 offset。

### 3. 必须从真实系统取证

- 25G83 `AppleIntelTGLGraphics` / `Framebuffer` / `MTLDriver` /
  `AppleIntelGraphicsShared` 的原始文件、`Info.plist`、`version.plist`、
  SHA-256、Mach-O UUID/`LC_BUILD_VERSION`；
- 25G83 `IOAcceleratorFamily2` 的符号和内部结构；
- 25G83 `IOSurface` 的真实 getter/offset（尤其 plane count）；
- 25G83 `MTLCompiler` / `GPUCompiler` / `libLLVM` 的版本、路径、导出、
  `getSerializedModule` 签名；
- 25G83 的 `xe.bundle` sandbox/路径是否仍可用；
- 9A49 上 Apple TGL 驱动能否加载/接管显示/提交 GPU；
- WindowServer/CoreAnimation/Metal 的实际像素与 flip 证据；
- 合法签名/AMFI 路径（当前禁止绕过）。

**一句话：** Apple TGL 内核栈可以复用，方案 A 在架构上比从零移植 i915
更直接；但 25G83 的目标二进制和合法加载路径都还没有，当前不能宣称
9A49/25G83 的 Metal 加速已可用。

## 九、安全边界与未做事项

- 未修改 EFI/OpenCore/NVRAM；未安装/加载 kext；未改 `/Library/Extensions`、
  `/Library/GPUBundles`、系统缓存；未改 SIP/SSV/AMFI；
- 未使用 `amfi_get_out_of_my_way=1`；
- 未执行上游 `install.sh`/`build-all.sh`/`build-shader-compiler.sh`；
- 未 SSH 目标 macOS；未重启；未执行 GPU MMIO/batch；
- 未在目标机实验；未下载 Apple 专有组件；未绕过任何版本/字节校验；
- GA40/GA41/GA42 封存树未修改。

## 十、Git

完整台账见 `reports/GIT-COMMITS.md`。逐单元本地提交，无 remote、无 push；
最终 HEAD 用 `git log -1` 读取。

## 十一、下一步

见 `reports/NEXT-STEPS.md`。最小顺序：

1. P0 取 25G83 真实文件并跑 `check-tgl-compat.py`；
2. P1 建 TGL 专用 NootedGreen 补丁层（FMT/PLANES2 移出、V40/V221/
   forceWake/HANGCHECK gate、xefix 拆分）；
3. P2 MTL/compiler 目标预检；
4. P3 解决合法签名/加载（否则不进入实机）；
5. P4 一次受控目标实验（需新授权）。

本轮到此停止，不自动进入第二阶段，不尝试安装 GPU 驱动。
