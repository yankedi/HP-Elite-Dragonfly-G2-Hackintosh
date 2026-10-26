# GA3.3 变更日志（诊断版；仅采集链路，无安全放宽）

基线：`WhateverGreen-GA3.2`（kext 466af67b…）→ GA3.3（kext **47771c398d60bb052947c4ccce67ae2e165ef13c79c6c29344d6913967eadbc3**）。

## 变更

1. `kern_tglhang.hpp`
   - 新增 `TglHang::Diag`（88B：version/size/stage/failReason/failLevel、
     pmapChecked/Accepted/Rejected、fenceRejected、readAttempts/Successes、
     batchBytes/vsBytes/psBytes、bridgeDiag、failGpuVA/failPhys/failTable）；
   - `Reader` 新增阶段/级/VA/表/读计数与 `markFail()` 首次拒绝归因）；
   - `fetch()` 记录 lastPhys、统计读取尝试/成功；`allowed()` 拒绝归因；
   - `translate()` 记录当前 level/GPU VA/页表基数；`capture()` 增加阶段标记。
2. `kern_igfx.hpp`：`HangRecord` 尾部追加 `TglHang::Diag diag`（记录尺寸 0xC2A0→0xC2F8）；
   模块新增 pmap/fence 计数成员。
3. `kern_igfx.cpp`：`hangPageAllowed()` 归因计数（fence 或 pmap+PPN）；`hangCapture()` 回填 diag。

## 明确未做（任务 O 禁止项）

- 未禁用/绕过 `pmap_valid_page`、未放宽 TSEG/stolen/SMRAM/4G/16TiB/maxMem；
- 未改 GPU 页表有效位判断、未强制映射保留页、未改 Batch/Shader、未启用翻译；
- 未动 Framebuffer/CSB/igfxtglss；未改 BIOS/DVMT/SIP/SSV/内部 EFI；
- 未新增物理访问路径；采集上限（次数/字节/页表读）与 fail-closed 逻辑原样保留。

## 兼容性

- v2 记录（GA3.1/GA3.2）仍可解析（parse_thag.py v4 自动识别）；
- v3 记录自带 version/size；旧解析器遇到 v3 会因长度不符报错——这是刻意的版本护栏。
