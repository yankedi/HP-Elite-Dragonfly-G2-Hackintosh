# HP Elite Dragonfly G2 Hackintosh (macOS 26 Tahoe)

**macOS 26 Tahoe (`26.6.2` / `25G83`) on HP Elite Dragonfly G2 (`8716`, Intel Core i5-1135G7 / Iris Xe Graphics G7 `8086:9a49` GT2 80 EU / 5 DualSubslices, 16 GiB LPDDR4X-4266) — OpenCore 1.0.8 configuration, Tiger Lake Gen12LP Metal compute & scheduler adaptations, Nix Flake reproducible build toolchain, and verified hardware telemetry.**

这是 HP Elite Dragonfly G2 的 macOS 26 Tahoe 完整移植与内核/图形驱动逆向工程仓库，整合了安装与外设/图形耐力工程 [`mac-for-elitebook`](mac-for-elitebook/README.md)、已发布图形驱动源码与补丁链 [`graphics`](graphics/README.md) 以及历代 Tiger Lake 图形实验与工具集 [`tgl26-usb`](tgl26-usb/README.md)。

---

## 核心实机成果总览（2026-11-06）

1. **完整 macOS 26.6.2 (`25G83`) 系统安装与内置 NVMe SSD 独立引导**：
   - 原生 macOS 26 Tahoe（`26.6.2`，Build `25G83`，Darwin `25.6.0` / `xnu-12377.161.14~5`）已完整安装至内置 Micron 2210 NVMe SSD，并通过内置盘 `/boot/EFI/OC`（OpenCore `1.0.8` + 自定义编译签名的 `NootedGreen.kext`）独立引导进入完整 macOS 桌面，97/97 引导文件经回读逐字节核验一致。
2. **Intel Iris Xe 80 EU Metal 硬件加速与 GPU 三阶段稳定性与耐力实机测试计划 100% 全程零挂死通关（[`R32-PCFIX27-PMAPFIX`](graphics/patches/nootedgreen-pcfix27-20261106.patch)）**：
   - 在实机上 **100% 通过 GPU 三阶段稳定性与耐力实机测试计划**（`Trial 27` `trial-r32-pcfix27-endurance-20261106` 与 `Trial 28` `trial-r32-pcfix27-full3stage-20261106`，全程净化并执行 **`705,024` 个计算编码器**，`pre=705,264`、`pf=610,384`、`rf=0`、`prblk=228,740`、`def=378,784`、`wsk=0`，**全程 `0` 次 `GPU hang:`、`0` 次 `GPURestart`、`0` 次内核 panic**）：
     - **Stage 1（连续 3 轮完整 Geekbench 6.5.0 `--gpu Metal` 共 24 项计算工作负载）**：连续 3 轮跑完 `Background Blur`、`Face Detection`、`Horizon Detection`、`Edge Detection`、`Gaussian Blur`、`Feature Matching`、`Stereo Matching`、`Particle Physics`（Run 1 `enc=25,088` -> Run 2 `enc=50,176` -> Run 3 `enc=75,264`，进程退出码全部 `rc=0`，`hang_count=0`）；
     - **Stage 2（90 秒 4 线程 `metal-concurrent-stress` Blit+Compute 并发压测 + `WindowServer` 合成）**：完成 `67,430` 批次、`404,570` 个编码器（`errors=0`、`avg_ms=2.264`、`max_ms=12.746`），推进至 `enc#547,328`（`hang_count=0`）；
     - **Stage 3（60 秒 RC6 深度休眠静置 + 30 秒 4 线程唤醒突发压测）**：完成 `22,513` 批次、`135,068` 个编码器（`errors=0`、`avg_ms=2.255`、`max_ms=9.398`），推进至 **`enc#705,024`**（`hang_count=0`，详见 [`mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md`](mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)）。
3. **RCS 无损单端口 Execlist 调度（`HP-SINGLEPORT-RCS`）与 GPU Reset 100% 无损自愈**：
   - 100% 消除了 `WindowServer`（Context `0xa0`）与 Metal 计算上下文（Context `0x5c0` / `0xcc0`）并发时的双端口 `Port1`（`EL[1]`）填充（`ELR1 = 0`）、同上下文 `LITE_RESTORE`（`0x8002`）以及 `EXECLIST_STATUS [0x2234]` 从 `0x00003098` 跌落为 `0x40002098`（`NO ACTIVE ELEMENTS`）的硬件仲裁冻结；
   - 在极端耐力压测触发 Watchdog 时，`XeNG GPUREC: reset RCS ret=1` 实现 **100% 干净自愈恢复**（无需重启系统即可继续高速执行后续数千个计算编码器）。
4. **内置 SSD 引导长稳运行零 Panic（`PMAPFIX` 根治 `pmap_recycle_page`）**：
   - 通过 7-bit 无损解码 EFI NVRAM `AAPL,PanicInfo0000..0003`，定位并隔离了物理内存窗口 `0x101000000..0x101400000`（`4 MiB`，覆盖早期 GA416/GA419 及内置盘启动约 252–394 秒必现的 `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511` 故障区间 `0x101304000..0x10131c000`），配合 `debug=0x100000` 彻底消除了该内核崩溃，在 **连续 28 轮实机高负载耐力测试中 `pmap_recycle_page` 崩溃发生率为 0%**。
5. **可复现 Nix Flake 工具链与双系统闭环验证体系**：
   - 基于 [`flake.nix`](flake.nix) 与 [`flake.lock`](flake.lock) 封装完整 LLVM 21（`clang_21` / `llvm_21` / `lld_21`）、`ld64`、`rcodesign`、`grub2`、`mtools`、`dosfstools`、`acpica-tools` 交叉构建环境，配合硬件寄存器快照采集与自动化校验脚本。

---

## 四大核心技术修复详解

> 完整寄存器取证、反汇编偏移、补丁 SHA-256 与 28 轮实机演进记录见 **[`mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md`](mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)**。

### 修复一：Tiger Lake (Gen12LP) RCS Execlist 硬件提交队列竞争、跨上下文抢占与无损单端口调度（`ELSQWAIT` + `PCFIX5` + `PCFIX6`）

- **根因定位**：
  1. **39 微秒高频提交导致 `ExecListQueueFull`（`0x4000219a`）**：`AppleIntelTGLGraphics` 在向 RCS 写 `ELSQ` 并敲击门铃 `0x2550 = 1` 时，若 `EXECLIST_STATUS [0x2234]` bit 30（`0x40000000`）仍置位，仅 39 微秒后的下一次提交就会把 `[0x2234]` 推入 `0x4000219a`（`ExecListQueueFull`），引发跨上下文硬件抢占覆盖。
  2. **双端口 `Port0 -> Port1` 元素切换冻结（`0x3098 -> 0x40002098`）**：当 `WindowServer`（Context `0xa0`）与 Geekbench Metal（Context `0x5c0`）并发时，宿主驱动发起软件 mid-batch 抢占或双端口 Execlist 提交（`Port0 = 0x5c0, Port1 = 0xa0`）。硬件在 `GPGPU_WALKER` 执行中途触发 `ELEMENT_SWITCH`（`CTXT_PREMP_DBG [0x2248] = 0x800`），使 `[0x2234]` 在 **4 微秒内**从 `0x00003098` 跌落为 `0x40002098`（`CurrentActiveElementStatus = NO ACTIVE ELEMENTS`），并隐式注入上下文保存刷新锁死 `CSFLTRK = 0x1c000001`。
- **修复机制**（[`nootedgreen-elsqwait-20261105.patch`](graphics/patches/nootedgreen-elsqwait-20261105.patch)、[`nootedgreen-pcfix5-20261105.patch`](graphics/patches/nootedgreen-pcfix5-20261105.patch)、[`nootedgreen-pcfix6-20261105.patch`](graphics/patches/nootedgreen-pcfix6-20261105.patch)）：
  - **无条件 `elsqWait` 排空等待**：在 `xePrepSubmit` 与 `xeCs5Submit` 中，只要 `([0x2234] & 0x40000000U) != 0` 即执行最多 `2000 us`（步长 `5 us`）的排空等待，并跳过 `port0 == nullptr && port1 == nullptr` 的空提交；
  - **禁用 mid-thread / per-context 抢占与软件 mid-batch 抢占**：编程 `GFXREG_CS_CHICKEN1 [0x2580] = 0x00020002`（`WaDisableGPGPUMidThreadPreemption`，改为线程组级抢占）并清零 `0x20e0` bit 14；挂钩 `IGScheduler5::updateOptions`（`0x385e0`）、`allowPreemption`（`0x3d9a6`）、`isPreemptionAllowed`（`0x3d9d2`）清零 `cs[0x1c50]`、`cs[0x1c5d]` 与 `sched[0x0c] bit 2`；
  - **无损单端口 RCS 策略（`HP-SINGLEPORT-RCS`）**：挂钩 `dequeueExecList`（`0x3b3b6`）在 `Port0` 活动（`el[cur][0] != 0 || !cs[0x1c3c]`）时延迟出队，并通过 `evalWorkQueues`（`0x3d5d0` `f_rcs1_hp` 将第 2 个上下文未消费的 ring 读指针 `%r12` 写回 `workQueue+0x4040`，保留优先级配额与轮转游标）与 `evalWaitQueue`（`0x3b971` `f_wait1_hp`）阻止填充 `Port1`（`EL[1]`），实现 **全程 `ELR1 = 0`、`0` 次 `LITE_RESTORE`、`0` 次 `0x40002098` 冻结**，以及 `XeNG GPUREC: reset RCS ret=1` **100% 干净自愈恢复**。

### 修复二：`AppleIntelTGLGraphicsMTLDriver`（`COCLGen8CommandTransport`）Gen8 遗留计算编码器就地净化、`CSFLTRK [0x2208]` 硬件真值表与 Tiger Lake `_WA_TABLE` 跨上下文持久化（`PCFIX2` ~ `PCFIX27`）

- **根因定位**：
  - 反编译 `IntelMTLComputeFunctions::execute`（`0x6bf20`）、`ResetPreambleCmds`（`0x378e8`）、`BuildPreambleCmds`（`0x38c48`）与 `AddPipeFlushCmd`（`0x37a0e`）查明，macOS 驱动在构建每个 151-dword 子分配计算编码器（`endOffDw = 95, totalDw = 151`，同一 4KB 页合并 5 个编码器 `k=0..4`）时存在多处 Gen8 遗留不兼容指令：
    1. `ResetPreambleCmds`（`dw[0..32]`）发射了两个未置 `CS_STALL`（`0x00100000`）的 `PIPE_CONTROL 0x00000480`（`TEXTURE_CACHE_INVALIDATE`），以及 Gen8 专属的 `MI_LOAD_REGISTER_IMM 0xb134`（`dw[15..17]`，Gen8 `L3ALLOC`，在 Gen12LP Tiger Lake 上破坏 L3/HDC 分配）；更重要的是，在 `dw[+12] PIPELINE_SELECT = GPGPU` 与 `dw[+15..+16] MEDIA_STATE_FLUSH`（`0x70040000U`）之后，`ResetPreambleCmds` Packet 3（`dw[+18..+23]`）在已切入 GPGPU 流水线模式后仍发射了带 `0x1000 RT_CACHE_FLUSH` 的 `0x001010a0U`，使 `CSFLTRK bit 28`（`0x10000000`）在 GPGPU 模式下重新锁存；
    2. 当多个计算编码器串联于同一 `MTLCommandBuffer` 时，均走 `0xac == 1` 慢路径而从不发射 `MEDIA_STATE_FLUSH`（`0x70040000`）；
    3. 编码器末尾 `AddPipeFlushCmd`（`dw[83..94]`）发射了 `7a000004 001044a0 <m_pScratchPage+0x10> 0 0 0`，在同一个 `PIPE_CONTROL` 包内同时混用 `POST_SYNC_OP = Write Immediate`（`0x4000`）、读缓存失效 `TEXTURE_CACHE_INVALIDATE`（`0x400`）与写缓存刷新 `DC_FLUSH_ENABLE`（`0x20`）。
  - **`HP-SLICE` 80 EU 硬件级空闲证实（`PCFIX22` ~ `PCFIX26`）**：挂死瞬间全部 5 个活动 DualSubslice（80 个 EU）100% 空闲完成（`SC_INSTDONE [0x7100] = 0xffffffff`、`ROW_INSTDONE[0..4] = 0xffffffff`、`SAMPLER_INSTDONE[0..4] = 0xffffffff`、`FAULT_REG [0xcec4] = 0x00000000`），死锁 **100% 发生在前端 Command Streamer Flush Tracker**（`CSFLFLAG [0x2204] = 0x50000000`、`CSFLTRK [0x2208]` bits 28..25 锁存未引退）。
- **修复机制**（[`graphics/src/NootedGreen/kern_gen11.cpp`](graphics/src/NootedGreen/kern_gen11.cpp)，最终版补丁 [`graphics/patches/nootedgreen-pcfix27-20261106.patch`](graphics/patches/nootedgreen-pcfix27-20261106.patch)）：
  - 在 `nativeRowPrefix` 写入 `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`；启用 `IntelAccelerator+0xf42 bit 0`（`_WA_TABLE+0x14 bit 0`）使 `AddPipeFlushCmd` 分配 12-dword 双包空间（`endOffDw = 95, totalDw = 151`）；
  - 挂钩 `IntelMTLComputeFunctions::execute`（仅针对计算编码器提交 token `eToken == 0x40001U` 调用 `hpSanitizeComputeEncoder`）：
    - **前导净化与 `PIPELINE_SELECT` 前后 `RT_CACHE_FLUSH` 解耦（`ResetPreambleCmds` `dw[0..32]`，`PCFIX27` 核心突破）**：保留 `dw[+12] PIPELINE_SELECT = GPGPU` 之前的 Packet 1（`dw[+1] = 0x001010a0U` = `CS_STALL | RT_CACHE_FLUSH | FLUSH_ENABLE | DC_FLUSH_ENABLE`）在 EU 空闲态排空并引退 3D/ring Render Target Cache；为 Packet 2（`dw[+7]`）与 Packet 4（`dw[+25]`）补齐 `CS_STALL`（`0x00100480U`）；将 `dw[+15..+17]` 的非法 `LRI 0xb134` 就地替换为 `MEDIA_STATE_FLUSH`（`0x70040000U, 0U`）+ `MI_NOOP`（`0U`）；并将紧随 `MEDIA_STATE_FLUSH` 之后（已处于 GPGPU 模式）的 **Packet 3（`dw[+19]`）从 `0x001010a0U` 改写为 `0x001000a0U`**（剥离 `0x1000 RT_CACHE_FLUSH`），使 `CSFLTRK bit 28`（`0x10000000`）在进入 `GPGPU_WALKER` 前彻底引退为 `0`；
    - **末尾刷新双包解耦（`AddPipeFlushCmd` `dw[83..94]`）**：解耦写刷新 Packet 0（`0x001000a0U` = `CS_STALL | FLUSH_ENABLE | DC_FLUSH_ENABLE`）与读缓存失效 Packet 1（`0x00100480U` = `CS_STALL | TEXTURE_CACHE_INVALIDATE | FLUSH_ENABLE`）；
  - **Tiger Lake `_WA_TABLE` 64 位偏移修正与黄金上下文镜像持久化验证（`PCFIX23` ~ `PCFIX27`）**：在 `PCFIX25` / `PCFIX26` 中证实通过 `that[0xf5f] |= 0x80U`（`0x7010 = 0x20002000`）与 `that[0xf68] |= 0x01U`（`0x20d8 = 0x00100010`）将 `CS_DBG1 = 0x00000010` 与 `CHKN3 = 0x00002000` 烘焙进 `_safeHardwareContextBufferRCS` 即可跨数千次上下文切换 100% 持久保留（`PCFIX25` 首次将 `CSFLTRK bits 31..1` 清零至 `0x00000001`），并在 **`R32-PCFIX27`** 中回退会产生副作用的 `0x7010`/`0x20d8`/`0x2050` 至干净 `PCFIX20` 基底，仅凭 `dw[+1]=0x001010a0U` + `MEDIA_STATE_FLUSH` + `dw[+19]=0x001000a0U` + 双包 `AddPipeFlushCmd` 实现 `CSFLTRK bits 28..25 = 0000b` 全清零，**100% 零挂死通过全部三阶段实机耐力测试（`705,024` 个计算编码器）**。

| 实机版本 | 补丁文件 | Stage 1 Run 1（8/8 项工作负载，`25,088` 编码器） | 耐力压测 `CSFLTRK [0x2208]` 锁存值 | 硬件验证结论 |
| --- | --- | --- | --- | --- |
| `R32-PCFIX2` | [`nootedgreen-pcfix2-20261105.patch`](graphics/patches/nootedgreen-pcfix2-20261105.patch) | 单轮基准 **100% 零挂死通关** | `0x06000001`（bits `26, 25`） | 首版就地净化，单轮 8/8 全通 |
| `R32-PCFIX6` | [`nootedgreen-pcfix6-20261105.patch`](graphics/patches/nootedgreen-pcfix6-20261105.patch) | 验证 `HP-SINGLEPORT-RCS` | `0x18000001`（bits `28, 27`） | 100% 消除 `Port1`、`LITE_RESTORE` 与 `0x40002098` 冻结 |
| `R32-PCFIX14` | [`nootedgreen-pcfix14-20261106.patch`](graphics/patches/nootedgreen-pcfix14-20261106.patch) | **100% 零挂死通关**（推进至 Run 2 `enc=32,142`） | `0x08000001`（仅剩 bit `27`） | `MEDIA_STATE_FLUSH` + `0x001000a0` 清除 bits `28, 26, 25` |
| `R32-PCFIX16` | [`nootedgreen-pcfix16-20261106.patch`](graphics/patches/nootedgreen-pcfix16-20261106.patch) | **100% 零挂死通关**（`enc=21,504`，推进至 Run 2 `enc=27,348`） | `0x06000001`（bits `28..27 = 0`） | `q+0x620=1` 关闭命令合并 + 双包 `0x00100000 / 0x001000a0` |
| `R32-PCFIX19` | [`nootedgreen-pcfix19-20261106.patch`](graphics/patches/nootedgreen-pcfix19-20261106.patch) | **100% 零挂死通关**（推进至 Run 2 `enc=32,202`） | `0x1e000001`（bits `28..25`） | 反证：`PIPE_CONTROL` 置于 `MEDIA_STATE_FLUSH` 之前会导致前导阻塞 |
| `R32-PCFIX20` | [`nootedgreen-pcfix20-20261106.patch`](graphics/patches/nootedgreen-pcfix20-20261106.patch) | **100% 零挂死通关**（推进至 Run 2 `enc=32,196`） | `0x10000001`（仅剩 bit `28`） | 前导 `MEDIA_STATE_FLUSH` + 末尾双包 `0x001000a0 + 0x00100480` 清除 bits `27..25` |
| `R32-PCFIX25` | [`nootedgreen-pcfix25-20261106.patch`](graphics/patches/nootedgreen-pcfix25-20261106.patch) | 验证 `_WA_TABLE` 跨上下文持久化 | **`0x00000001`（bits `31..1` 全清零）** | `CS_DBG1=0x10` 与 `CHKN3=0x2000` 跨上下文持久化，**首次清除全部缓存刷新位** |
| `R32-PCFIX26` | [`nootedgreen-pcfix26-20261106.patch`](graphics/patches/nootedgreen-pcfix26-20261106.patch) | 验证无运行时 MMIO 写黄金镜像持久化（`enc=7,186`） | `0x06000001`（bits `28..27 = 0`） | 证实黄金上下文镜像跨 7,158 次切换持久保留 `CS_DBG1`/`CHKN3`；隔离出 `0x7010`/`0x20d8`/`0x2050` 回退副作用 |
| **`R32-PCFIX27`** | **[`nootedgreen-pcfix27-20261106.patch`](graphics/patches/nootedgreen-pcfix27-20261106.patch)** | **三阶段全通（3 轮 24/24 项 GB6 + 90s 并发 + RC6 唤醒，`705,024` 编码器）** | **`0` 次挂死（`CSFLTRK bits 28..25 = 0000b`）** | **保留 `dw[+1]=0x001010a0` + 将 GPGPU 后 `dw[+19]` 改为 `0x001000a0`（回退 `0x7010`/`0x20d8`/`0x2050`），三阶段耐力测试 100% 零挂死通关** |

### 修复三：内置 SSD 启动 `pmap_recycle_page: page 0x101310000 is referenced` 内核崩溃根治（`PMAPFIX`）

- **根因定位**：
  - 用户观察到从内置 SSD 启动 macOS 后约 6–7 分钟锁屏黑屏后按任意键无响应。通过读取 EFI NVRAM 变量并编写 7-bit 无损解包器还原 `AAPL,PanicInfo0000..0003`（`panic-decoded.txt` SHA256 `d1c3e3018b832b524cd3a7df730de77428f372222540c8a42e6d29ec11b628e6`），查明系统从未进入睡眠（`Last Sleep: 0`），而是在开机 **394.46 秒（6 分 34 秒）** 触发了：
    `panic(cpu 6 caller 0xffffff800046709b): pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511`
  - 故障物理页 `0x101310000` 与此前 GA416/GA419 四次加速图形启动在 252–340 秒触发的 `pmap_recycle_page` 崩溃页（`0x101304000`、`0x10130e000`、`0x101313000`，详见 [`docs/GRAPHICS-STABILITY.md`](docs/GRAPHICS-STABILITY.md) 与 [`evidence/README.md`](evidence/README.md)）100% 落在同一个 **128 KiB 物理内存窗口（`0x101304000..0x10131c000`）**；同时 `boot-args` 中的 `debug=0x100100` 置位了 `DB_HALT`（`0x100`），使内核在打印 panic 后死循环停机在 `_kdp_i386_trap` 而不自动重启。
- **修复机制**：
  1. 在 OpenCore `config.plist` 的 `UEFI -> ReservedMemory` 中新增 `4 MiB` 物理内存保留条目（`Address = 0x101000000`、`Size = 0x00400000`、`Type = Reserved`、`Enabled = true`），使 XNU `pmap` 永不分配 `0x101000000..0x101400000` 物理页；
  2. 将 `boot-args` 中的 `debug=0x100100` 改为 `debug=0x100000`（去掉 `DB_HALT = 0x100`）。
- **实机验证效果**：在随后的 **连续 28 轮实机高负载压测** 中，**`pmap_recycle_page` 崩溃发生率为 0%**。

### 修复四：可复现 Nix Flake 构建环境与外设/引导工程化整合

- **Nix Flake 持久化构建环境**：新增 [`flake.nix`](flake.nix) 与 [`flake.lock`](flake.lock)，统一提供 `clang_21`、`llvm_21`、`lld_21`、`rcodesign`、`grub2`、`mtools`、`dosfstools`、`acpica-tools`、`python3`、`openssh`、`rsync`、`jq`、`gnumake`、`git`，消除硬编码 `/nix/store/...` 路径或临时 `nix-shell` 调用。
- **ACPI 与外设基线**：
  - [`EFI/ACPI/SSDT-EC-USBX-HP.dsl`](EFI/ACPI/SSDT-EC-USBX-HP.dsl)、[`EFI/ACPI/SSDT-RHUB-HP.dsl`](EFI/ACPI/SSDT-RHUB-HP.dsl)、[`EFI/ACPI/SSDT-PNLF-HP-GA419.dsl`](EFI/ACPI/SSDT-PNLF-HP-GA419.dsl) 与 [`mac-for-elitebook/acpi/SSDT-PLUG.dsl`](mac-for-elitebook/acpi/SSDT-PLUG.dsl)；
  - Wi-Fi（Intel AX201 `itlwm`）、蓝牙（含双向蓝牙音频）、I²C 触控板（Synaptics `06cb:cd74`）、PS/2 键盘、电池状态、RGB 摄像头与 PCH USB 均已实机工作（外设完整状态见 [`docs/STATUS.md`](docs/STATUS.md) 与 [`mac-for-elitebook/docs/peripheral-adaptation-status-20261104.md`](mac-for-elitebook/docs/peripheral-adaptation-status-20261104.md)）。

---

## 项目入口

| 内容 | 入口 |
| --- | --- |
| **2026-11-06 GPU Metal 加速、单端口 RCS 与 `PMAPFIX` 技术总结** | **[`mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md`](mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)** |
| **2026-11-05 Geekbench 6.5.0 Metal 8/8 全通记录（`R32-PCFIX2`）** | **[`mac-for-elitebook/docs/repair32-pcfix2-20261105.md`](mac-for-elitebook/docs/repair32-pcfix2-20261105.md)** |
| **2026-11-05 Horizon Detection 突破记录（`R32-ELSQWAIT`）** | **[`mac-for-elitebook/docs/repair32-elsqwait-20261105.md`](mac-for-elitebook/docs/repair32-elsqwait-20261105.md)** |
| 当前硬件支持矩阵与功能状态 | [`docs/STATUS.md`](docs/STATUS.md) |
| 实测图形源码（`NootedGreen` + `HookCase`）、补丁链与 SHA-256 清单 | [`graphics/README.md`](graphics/README.md) |
| OpenCore 配置示例与 ACPI 源码 | [`EFI/README.md`](EFI/README.md) |
| 安装、ACPI、外设与诊断工程主文档 | [`mac-for-elitebook/README.md`](mac-for-elitebook/README.md) |
| 外设适配现状与驱动深度调研（2026-11-04） | [`mac-for-elitebook/docs/peripheral-adaptation-status-20261104.md`](mac-for-elitebook/docs/peripheral-adaptation-status-20261104.md)、[`mac-for-elitebook/docs/peripheral-driver-research-20261104.md`](mac-for-elitebook/docs/peripheral-driver-research-20261104.md) |
| 早期 `pmap_recycle_page` 加速 panic 与软件显示对照（已由 `PMAPFIX` 根治） | [`docs/GRAPHICS-STABILITY.md`](docs/GRAPHICS-STABILITY.md)、[`evidence/README.md`](evidence/README.md) |
| 历代图形实验与自研工具 | [`tgl26-usb/README.md`](tgl26-usb/README.md) |
| 构建与验证说明 | [`docs/BUILDING.md`](docs/BUILDING.md) |
| 目录与发布范围 | [`docs/REPOSITORY.md`](docs/REPOSITORY.md) |
| 历史上传版本与检查记录 | [`docs/PUBLICATION.md`](docs/PUBLICATION.md)、[`docs/ISSUE-DRAFT.md`](docs/ISSUE-DRAFT.md)、[`docs/UPSTREAM-CONTROL-PREPARATION.md`](docs/UPSTREAM-CONTROL-PREPARATION.md) |

---

## 实测机器规格

- **机型：** HP Elite Dragonfly G2，主板 `8716`，BIOS `T90 01.25.00`
- **CPU：** Intel Core i5-1135G7（Tiger Lake-UP3，4 核 8 线程，8 MiB L3）
- **GPU：** Intel Iris Xe Graphics G7 `8086:9a49`（Rev `0x01` B0，GT2 80 EUs / 5 DualSubslices / 10 Gen12 subslices，有效 L3=6 banks）
- **内存：** 16 GiB LPDDR4X-4266
- **内屏：** IVO8596 `X133NVFF R0`，1920×1080@60Hz eDP（pipe A / DDI A / PHY A，2 lane，2.7 Gbps/lane）
- **存储：** Micron 2210 512 GB NVMe SSD（PCIe 直连，VMD 关闭）
- **系统：** macOS Tahoe `26.6.2` / `25G83`（Darwin `25.6.0`），OpenCore `1.0.8`

---

## 快速查看与检查

```sh
git clone git@github.com:yankedi/HP-Elite-Dragonfly-G2-Hackintosh.git
cd HP-Elite-Dragonfly-G2-Hackintosh
nix develop -c python3 scripts/check-publication.py
nix develop -c make -C mac-for-elitebook check
```

（若未启用 Nix Flake，亦可直接运行 `python3 scripts/check-publication.py` 与 `make -C mac-for-elitebook check`。）

## 来源与许可

本项目基于多个上游项目及本地 HP 适配。各源文件、子项目的许可证和版权声明保持有效；没有以一个总许可证重新授权所有第三方代码。参见 [`LICENSING.md`](LICENSING.md) 及 [`graphics/NOTICE.md`](graphics/NOTICE.md)。

完整的私有硬件采集、机器身份、安装介质和原始全量日志保存在本地开发机私有目录中；公开仓库仅收录源码、补丁、配置示例与脱敏验证记录。
