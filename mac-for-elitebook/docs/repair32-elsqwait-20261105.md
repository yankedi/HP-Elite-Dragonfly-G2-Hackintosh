# R32-ELSQWAIT：无条件 ELSQ bit30 等待 + GEN8_ROW_CHICKEN2 0xc100c100 突破 Horizon Detection（2026-11-05）

## 1. 变更摘要
在 `kern_gen11.cpp` 与 `hp_repair_policy.hpp` 中（基于 `R32-PERCTX`，对应补丁 [`patches/nootedgreen-r32-elsqwait-20261105.patch`](../patches/nootedgreen-r32-elsqwait-20261105.patch)）：

1. **`elsqWait`（`xeCs5Submit` 与 `xePrepSubmit`）**：
   - 将等待条件恢复为只要 `(EXECLIST_STATUS_LO & 0x40000000) != 0` 即轮询等待（5 µs 步进，上限 2000 µs），避免在 `0x2234` 的 bit 30 尚未落下时向 `0x2510..0x2550` 发起新的 Execlist 装载导致 Lite Restore / 跨上下文提交竞争。
2. **`GEN8_ROW_CHICKEN2`（`0xe4f4`）掩码写入**：
   - 在 `nativeRowPrefix` 中将写入值从 `0xc000c000`（bits 14, 15）更新为 `0xc100c100`（bits 8, 14, 15，同时开启 `DISABLE_PARTIAL_INSTRUCTION_SHOOTDOWN`、`DISABLE_DOP_GATING` 与 `DISABLE_EARLY_READ`）。
3. **保留既有修复**：
   - `CS_CHICKEN1`（`0x2580`）引擎启动与每上下文 LRI 写入 `0x00020002`（Thread-Group Preemption，`WaDisableGPGPUMidThreadPreemption`）。
   - `FF_DOP_CLOCK_GATE_DISABLE`（`0x20ec = 0x13`）、`NOAUX`、`NOCCS3`、`L3=6`、`FBABI`、`RECT4`、`XE-GPUREC`。

## 2. 构建与哈希
- 镜像路径：`.local/driver-repair-20261103/repair32-readback/HP-UPSTREAM-6F03560-REPAIR32-ELSQWAIT.img`
- 镜像 SHA256：`cb62501d35fa12dc295f34fa49fa4ecda9b2751586ad1fde18a61ec580a766bc`
- `NootedGreen` 二进制 SHA256：`e0d6fe75c2d4f4e488d3ff936f70f3551f71d5ea10a29158d364fd194139ad7c`
- `NootedGreen` Mach-O UUID：`4C4C440C-5555-3144-A1CF-CF98321C87D2`

## 3. 实机结果（`trial-r32-elsqwait-20261105`）
- **起始 NixOS boot**：`482d3ad8-7ce2-4737-b6e3-1b23b7db4cde`
- **macOS boot**：`85DC6896-0E25-43AE-A423-7BA5FE6CD3F5`
- **返回 NixOS boot**：`c7f9af8d-2372-4d01-ada7-f235492299ca`
- **安装与启动门控**：12/12 全部通过；7/7 次启动样本读回 `0xe4f4 = 0xffffc100`、`0x2580 = 0x00000003`、`0x95c = 0x8f000000`。
- **Geekbench 6 Metal 进展**：
  - `Background Blur`：完成
  - `Face Detection`：完成（303 validation warning）
  - **`Horizon Detection`：100% 完成，未发生 GPU hang（重大突破！）**
  - **`Edge Detection`**：Context 52（`0x680`）连续成功执行 7 次单上下文计算 batch（`EXEC 7418..741e`，`stamp = 2248..2254`，`gpu = 0x4ecfe000`，每次耗时 `26.37–27.29 ms`），在第 8 次提交（`EXEC 741f`，`stamp = 2255` / `0x8cf`）执行至 `ACTHD = 0x4ecfe3a8`、`IPEHR = 0x7a000004`（`PIPE_CONTROL`）、`CSFLFLAG = 0x50000000`、`CSFLTRK = 0x12000001` 时遇到 `WindowServer`（`0xa0`）提交抢占（`[0x2234] = 0x40003098`、`[0x2214] = 0xa0`、`[0x2248] = 0x800`）并挂起。
- **回程与诊断核验**：
  - 首 hang 原始快照 `first-hang-78f2e21f-fdb8-4305-a86e-b58a730b3a8c.dmesg`（SHA256 `89b1ce94de7f9a014b3809fd59a737242d4a398d0d85874a040df7f2d55bfdd3`）完整保存。
  - `post-nixos` 采集 `efivars-full.tar`（SHA256 `9c1ef5eae3743171a1fae807ef6ff7bb0060bdf1148b82d237bba3196ee37bb8`，0 新增 `PanicInfo`）与 `DiagnosticReports-full.tar`（SHA256 `04ce3f2158a9c7405f5d21e87984283bd69e8d35ab51eac006c254e004c9c1c1`，0 新增 `.panic`）。
  - 子代理审计会话：`a72eacfe-73c5-4804-84d5-590c672021c6`。

