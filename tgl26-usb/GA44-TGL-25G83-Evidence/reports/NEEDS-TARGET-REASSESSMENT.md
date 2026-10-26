# 重新评估 GA4.4 的 NEEDS_TARGET_BINARY

日期：2026-10-22。本文纠正 GA4.4 报告中的一个语义错误：**25G83 stock 系统
没有 TGL 驱动是预期事实，不是 Apple TGL 适配的前置缺失。**

## 1. 原报告的问题

GA4.4 把以下两者混在同一个 `NEEDS_TARGET_BINARY` 里：

1. 目标 25G83 **stock** 系统没有 `AppleIntelTGLGraphics*`；
2. 要移植的 **donor Apple TGL 16.0.32** 二进制应作为补丁对象。

实际上：

- donor 16.0.32 已经在 GA4.3 固定树中，SHA-256 和全部补丁 pattern 已验证；
- 目标 25G83 不需要预装 TGL 驱动；它的角色是提供 **ABI/框架/内核符号**
  和运行环境；
- 因此“目标没有 stock TGL”应标 `EXPECTED_ABSENT`，不是
  `NEEDS_TARGET_BINARY`。

## 2. 正确的四类对象

| 对象 | 当前位置 | 角色 | 状态 |
|---|---|---|---|
| `DONOR_TGL_16.0.32` | GA4.3 固定 NootedGreen `sle_Internal/` | **补丁/构建对象**（AppleIntelTGLGraphics、framebuffer、MTL driver、libigc、plugin） | `VERIFIED_LOCAL`；18/18 pattern 匹配 |
| `STOCK_25G83_SYSTEM` | 目标 macOS 25G83 | ABI/框架/内核符号（IOAF2 487.4.3、Metal 373.7、GPUCompiler 32023、IOSurface 393.5.8） | `VERIFIED_REMOTE`（部分运行时 ABI 未探针） |
| `INSTALLED_TGL_16.0.32` | 目标 `/Library/Extensions`、`/Library/GPUBundles` | 可选部署观察，不是离线构建前提 | `EXPECTED_ABSENT` / `NOT_INSTALLED_ON_TARGET` |
| `TARGET_ABI` | 目标 25G83 KC/框架 | donor 16.0.32 是否能与 25G83 IOAF2/Metal/编译器协同 | `PARTIAL_REMOTE`；需运行时探针 |

## 3. 已由真实目标/ donor 验证的内容

### 3.1 Donor TGL 16.0.32

- AppleIntelTGLGraphics 16.0.32、MTL driver 16.0.32、libigc 16.0.32；
- donor `libigc` 有 `gen12`/`gen12lp`/`TGLLP`；
- `logs/local/donor-audit-001.json`：10 条 MTL patch + 5 条 HW pattern +
  3 条 FB VALD pattern 全部匹配；
- 因此 **donor 是已知字节的补丁对象**，不需要目标 stock TGL 文件。

### 3.2 目标 25G83

- IOAF2 487.4.3 KC 符号：`waitForStamp`、DisplayPipe 事务、命令池、
  orphan pool、SysMemory lock/unlock、Resource2 getStorageResource 均存在；
- Metal 373.7、MTLCompiler 373.7、GPUCompiler 32023.255.1、
  IOSurface 393.5.8；
- 目标没有 TGL stock，符合预期；不是“无法开始适配”的理由；
- 目标也没有安装 NootedGreen/TGL；这同样不是离线构建前提。

### 3.3 仍需目标运行时探针

- `libxedrv` 的 descriptor class size / `_private` offset /附件布局；
- `MTLCompilerService` 的实际插件路径、`getSerializedModule` 签名；
- `libLLVM.dylib` 的 shared-cache `dlopen` 行为；
- 25G83 IOAF2 内部 offset（不是符号存在性）；
- 目标是否允许合法签名/加载（AMFI 约束）。

## 4. 状态语义修正

| 旧标签 | 新标签 | 说明 |
|---|---|---|
| TGL target `NEEDS_TARGET_BINARY` | `DONOR_TGL_16.0.32` + `VERIFIED_LOCAL` | donor 已存在且 pattern 已验证 |
| target TGL absent | `EXPECTED_ABSENT` / `NOT_INSTALLED_ON_TARGET` | 25G83 stock 不预装 TGL，属预期 |
| target ABI `NEEDS_TARGET_BINARY` | `TARGET_ABI_PARTIAL` / `NEEDS_TARGET_RUNTIME_PROBE` | 框架/符号已取，运行时布局未取 |
| target install optional | `DEPLOYMENT_OPTIONAL` | 只有安装后才需要 target-preflight 文件 |

`tools/check-tgl-compat.py` 的 `NOT_INSTALLED_ON_TARGET` 仍然正确，但
`reports/PATCH-REVALIDATION.md` 与 `FINAL-REPORT.md` 中“TGL target binary
missing = blocker”的表述应按本文修正。

## 5. 历史 1536 MB 显示基线与 Apple TGL 路线的关系

**必须分开两条验证轨道：**

### 轨道 D — 历史 ICL framebuffer/display 基线

- 镜像：`HP-Tahoe-TGL-eDP-483F.img`（候选）或 `GA32a`（GA3.2 非 Hang
  回退）；
- 机制：`lilucpu=12` + `igfxtglmap=0x483F` + `device-id=8A5A` /
  `AAPL,ig-platform-id=8A5C0002` + ICL LP framebuffer + WEG map；
- 目标：1536 MB / `AppleIntelFramebuffer@0/1/2` active；
- 这不是 Apple TGL 驱动，也不是 Metal 3D；历史镜像没有 `-allow3d`；
- 详见 `reports/BOOT-BASELINE-AUDIT.md`。

### 轨道 T — Apple TGL 16.0.32 donor + 25G83 ABI

- 输入：donor TGL 16.0.32 + NootedGreen TGL profile + `libxedrv` +
  compiler adapter/bridge；
- 目标 ABI：25G83 IOAF2/Metal/MTLCompiler/IOSurface；
- 目标不是“stock 25G83 TGL”，而是“把 donor 16.0.32 安全接到 25G83”；
- 历史 1536 MB 不能作为轨道 T 成功证据；轨道 T 也不应影响轨道 D 的回退。

两条轨道可以在后续受控实验中顺序验证，但必须一次只改一个变量，且不得
把 ICL framebuffer 的 1536 MB 写成 Apple TGL Metal 成功。

## 6. 下一阶段最小方案（仅规划，不执行）

### 阶段 1 — 显示基线恢复（轨道 D）

1. 只读确认目标 BIOS/DVMT GGC 仍为 `0x4C1`（128 MB）；记录当前 ICL
   framebuffer/accelerator 版本（当前 24.5.8，历史报告 24.0.5）。
2. 首选 `HP-Tahoe-TGL-eDP-483F.img`（map-only，无 Hang 参数）；
   `GA32a` 作为回退，`GA32b` 禁止。
3. 若启动，保存完整 `system_profiler`、`ioreg`、`kmutil showloaded`；
   1536 MB/3FB 通过后停止，不进入 3D/Hang。

### 阶段 2 — 轨道 T 离线预检与构建

1. 以 donor 16.0.32 为补丁对象，不要求目标 stock TGL；
2. 用 25G83 IOAF2/Metal/MTLCompiler 做 ABI 预检；
3. 构建 donor TGL 的离线 bundle（NootedGreen + libxedrv + compiler
   adapter/bridge）；不安装；
4. 对 `libxedrv` 做 25G83 descriptor 运行时探针（需新授权或用户提供）；
5. 对 `libLLVM`/`MTLCompilerService` 做 shared-cache `dlopen`/签名扫描；
6. 解决合法签名/加载；否则轨道 T 停在离线。

### 阶段 3 — 受控实机（仅新授权）

1. 先确认轨道 D 可回退；
2. 一次只改一个变量；
3. 不自动重启、不循环重试；
4. Metal/GPU 提交单独验收，不以 1536 MB/3FB 代替。

## 7. 结论

- **`DONOR_TGL_16.0.32` 是适配目标，不是缺失目标。** 目标 25G83 没有
  stock TGL 是预期事实，不构成 `NEEDS_TARGET_BINARY`。
- 25G83 仍需要的是 **ABI/runtime 证据**，不是“再找一个 stock TGL 驱动”。
- 历史 1536 MB/3FB 是 ICL framebuffer + WEG map 的显示基线；它与 Apple
  TGL 16.0.32 的 Metal 路线是两条独立轨道。
- 下一阶段应先恢复并记录显示基线，再离线构建/预检轨道 T；两者都不得
  绕过签名、ABI 或二进制校验。
