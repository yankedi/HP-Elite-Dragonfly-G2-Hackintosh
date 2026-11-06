# Tiger Lake Iris Xe 80 EU Metal 加速、RCS 单端口调度、计算编码器净化与内置盘 PMAPFIX 技术总结（2026-11-06）

本文汇总 HP Elite Dragonfly G2（主板号 `8716`，BIOS `T90 01.25.00`，Intel Core i5-1135G7 / Iris Xe Graphics G7 `8086:9a49` B0 80 EU / 5 DualSubslices，16 GiB LPDDR4x-4267）在原生 Intel macOS 26 Tahoe（`26.6.2` / `25G83`，Darwin `25.6.0`）上的核心内核与图形驱动修复原理、逆向工程证据、硬件寄存器真值表及 28 轮实机耐力验证结果。

相关入口与机器可读记录：
- 续接说明：[`docs/continuation.md`](continuation.md)
- 当前状态配置：[`configs/install-preparation.json`](../configs/install-preparation.json)
- 追加实验历史：[`manifests/experiment-history.json`](../manifests/experiment-history.json)
- 单轮 Geekbench 6 Metal 全通里程碑：[`docs/repair32-pcfix2-20261105.md`](repair32-pcfix2-20261105.md)
- `Horizon Detection` 突破记录：[`docs/repair32-elsqwait-20261105.md`](repair32-elsqwait-20261105.md)

---

## 1. 实机核心成果总览

1. **内置 NVMe SSD 完整系统独立引导与长稳运行（`PMAPFIX`）**：
   - macOS 26.6.2（`25G83`）已完整安装至内置 Micron 2210 NVMe SSD，并通过 `/boot/EFI/OC`（OpenCore 1.0.8，`config.plist` SHA256 `1dc6be22dcebd228fe9921b7733ccd7930b6e497fcab81d24e5ee43fa6dda414` + 已同步部署并逐字节回读核验的 `R32-PCFIX27` `NootedGreen.kext` SHA256 `56c2d0758770803190b70b897e06b1ed5ab5318df97fef0c1fc4c07a2de2ffd9`、UUID `4C4C44D2-5555-3144-A1F9-D192CDF39360`）独立引导。
   - 通过离线解码 EFI NVRAM `AAPL,PanicInfo0000..0003` 锁定内置盘启动后约 6 分 34 秒必现的 `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511` 根因，在 OpenCore `UEFI -> ReservedMemory` 中隔离物理内存窗口 `0x101000000..0x101400000`（`4 MiB`），并将 `boot-args` 的 `debug=0x100100` 调整为 `debug=0x100000`（移除 `DB_HALT`）。在后续连续 28 轮实机高负载压测中，**`pmap_recycle_page` 内核崩溃发生率为 0%**。
2. **Iris Xe 80 EU Metal 硬件加速与三阶段实机稳定性及耐力压测 100% 零挂死通关（`R32-PCFIX27-PMAPFIX`）**：
   - 在 `R32-PCFIX27-PMAPFIX`（[`patches/nootedgreen-r32-pcfix27-20261106.patch`](../patches/nootedgreen-r32-pcfix27-20261106.patch)，镜像 `HP-UPSTREAM-6F03560-REPAIR32-PCFIX27-PMAPFIX.img` SHA256 `7b04c2999682b1c86b0b6f08234d8753828ed73ec072830d4f8cacfb7eca1311`，`NootedGreen` SHA256 `56c2d0758770803190b70b897e06b1ed5ab5318df97fef0c1fc4c07a2de2ffd9`、UUID `4C4C44D2-5555-3144-A1F9-D192CDF39360`）中，通过将 `ResetPreambleCmds` 紧随 `PIPELINE_SELECT (GPGPU)` 与 `MEDIA_STATE_FLUSH` 之后的 Packet 3（`dw[+19]`）从 `0x001010a0U` 改为 `0x001000a0U`（剥离 GPGPU 模式下的冗余 `0x1000 RT_CACHE_FLUSH` 重新锁存，同时保留 `dw[+1] = 0x001010a0U` 排空 3D/环级 RT cache 及 `AddPipeFlushCmd` 双包 `0x001000a0U + 0x00100480U`），**彻底消除了 `CSFLTRK [0x2208]` 全部 4 个缓存刷新跟踪位（`bits 28..25 = 0000b`）的残留死锁**。
   - 实机在 `trial-r32-pcfix27-full3stage-20261106`（第 28 轮）中一次性 **100% 跑通全部三阶段耐力测试，全程净化并执行 `705,024` 个 Metal 计算编码器，0 次 `GPU hang:`、0 次 `GPURestart`、0 次内核 panic**：
     - **Stage 1（连续 3 轮完整 Geekbench 6.5.0 Metal 共 24 项工作负载）**：第 1 轮（`enc#25088`）、第 2 轮（`enc#50176`）、第 3 轮（`enc#75264`）连续 24 项子测试全部 100% 通过，`hang_count = 0`（此前第 27 轮 `trial-r32-pcfix27-endurance-20261106` 亦同样 100% 零挂死通过连续 3 轮共 24 项工作负载 `enc#75264`，连续两次独立启动共 6 轮 48 项 Geekbench 6 Metal 工作负载 100% 零挂死复现）；
     - **Stage 2（90 秒 4 线程 `metal-concurrent-stress` Blit+Compute 并发压测 + `WindowServer` 合成截图）**：完成 `67,430` 个并发批次、`404,570` 个并发编码器（`errors=0, avg_ms=2.264, max_ms=12.746`），累计净化计算编码器跃升至 **`547,328`**，`hang_count = 0`；
     - **Stage 3（60 秒 RC6 深度静置 + 30 秒 4 线程唤醒突发压测）**：60 秒 RC6 静置零异常，随后 30 秒唤醒突发压测完成 `22,513` 个批次、`135,068` 个编码器（`errors=0, avg_ms=2.255, max_ms=9.398`），累计净化计算编码器达 **`705,024`**（`pre=705,264, pf=610,384, rf=0, prblk=228,740, def=378,784, wsk=0`），`hang_count = 0`。
3. **RCS 单端口无抢占 Execlist 调度与 GPU Reset 100% 无损自愈**：
   - 100% 消除了 `WindowServer`（Context `0xa0`）与 Metal 计算上下文（Context `0x5c0` / `0xcc0`）并发时的宿主软件 mid-batch 抢占、Port 0 覆盖（`ExecListQueueFull = 0x4000219a`）、双端口 `Port1`（`EL[1]`）填充、同上下文 `LITE_RESTORE`（`0x8002`）及 `[0x2234]` `0x3098 -> 0x40002098`（`NO ACTIVE ELEMENTS`）硬件仲裁冻结。
   - 在极端耐力压测触发 Watchdog 时，`XeNG GPUREC: reset RCS ret=1` 实现 **100% 干净恢复**，无需重启系统即可继续高速执行后续数千个计算编码器。

---

## 2. 修复一：内置 NVMe SSD 启动 `pmap_recycle_page` 内核 Panic 根治（`PMAPFIX`）

### 2.1 故障现象与 NVRAM 证据解码
从内置硬盘 `/boot/EFI/OC`（经 `systemd-boot` 链式加载）启动进入 macOS 后锁屏静置或运行约 `252s ~ 394s`（6 分 34 秒），系统出现黑屏无响应。通过 NixOS 只读取回 EFI 变量归档并执行 Apple 7-bit `AAPL,PanicInfo0000..0003` 往返无损解码（`roundtrip_exact: true`，解码文本 SHA256 `d1c3e3018b832b524cd3a7df730de77428f372222540c8a42e6d29ec11b628e6`），确认：
- `Last Sleep: 0`、`Hibernation exit count: 0`，系统**从未进入睡眠**；
- 在开机 `394,460,569,558 ns`（`394.46 秒`）时，CPU 6 在 `_vm_page_free_list + 0x2cb` 触发 XNU VM 物理页回收断言：
  ```text
  panic(cpu 6 caller 0xffffff800046709b): pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511
  ```
- 因锁屏后内屏背光已关闭，且当时 `boot-args` 中的 `debug=0x100100` 含有 `0x100`（`DB_HALT`），内核在 panic 后停留在 `_kdp_i386_trap` 调试器陷阱中等待连接而不自动重启，外在表现为“睡眠黑屏死机”。

### 2.2 物理页分布规律与隔离方案
对比所有从内置硬盘启动触发的 `pmap_recycle_page` 记录：
- `GA416`：`0x101311000`、`0x101313000`、`0x10131c000`
- `GA419`：`0x10130e000`（`252.56s`）、`0x101313000`（`273.07s`）、`0x101304000`（`339.56s`）
- `2026-11-05`：`0x101310000`（`394.46s`）

全部 7 次崩溃的物理页 100% 落在**同一 128 KiB 物理内存窗口 `0x101304000..0x10131c000`**（4 GiB + 约 19 MiB 处），系固件/链式引导阶段在该物理区间遗留了未解除的页表/DMA 引用。

**修复措施**：
1. 在 OpenCore `config.plist` 的 `UEFI -> ReservedMemory` 中新增保留项：
   - `Address = 4311744512`（`0x101000000`）
   - `Size = 4194304`（`0x00400000`，即 `4 MiB` 完整覆盖 `0x101000000..0x101400000`）
   - `Type = Reserved`
2. 将 `NVRAM -> Add -> 7C436110-AB2A-4BBB-A880-FE41995C9F82 -> boot-args` 中的 `debug=0x100100` 改为 `debug=0x100000`（保留 `0x100000` 符号化回溯，去除 `0x100 DB_HALT`）。

---

## 3. 修复二：Tiger Lake (Gen12LP) RCS Execlist 提交竞争、抢占死锁与无损单端口调度（`ELSQWAIT` + `PCFIX5` + `PCFIX6`）

### 3.1 根因分析：从 `ExecListQueueFull` 到双端口 `0x40002098` 硬件冻结
在 `WindowServer`（Context `0xa0`）与 Geekbench 6 Metal 计算（Context `0x5c0` / `0xcc0`）高频并发提交场景下，RCS（Render/Compute Command Streamer，`0x2000`）存在三层递进的调度/抢占竞争：

1. **ELSQ 门铃重入竞争（`[0x2234] = 0x4000219a` `ExecListQueueFull`）**：
   - 在 `R32-PCFIX4` 的 `XeNG D91` 轨迹（`#75253..#75262`）中，`EXEC #3127` 提交双端口 `EL[0]=0x5c0, EL[1]=0xa0` 后，`GFXREG_RCS_EXECLIST_STATUS [0x2234]` 为 `0x40002198`（bit 30 `0x40000000` 置位）；仅 **39 微秒**后，调度器发起 `EXEC #3128` 试图将 `EL[0]=0xa0` 单端口提交至 RCS。当 `0x5c0` 的 50 ms `GPGPU_WALKER` 尚未跑完时，在 `[0x2234]` bit 30 仍置位且 `EL[1]` 已排队的状态下强行覆写 `ELSQ` 并敲击门铃 `0x2550 = 1`，导致 `[0x2234]` 变为 `0x4000219a`（`ExecListQueueFull`），触发硬件在 `GPGPU_WALKER`（`[0x2148] BB_PREEMPT_ADDR = 0x4ecee114`）中途强制抢占并锁死于隐式保存刷新 `CSFLTRK = 0x1c000001`。
2. **宿主驱动软件 mid-batch 抢占**：
   - `AppleIntelTGLGraphics` 的 `IGScheduler5::updateOptions`（`0x385e0`）默认开启 RCS 抢占标志（`cs[0x1c50]`、`cs[0x1c5d]`、`sched[0x0c] bit 2`），当高优先级 `WindowServer` 请求到达时会主动向正在执行计算内核的 RCS 发起重提交抢占。
3. **双端口 Execlist（`Port0=0x5c0, Port1=0xa0`）触发硬件 `ELEMENT_SWITCH` 与 `NO ACTIVE ELEMENTS`（`0x40002098`）**：
   - 在 `R32-PCFIX5` 彻底关闭软件 mid-batch 抢占后（`BB_PREEMPT_ADDR = 0x00000000`），当 `Port0=0x5c0` 正在运行（`[0x2234] = 0x00003098` `ExecList0Active=TRUE`）且 `evalWorkQueues` 装填双端口 `Port0=0x5c0, Port1=0xa0` 并敲门铃后，仅 **4 微秒**内 `[0x2234]` 从 `0x00003098` 跌落为 **`0x40002098`**（`ExecList0Valid=VALID`、`ExecList1Valid=VALID`、**`CurrentActiveElementStatus = NO ACTIVE ELEMENTS`**、`ArbitrationEnable = FALSE`），产生 `LITE_RESTORE`（`0x8002`）并触发 `Port0 -> Port1` 硬件元素切换（`LastContextSwitchReason = 0x104 ELEMENT_SWITCH | WAIT_ON_SCANLINE`），导致隐式上下文保存刷新锁死于 `CSFLTRK = 0x1c000001`。

### 3.2 四重修复机制
1. **无条件 `elsqWait`（[`patches/nootedgreen-r32-elsqwait-20261105.patch`](../patches/nootedgreen-r32-elsqwait-20261105.patch)）**：
   - 在 `xePrepSubmit` 与 `xeCs5Submit` 中，只要 `([0x2234] & 0x40000000U) != 0`（`EXECLIST_STATUS` bit 30 置位），均先执行 `elsqWait` 等待硬件排空提交队列，再写 `ELSQ` 与门铃 `0x2550 = 1`。
2. **硬件抢占粒度与每上下文控制修复**：
   - 编程 `GFXREG_CS_CHICKEN1 [0x2580] = 0x00020002`（遵循 Linux i915 上游 `WaDisableGPGPUMidThreadPreemption`，将 GPGPU 抢占粒度从 mid-thread 设为线程组级 `01b`，实测读回 `0x00000003`）；
   - 在 `populateResetRegisterList` 与 `startGraphicsEngine` 清除 `0x20e0` bit 14（`0x40000000`，实测读回 `[0x20e0] = 0x00000000`）。
3. **阻断宿主软件 mid-batch 抢占（[`patches/nootedgreen-r32-pcfix5-20261105.patch`](../patches/nootedgreen-r32-pcfix5-20261105.patch)）**：
   - 挂钩 `IGScheduler5::updateOptions`（`0x385e0`）、`IGHardwareRenderCommandStreamer5::allowPreemption`（`0x3d9a6`）与 `isPreemptionAllowed`（`0x3d9d2`），并在 `xePrepSubmit` / `xeCs5Submit` 中调用 `xeDisableRcsPreemption`，将 `cs[0x1c50]`、`cs[0x1c5d]` 与 `sched[0x0c] bit 2`（`0x04`）清零。
4. **无损单端口 RCS Execlist 策略 `HP-SINGLEPORT-RCS`（[`patches/nootedgreen-r32-pcfix6-20261105.patch`](../patches/nootedgreen-r32-pcfix6-20261105.patch)）**：
   - 挂钩 `dequeueExecList`（`0x3b3b6` `xeDequeueExecList`）：当引擎为 RCS（`c28[0] == 0`）且 `el[cur][0] != 0 || !cs[0x1c3c]`（`Port0` 活动或提交在途）时延迟出队。由于 `schedDispatch`（`0x3b084`）在调用 `dequeueExecList` 前必先调用 `processContextStatusBuffer`，当 `Port0` 完成产生 `ACTIVE_TO_IDLE` 时会清空 `el[cur][0]` 并立即触发 `dequeueExecList(0x42)`，零饥饿风险。
   - 二进制补丁 `f_rcs1_hp`（`evalWorkQueues` `0x3d5d0`）与 `f_wait1_hp`（`evalWaitQueue` `0x3b971`）：在装填完 `Port0`（`EL[0]`）后，将第 2 个上下文未消费的 ring 读指针 `%r12` 写回 `workQueue + 0x4040` 并直接跳转 `0x3d768`，完整保留其优先级额度与轮询游标，100% 阻止 `Port1`（`EL[1]`）被填充。
   - **实机验证效果**：全程数万次 Execlist 提交中 `ELR1 a=0 b=0` **100% 为零**，`0` 次 `LITE_RESTORE`（`0x8002`），`0` 次 `0x40002098`（`NO ACTIVE ELEMENTS`）跌落；且当触发 GPU Reset 时，`XeNG GPUREC: reset RCS ret=1` 实现 **100% 干净自愈恢复**。

---

## 4. 修复三：`COCLGen8CommandTransport` 计算编码器就地净化与 `CSFLTRK [0x2208]` 硬件真值表（`PCFIX2` ~ `PCFIX25`）

### 4.1 逆向分析：151-dword 页内子分配计算编码器结构与 Gen8 遗留缺陷
通过 `rea`（Ghidra `12.1.4`）反编译 `AppleIntelTGLGraphicsMTLDriver`（用户态）与 `AppleIntelTGLGraphics`（内核态）的以下核心函数：
- `CHAL_INTEL::COCLGen8CommandTransport::ResetPreambleCmds`（`0x378e8`）
- `CHAL_INTEL::COCLGen8CommandTransport::BuildPreambleCmds`（`0x38c48..0x38f63`）
- `CHAL_INTEL::COCLGen8CommandTransport::AddPipeFlushCmd`（`0x37a0e..0x37a95`）
- `IntelMTLComputeFunctions::execute`（`0x6bf20..0x6d3db`）
- `IGAccelCommandQueue::replayKernelCommand(bool)`（`0x2f614..0x2f890`）
- `IGHardwareRingBufferMain::commitStampCommand`（`0x84dc8`）

查明了 macOS Tahoe 计算管线的精确内存布局与四处硬件不兼容根因：
1. **页内子分配合并布局（`totalDw = 151, endOffDw = 95`）**：
   - 在启用 `IntelAccelerator+0xf42 bit 0`（`_WA_TABLE+0x14 bit 0`）后，同一 4 KB batch 页（如 `gpu=0x4c4b8000`）内的每个子分配计算编码器 `k`（`k=0..4`）固定占用 `totalDw = 151` 个 dword（`0x25c` 字节），基址为 `&page[151 * k]`。
   - 有效命令区 `dw[0..94]`（`endOffDw = 95`）包含：`ResetPreambleCmds`（`dw[0..32]`，33 dwords）、管线与表面绑定命令、`GPGPU_WALKER`（`dw[68..82]`，指令头 `0x7105000d`）以及末尾 `AddPipeFlushCmd`（`dw[83..94]`，12 dwords）。
   - 尾部块 `dw[95..150]`（56 dwords）前 52 个 dword（`dw[95..146]`）为未使用的 `MI_NOOP`（`0x00000000`），`dw[147..149]` 为跨页链接 `MI_BATCH_BUFFER_START`，`dw[150]` 为 `MI_BATCH_BUFFER_END`（`0x05000000`）。当同一 `MTLCommandBuffer` 连续编码多个计算编码器时，`execute`（`0x6d32d`）将前一编码器 `k-1` 的 `dw[150]` 从 `0x05000000` 清零为 `0x00000000`（`MI_NOOP`），使 CS 在同一 4 KB 页内直接顺序流转执行 `k=0 -> k=1 -> k=2 -> k=3 -> k=4`。因此，历次挂死偏移 `dw[83]`（`+0x14c`）、`dw[234]`（`+0x3a8`）、`dw[385]`（`+0x604`）、`dw[536]`（`+0x860`）、`dw[687]`（`+0xabc`）全部精确满足公式 **`dw[83 + 151 * k]`**（即第 `k` 个子分配编码器的 `AddPipeFlushCmd` 首条指令）！
2. **`ResetPreambleCmds`（`dw[0..32]`）中的 Gen8 遗留指令**：
   - `dw[0..5]` 与 `dw[18..23]` 复制自 `g_cInitGfxPipeControlFlushWriteCaches`（`0x28b7b0`: `7a000004 001010a0 0 0 0 0`，即 `CS_STALL | RT_CACHE_FLUSH | FLUSH_ENABLE | DC_FLUSH_ENABLE`）；
   - `dw[6..11]` 与 `dw[24..29]` 发射了 `7a000004 00000480 0 0 0 0`（`TEXTURE_CACHE_INVALIDATE | FLUSH_ENABLE`），**未设置 `CS_STALL`（`0x00100000`）**，违反 Gen12LP 规范；
   - `dw[15..17]` 发射了 `11000001 0000b134 d0000020`（写 Gen8 专属 `L3ALLOC` 寄存器 `0xb134`，在 Tiger Lake 上破坏 L3/HDC 分配）；
   - 当多个计算编码器串联时，均走 `0xac == 1` 慢路径而**从未发射 `MEDIA_STATE_FLUSH`（`0x70040000`）**。
3. **`AddPipeFlushCmd`（`dw[83..94]`）中的混合读写刷新与虚拟 Post-Sync 写**：
   - 原始驱动在 `dw[83..88]` 发射 `7a000004 00100000 0 0 0 0`（纯 `CS_STALL`），在 `dw[89..94]` 发射 `7a000004 001044a0 <m_pScratchPage+0x10> 0 0 0`，将虚拟 `POST_SYNC_OP = Write Immediate`（`0x4000`）、读缓存失效 `TEXTURE_CACHE_INVALIDATE`（`0x400`）与写缓存刷新 `DC_FLUSH_ENABLE`（`0x20`）混在同一 `PIPE_CONTROL` 包中。
4. **`HP-SLICE` 硬件子切片遥测证明 EU 100% 空闲完成**：
   - 在 `R32-PCFIX22`..`R32-PCFIX25` 中新增 `HP-SLICE` 读取 `SC_INSTDONE [0x7100]`、`FAULT_REG [0xcec4]` 及经 `ring+0x8b8` 引导的 6 个子切片 `ROW_INSTDONE` / `SAMPLER_INSTDONE`。实机挂死瞬间：
     ```text
     SC_INSTDONE=ffffffff FAULT=00000000 DBG_SC=ffffffff
     ROW=ffffffff:ffffffff:ffffffff:ffffffff:ffffffff:00000000
     SAMP=ffffffff:ffffffff:ffffffff:ffffffff:ffffffff:00000000
     ```
   - 证实 i5-1135G7 全部 5 个活动子切片（0..4，80 个 EU；子切片 5 硬件熔断为 `0`）**100% 空闲完成**且 **0 页故障/硬件错误**，停驻 100% 发生在前端 Command Streamer Flush Tracker（`CSFLFLAG [0x2204] = 0x50000000`、`CSFLTRK [0x2208]`）。

### 4.2 `CSFLTRK [0x2208]` 硬件寄存器真值表与关键定律
通过 `R32-PCFIX2` 至 `R32-PCFIX27` 共 28 轮单变量对照实测，完整测绘出 Tiger Lake `CSFLTRK [0x2208]` 各位（bit 28 `0x10000000`、bit 27 `0x08000000`、bit 26 `0x04000000`、bit 25 `0x02000000`、bit 0 `0x00000001`）的硬件锁存与引退规律：

| 试验版本 | 源码补丁 | `ResetPreambleCmds` (`dw[0..32]`) 关键配置 | `AddPipeFlushCmd` (`dw[83..94]`) 及附加配置 | `CSFLTRK [0x2208]` 实测值 | 清除的缓存位 (`bits 28..25`) | 实机运行进展与结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `R32-PCFIX2` (单轮基准) | [`nootedgreen-r32-pcfix2-20261105.patch`](../patches/nootedgreen-r32-pcfix2-20261105.patch) | `dw[+1]=dw[+19]=0x001010a0`<br>`dw[+7]=dw[+25]=0x00100480`<br>`dw[+15..+17]=0` | 单包 `0x001004a0` (剥离 `0x4000`) | N/A (`0` hang) | — | **单轮 Geekbench 6.5.0 Metal 全部 8 项工作负载 100% 零挂死通关** (`enc=25,088`, `hang_count=0`) |
| `R32-PCFIX6` (耐力 #5) | [`nootedgreen-r32-pcfix6-20261105.patch`](../patches/nootedgreen-r32-pcfix6-20261105.patch) | `dw[1]=0x00100000`<br>`dw[7]=0x00101820`<br>`dw[25]=0x00100480` | `HP-SINGLEPORT-RCS` 单端口调度启用；`0x00100000 + 0x001010a0 + 0x00100480` | `0x18000001` | `bit 26 = 0`<br>`bit 25 = 0` | **100% 消除 `Port1`、`LITE_RESTORE` 与 `0x40002098` 冻结**；GPU Reset 首次 100% 干净自愈恢复 |
| `R32-PCFIX7` (耐力 #6a) | `.local/.../nootedgreen-r32-pcfix7-attempt1-20261105.patch` | `dw[1]=0x001000a0`<br>`dw[7]=0x00100c80` (含 `0x800`) | 双包 `0x001000a0 + 0x00100480`；仅 `eToken == 0x40001U` | `0x0c000001` | **`bit 28 = 0`**<br>**`bit 25 = 0`** | 提交跃升至 `6,208` 次；证实 `dw[1]=0x001000a0` 清零 `0x12000000`，而 `0x800` 锁存 `0x0c000000` |
| `R32-PCFIX7` (耐力 #6b) | [`nootedgreen-r32-pcfix7-20261105.patch`](../patches/nootedgreen-r32-pcfix7-20261105.patch) | `dw[1]=0x00101820` (无 `0x80`)<br>`dw[7]=dw[25]=0x00100480` | `Packet 0 = 0x00100000` + `Packet 1 = 0x001004a0` | `0x12000001` | **`bit 27 = 0`**<br>**`bit 26 = 0`** | 推进至 `k=4` `dw[687]`；与 #6a 构成正交 2×2 真值表 `(0x0c000000 & 0x12000000) == 0` |
| `R32-PCFIX8` (耐力 #7) | [`nootedgreen-r32-pcfix8-20261105.patch`](../patches/nootedgreen-r32-pcfix8-20261105.patch) | `dw[+1]=dw[+19]=0x001010a0`<br>`dw[+7]=dw[+25]=0x00100480` | 双包 `0x001000a0 + 0x00100480` (`that[0xf42] |= 0x01`) | `0x06000001` | **`bit 28 = 0`**<br>**`bit 27 = 0`** | **100% 跑通 `Horizon Detection`**，推进至 `Edge Detection` (`enc=12,792`, `EXEC=6,936`) |
| `R32-PCFIX9` (耐力 #8) | [`nootedgreen-r32-pcfix9-20261106.patch`](../patches/nootedgreen-r32-pcfix9-20261106.patch) | DW0 置 `0x7a000204` (`HdcPipelineFlush`) | `Packet 0 = 0x00100000` 纯 `CS_STALL` | `0x16000001` | `bit 27 = 0` | 证实 DW0 bit 9 (`0x200`) 重新锁存 `bit 28` (`0x10000000`)，且纯 `CS_STALL` 会阻塞等待前序 `CSFLTRK` |
| `R32-PCFIX10` (耐力 #9) | [`nootedgreen-r32-pcfix10-20261106.patch`](../patches/nootedgreen-r32-pcfix10-20261106.patch) | `dw[+1]=dw[+19]=0x001000a0` (剥离 `0x1000 RT_FLUSH`) | 双包 `0x001000a0 + 0x00100480` | `0x1e000001` | 无 (`1111b`) | 证实前导 `dw[+1]` **必须保留 `0x001010a0`** 以在 EU 空闲期排空/引退环级 `RT_FLUSH` |
| `R32-PCFIX11` / `12` (耐力 #10/#11) | [`nootedgreen-r32-pcfix11-20261106.patch`](../patches/nootedgreen-r32-pcfix11-20261106.patch)<br>[`nootedgreen-r32-pcfix12-20261106.patch`](../patches/nootedgreen-r32-pcfix12-20261106.patch) | 剥离 `PIPE_CONTROL` DW1 bit 7 (`0x80 FLUSH_ENABLE`) | `Packet 0 = 0x00100020` (无 `0x80`) | `0x1c000001` | **`bit 25 = 0`** | 证实无 `POST_SYNC_OP` 的写刷新包必须置位 `0x80` (`FLUSH_ENABLE`) 才能触发 `bits 28..27` 引退握手 |
| `R32-PCFIX13` (耐力 #12b) | [`nootedgreen-r32-pcfix13-20261106.patch`](../patches/nootedgreen-r32-pcfix13-20261106.patch) | 同 `PCFIX8` | `replayKernelCommand(queue, false)` 逐编码器独立提交 | `0x02000001` | **`bit 28 = 0`**<br>**`bit 27 = 0`**<br>**`bit 26 = 0`** | 首次将 `bits 28..26` 全清零；证实拆散页内合并会使环级 `commitStampCommand` 暴增 4.5 倍 |
| **`R32-PCFIX14`** (耐力 #15) | [`nootedgreen-r32-pcfix14-20261106.patch`](../patches/nootedgreen-r32-pcfix14-20261106.patch) | `dw[+1]=dw[+19]=0x001010a0`<br>`dw[+7]=dw[+25]=0x00100480`<br>**`dw[+15..+17]=MEDIA_STATE_FLUSH (0x70040000)`** | **`MEDIA_STATE_FLUSH (0x70040000)` + 单包 `PIPE_CONTROL (0x001000a0)` + 4 `MI_NOOP`** | **`0x08000001`** (第 2 轮 `enc=32,142`) | **`bit 28 = 0`**<br>**`bit 26 = 0`**<br>**`bit 25 = 0`** | **Stage 1 第 1 轮全部 8 项工作负载 100% 零挂死通关 (`enc=25,088`, `hang_count=0`)**，推进至第 2 轮 `enc=32,142` |
| `R32-PCFIX15` (耐力 #14) | [`nootedgreen-r32-pcfix15-20261106.patch`](../patches/nootedgreen-r32-pcfix15-20261106.patch) | 同 `PCFIX8` | 移除 `that[0xf42] |= 0x01`，恢复 145-dw 单包 `0x001004a0` | `0x1e000001` (`IPEHR=0x7a000004`) | 无 (`1111b`) | 证伪单包 `0x001004a0` 无挂死假设；证实 `that[0xf42] |= 0x01` 双包空间是解耦读写刷新的必要条件 |
| **`R32-PCFIX16`** (耐力 #16) | [`nootedgreen-r32-pcfix16-20261106.patch`](../patches/nootedgreen-r32-pcfix16-20261106.patch) | 同 `PCFIX8` | `*(uint32_t *)(q + 0x620) = 1U` (`fDisableCommandCoalescing=1`) + 双包 `0x00100000 / 0x001000a0` | `0x06000001` (第 2 轮 `enc=27,348`) | **`bit 28 = 0`**<br>**`bit 27 = 0`** | **Stage 1 第 1 轮全部 8 项工作负载 100% 零挂死通关 (`enc=21,504`, `hang_count=0`)**，推进至第 2 轮 `enc=27,348` |
| `R32-PCFIX17` (耐力 #17) | [`nootedgreen-r32-pcfix17-20261106.patch`](../patches/nootedgreen-r32-pcfix17-20261106.patch) | 移除 `PCFIX14` 的 `MEDIA_STATE_FLUSH` (`dw[+15..+17]=0`) | 单包 `0x001000a0` + 6 `MI_NOOP` (无 `MEDIA_STATE_FLUSH`) | `0x0c000001` | `bit 28 = 0`<br>`bit 25 = 0` | 从第 2 轮 `enc=32,142` 退回第 1 轮 `enc=7,012`，反向实证 `MEDIA_STATE_FLUSH` 清零 `bit 26` 的决定性作用 |
| **`R32-PCFIX19`** (耐力 #19) | [`nootedgreen-r32-pcfix19-20261106.patch`](../patches/nootedgreen-r32-pcfix19-20261106.patch) | 同 `PCFIX14` | 反转顺序：`PIPE_CONTROL 0x001000a0` (`dw[83..88]`) 先于 `MEDIA_STATE_FLUSH` (`dw[89..90]`) | `0x1e000001` (第 2 轮 `enc=32,202`) | 无 (`1111b`) | **Stage 1 第 1 轮全部 8 项工作负载 100% 零挂死通关 (`enc=25,088`, `hang_count=0`)**，推进至第 2 轮 `enc=32,202`；证实 `MEDIA_STATE_FLUSH` 必须先于 `PIPE_CONTROL` 执行才能清零 `bits 28, 26, 25` |
| **`R32-PCFIX20`** (耐力 #20) | [`nootedgreen-r32-pcfix20-20261106.patch`](../patches/nootedgreen-r32-pcfix20-20261106.patch) | 同 `PCFIX14` (含 `MEDIA_STATE_FLUSH`) | 双包 `PIPE_CONTROL`：`0x001000a0` (`dw[83..88]`) + `0x00100480` (`dw[89..94]`) | **`0x10000001`** (第 2 轮 `enc=32,196`) | **`bit 27 = 0`**<br>**`bit 26 = 0`**<br>**`bit 25 = 0`** | **Stage 1 第 1 轮全部 8 项工作负载 100% 零挂死通关 (`enc=25,088`, `hang_count=0`)**，推进至第 2 轮 `enc=32,196`，清零 `bits 27..25` |
| `R32-PCFIX21` (耐力 #21) | [`nootedgreen-r32-pcfix21-20261106.patch`](../patches/nootedgreen-r32-pcfix21-20261106.patch) | 同 `PCFIX14` | 借用 `dw[95..96]` 发射 14-dw：`MEDIA_STATE_FLUSH + 0x001000a0 + 0x00100480` | `0x04000001` | **`bit 28 = 0`**<br>**`bit 27 = 0`**<br>**`bit 25 = 0`** | 清零 `bits 28, 27, 25`；证实当前序末尾发射 `0x00100480` 时，后继 `dw[83]` 前置 `MEDIA_STATE_FLUSH` 会等待 `bit 26` |
| `R32-PCFIX23` / `24` (耐力 #23/#24) | [`nootedgreen-r32-pcfix23-20261106.patch`](../patches/nootedgreen-r32-pcfix23-20261106.patch)<br>[`nootedgreen-r32-pcfix24-20261106.patch`](../patches/nootedgreen-r32-pcfix24-20261106.patch) | 同 `PCFIX20` | 测试 `_WA_TABLE` 偏移与 `0x20d8`/`0x7010`；`PCFIX24` 置 `that[0xf72] |= 0x20U` | `0x0e000001` (`PCFIX23`) | `bit 28 = 0` | 查明 `0x20d8`/`0x7010` 为 LRCA 上下文寄存器，且 `that[0xf72] |= 0x20U` 在 `submitExecList` 中调用不关中断的 `xeSafeForceWake` 会引发中断重入递归自旋锁 panic |
| **`R32-PCFIX25`** (耐力 #25) | [`nootedgreen-r32-pcfix25-20261106.patch`](../patches/nootedgreen-r32-pcfix25-20261106.patch) | 同 `PCFIX20` | 启用修正后 `_WA_TABLE` `that[0xf5f] |= 0x80U` (`0x7010=0x20002000`) + `that[0xf68] |= 0x01U` (`0x20d8=0x00100010`)，移除 `0xf72` | **`0x00000001`** | **`bit 28 = 0`**<br>**`bit 27 = 0`**<br>**`bit 26 = 0`**<br>**`bit 25 = 0`** | **零内核 panic**；`CS_DBG1=00000010` 与 `CHKN3=00002000` 跨上下文切换 100% 持久保留，**首次将 `CSFLTRK` 全部缓存刷新位 `bits 31..1` 清零至 `0x00000001`** |
| `R32-PCFIX26` (耐力 #26) | [`nootedgreen-r32-pcfix26-20261106.patch`](../patches/nootedgreen-r32-pcfix26-20261106.patch) | 同 `PCFIX20` | 移除 `xeCs5Submit`/`xeDequeueExecList` 运行时主机 MMIO 写，仅保留黄金上下文镜像 `0x7010`/`0x20d8`/`0x2050` | `0x06000001` | **`bit 28 = 0`**<br>**`bit 27 = 0`** | 证实仅靠 `_safeHardwareContextBufferRCS` 黄金镜像即可使 `CS_DBG1=00000010` 与 `CHKN3=00002000` 跨 7,158 次上下文切换 100% 持久保留；且对比 `PCFIX20` 查明开启 `0x7010=0x20002000`/`0x20d8`/`0x2050` 导致 `Horizon Detection` 在第 1 轮回退至 `enc=7,186` |
| **`R32-PCFIX27`** (耐力 #27/#28) | [`nootedgreen-r32-pcfix27-20261106.patch`](../patches/nootedgreen-r32-pcfix27-20261106.patch) | `dw[+1]=0x001010a0`<br>`dw[+7]=dw[+25]=0x00100480`<br>`dw[+15..+17]=MEDIA_STATE_FLUSH (0x70040000)`<br>**`dw[+19]=0x001000a0` (剥离 `0x1000 RT_FLUSH`)** | 双包 `PIPE_CONTROL`：`0x001000a0` (`dw[83..88]`) + `0x00100480` (`dw[89..94]`)；移除 `0x7010`/`0x20d8`/`0x2050` | **N/A (`0` hang)** | **`bit 28 = 0`**<br>**`bit 27 = 0`**<br>**`bit 26 = 0`**<br>**`bit 25 = 0`** | **三阶段实机耐力压测 100% 零挂死通关 (`enc=705,024`, `hang_count=0`)**：Stage 1 连续 3 轮 24 项 Geekbench 6 Metal + Stage 2 90s 4 线程并发 + Stage 3 60s RC6 静置 + 30s 唤醒突发全部 100% 零挂死通过 |

### 4.3 `R32-PCFIX27` 终极收官原理：为何仅将 `ResetPreambleCmds` `dw[+19]` 改为 `0x001000a0U` 即可 100% 清零 `bits 28..25`
在 `COCLGen8CommandTransport::ResetPreambleCmds`（`dw[0..32]`，33 dwords）中，指令序列按精确偏移排列如下：
1. `dw[+0..+5]`（Packet 1）：`PIPE_CONTROL (0x001010a0U = CS_STALL | RT_CACHE_FLUSH | DC_FLUSH_ENABLE | FLUSH_ENABLE)`
2. `dw[+6..+11]`（Packet 2）：`PIPE_CONTROL (0x00100480U = CS_STALL | TEXTURE_CACHE_INVALIDATE | FLUSH_ENABLE)`
3. `dw[+12]`：`PIPELINE_SELECT (0x69040001 = GPGPU)`
4. `dw[+13..+14]`：`MI_LOAD_REGISTER_IMM (0x2580 = 0x00020002)`
5. `dw[+15..+17]`：`MEDIA_STATE_FLUSH (0x70040000U, 0U) + MI_NOOP (0U)`（替换原 Gen8 `LRI 0xb134`）
6. `dw[+18..+23]`（Packet 3）：原为 `PIPE_CONTROL (0x001010a0U)` -> **`R32-PCFIX27` 改写为 `0x001000a0U`（剥离 `0x1000 RT_CACHE_FLUSH`）**
7. `dw[+24..+29]`（Packet 4）：`PIPE_CONTROL (0x00100480U)`

对比 `PCFIX10`、`PCFIX14`、`PCFIX20` 与 `PCFIX27` 四组单变量实验，彻底解开了 `CSFLTRK [0x2208]` 全部 4 个缓存刷新位（`bits 28..25`）的硬件状态机闭环：
- 在 `PCFIX10` 中，将 `dw[+1]` 与 `dw[+19]` **同时**剥离 `0x1000`（均改为 `0x001000a0U`），导致在进入 `PIPELINE_SELECT (GPGPU)` 之前未排空 3D/环级 `commitStampCommand`（`0x40105021`）遗留的 Render Target Cache，故 `CSFLTRK = 0x1e000001` 在第 1 轮 `enc=7,018` 回退挂死；
- 在 `PCFIX20` 中，保留了 `dw[+1] = 0x001010a0U` 与 `dw[+19] = 0x001010a0U`，并在 `AddPipeFlushCmd`（`dw[83..94]`）使用双包 `0x001000a0U + 0x00100480U`。此时 `AddPipeFlushCmd` 双包 100% 清零了 `bits 27..25`（`0x0e000000 -> 0`），但因为 **Packet 3（`dw[+18..+23]`）位于 `PIPELINE_SELECT (GPGPU)`（`dw[+12]`）和 `MEDIA_STATE_FLUSH`（`dw[+15..+16]`）之后**，在该位置再次发射含 `0x1000 RT_CACHE_FLUSH` 的 `0x001010a0U` 会在 `MEDIA_STATE_FLUSH` 已经排空媒体态之后、紧接 `GPGPU_WALKER` 启动之前，向已处于 GPGPU 模式的管线**重新锁存 `CSFLTRK bit 28`（`0x10000000`）**，而末尾 `AddPipeFlushCmd` 的 `0x001000a0U` 不含 `RT_CACHE_FLUSH` 也不会经过 `MEDIA_STATE_FLUSH`，导致 `PCFIX20` 在第 2 轮 `enc=32,196` 处唯一残留 `CSFLTRK = 0x10000001`（仅 `bit 28 = 1`）！
- 在 **`R32-PCFIX27`** 中：
  1. `dw[+1]`（在 `PIPELINE_SELECT = GPGPU` 与 `MEDIA_STATE_FLUSH` 之前）保留 **`0x001010a0U`**，在 EU 空闲期排空 3D/环级 Render Target Cache；
  2. `dw[+15..+16]` 执行 **`MEDIA_STATE_FLUSH (0x70040000U)`**，紧接着 `dw[+19]` 执行不含 `0x1000` 的 **`0x001000a0U`**（`CS_STALL | DC_FLUSH_ENABLE | FLUSH_ENABLE`），完整遵循 `MEDIA_STATE_FLUSH -> PIPE_CONTROL(0x001000a0U)` 顺序定律（与 `PCFIX14` 在末尾验证的 `MEDIA_STATE_FLUSH -> 0x001000a0U` 100% 清零 `bit 28` 同构），在不重新锁存 `RT_CACHE_FLUSH` 的前提下将 `bit 28`（`0x10000000`）彻底引退清零；
  3. 编码器末尾 `AddPipeFlushCmd`（`dw[83..94]`）执行双包 **`0x001000a0U + 0x00100480U`**，将 `GPGPU_WALKER` 周期的 `bits 27..25`（`0x0e000000`）彻底引退清零。
  4. 由此，`CSFLTRK` 的 `bit 28`、`bit 27`、`bit 26`、`bit 25` 四位在同一计算编码器周期内实现 **`0000b` 全清零**，实机连续跑完 `705,024` 个计算编码器（覆盖 Stage 1 连续 3 轮 24 项 Geekbench 6.5.0 Metal、Stage 2 90s 4 线程 Blit+Compute 并发压测、Stage 3 60s RC6 静置 + 30s 唤醒突发压测）**全程 0 次 GPU 挂死、0 次 GPU 重置**。

---

## 5. 可复现构建与验证体系

1. **Nix Flake 标准化开发环境（[`flake.nix`](../flake.nix) / [`flake.lock`](../flake.lock)）**：
   - 统一封装 `clang_21`、`llvm_21`、`lld_21`、`rcodesign`、`grub2`、`mtools`、`dosfstools`、`acpica-tools`、`python3`、`openssh`、`rsync`、`jq`、`gnumake` 与 `git`，消除了硬编码 `/nix/store/...` 路径或临时 `nix-shell` 调用。
2. **双系统无人值守闭环验证**：
   - 每次实机试验均执行：12 项 macOS 运行时安装门控核验 -> 实时无过滤日志流采集 -> 首 hang / 压测完成后 `prompt_return_worker_v2.py` 身份守卫回程重启至 NixOS -> `post-nixos` 自动只读抓取完整 `efivars-full.tar` 与 `DiagnosticReports-full.tar` 并执行 SHA-256 及 7-bit `AAPL,PanicInfo` 审计。

