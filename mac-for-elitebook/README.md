# HP Elite Dragonfly G2 → macOS Tahoe (26.6.2 / 25G83)

针对 **HP Elite Dragonfly G2**（主板号 `8716`，BIOS `T90 01.25.00`，Intel Core i5-1135G7 / Tiger Lake-UP3 `0x8C`，**Intel Iris Xe Graphics G7 `8086:9a49` B0 80 EU / 5 DualSubslices**，16 GiB LPDDR4x-4267）运行原生 Intel 版 **macOS 26 Tahoe（`26.6.2` / `25G83`，Darwin `25.6.0`）** 的实机内核与图形驱动适配工程。

---

## 最终 / 当前实机成果总览

1. **完整 macOS 26.6.2 (`25G83`) 系统安装与内置 NVMe SSD 独立引导**：
   - 已将完整 macOS 26.6.2（`25G83`）安装至内置 Micron 2210 NVMe SSD，并在内置 EFI 分区（`/boot/EFI/OC`）部署经实机闭环验证的 OpenCore 1.0.8 引导与自定义交叉编译签名的 `NootedGreen.kext`。
   - 内屏 eDP（IVO8596 `X133NVFF R0`，`1920×1080@60Hz`，pipe A / DDI A / PHY A）、Wi-Fi（`itlwm` AX201）、蓝牙（含蓝牙音频）、I²C 触控板（Synaptics `06cb:cd74`）、PS/2 键盘、电池状态、RGB 摄像头与 PCH USB 均已在完整系统中正常工作。
2. **Iris Xe 80 EU Metal 硬件加速与三阶段实机稳定性及耐力压测 100% 零挂死通关（`R32-PCFIX27-PMAPFIX`）**：
   - 在实机上一次性 **100% 跑通全部三阶段 GPU 稳定性与耐力测试计划**（[`Trial 27` `trial-r32-pcfix27-endurance-20261106` 与 `Trial 28` `trial-r32-pcfix27-full3stage-20261106`](docs/repair32-gpu-stability-and-pmapfix-20261106.md)，对应补丁 [`patches/nootedgreen-r32-pcfix27-20261106.patch`](patches/nootedgreen-r32-pcfix27-20261106.patch)），单次启动连续净化并执行 **705,024 个 Metal 计算编码器**，全程 **0 次 `GPU hang:`、0 次 `GPURestart`、0 次内核 panic**：
     - **Stage 1（连续 3 轮完整 Geekbench 6.5.0 `--gpu Metal` 共 24 项计算工作负载）**：`Background Blur`、`Face Detection`、`Horizon Detection`、`Edge Detection`、`Gaussian Blur`、`Feature Matching`、`Stereo Matching`、`Particle Physics` 连续 3 轮 24/24 项工作负载 100% 完成（`enc=25,088 -> 50,176 -> 75,264`，`rc=0`，`hang_count=0`，连续两次独立实机试验共 6 轮 48 项工作负载 100% 零挂死复现）；
     - **Stage 2（90 秒 4 线程 `metal-concurrent-stress` Blit+Compute 并发压测 + `WindowServer` 实时合成）**：完成 `67,430` 个并发批次、`404,570` 个并发编码器（`errors=0`，`avg_ms=2.264`，`max_ms=12.746`），累计净化计算编码器推进至 **`enc#547,328`**（`hang_count=0`）；
     - **Stage 3（60 秒 RC6 深度电源门控静置 + 30 秒 4 线程 Metal 唤醒突发压测）**：60 秒 RC6 静置零异常，30 秒唤醒突发压测完成 `22,513` 个批次、`135,068` 个编码器（`errors=0`，`avg_ms=2.255`，`max_ms=9.398`），累计净化计算编码器达 **`enc#705,024`**（`pre=705,264, pf=610,384, rf=0, prblk=228,740, def=378,784, wsk=0`，`hang_count=0`）。
3. **RCS 单端口无抢占 Execlist 调度与 GPU Reset 100% 无损自愈**：
   - 100% 消除了 `WindowServer`（Context `0xa0`）与 Metal 计算上下文（Context `0x5c0` / `0xcc0`）并发时的宿主软件 mid-batch 抢占、Port 0 覆盖（`ExecListQueueFull = 0x4000219a`）、双端口 `Port1`（`EL[1]`）填充、同上下文 `LITE_RESTORE`（`0x8002`）及 `EXECLIST_STATUS` `0x3098 -> 0x40002098`（`NO ACTIVE ELEMENTS`）硬件仲裁冻结。
   - 在极端耐力对照试验触发 Watchdog 时，`XeNG GPUREC: reset RCS ret=1` 实现 **100% 干净自愈恢复**（无需重启系统即可继续高速执行后续数千个计算编码器）。
4. **内置 SSD 引导长稳运行零 Panic（根治 `pmap_recycle_page`）**：
   - 定位并隔离了内置硬盘链式引导遗留的物理内存脏页窗口 `0x101000000..0x101400000`（`4 MiB`），彻底消除了内置盘启动后约 6 分 34 秒必现的 `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511` 内核崩溃；在连续 **28 轮**实机高负载耐力测试（`Trials 1–28`）中 **0 次 `pmap_recycle_page` 崩溃**。
5. **可复现 Nix Flake 工具链与双系统无人值守闭环验证体系**：
   - 基于 [`flake.nix`](flake.nix) 与 [`flake.lock`](flake.lock) 封装完整 LLVM 21 / `ld64` / `rcodesign` / `grub2` / `mtools` 交叉构建环境，配合 NixOS ↔ macOS 身份守卫自动回程、7-bit `AAPL,PanicInfo` 无损往返解码与硬件寄存器快照采集。

---

## 四大核心技术修复详解

完整逆向工程证据、寄存器转储与 **28 轮**对照实验数据（`Trials 1–28`）详见 **[`docs/repair32-gpu-stability-and-pmapfix-20261106.md`](docs/repair32-gpu-stability-and-pmapfix-20261106.md)**。

### 修复一：Tiger Lake (Gen12LP) RCS Execlist 提交队列竞争、跨上下文抢占与无损单端口调度（`ELSQWAIT` + `PCFIX5` + `PCFIX6`）

- **根因定位**：
  1. **ELSQ 门铃重入竞争（`[0x2234] = 0x4000219a` `ExecListQueueFull`）**：`AppleIntelTGLGraphics` 在向 RCS 写 `ELSQ` 并敲击门铃 `0x2550 = 1` 时，若 `GFXREG_RCS_EXECLIST_STATUS [0x2234]` bit 30（`0x40000000`）仍置位，仅 39 微秒后的高频提交就会导致 `[0x2234]` 变为 `0x4000219a`（`ExecListQueueFull`），触发硬件在 `GPGPU_WALKER`（`[0x2148] BB_PREEMPT_ADDR = 0x4ecee114`）中途强制抢占。
  2. **软件 mid-batch 抢占与双端口 `0x3098 -> 0x40002098`（`NO ACTIVE ELEMENTS`）冻结**：当 `WindowServer`（Context `0xa0`）与 Geekbench Metal（Context `0x5c0` / `0xcc0`）并发时，即使关闭软件 mid-batch 抢占（`BB_PREEMPT_ADDR = 0`），只要 `evalWorkQueues` 在 `Port0=0x5c0` 活动期间（`[0x2234] = 0x00003098`）装填双端口 `Port0=0x5c0, Port1=0xa0` 并敲门铃，硬件在 **4 微秒**内即从 `0x00003098` 跌落为 **`0x40002098`**（`CurrentActiveElementStatus = NO ACTIVE ELEMENTS`），产生 `LITE_RESTORE`（`0x8002`）并触发 `Port0 -> Port1` 硬件元素切换（`LastContextSwitchReason = 0x104 ELEMENT_SWITCH | WAIT_ON_SCANLINE`），隐式注入上下文保存刷新锁死于 `CSFLTRK = 0x1c000001`。
- **修复机制**：
  - **无条件 `elsqWait`**（[`patches/nootedgreen-r32-elsqwait-20261105.patch`](patches/nootedgreen-r32-elsqwait-20261105.patch)）：在 `xePrepSubmit` 与 `xeCs5Submit` 中对任意 `([0x2234] & 0x40000000U) != 0` 实施轮询排空等待；
  - **线程组抢占粒度与每上下文控制**：编程 `GFXREG_CS_CHICKEN1 [0x2580] = 0x00020002`（`WaDisableGPGPUMidThreadPreemption`，将 GPGPU 抢占从 mid-thread 改为线程组级 `01b`）并在引擎启动与复位列表中清零 `0x20e0` bit 14（`0x40000000`）；
  - **阻断宿主软件 mid-batch 抢占**（[`patches/nootedgreen-r32-pcfix5-20261105.patch`](patches/nootedgreen-r32-pcfix5-20261105.patch)）：挂钩 `IGScheduler5::updateOptions`（`0x385e0`）、`allowPreemption`（`0x3d9a6`）、`isPreemptionAllowed`（`0x3d9d2`）清零 `cs[0x1c50]`、`cs[0x1c5d]` 与 `sched[0x0c] bit 2`；
  - **无损单端口 RCS 策略 `HP-SINGLEPORT-RCS`**（[`patches/nootedgreen-r32-pcfix6-20261105.patch`](patches/nootedgreen-r32-pcfix6-20261105.patch)）：挂钩 `dequeueExecList`（`0x3b3b6`）在 `Port0` 活动或提交在途（`el[cur][0] != 0 || !cs[0x1c3c]`）时延迟出队（由 `ACTIVE_TO_IDLE` CSB 中断自动触发重出队，零饥饿风险），并通过 `evalWorkQueues`（`0x3d5d0` `f_rcs1_hp` 将第 2 个上下文未消费的 ring 读指针 `%r12` 写回 `workQueue+0x4040`）与 `evalWaitQueue`（`0x3b971` `f_wait1_hp`）阻止填充 `Port1`（`EL[1]`），实现全程 `ELR1 = 0`、`0` 次 `LITE_RESTORE`、`0` 次 `0x40002098` 冻结，以及 `XeNG GPUREC: reset RCS ret=1` 100% 干净恢复。

### 修复二：`AppleIntelTGLGraphicsMTLDriver`（`COCLGen8CommandTransport`）Gen8 遗留计算编码器就地净化与 `CSFLTRK [0x2208]` 刷新跟踪器解耦（`PCFIX2` ~ `PCFIX27`）

- **根因定位**：
  通过 `rea`（Ghidra `12.1.4`）反编译 `IntelMTLComputeFunctions::execute`（`0x6bf20`）、`ResetPreambleCmds`（`0x378e8`）、`BuildPreambleCmds`（`0x38c48`）与 `AddPipeFlushCmd`（`0x37a0e`），查明 macOS Tahoe 的 Metal 计算命令传输层直接沿用了 Gen8 `COCLGen8CommandTransport`。在同一 4 KB 页内合并至多 5 个 151-dword 子分配计算编码器（`endOffDw = 95, totalDw = 151`，编码器 `k=0..4` 位于 `&page[151 * k]`，前一编码器末尾 `dw[150]` 的 `MI_BATCH_BUFFER_END` `0x05000000` 被清零为 `MI_NOOP`）时，存在四处硬件级冲突：
  1. `ResetPreambleCmds`（`dw[0..32]`）发射了两个未置 `CS_STALL`（`0x00100000`）的 `PIPE_CONTROL 0x00000480`（`TEXTURE_CACHE_INVALIDATE`），以及 Gen8 专属的 `MI_LOAD_REGISTER_IMM 0xb134`（`dw[15..17]`，Gen8 `L3ALLOC`，在 Gen12LP Tiger Lake 上破坏 L3/HDC 分配）；且在 `dw[+12]` `PIPELINE_SELECT = GPGPU`（`0x69040001`）之后，Packet 3（`dw[+18..+23]`）再次发射含 `0x1000 RT_CACHE_FLUSH` 的 `0x001010a0U`，在 GPGPU 管线模式下重新锁存 `CSFLTRK bit 28`（`0x10000000`）；
  2. 多个计算编码器串联时均走 `0xac == 1` 慢路径而从不发射 `MEDIA_STATE_FLUSH`（`0x70040000`）；
  3. 编码器末尾 `AddPipeFlushCmd`（`dw[83..94]`）发射了 `7a000004 001044a0 <m_pScratchPage+0x10> 0 0 0`，在同一 `PIPE_CONTROL` 包内同时混用虚拟 `POST_SYNC_OP = Write Immediate`（`0x4000`）、读缓存失效 `TEXTURE_CACHE_INVALIDATE`（`0x400`）与写缓存刷新 `DC_FLUSH_ENABLE`（`0x20`）。
  4. `HP-SLICE` 硬件子切片遥测证实：挂死瞬间全部 5 个活动子切片（80 个 EU）100% 空闲完成（`SC_INSTDONE = 0xffffffff`、`ROW_INSTDONE[0..4] = 0xffffffff`、`SAMPLER_INSTDONE[0..4] = 0xffffffff`、`FAULT_REG = 0x00000000`），死锁 100% 发生在前端 Command Streamer Flush Tracker（`CSFLFLAG [0x2204] = 0x50000000`、`CSFLTRK [0x2208]`）。
- **修复机制**：
  - 在 `nativeRowPrefix` 写入 `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`；
  - 启用 `IntelAccelerator+0xf42 bit 0`（`_WA_TABLE+0x14 bit 0`）使 `AddPipeFlushCmd` 分配 12-dword 双包空间（`endOffDw = 95, totalDw = 151`）；在 `PCFIX25` / `PCFIX26` 中验证了通过 `that[0xf5f] |= 0x80U`（`0x7010 = 0x20002000`）与 `that[0xf68] |= 0x01U`（`0x20d8 = 0x00100010`）将 `CS_DBG1` 与 `CHKN3` 捕获进黄金上下文镜像 `_safeHardwareContextBufferRCS` 实现跨上下文持久化的硬件机制，并在最终版 **`PCFIX27`**（[`patches/nootedgreen-r32-pcfix27-20261106.patch`](patches/nootedgreen-r32-pcfix27-20261106.patch)）中回退会产生副作用的 `0x7010`/`0x20d8`/`0x2050`，在干净 `PCFIX20` 基底上完成 `CSFLTRK bits 28..25 = 0000b` 终极收官；
  - 挂钩 `IntelMTLComputeFunctions::execute`（仅针对计算编码器提交 token `eToken == 0x40001U` 调用 `hpSanitizeComputeEncoder`）：
    - **前导净化（`ResetPreambleCmds` `dw[0..32]`，`PCFIX27` 决定性修复）**：保留位于 `PIPELINE_SELECT = GPGPU`（`dw[+12]`）之前的 Packet 1 `dw[+1] = 0x001010a0U`（`CS_STALL | RT_CACHE_FLUSH | DC_FLUSH_ENABLE | FLUSH_ENABLE`，在 EU 空闲期排空并引退 3D/环级 `commitStampCommand` `0x40105021` 遗留的 Render Target Cache），将 `dw[+7] = dw[+25]` 补齐 `CS_STALL` 为 `0x00100480U`（不含 `0x0800 STATE_CACHE_INVALIDATE`），将 `dw[+15..+17]`（原 Gen8 `LRI 0xb134`）就地替换为 `MEDIA_STATE_FLUSH`（`0x70040000U, 0U`）+ `MI_NOOP`（`0U`），并将紧随 `MEDIA_STATE_FLUSH` 之后的 **Packet 3（`dw[+19]`）从 `0x001010a0U` 改写为 `0x001000a0U`**（剥离 GPGPU 模式下的 `0x1000 RT_CACHE_FLUSH` 重新锁存，严格遵循 `MEDIA_STATE_FLUSH -> PIPE_CONTROL(0x001000a0U)` 顺序定律使 `CSFLTRK bit 28` 引退清零为 `0`）；
    - **尾声净化（`AddPipeFlushCmd` `dw[83..94]`）**：剥离 `0x4000`（虚拟 Scratch 页 `POST_SYNC_OP` 写立即数）并将读写刷新解耦为写刷新 `Packet 0 = 0x001000a0U`（`dw[83..88]`）+ 读失效 `Packet 1 = 0x00100480U`（`dw[89..94]`）双包拆分，将 `GPGPU_WALKER` 周期的 `CSFLTRK bits 27..25` 彻底引退清零，最终实现同一编码器周期内 **`CSFLTRK bits 28..25 = 0000b` 全清零**，连续跑通 **`705,024` 个计算编码器** 零挂死。

| 代表性版本 | 补丁文件 | `ResetPreambleCmds` (`dw[0..32]`) | `AddPipeFlushCmd` (`dw[83..94]`) 及硬件 WA | `CSFLTRK [0x2208]` | 实机验证结果 |
| --- | --- | --- | --- | --- | --- |
| `R32-PCFIX2` | [`nootedgreen-r32-pcfix2-20261105.patch`](patches/nootedgreen-r32-pcfix2-20261105.patch) | `0x001010a0` + `0x00100480` + `LRI 0xb134 -> 0` | 单包 `0x001004a0`（剥离 `0x4000`） | N/A (`0` hang) | **单轮 Geekbench 6.5.0 Metal 全部 8 项工作负载 100% 零挂死通关**（`enc=25,088`） |
| `R32-PCFIX8` | [`nootedgreen-r32-pcfix8-20261105.patch`](patches/nootedgreen-r32-pcfix8-20261105.patch) | `0x001010a0` + `0x00100480` + `LRI 0xb134 -> 0` | 双包 `0x001000a0 + 0x00100480` + 单端口 RCS | `0x06000001` (`bits 28..27 = 0`) | 100% 跑通 `Horizon Detection`，推进至 `Edge Detection`（`enc=12,792`） |
| `R32-PCFIX13` | [`nootedgreen-r32-pcfix13-20261106.patch`](patches/nootedgreen-r32-pcfix13-20261106.patch) | 同 `PCFIX8` | `replayKernelCommand` 逐编码器独立提交 | `0x02000001` (`bits 28..26 = 0`) | 首次清零 `bits 28..26`；证实拆散页内合并使环级 `commitStampCommand` 暴增 4.5× |
| **`R32-PCFIX14`** | [`nootedgreen-r32-pcfix14-20261106.patch`](patches/nootedgreen-r32-pcfix14-20261106.patch) | 注入 `MEDIA_STATE_FLUSH` (`0x70040000`) | `MEDIA_STATE_FLUSH (0x70040000)` + 单包 `0x001000a0` | `0x08000001` (`bits 28,26,25 = 0`) | **耐力 Stage 1 第 1 轮 8 项全通（`enc=25,088`, `hang=0`）**，推进至第 2 轮 `enc=32,142` |
| **`R32-PCFIX16`** | [`nootedgreen-r32-pcfix16-20261106.patch`](patches/nootedgreen-r32-pcfix16-20261106.patch) | 同 `PCFIX8` | `q+0x620 = 1` + 双包 `0x00100000 / 0x001000a0` | `0x06000001` (`bits 28..27 = 0`) | **耐力 Stage 1 第 1 轮 8 项全通（`enc=21,504`, `hang=0`）**，推进至第 2 轮 `enc=27,348` |
| **`R32-PCFIX19`** | [`nootedgreen-r32-pcfix19-20261106.patch`](patches/nootedgreen-r32-pcfix19-20261106.patch) | 同 `PCFIX14` | `0x001000a0` 先于 `MEDIA_STATE_FLUSH` | `0x1e000001` | **耐力 Stage 1 第 1 轮 8 项全通（`enc=25,088`, `hang=0`）**，推进至第 2 轮 `enc=32,202` |
| **`R32-PCFIX20`** | [`nootedgreen-r32-pcfix20-20261106.patch`](patches/nootedgreen-r32-pcfix20-20261106.patch) | 同 `PCFIX14`（含 `MEDIA_STATE_FLUSH`） | 双包 `0x001000a0 + 0x00100480` | `0x10000001` (`bits 27..25 = 0`) | **耐力 Stage 1 第 1 轮 8 项全通（`enc=25,088`, `hang=0`）**，推进至第 2 轮 `enc=32,196` |
| **`R32-PCFIX25`** | [`nootedgreen-r32-pcfix25-20261106.patch`](patches/nootedgreen-r32-pcfix25-20261106.patch) | 同 `PCFIX20` | 启用 `_WA_TABLE` `0xf5f\|=0x80` (`0x7010`) + `0xf68\|=0x01` (`0x20d8`) | **`0x00000001`** (**`bits 31..1 = 0`**) | `CS_DBG1=00000010` 与 `CHKN3=00002000` 跨上下文持久保留，**全部缓存跟踪位清零** |
| `R32-PCFIX26` | [`nootedgreen-r32-pcfix26-20261106.patch`](patches/nootedgreen-r32-pcfix26-20261106.patch) | 同 `PCFIX20` | 移除运行时主机 MMIO 写，仅保留 `_safeHardwareContextBufferRCS` 黄金镜像 | `0x06000001` (`bits 28..27 = 0`) | 证实黄金上下文镜像跨 7,158 次切换持久保留 `CS_DBG1`/`CHKN3`；隔离出 `0x7010`/`0x20d8`/`0x2050` 回退副作用 |
| **`R32-PCFIX27`** | [`nootedgreen-r32-pcfix27-20261106.patch`](patches/nootedgreen-r32-pcfix27-20261106.patch) | `dw[+1]=0x001010a0` + `MEDIA_STATE_FLUSH` + **`dw[+19]=0x001000a0`（剥离 `0x1000`）** | 双包 `0x001000a0 + 0x00100480`（回退 `0x7010`/`0x20d8`/`0x2050`） | **N/A (`0` hang, `bits 28..25 = 0000b`)** | **三阶段实机耐力压测 100% 零挂死通关（`enc=705,024`, `hang=0`）**：连续 3 轮 24 项 Geekbench 6 Metal + 90s 并发 + 60s RC6 + 30s 唤醒突发全通 |

### 修复三：内置 NVMe SSD 启动 `pmap_recycle_page: page 0x101310000` 内核 Panic 根治（`PMAPFIX`）

- **根因定位**：从内置硬盘 `/boot/EFI/OC`（经 `systemd-boot` 链式加载）启动进入 macOS 后约 `252s ~ 394s`（6 分 34 秒），XNU VM 页面回收器在 `_vm_page_free_list -> pmap_recycle_page` 必现断言崩溃 `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511`。通过离线解码 EFI NVRAM `AAPL,PanicInfo0000..0003` 确认历次崩溃页（`0x101304000`、`0x10130e000`、`0x101310000`、`0x101311000`、`0x101313000`、`0x10131c000`）100% 集中在同一 **128 KiB 物理内存窗口 `0x101304000..0x10131c000`**（固件/链式引导残留 DMA/页表引用），且 `debug=0x100100` 中的 `0x100`（`DB_HALT`）使内核在锁屏关背光后停留在 `_kdp_i386_trap`，外在表现为“睡眠黑屏死机”。
- **修复机制**：在 OpenCore `config.plist` 的 `UEFI -> ReservedMemory` 中保留 `Address = 0x101000000 (4311744512), Size = 0x00400000 (4 MiB), Type = Reserved`，并将 `boot-args` 的 `debug=0x100100` 调整为 `debug=0x100000`。实测连续 **28 轮**高强度压测中 **`pmap_recycle_page` 崩溃发生率为 0%**。

### 修复四：显示、网络、输入外设与可复现工程基础设施适配

- **显示与 Framebuffer**：Tiger Lake `8086:9a49` eDP pipe A / DDI A / PHY A 内屏 `1920×1080@60Hz` 原生分辨率点亮、`DevirtualiseMmio` 与 `slide=0` 内存布局适配（详见 [`docs/display-analysis.md`](docs/display-analysis.md) 与 [`docs/runtime-display-notes.md`](docs/runtime-display-notes.md)）；
- **网络与远程诊断**：固定 `itlwm` Wi-Fi 驱动支持 Intel AX201，配合内置数据卷 `/hpdiag` 专用 SSH/SFTP 通道实现无人值守远程诊断（详见 [`docs/recovery-network.md`](docs/recovery-network.md)）；
- **输入与外设**：Synaptics `06cb:cd74`（I²C 触控板）与 Wacom `056a:4924`（I²C 触屏与手写笔）`VoodooI2C` / `VoodooI2CHID` 适配，以及外设现状梳理（详见 [`docs/peripheral-adaptation-status-20261104.md`](docs/peripheral-adaptation-status-20261104.md) 与 [`docs/peripheral-driver-research-20261104.md`](docs/peripheral-driver-research-20261104.md)）；
- **Nix Flake 可复现构建环境**：仓库根目录 [`flake.nix`](flake.nix) 与 [`flake.lock`](flake.lock) 提供标准化 `nix develop` 环境，彻底消除硬编码 `/nix/store` 路径。

---

## 入口

- **[新会话续接 / 迁移必读](docs/continuation.md)**；当前状态见 [`configs/install-preparation.json`](configs/install-preparation.json)，追加事件历史见 [`manifests/experiment-history.json`](manifests/experiment-history.json)。
- **[2026-11-06 Iris Xe 80 EU Metal 加速、单端口 RCS、计算编码器净化与 PMAPFIX 完整技术总结](docs/repair32-gpu-stability-and-pmapfix-20261106.md)**（对应源码补丁：[`patches/nootedgreen-r32-pcfix14-20261106.patch`](patches/nootedgreen-r32-pcfix14-20261106.patch)、[`patches/nootedgreen-r32-pcfix20-20261106.patch`](patches/nootedgreen-r32-pcfix20-20261106.patch)、[`patches/nootedgreen-r32-pcfix25-20261106.patch`](patches/nootedgreen-r32-pcfix25-20261106.patch)、[`patches/nootedgreen-r32-pcfix26-20261106.patch`](patches/nootedgreen-r32-pcfix26-20261106.patch)、[`patches/nootedgreen-r32-pcfix27-20261106.patch`](patches/nootedgreen-r32-pcfix27-20261106.patch)）
- **[2026-11-05 Geekbench 6 Metal 全部 8 项工作负载通关记录](docs/repair32-pcfix2-20261105.md)**（对应源码补丁：[`patches/nootedgreen-r32-pcfix2-20261105.patch`](patches/nootedgreen-r32-pcfix2-20261105.patch)）
- [2026-11-05 Horizon Detection 突破记录](docs/repair32-elsqwait-20261105.md)（对应源码补丁：[`patches/nootedgreen-r32-elsqwait-20261105.patch`](patches/nootedgreen-r32-elsqwait-20261105.patch)）
- [2026-11-05 R32 抢占与读回调查记录](docs/repair32-preemption-investigation-20261105.md)
- [2026-11-04 GPU 证据审查与无人值守回程设计](docs/gpu-evidence-review-20261104.md)
- [2026-11-04 外设适配现状分析](docs/peripheral-adaptation-status-20261104.md) 与 [外设驱动调研](docs/peripheral-driver-research-20261104.md)
- [分阶段适配计划](docs/roadmap.md)
- [实机结论与待采集项](docs/hardware.md)
- [DVMT 与内屏运行态补充](docs/runtime-display-notes.md)
- [VBT 解码与 HP 显示差异](docs/display-analysis.md)
- [Framebuffer 构建就绪度](docs/framebuffer-build-readiness.md)
- [不启动 macOS 的图形组件验证](docs/nonboot-graphics-validation.md)
- [非启动验证范围与受控 ACPI 实验](docs/nonboot-component-survey.md)
- [无安装虚拟机、UEFI driver 与 Recovery 验证](docs/nonboot-vm-validation.md)
- [Recovery 下载修复、真实 XNU 与 kext 加载验证](docs/recovery-kext-validation.md)
- [实机首启失败、完整安装输入与重启后交接](docs/install-handoff.md)
- [Recovery 已启动后的 I2C / USB 输入适配](docs/input-recovery.md)
- [Recovery 自动硬件观察与 USB 归档](docs/recovery-observer.md)
- [Recovery Wi-Fi / SSH 候选与内置诊断入口](docs/recovery-network.md)
- [无 VM 的完整离线安装 app 数据映像](docs/offline-installer-inputs.md)
- [离线 HID descriptor 解析验证](docs/nonboot-hid-validation.md)
- [HP ACPI 部署前审阅](docs/acpi-preflight.md)
- [脱敏硬件清单](hardware/elite-dragonfly-g2.json)
- [本机 Lexar / Ventoy 介质记录](hardware/development-usb.json)
- [图形源码与移植边界](docs/graphics-research.md)
- [周边驱动路线](docs/peripherals.md)
- [本机构建环境](docs/build-environment.md)
- [VESA 离线原型与静态校验](docs/vesa-prototype.md)
- [验证记录](docs/verification.md)
- `manifests/`：第三方来源、版本、提交与许可记录。

## 固定约束

远端只做在线、只读采集；未经明确许可不关机、不重启、不休眠，不写 BIOS、NVRAM 或固件设置。本机 Lexar U 盘已有 Ventoy，保留其文件及分区。编译、反编译和静态检查全部在本地开发机通过 `nix develop` 执行。

## 已建立的实机基线

| 项目 | 在线核实与实机运行结果 |
| --- | --- |
| 机器 / 固件 | HP Elite Dragonfly G2，板号 8716，T90 01.25.00 |
| CPU / 内存 | i5-1135G7，4C/8T；16GiB 板载 LPDDR4x，SMBIOS 报告 4267MT/s |
| GPU | Iris Xe `8086:9a49`，B0，80EU / 5 DualSubslice；**macOS 26.6.2 Metal 硬件加速已启用并 100% 跑通三阶段实机耐力压测（连续 3 轮 24 项 Geekbench 6.5.0 Metal + 90s 4 线程并发 + 60s RC6 静置 + 30s 唤醒突发，共 `705,024` 个计算编码器 0 挂死）** |
| 内屏 | IVO8596，`X133NVFF R0`，1920×1080 约 60Hz（macOS 原生点亮） |
| eDP 工作状态 | pipe A / DDI A / PHY A，2 lane，2.7Gbps/lane |
| 触控板 / 触屏与笔 | Synaptics `06cb:cd74`（I²C 触控板已驱动） / Wacom `056a:4924`，两条独立 I²C 路线 |
| 无线 / 蓝牙 | Intel AX201（`itlwm` Wi-Fi 与蓝牙均已正常工作） |
| 音频 | ALC285 `10ec:0285`，子系统 `103c:8716`；Linux 使用 SOF（macOS 内置声卡待适配，蓝牙音频可用） |
| 存储 | Micron 2210，HPS1022；SSD 未被 VMD 映射，已安装完整 macOS 26.6.2 (`25G83`) 与内置 OpenCore 引导 |
| 当前系统 | NixOS 与 macOS 26.6.2 (`25G83`) 双系统在线；内置盘保留 NTFS 等现有分区 |
| BIOS | Secure Boot 关（测试期间），Fast Boot 开，VMD 存储映射关，Video Memory 512MB |

## 本机命令

```sh
nix develop -c make check
make check
make prototype
make collect HOST=<已配置的SSH目标>
make verify-evidence CAPTURE=.local/hardware/<时间戳>
make acpi CAPTURE=.local/hardware/<时间戳>
make vbt CAPTURE=.local/hardware/<时间戳> DECODER=<intel_vbt_decode>
make framebuffer-objects LLVM_BIN=<LLVM21工具目录>
make framebuffer LLVM_BIN=<LLVM21工具目录> LINKER=<支持kext的ld64>
make nonboot-graphics
python3 scripts/summarize_hardware.py .local/hardware/<时间戳> \
  --output hardware/elite-dragonfly-g2.json
```

采集脚本仅在开发主机写文件。原始 ACPI、DMI、描述符和日志保存在 Git 忽略的 `.local/` 下；版本库保留脱敏结论及原始证据的 SHA-256。不要将 `.local/` 整包公开。

## 早期阶段演进归档（M0 → M4）

- **离线原型与编译基线**：VESA EFI 原型通过 OpenCore 1.0.8 静态校验；固定 framebuffer 补丁在 Linux 编译并链接成真实 `x86_64` kext bundle，独立存放于 `.local/framebuffer-build/`。构建依赖固定缓存，来源见 `manifests/`。
- **Recovery 引导与 MMIO 突破**：实机单独 `slide=0` 重试在 runtime 内存申请处失败；保留该参数并开启 `DevirtualiseMmio` 后成功进入 Recovery 工具界面。完整 26.6.2 / `25G83` 离线 app 数据映像复制到 USB 并完整回读校验。
- **I²C 输入与内置诊断通道**：新增 `VoodooI2C`/`VoodooI2CHID` 与 Tiger Lake 精确匹配 ID 后，触控板与键盘可用；独立 **WiFi IMG** 实测 Wi-Fi、root SSH 和 SFTP 成功，内置 NTFS `/hpdiag` 可读，首份完整运行态归档见[网络交接](docs/recovery-network.md)和[运行态证据](manifests/hp-recovery-runtime-check.json)。
- **完整系统安装与 Xe Metal 硬件加速闭环**：从 VESA 基础启动 → Framebuffer 内屏 → 完整 macOS 26.6.2 安装 → `NootedGreen` Tiger Lake Iris Xe 80 EU Metal 计算管线修复，最终通过 `R32-ELSQWAIT` 与 `R32-PCFIX2` ~ `R32-PCFIX27` 实现三阶段实机 GPU 稳定性与耐力测试（连续 3 轮 24 项 Geekbench 6.5.0 Metal + 90s 并发压测 + 60s RC6 静置 + 30s 唤醒突发，共 `705,024` 个计算编码器）100% 零挂死通关及内置 NVMe 引导长稳运行。
