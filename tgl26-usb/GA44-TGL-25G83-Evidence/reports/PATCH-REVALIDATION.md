# 25G83 补丁重新验证（任务 B/C/D 的目标证据版）

本表把 GA4.3 的补丁分类与本次实机证据对齐。**没有把 donor 结果当成目标
结果。** 目标 25G83 没有 stock TGL bundle 是 `EXPECTED_ABSENT`；Apple TGL
16.0.32 donor 才是拟移植的补丁对象，donor 字节已在本地验证。仍缺的是
**目标 25G83 ABI/runtime 证据**，不是再找一个 stock TGL 驱动。IOAF2 符号、
目标 compiler/framework 和当前 GPU 状态已经有真实目标证据。

## 1. 目标证据总表

| 项目 | 目标 25G83 结果 | 状态 |
|---|---|---|
| macOS 26.6.2 / 25G83 | 确认 | `REMOTE_READ_ONLY` |
| GPU `8086:9A49` | 确认，rev 0x0001 | `REMOTE_READ_ONLY` |
| VRAM / Metal | 7 MB，No Kext Loaded，无 IntelAccelerator | `REMOTE_READ_ONLY` |
| 显示路径 | `IONDRVFramebuffer`，固件 framebuffer | `REMOTE_READ_ONLY` |
| NootedGreen | 未加载 | `REMOTE_READ_ONLY` |
| `AppleIntelTGLGraphics` | `NOT_INSTALLED_ON_TARGET` | `EXPECTED_ABSENT`；donor 16.0.32 已本地验证 |
| `AppleIntelTGLGraphicsMTLDriver` | `NOT_INSTALLED_ON_TARGET` | `EXPECTED_ABSENT`；donor 16.0.32 已本地验证 |
| `AppleIntelTGLGraphicsFramebuffer` | `NOT_INSTALLED_ON_TARGET` | `EXPECTED_ABSENT`；donor 16.0.32 已本地验证 |
| 目标 Intel 图形栈 | ICL/KBL/CFL 24.5.8 | `REMOTE_READ_ONLY` |
| IOAF2 | 487.4.3，binary 在 KC | `VERIFIED_TARGET_SYMBOL` |
| 目标编译器 | 新 API 插件；IGC 无 gen12 | `VERIFIED_BINARY` |
| donor 编译器 | 旧 API 插件；IGC 有 gen12/TGLLP | `VERIFIED_BINARY`（本地） |
| 目标 `MTLCompiler` | 373.7，32023/32024，binary shared-cache | `REMOTE_READ_ONLY` |
| 目标 `GPUCompiler` | 32023.255.1，lazy dylib 独立文件 | `REMOTE_READ_ONLY` |
| 目标 `Metal` | 373.7 | `REMOTE_READ_ONLY` |
| 目标 `IOSurface` | 393.5.8 | `REMOTE_READ_ONLY` |

## 2. 逐补丁验证

| 补丁 | GA4.3 分类 | 目标 25G83 验证 | 结果/下一步 |
|---|---|---|---|
| `XE-FMT` | B | 目标无 TGL kext；donor 16.0.32 pattern 1 次匹配 | `DONOR_VERIFIED` + `TARGET_ABI_UNVERIFIED`；已在 `patches/nootedgreen-tgl-native.patch` 中移出 `!isRealTGL`，由 `-ngreentgltahoe` 控制 |
| `XE-PLANES2` | B | 目标无 TGL kext；donor pattern 1 次匹配；`+0x98` 仍是 25G241 证据 | `DONOR_VERIFIED` + `TARGET_ABI_UNVERIFIED`；补丁保留 `+0x98` 并注释风险；目标 getter 优先 |
| `XE-VALD` | B | 目标无 TGL framebuffer；donor FB pattern 各 1 次匹配 | `DONOR_VERIFIED` + `TARGET_ABI_UNVERIFIED`；当前无条件应用，不能从配置关闭 |
| `XE-POOLALIGN` | B/C | 目标 IOAF2 `init/getBufferPtrNoInc` 符号存在；pool 内部 offset 未验证 | `VERIFIED_TARGET_SYMBOL` + `NEEDS_TARGET_OFFSET` |
| `XE-NOORPHAN` | C/D | 目标 `IOAccelOrphanedMemoryPool::getMemory` 存在 | 符号可解析；是否启用仍 `NOT_TESTED_ON_GPU` |
| `XE-PAGESYNC` | C | 目标 `pageon/pageoff` 类符号存在 | 符号可解析；行为未测 |
| `V221 waitForStamp` | B/D | 目标 `IOAccelEventMachine2::waitForStamp` 存在 | 符号可解析；仍应加 TGL gate，不能默认假成功 |
| `V40 IOAF2 capability bypass` | B/D | 目标 IOAF2 符号/结构存在；模式未在目标运行 | 仍是无条件补丁；需要 TGL gate |
| `V500 set_id_mode` | 诊断 | 目标 KC **没有** `IOAccelLegacySurface::set_id_mode` | 从 TGL profile 排除 |
| `XE-NOCCS3` | D | 目标无 TGL kext；目标 IOAF2 resolve 符号存在但未运行 | 默认关闭；不能把 RPL 的 resolve 绕过套到 TGL |
| `XE-NODEPTH` | D | 同上 | 默认关闭 |
| `XE-NOAUX` | A | 目标无 TGL；RPL AUX 绕过不应使用 | 禁止 |
| `V99R/V99G`、`V193`、`V52`、`V46`、`V54/V65`、`V57/V71`、`V111`、`V132/V148/V165`、`V212`、`V509` | A | 目标没有 TGL 驱动可运行；这些是 RPL/ADL 路径 | 保持默认关闭 |
| display 13 xefix / BLR / FBDPMS | A/D | 目标没有 TGL；xefix 仍可能误开 | 已在新 patch 中对真 TGL 加 `getIsRealTGL()` 门 |
| `GTFREQ` / `IDLEBOUND` | A/C | 目标当前未加载 TGL；无法测 | 新 patch 对真 TGL 直接调用原实现 |
| `forceWake` 替换 / HANGCHECK | D | 目标没有 TGL；新 profile 不安装 forceWake 替换 | 新 patch 在 `-ngreentgltahoe` 下跳过 |
| MTL header/load command（2 条） | B | 目标无 TGL MTL driver；donor 两条匹配 | `DONOR_VERIFIED` + `TARGET_ABI_UNVERIFIED` |
| MTL compiler plugin path | B | 目标无 TGL MTL driver；目标 stock 路径不同 | `DONOR_VERIFIED` + `TARGET_ABI_UNVERIFIED` |
| MTL13–18 / PoshDisable | A/D | 目标无 TGL MTL driver | 保持排除 |
| `libxedrv` descriptor | B | 目标 `Metal` 373.7 存在；未运行 `_descriptorPrivate` | `REMOTE_READ_ONLY` + `NOT_TESTED_ON_GPU`；保留源码补强 |
| compiler adapter/bridge | B | 目标新 API 插件；donor 旧 API 插件 + Gen12 IGC | **仍需要**；`libLLVM` shared-cache 路径需运行时探针 |

## 3. 目标文件验证的具体结果

### 3.1 donor 16.0.32 字节

`logs/local/donor-audit-001.json`：

- 10 条 MTL patch 全部匹配 donor；
- 5 条 TGL HW pattern 全部匹配 donor；
- 3 条 TGL framebuffer VALD pattern 全部匹配 donor；
- 总状态 `DONOR_ONLY`，不是目标通过。

### 3.2 目标 IOAF2 符号

`input/kernel-metadata/ioaf2-symbol-map.txt`：

- `waitForStamp`、`submitTransaction`、`isTransactionComplete`、
  `signalTransactionComplete`、`completeTransaction` 均存在；
- `IOAccelCommandBufferPool2::init` 的参数签名
  `...P11IOAccelTaskiijjjj` 与 NootedGreen 目标一致；
- `IOAccelOrphanedMemoryPool::getMemory`、`IOAccelSysMemory` lock/unlock、
  `IOAccelResource2::getStorageResource` 均存在；
- `IOAccelLegacySurface::set_id_mode` 不存在。

这是**目标符号级**证据，不是 offset 级证据。

### 3.3 目标 compiler

`reports/COMPILER-25G83.md`：

- 目标插件有 `MTLCompilerBuildRequestWithSerializedBitcode`，没有旧
  `BuildRequestWithOptions`；
- 目标 `libigc` 平台列表没有 `gen12`/`gen12lp`；
- donor 插件有旧入口，donor `libigc` 有 `gen12`/`gen12lp`/`TGLLP`；
- `libLLVM.dylib` 在目标上只有 shared-cache 路径，无独立文件。

因此参考项目的 adapter/bridge 仍然需要，但需要针对 25G83 重写路径/扫描，
不能直接声称 GA4.3 的用户态编译链在 25G83 可用。

## 4. 结论

- **已验证到目标符号级：** IOAF2 hook 所需的符号在 25G83 KC 中存在；
- **已验证到 donor 字节级：** GA4.3 的 18 条 donor 补丁/pattern 匹配 16.0.32；
- **仍缺目标 ABI/runtime 证据：** 25G83 上未安装 TGL 是预期；FMT/PLANES2/
  VALD/MTL 的 donor 字节已验证，但目标 ABI offset/行为仍需运行时验证；
- **已发现目标 compiler 的方向性差异：** 新 API 但无 Gen12；donor 有 Gen12
  但旧 API；adapter/bridge 仍必要；
- **当前目标没有 Metal 加速：** 没有 IntelAccelerator，显示仍是
  `IONDRVFramebuffer`；不能因为 SSH/符号/编译通过而宣称 Metal 成功。


## 5. 审计后修正（2026-10-22）

GA4.4 初版把“25G83 stock 没有 TGL 驱动”写成 TGL 适配的
`NEEDS_TARGET_BINARY`。这是语义错误；上表和结论已按本节修正：

- `DONOR_TGL_16.0.32` 是**拟移植的补丁对象**，已在 GA4.3 固定树中；
  donor 的 18 条 pattern/字节已验证；
- 25G83 stock 没有 TGL 是 `EXPECTED_ABSENT`，不是缺失前置；
- 25G83 仍需的是 **ABI/runtime 证据**（IOAF2/Metal/MTLCompiler），
  不是再找一个 stock TGL 驱动；
- `installed_tgl_*` 只是部署观察，optional。

历史 1536 MB/3FB 是 ICL framebuffer + WEG map 的显示基线，不是 Apple
TGL donor 的 Metal 成功。详见 `reports/NEEDS-TARGET-REASSESSMENT.md` 与
`reports/BOOT-BASELINE-AUDIT.md`。
