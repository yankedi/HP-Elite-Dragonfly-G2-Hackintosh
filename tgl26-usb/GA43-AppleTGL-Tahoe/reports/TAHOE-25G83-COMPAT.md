# Tahoe 25G83 兼容性核对（任务 C）

参考项目目标：Tahoe 26.7.1 / **25G241**，RPL-P `8086:A7A0` 伪装为 `9A49`。
本机目标：Tahoe 26.6.2 / **25G83**，原生 TGL `8086:9A49`。
本报告只使用固定 commit 的源码、NootedGreen 内的 16.0.32 donor 二进制，
以及同系统 25G83 的 IntelIGPU-Tahoe 源码作交叉证据。**本机没有 25G83 的
Apple TGL kext、MTL driver、IOAF2 或 MTLCompiler 文件**，因此所有需要
这些文件的项目都标 `NEEDS_TARGET_BINARY`。

## 0. 证据等级图例

| 标记 | 含义 |
|---|---|
| `[1]` | 源码可确认与 OS 构建号无关 |
| `[2]` | 有充分源码证据可兼容 25G83（不是本机运行证据） |
| `[3]` | 依赖具体 Apple 二进制版本/偏移，必须拿 25G83 文件比对 |
| `[4]` | 当前无法确认 |

状态另用 `VERIFIED_SOURCE`、`VERIFIED_BINARY`、`NEEDS_TARGET_BINARY`、
`NOT_TESTED`、`UNSAFE_FOR_TARGET` 标注。

## 1. 版本与文件身份

| 项目 | 参考/本地事实 | 25G83 证据 | 等级 | 结论 |
|---|---|---|---|---|
| Apple TGL 驱动版本 | NootedGreen donor `CFBundleShortVersionString=16.0.32`，`version.plist SourceVersion=16000032000000` | IntelIGPU-Tahoe docs 说 TGL runtime 也是 16.0.32 级别，但给出不同哈希 | `[1]` 版本号；`[3]` 文件字节 | 版本号可复用，字节必须比对 |
| `AppleIntelTGLGraphics` | donor `sle/` `890735a9…`；`le/` 改名副本 `1b2f5aa3…` | 25G83 声明哈希 `ae99582b…` | `[3]` | `NEEDS_TARGET_BINARY` |
| `AppleIntelTGLGraphicsMTLDriver` | donor `e21a8d12…`，LC_BUILD_VERSION minos 10.16.0 | 25G83 声明哈希 `4c161bc5…` | `[3]` | `NEEDS_TARGET_BINARY` |
| Framebuffer | `le/` `285ee7a9…`（3.89 MB，UUID `b96a8448…`）；`lep/` `a562cff0…`（2.92 MB，UUID `b6078743…`） | 同系统参考未公布 framebuffer 哈希 | `[3]`/`[4]` | 必须提供目标文件；不能凭版本号选 `le`/`lep` |
| `libigc.dylib` / `libMTLIGCCompilerPlugin.dylib` | `9ff8b3b3…` / `477083cb…`，插件字符串 `LLVM Version is 3902` | 25G83 参考没有使用同一 `xe.bundle` 桥 | `[3]`/`[4]` | 必须比对目标 `AppleIntelGraphicsShared.bundle` |
| MTL driver 构建目标 | `LC_BUILD_VERSION minos 10.16.0 / sdk 10.16.0` | 25G83 的 MTL driver 仍未提供 | `[3]` | 证明它是 Big Sur 时代二进制，不是 Tahoe 构建 |
| `MTLCompiler` / `GPUCompiler` | 参考桥写死 `GPUCompiler 32023`，旧插件 LLVM 3902 | 25G83 的 MTLCompiler 版本/导出未提供 | `[3]`/`[4]` | 必须取目标系统 `libLLVM`/`MTLCompiler` |

**关键点：** 25G83 声明哈希与 donor 哈希不同，说明“16.0.32”只是版本号，
不是同一文件。任何固定文件偏移的补丁（尤其 `patch-mtl17.py`）都不能仅凭
版本号复用。

## 2. IOAcceleratorFamily2 符号与内部结构

NootedGreen 依赖的 IOAF2 接口：

| 接口 | 用途 | 25G83 证据 | 等级 |
|---|---|---|---|
| `IOAccelEventMachine2::waitForStamp` | V221 在 GFX start 前假成功 | 25G83 参考未直接使用该符号；其 Metal/显示路径存在 | `[3]`/`[4]` |
| `IOAccelLegacySurface::set_id_mode` | V500 剥掉 TGL-only mode bits | 未在 25G83 源码中见到 | `[4]` |
| `IOAccelCommandBufferPool2::init` / `getBufferPtrNoInc` | XE-POOL / POOLALIGN | 25G83 源码使用自己的命令缓冲/显示路径，但没有给出这些 symbol | `[3]`/`[4]` |
| `IOAccelOrphanedMemoryPool::getMemory` | XE-NOORPHAN | 未在 25G83 源码中见到 | `[4]` |
| `IOAccelSysMemory::lockForCPUAccess` / `unlockForCPUAccess` | BLITSCRATCH2 | 未在 25G83 源码中见到 | `[4]` |
| `IOAccelDisplayPipe::transaction_*` / `completeTransaction` | flipdiag / 显示事务 | 25G83 源码使用 `IOAccelDisplayPipeTransaction2` 的导出方法 | `[2]`/`[3]` |
| `IOAccelResource2` 内部 offset `+0xe0/+0xf8/+0xfc` | 资源 plane 表 | 25G83 源码避免内部 offset，使用导出方法 | `[3]` |

25G83 的 IntelIGPU-Tahoe 明确声明：

- `IOSurface` 的 getter 返回 64 位 size/offset、32 位 format/count；
- `getMemoryDescriptor`、`getPlaneOffset`、`getPlaneBytesPerRow`、
  `getPixelFormat`、`getPlaneCount` 是导出的非虚方法；
- 不应实例化这些私有类，也不应依赖 C++ 对象大小；
- `IOAccelDisplayPipeTransaction2` 通过 `getPlaneResource` /
  `getPlaneIOSurface` 取得资源/表面。

这对我们是一个重要提示：**NootedGreen 的固定 offset hook 在 25G83 上
没有源码级证明；更稳妥的做法是优先使用导出方法。** 但 NootedGreen 的
hook 是按符号名解析的，符号是否存在仍要目标二进制确认。`NEEDS_TARGET_BINARY`。

## 3. Metal Framework 插件加载 ABI

| 项目 | 25G241 做法 | 25G83 证据 | 等级 | 结论 |
|---|---|---|---|---|
| GPU bundle 位置 | `/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle` | IntelIGPU-Tahoe 使用 `/Library/GPUBundles/ReimsTahoeTGLGraphicsMTLDriver.bundle`，`MetalPluginName`/`MetalPluginClassName` 指向自定义 principal class | `[2]` | 目录/ML plugin 机制在 25G83 可用 |
| 编译器插件位置 | `/System/Library/Caches/xe.bundle/...`，用 `PrivateFrameworks/../Caches` 绕过前缀规则 | 25G83 参考没有采用 `xe.bundle` 桥；其 Metal 路径不同 | `[4]` | 25G83 是否仍接受该路径未知 |
| `MTLCompilerService` sandbox | 需要 `amfi_get_out_of_my_way=1` 让 ad-hoc 代码进入 WindowServer/CompilerService | 25G83 参考也要求用户本地合法取得 Apple 组件；未证明可绕过 AMFI | `[3]`/`[4]` | 当前任务禁止 AMFI 绕过，方案 A 部署受阻 |
| `MTLDevice` 枚举 | `MTLCopyAllDevices()` 只从 GPU bundle 枚举 | 25G83 源码有 `metal_entry_loader`/principal class，说明路径存在 | `[2]` | 机制可借鉴；9A49 未测 |
| `supportsDynamicLibraries` 等 | 旧 driver 不支持，adapter 明确拒绝 | 25G83 参考也拒绝 dynamic library/binary archive/mesh | `[2]` | 方向一致 |

**结论：** GPU bundle 加载机制在 25G83 有源码级证据；`xe.bundle` 编译器路径
和 AMFI 绕过没有。后者是方案 A 的最大部署阻塞。

## 4. IOSurface 关键字段

| 字段/读取 | 25G241 | 25G83 | 等级 | 结论 |
|---|---|---|---|---|
| `performTransaction+0x81361` 读 `+0xa4` | 16.0.32 代码固定；Tahoe 布局变化后为 0 | IntelIGPU-Tahoe 源码明确写：`TGL 16.0 performTransaction+0x81361 reads IOSurface+0xa4 inline, overwriting its default BGRA with zero on 25G83` | `[2]` | **25G83 也需要处理**；FMT/VALD 是 B 类 |
| `getPixelFormat()` | 25G241 kernelcache 读 `+0x80`（源码注释） | 25G83 源码用导出 getter，未给 raw offset | `[2]`/`[3]` | 优先用 getter；raw `+0x80` 需目标确认 |
| `getPlaneCount()` | 25G241 读 `+0x98`（源码注释） | 25G83 源码用导出 getter；未证明 raw `+0x98` | `[3]` | `XE-PLANES2` 不能直接复用 `+0x98`；先测目标 |
| 16.0.32 `calculateIOSurfaceDeviceCacheVRAMBytes` | 在 `0x7287d` 读 `+0xb0` | 同 16.0.32 donor；25G83 目标文件未提供 | `[2]` 代码 / `[3]` 目标 | 逻辑上仍需修，但 offset 选择要看目标 |
| `IOSurface` 对象大小/布局 | 旧 driver 直接读内存 | 25G83 源码明确避免依赖对象大小 | `[2]` | 不应新增 raw offset，除非有目标证据 |

**结论：** `+0xa4` stale 在 25G83 有直接源码证据；`+0x98` 只有 25G241
证据，不能外推。`XE-FMT` 和 `XE-VALD` 应优先移植；`XE-PLANES2` 需要
目标 getter/offset 验证。

## 5. Metal Pipeline Descriptor 布局

25G83 独立项目 `app-blank-candidate/logic-source/pipeline_descriptor_compat.m`
的 preflight：

- `MTLRenderPipelineDescriptorInternal`：`class_getInstanceSize == 0x338`；
  `_private` ivar offset `0x30`；
- type encoding 必须含
  `"shaderValidation"q"shaderValidationState"q"textureWriteRoundingMode"q`；
- `MTLRenderPipelineColorAttachmentDescriptorInternal`：size `0x10`，
  `_private` offset `0x8`；
- 动态探针：`rasterSampleCount @ 0xb8`、`vertexDescriptor @ 0x110`；
- `logicOp` 新位 32，旧 TGL 消费位 27；`coverage/one` 单独处理。

`libxedrv.m` 的 `check_layout()` 目前检查 type encoding 和两个动态探针，
但**不检查 class size `0x338`、`_private` offset `0x30`、颜色附件 size/offset**。
`libxedrv` 的 `MISC[]` 表也把 `logicOp` 从新位 32 映射到旧位 27（`{27,4,32,4}`），
与 25G83 项目的注释一致。

**等级：** `[2]`（25G83 源码与 25G241 适配器同形）。**建议：** 在 TGL
适配中把 25G83 项目的 size/offset 检查加入 `libxedrv` 的 preflight；这样
25G83 布局变化时会拒绝转换，而不是静默产生错误 pipeline。

## 6. WindowServer / CoreAnimation

| 项目 | 证据 | 等级 | 结论 |
|---|---|---|---|
| 25G83 桌面合成 | IntelIGPU-Tahoe 源码/README 声称 WindowServer 桌面、Metal 基础路径可用；用户实测反馈 | `[2]` 源码/声明，**不是本机日志** | 说明存在可行路径，但不证明 9A49 |
| 9A49 + 25G83 | 无 | `[4]` | `NOT_TESTED` |
| IOSurface flip/transaction | 25G83 源码 `intel_framebuffer.cpp` 有完整 flip/transaction 处理 | `[2]` | 可借鉴其“使用导出 getter、避免 raw offset”的策略 |
| 零拷贝纹理/stencil | `libxedrv` v15/v17 只有 25G241 经验 | `[3]`/`[4]` | 需要在 25G83 上重测 |
| 显示模式/时序 | 参考项目是 3840×2400 eDP；本机 1920×1080 | `[3]` | 不能复用参考的 timing/stride |

**结论：** 25G83 有另一项目的桌面路径证据，但 CPU/GPU 不同（ADL 46A3），
不能直接移植到 TGL 9A49。WindowServer 是“最后验证项”，不是本阶段可宣称的。

## 7. MTLCompilerService 与 Shader Compiler

| 项目 | 25G241 参考 | 25G83 | 等级 | 结论 |
|---|---|---|---|---|
| Tahoe 编译器入口 | `MTLCompilerBuildRequestWithSerializedBitcode` | 同系统参考没有给出该入口的源码/反汇编 | `[3]` | 需要目标 `MTLCompiler` 反汇编 |
| 新 LLVM | 32023（`GPUCompiler.framework/Versions/32023`） | 25G83 可能不同 | `[3]`/`[4]` | 必须取 `libLLVM` 版本/导出 |
| 旧插件 LLVM | 3902，`libMTLIGCCompilerPlugin.dylib` | donor 16.0.32 插件字符串确认 3902 | `[1]` 旧端；`[3]` 新端 | 旧端可复用 |
| `getSerializedModule` | 参考用签名扫描（`81 fa 3d 0f 00 00` / `81 fa 3e 0f 00 00`） | 未验证 25G83 的 MTLCompiler 是否有同一签名 | `[4]` | 必须目标扫描；不能固定 offset |
| `GPUCompiler` 路径 | 参考写死 32023 | 未验证 | `[3]` | 目标系统路径可能不同 |
| `xe.bundle` 路径 | `/System/Library/Caches/xe.bundle` | 25G83 参考未用 | `[4]` | 需要目标 sandbox/路径测试 |
| AMFI | 参考要求 `amfi_get_out_of_my_way=1` | 任务禁止 | `[3]`/`UNSAFE` | 部署阻塞 |

**结论：** 编译器桥的**旧端**（16.0.32 + LLVM 3902）有二进制证据；**新端**
（25G83 的 Tahoe MTLCompiler/LLVM/路径）没有。必须把目标
`MTLCompiler`、`libLLVM`、`libMTLIGCCompilerPlugin` 和 `Info.plist` 取回，
再决定 adapter/bridge 是否仍可用。

## 8. `patch-mtl17.py` 与 `mtl17-patches.json` 逐项核对

`macos/mtl17-patches.json` 当前有 10 条，文件名仍叫 MTL17，但内容对应
文档所说的 **MTL18**（去掉了 0x7ff77/0x80253 两个误伤字节）。脚本行为：

1. 复制 stock bundle；
2. 对每条 patch 检查 `old` 字节，然后写入 `new`；
3. `plutil -replace Development.PoshDisable -integer 1`；
4. 复制 `libxedrv.dylib`，ad-hoc `codesign`。

它**没有**校验目标 bundle 的 SHA-256、OS build、driver 版本或 Mach-O UUID；
只检查固定 offset 的原始字节。`patch-mtl17.py` **不是只读工具**，它写输出
目录；本阶段的 `check-tgl-compat.py` 才是只读预检。

| Offset | old → new | 作用 | 对 TGL 的选择 | 25G83 依赖 |
|---|---|---|---|---|
| `0x000010` | `1a00000060` → `1b000000d0` | Mach-O `ncmds/sizeofcmds`，为新增 `LC_LOAD_DYLIB` 腾位置 | **选中**（注入 libxedrv） | 目标 header 布局；`[3]` |
| `0x001080` | 111 个 0 → 新 load command | 写入 `libxedrv.dylib` 的 `LC_LOAD_DYLIB` | **选中** | 目标 header padding；`[3]` |
| `0x0a2e7b` | 旧 `.../Extensions/AppleIntelGraphicsShared.bundle/.../libMTLIGCCompilerPlugin.dylib` → `PrivateFrameworks/../Caches/xe.bundle/...` | 编译器插件路径 | **选中**（若 25G83 仍用该路径） | 目标字符串/路径；`[3]`/`[4]` |
| `0x018c28` | `8b4818` → `31c990` | 忽略 IOSurface 压缩标志 | **不选**（RPL/AUX） | `[3]` |
| `0x01c7c0` | `0f95c2` → `909090` | 关闭 render-target fast clear | **不选** | `[3]` |
| `0x01c7cf` | `400f95c6` → `90909090` | 同上 | **不选** | `[3]` |
| `0x049cfe` | `0f95c0` → `909090` | 关闭 dual-SIMD8 clear PS | **不选** | `[3]` |
| `0x065f12` | `88` → `d0` | RPL-P L3 allocation | **不选** | `[3]` |
| `0x067c27` | `745c` → `9090` | clear pipeline `je` → NOP | **不选/待测** | `[3]` |
| `0x067c5c` | `75` → `eb` | clear 后 VS dirty | **不选/待测** | `[3]` |
| Info.plist | `Development.PoshDisable=1` | 关闭 POSH | **不选**（TGL 有 POSH） | `[3]` |

**Donor 校验结果：** `logs/tool/donor-audit-003-all-patches.json` 显示
10 条 MTL patch 的原始字节在 16.0.32 donor 上**全部匹配**；kernel/FB 的
8 条候选模式也全部匹配。但这只是 donor，不是 25G83。
**25G83：** 目标文件未提供，所有 offset 仍是 `NEEDS_TARGET_BINARY`。

**重要：** `patch-mtl17.py` 会**无条件应用全部 10 条 + PoshDisable**，
因此不能直接用于 TGL。我们的 `configs/tgl-9a49-25G83.json` 只选 3 条
MTL 项；剩余项明确排除。必须新增一个“只应用选中项”的受控构建脚本，
或在目标预检通过后手工生成清单。

## 9. 内核静态偏移/特征码

NootedGreen 的内核补丁以 `LookupPatchPlus` 模式匹配为主，不是固定 offset。
这是相对 MTL 固定 offset 更安全的做法，但仍依赖 16.0.32 的指令字节。

Donor 审计（`donor-audit-003-all-patches.json`）：

- `kernel.vald.*`：在 **framebuffer** donor 上各 1 次匹配（不是 HW kext）；
- `kernel.fmt.perform_transaction`：HW donor 上 1 次匹配（0x81361）；
- `kernel.planes2.plane_count`：HW donor 上 1 次匹配；
- `kernel.noccs3` / `nodepth` / `noaux`：HW donor 上各 1 次匹配。

**25G83：** 仍需目标文件确认这些模式是否存在、是否唯一、是否在同一函数。
`check-tgl-compat.py --audit-unselected` 可以在用户提供目标文件后做这件事；
当前目标文件缺失，状态 `NEEDS_TARGET_BINARY`。

**注意：** `XE-VALD` 的目标是 framebuffer，不是 `AppleIntelTGLGraphics`；
`configs/tgl-9a49-25G83.json` 已把三条 VALD 放到
`AppleIntelTGLGraphicsFramebuffer.kext`。这是一个容易搞错的二进制归属。

## 10. 25G83 最小取证清单（只读）

本阶段禁止 SSH 控制目标 macOS。以下命令应由用户在本机手动执行，或把文件
以只读方式复制到 NixOS 后交给 `check-tgl-compat.py`。**不要安装/加载/修改
任何东西。**

### 10.1 必取文件

优先从目标系统复制（保留相对目录）：

```text
/System/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics
/System/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/Info.plist
/System/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/version.plist
/System/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer
/System/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/Info.plist
/System/Library/Extensions/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver
/System/Library/Extensions/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/Info.plist
/System/Library/Extensions/AppleIntelGraphicsShared.bundle/Contents/Info.plist
/System/Library/Extensions/AppleIntelGraphicsShared.bundle/Contents/MacOS/libigc.dylib
/System/Library/Extensions/AppleIntelGraphicsShared.bundle/Contents/MacOS/libMTLIGCCompilerPlugin.dylib
```

如果这些路径不存在，先在目标机用只读方式定位：

```sh
kmutil showloaded | grep -i -E 'TGL|IntelGraphics|IOAccelerator'
find /System/Library/Extensions /Library/Extensions -maxdepth 2 \
  -iname '*TGL*' -o -iname 'AppleIntelGraphicsShared.bundle' 2>/dev/null
```

只读属性/哈希：

```sh
shasum -a 256 <每个文件>
plutil -p <每个 Info.plist>
file <每个 Mach-O>
```

### 10.2 编译器/ABI 额外文件

```text
/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/*/Libraries/libLLVM.dylib
/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/*/Libraries/libLLVM.tbd (如有)
/System/Library/PrivateFrameworks/MTLCompiler.framework/.../MTLCompiler (如存在)
/System/Library/Caches/com.apple.xbs/Sources/... (不需要)
```

只读导出：

```sh
ls -l /System/Library/PrivateFrameworks/GPUCompiler.framework/Versions
dyld_info -exports /System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/*/Libraries/libLLVM.dylib
```

`MTLCompiler` 的真实路径随系统版本变化；如找不到，不要猜路径，先用
`find /System/Library/PrivateFrameworks -name 'MTLCompiler'` 只读定位。

### 10.3 IOAcceleratorFamily2 / kernelcache 符号

`IOAcceleratorFamily2` 通常在内核集合里，不在普通文件系统：

```sh
kmutil showloaded | grep -i IOAccelerator
# 如需符号，必须在合法只读副本上做；不要修改/重建当前 kernel collection。
```

本阶段不要求用户做内核转储；如果无法安全取得，保持 `[4]`，不要用
“25G241 的符号表”代替 25G83。

### 10.4 交付格式

把文件放在一个私有目录，例如：

```text
tgl-25G83-input/
  AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics
  AppleIntelTGLGraphics.kext/Contents/Info.plist
  AppleIntelTGLGraphicsFramebuffer.kext/...
  AppleIntelTGLGraphicsMTLDriver.bundle/...
```

然后运行：

```sh
python3 tools/check-tgl-compat.py \
  --config configs/tgl-9a49-25G83.json \
  --input-dir /path/to/tgl-25G83-input \
  --audit-unselected --json
```

工具会：SHA-256、Mach-O 架构/类型、`LC_BUILD_VERSION`、`Info.plist` 版本、
选中 patch 的原始字节/模式计数、重复/冲突检查；缺文件或哈希不符会拒绝。
它**不会**写文件，也不会把 donor 结果当成目标结果。

## 11. 结论

- **25G83 源码可确认的：** pipeline descriptor 的 size/offset/bit 位置与
  25G241 同形；`performTransaction+0x81361` 仍读 `IOSurface+0xa4` 并得到 0；
  GPU bundle 机制存在。`[2]`。
- **25G83 仍需目标二进制：** TGL kext/MTL driver/framebuffer 的具体哈希与
  字节、IOAF2 符号/offset、`+0x98` plane count、MTLCompiler/LLVM 路径、
  `getSerializedModule` 签名、所有 MTL 固定 offset。`[3]`/`[4]`。
- **不能在 25G83 上直接用的：** 25G241 的 `patch-mtl17.py` 全量补丁、
  `ngreen-dmc=adlp`、`-disablegfxfirmware`、`-ngreenxefix` 全套、
  display 13 寄存器过滤、RPL scheduler/CSR/GTFREQ 补丁。
- **部署阻塞：** 参考实现依赖 `amfi_get_out_of_my_way=1`，本任务禁止；
  没有合法签名/加载路径前，方案 A 只能离线推进。
