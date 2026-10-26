# GA4.4 之后的最小下一步（审计修正版）

本阶段已停止。以下操作不会自动执行；需要新的明确授权，尤其是目标机启动、
安装或 GPU 实验。

## 0. 对象重新定义

- **`DONOR_TGL_16.0.32` 是拟移植/补丁对象**，已在 GA4.3 固定树中；
  donor 18 条 pattern/字节已验证。**不是缺失目标。**
- 25G83 stock 没有 TGL 驱动是 `EXPECTED_ABSENT`，不是
  `NEEDS_TARGET_BINARY`。
- 25G83 提供的是 **ABI/框架/内核符号**：IOAF2 487.4.3、Metal 373.7、
  MTLCompiler 373.7、GPUCompiler 32023、IOSurface 393.5.8。
- 历史 1536 MB/3FB 是 **ICL framebuffer + WEG map** 的显示基线，
  不是 Apple TGL donor 的 Metal 成功；两条轨道分离。

详见 `reports/NEEDS-TARGET-REASSESSMENT.md` 和
`reports/BOOT-BASELINE-AUDIT.md`。

## P0 — 恢复历史显示基线（轨道 D）

目标：先确认 2026-10-17 的 1536 MB/3FB 显示状态，不进入 3D/Hang。

首选镜像：`HP-Tahoe-TGL-eDP-483F.img`（map-only，无 Hang 参数）。
回退：`HP-Tahoe-TGL-GA32a.img`（GA3.2 非 Hang，但含 `igfxtglss=6`/
`igfxtglcsb=1`，且历史报告基于 ICL 24.0.5）。
禁止：`GA32b`/`GA31b`（Hang 实验）。

准确参数（eDP-483F）：

```text
-v keepsyms=1 debug=0x100 slide=0 -vi2c-force-polling
lilucpu=12 -igfxcdc igfxtglmap=0x483F
```

DeviceProperties：

```text
PciRoot(0x0)/Pci(0x2,0x0)
  device-id           = 5a8a0000  (0x8A5A)
  AAPL,ig-platform-id = 02005c8a  (0x8A5C0002)
```

前置只读检查：

1. 目标 GGC/GMS 是否仍为 `0x4C1`/4（128 MB DVMT）；若变了，先记录，不
   沿用历史假设；
2. 目标 stock ICL framebuffer/accelerator 版本（当前 24.5.8；历史
   GA32 报告是 24.0.5）；
3. `Kernel/Block` 是否仍无法阻止 ICL accelerator（历史报告显示它仍加载）；
4. 启动后保存完整 `system_profiler`、`ioreg`、`kmutil showloaded`。

**退出条件：** 有真实 `VRAM (Dynamic, Max): 1536 MB` 和
`AppleIntelFramebuffer@0/1/2` 的原始输出，或明确失败。不得以截图/文件名
代替；不得用 1536 MB 宣称 Metal 成功。

## P1 — 轨道 T：donor 16.0.32 的离线构建/预检

1. 以 donor 16.0.32 为补丁对象，不需要目标 stock TGL。
2. 用 25G83 IOAF2/Metal/MTLCompiler 做 ABI 预检。
3. 构建 donor TGL 的离线 bundle（NootedGreen + `libxedrv` + compiler
   adapter/bridge）；不安装。
4. `libLLVM` 目标上只有 shared cache 路径；需要运行时 `dlopen`/导出探针，
   不能把普通路径不存在当库不存在。
5. 目标 stock 插件是新 API 但没有 gen12；donor 旧 API 有 gen12/TGLLP；
   adapter/bridge 仍需要。

## P2 — `libxedrv` 25G83 运行时探针

在 25G83 Metal 373.7 上只读取得：

- `MTLRenderPipelineDescriptorInternal` size（期望 0x338）；
- `_private` offset（期望 0x30）；
- 颜色附件 size 0x10 / `_private` 0x8；
- `rasterSampleCount@0xb8`、`vertexDescriptor@0x110`；
- `logicOp` 位 32 / 旧位 27。

未取得前不更新 `libxedrv` 的 25G83 兼容状态。

## P3 — 合法签名/加载

参考方案仍依赖 `amfi_get_out_of_my_way=1`；本任务禁止。没有合法
Developer ID/公证或用户明确授权的新安全策略，不能进入实机安装。

## P4 — 受控实机实验（仅新授权）

前置：P0 显示基线可回退、P1/P2 离线通过、P3 有合法路径、用户明确批准。
一次只改一个变量；完整备份；只读采集；panic/hang 立即停止；不自动重启。

## 建议顺序

1. P0 显示基线（eDP-483F，必要时 GA32a）——只验证显示，不进入 3D；
2. P1 donor TGL 离线构建；
3. P2 `libxedrv`/ABI 探针；
4. P3 签名/加载；
5. P4 一次受控轨道 T 实验。

**不要**把 donor 结果写成 25G83 目标通过；**不要**把 SSH 成功/符号匹配
写成 Metal 加速成功；**不要**把 1536 MB/3FB 写成 Metal 成功。
