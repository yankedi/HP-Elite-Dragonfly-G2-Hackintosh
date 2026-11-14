# HP Elite Dragonfly G2 Hackintosh (macOS 26 Tahoe)

**macOS 26 Tahoe (`26.6.2` / `25G83`) on HP Elite Dragonfly G2 (`8716`, Intel Core i5-1135G7 / Iris Xe Graphics G7 `8086:9a49` GT2 80 EU / 5 DualSubslices, 16 GiB LPDDR4X-4266) — OpenCore 1.0.8 configuration, Tiger Lake Gen12LP Metal compute & scheduler adaptations, Nix Flake reproducible build toolchain, and verified hardware telemetry.**

这是 HP Elite Dragonfly G2 的 macOS 26 Tahoe 完整移植与内核/图形驱动逆向工程仓库，整合了安装与外设/图形耐力工程 [`mac-for-elitebook`](mac-for-elitebook/README.md)、已发布图形驱动源码与补丁链 [`graphics`](graphics/README.md) 以及历代 Tiger Lake 图形实验与工具集 [`tgl26-usb`](tgl26-usb/README.md)。

---

## 核心实机成果总览（2026-11-14）

1. **完整 macOS 26.6.2 (`25G83`) 系统安装、内置 NVMe `~18.5s` 极速引导与一键重装/净室重编译闭环**：
   - 原生 macOS 26 Tahoe（`26.6.2`，Build `25G83`，Darwin `25.6.0` / `xnu-12377.161.14~5`）已完整安装至内置 Micron 2210 NVMe SSD，并通过主引导 ESP `disk0s1`（`/dev/nvme0n1p1`，`314.6 MB` EFI `/boot/EFI/OC`，与 Windows / NixOS `systemd-boot` 共存；`disk0s6` `/dev/nvme0n1p6` 为 `1.0 GB` 备用第二 EFI 分区；日用定版 OpenCore `1.0.8` `config.plist` `60,987` B SHA256 `80f1e1bfe46ea7fb22a57e4486c8f405fe790b85167969df2ee003d938dad8e5`，含 `PT04->XT04` ACPI 重命名及 `Timeout=1`/`HideAuxiliary=true`/`PollAppleHotKeys=true`/`AllowSetDefault=true`/`ApplePanic=false`/`DisableWatchDog=false`/`AppleDebug=false`/`Target=0`/`ShowPicker=true`/`ScanPolicy=0` + 实测通过的 `R32-PCFIX50-HDMI` `NootedGreen.kext` `580,640` B SHA256 `da62b067f6561568fe0f203ef18663f1f0c137c30d2759ab37d736346dbffca6`、UUID `4C4C44B8-5555-3144-A17C-F348EF4AFF41`，已同步至内置 `disk0s1`、`systemd-boot` 启动项、恢复镜像 `7ca6ea48...` 与 Windows NTFS 暂存包 `06502878...`；外接 `Ventoy` U 盘本次未连接故仍保留上一版 `PCFIX50`）独立引导运行，OpenCore 入口至 1080p 桌面启动仅 **`~18.5s`**（[`R32-PCFIX41`](graphics/patches/nootedgreen-pcfix41-fastboot-20261112.patch)：`WindowServer` `3.17s`、`IntelAccelerator` `8.17s`、1080p 30-bit 桌面 `12.17s`、`0` 个 `opencore-*.txt` 磁盘日志）；稳态亮屏办公整机平均功耗仅 **`7.23 W`**（轻载浏览 **`5.03–5.63 W`**，RAPL SoC 封装 **`3.13 W`**、CPU 核心 **`0.94 W`**、核显 **`0.043 W`**）；完整全新重装流程与从零源码净室重编译指南见 [`mac-for-elitebook/docs/clean-install-guide.md`](mac-for-elitebook/docs/clean-install-guide.md) 与 [`mac-for-elitebook/docs/from-source-rebuild-guide.md`](mac-for-elitebook/docs/from-source-rebuild-guide.md)。
2. **Intel Iris Xe 80 EU Metal 硬件加速、三阶段耐力通关（[`R32-PCFIX27`](graphics/patches/nootedgreen-pcfix27-20261106.patch)）、原生机载 HDMI 2.0b `2560×1440@60/120/144Hz`（[`R32-PCFIX50-HDMI`](graphics/patches/nootedgreen-pcfix50-hdmi-20261114.patch)）与 `420v` 视频零绿屏（[`R32-PCFIX35`](graphics/patches/nootedgreen-pcfix35-blitalign-20261108.patch)）**：
   - 在实机上 **100% 通过 GPU 三阶段稳定性与耐力实机测试计划**（`Trial 27` 与 `Trial 28`，全程净化并执行 **`705,024` 个计算编码器**，**全程 `0` 次 `GPU hang:`、`0` 次 `GPURestart`、`0` 次内核 panic**）：
     - **Stage 1（连续 3 轮完整 Geekbench 6.5.0 `--gpu Metal` 共 24 项计算工作负载）**：`enc=25,088 -> 50,176 -> 75,264`（`rc=0`，`hang_count=0`）；
     - **Stage 2（90 秒 4 线程 `metal-concurrent-stress` Blit+Compute 并发压测 + `WindowServer` 合成）**：`67,430` 批次、`404,570` 个编码器（`errors=0`，推进至 `enc#547,328`）；
     - **Stage 3（60 秒 RC6 深度休眠静置 + 30 秒 4 线程唤醒突发压测）**：`22,513` 批次、`135,068` 个编码器（`errors=0`，推进至 **`enc#705,024`**，详见 [`mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md`](mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)）。
   - **原生 Tiger Lake ComboPHY `DDI-B`（`ddi=1`）机载 HDMI 2.0b `600 MHz` 输出（[`R32-PCFIX42..PCFIX50-HDMI`](graphics/patches/nootedgreen-pcfix50-hdmi-20261114.patch)）**：将 `connectors[1]` 从 `ConnectorDP` + `busId=1` 修正为 `ConnectorHDMI` + GMBUS `busId=2`（3 pipes / 6 ports，支持 `-ngreennohdmi` 关闭），补齐 `hpGetStreamAccessAUX` 避免 `AppleIntelPort::probePortStateEv` `__cxa_pure_virtual` 启动挂死，修复 `hwDoGMBusRequest` `(reg, val)` 参数反置与 `0xC5108` GMBUS2 轮询，限制 `FB1` 仅接受 24-bit 8bpc RGB 4:4:4 TMDS 模式，将 `AppleIntelTGLGraphicsFramebuffer` `0xf3518` DPLL 表从 Ice Lake 偏移重定位至 Tiger Lake ComboPHY `DPLL{0,1,4}_CFGCR{0,1}`（`0x164284..0x164298`）并加掩码保护，扩展 `IOFBTimingRange` 至 `600 MHz` 并在 `>= 340 MHz` 时通过 GMBUS2 编程 HDMI 2.0 SCDC `0x54`/`0x20`（加扰 + 1/40 bit clock）及 `TRANS_DDI_FUNC_CTL_B` `HIGH_TMDS_CHAR_RATE`；实机双屏扩展（`Mirror: Off`，eDP 1080p 10-bit + HDMI ASUS VG27AQ5A `2560×1440@60/120/144Hz` 24-bit RGB）切换全通，144 Hz 下像素时钟 **`593.700000 MHz`**（`DPLL1 = 0x01A801CF / 0x00002448`、`0.000 ppm`、`scdc=3/3 cfg=3 st=1`、`0` panic、`0` `GPURestart`）。
   - **`HP-CAMELLIA-NULLGUARD` + `HP-ORPHAN-CAP` + `HP-QUIET-HOTPATH`（[`R32-PCFIX39`](graphics/patches/nootedgreen-pcfix39-camellia-orphan-20261111.patch) / [`R32-PCFIX40`](graphics/patches/nootedgreen-pcfix40-quiet-hotpath-20261111.patch)）+ `HP-BLITALIGN`（[`R32-PCFIX35`](graphics/patches/nootedgreen-pcfix35-blitalign-20261108.patch)）**：拦阻 `powermetrics --samplers gpu_power` 下 `CamelliaBase::ReadDpbResidency(this=NULL)` 内核空指针崩溃，启用 O(1) `IOAccelOrphanedMemoryPool` 复用并设置 `512 MiB / 10m` 上限，消除同步热路径日志；`HP-BLITALIGN` + `xe-h264sw-fixd` 彻底消除 `420v` NV12 视频绿屏与花屏。
3. **Modern Standby `S0ix` 深度休眠唤醒、`ICCMAX/PL4` 卡顿与校园网 48s DarkWake 根治、禁用 USB 误唤醒与原生 10-bit 唤醒色彩（[`SSDT-DEEPIDLE.dsl`](EFI/ACPI/SSDT-DEEPIDLE.dsl) + [`SSDT-EC0-ITLB.dsl`](EFI/ACPI/SSDT-EC0-ITLB.dsl) + `S0ixStandby v0.4.4` + [`R32-PCFIX38`](graphics/patches/nootedgreen-pcfix38-wakecolor-20261111.patch)）**：
   - 通过 [`SSDT-DEEPIDLE.dsl`](EFI/ACPI/SSDT-DEEPIDLE.dsl)（`371` B AML SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`）、[`SSDT-EC0-ITLB.dsl`](EFI/ACPI/SSDT-EC0-ITLB.dsl)（`1,854` B AML SHA256 `8a931eb6565d57e58cb4a798028486e443e72ff0756edb7afff9a8ffa15ee998`：覆盖 HP DSDT `PT04` `Local1` 反置判断与 `EC12` 下限，根治弱适配器 `GSWS(0xB6)` 误锁死 `ICCMAX/PL4` `0x01000100` 导致的卡顿）、`S0ixStandby.kext`（`v0.4.4`，`74,840` B SHA256 `bffd2681628aca10f8039ac7ca312d6103f487e1457b99b63d29cd99ff5f9d3c`，`LC_UUID` `4C4C44D1-5555-3144-A159-4D08A3482CB2`：解除 PCI `PME_EN` + 屏蔽 GPE `0x6D`/`0x69` + `CNVW` 纯 `PMCSR` `D3hot` 保留 `PC8` + 唤醒改调 `EC0.PWUP(0x07,0x03)`/`AC._PSR` 避免误触 `_Q06`/`_Q09`）与 `pmset networkoversleep=0/powernap=0` + `mDNSResponder NoMulticastAdvertisements=YES`（消除 48s Maintenance DarkWake 导致的 `bluetoothd` HCI 卡死），配合 [`R32-PCFIX38`](graphics/patches/nootedgreen-pcfix38-wakecolor-20261111.patch) + `hp-wake-helper`，实现 `62.4 分钟` 连续盒盖 S0ix 零异常唤醒与干净 10-bit 色彩唤醒。
4. **全外设驱动、触控/手写笔、守护进程稳固与持久化日志闭环**：
   - **声卡与四阵列数字麦克风**：Realtek ALC285 四扬声器 + 3.5 mm 耳麦自动切换（`SimpleHDA 1.0.1` + `AppleALC 1.9.8` `layout-id = 71` + `hp-alc285-ampinit.sh` + `hp-wake-helper`）与自研 Tiger Lake Intel cAVS 2.5 DSP（`sof-tgl.ri`）四通道麦克风驱动 `TGLDmic.kext v0.5.0`（`1,187,520` B SHA256 `04cd2c7d38ae8fd8dff1c3d2375c53f5f756b0b0bdad2c9535bfc59e9649ecfe` + `TGLDmic.driver` CoreAudio HAL）；
   - **原生屏幕亮度、事件驱动零轮询 `hp-bridge` v3、触控板与 `WACF4233` 触摸屏/压感笔**：[`R32-PCFIX31`](graphics/patches/nootedgreen-pcfix31-backlight-20261107.patch) + `hp-cb-shim-loader.sh` + 事件驱动 `hp-bridge` v3（`79,888` B SHA256 `b79773763955e2ca64e78b93b978f37ffd6b18374dae0442a45f979dccfd9cff`，彻底移除 25 Hz XPC 轮询，`corebrightnessd` 日志降幅 **99.81%**；支持按速自适应调光、零 TCC 原生 `prt scr` 截屏及全顶排 `Fn+F1`..`Fn+F11`）；`TPD0` (`SYNA30B6`) 启用 `QuietTimeAfterTyping=0` + `VoodooI2CNativeEngine`（保留单击拖动 `Dragging=1` 与三/四指切换桌面）；`TPL0` (`WACF4233`) 配合签名 `PenBridge` (`/Applications/PenBridge.app`, `203,072` B SHA256 `caff70ce5d4da40647d2f7d0fd80c026fec0bac1fc8a9e1589a979fce0413d0f`)；
   - **内置 `06cb:00f0` 指纹解锁、蓝牙稳固与登录前 Tailscale 自连**：`RidgeKey 1.0.0` 原生驱动内置 Synaptics `06cb:00f0` USB 指纹；`AirportItlwm 2.4.0` 原生 `en0` Wi-Fi 6；`hp-syslogger.py` `v1.3`（`mlock()` 锁页消除 `bluetoothd` APFS `decmpfs` `error 94` `SIGBUS` + 零 peripherials 蓝牙 HCI 自愈脚本 `hp-bt-compat-check.sh`）+ `/var/log/hp/boot-<STAMP>-<UUID8>/` 持久化日志；Clash Verge（`find-process-mode: 'off'`）与 Tailscale 开机 `20s` 登录前无感自连 + Split MagicDNS 共存。
5. **内置 SSD 引导长稳运行零 Panic（`PMAPFIX`）与可复现 Nix Flake 工具链**：
   - 隔离物理内存窗口 `0x101000000..0x101400000`（`4 MiB`）+ `debug=0x100000`，`pmap_recycle_page` 崩溃发生率 **0%**；基于 [`flake.nix`](flake.nix) / [`flake.lock`](flake.lock) 与 [`verify_release_artifacts.py`](mac-for-elitebook/scripts/verify_release_artifacts.py) 实现 **`436` 文件**部署包、`111` 文件内置 ESP（恢复镜像 `112` 文件）对等性及 **`11/11` 核心组件净室重编译**逐字节确定性核验。

---

## 核心技术修复详解

> 完整寄存器取证、反汇编偏移、补丁 SHA-256 与演进记录见 **[`mac-for-elitebook/README.md`](mac-for-elitebook/README.md)**、**[`mac-for-elitebook/docs/clean-install-guide.md`](mac-for-elitebook/docs/clean-install-guide.md)**、**[`mac-for-elitebook/docs/from-source-rebuild-guide.md`](mac-for-elitebook/docs/from-source-rebuild-guide.md)** 与 **[`mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md`](mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)**。

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
- **修复机制**（[`graphics/src/NootedGreen/kern_gen11.cpp`](graphics/src/NootedGreen/kern_gen11.cpp)，计算耐力补丁 [`graphics/patches/nootedgreen-pcfix27-20261106.patch`](graphics/patches/nootedgreen-pcfix27-20261106.patch)，最新累积补丁 [`graphics/patches/nootedgreen-pcfix50-hdmi-20261114.patch`](graphics/patches/nootedgreen-pcfix50-hdmi-20261114.patch)）：
  - 在 `nativeRowPrefix` 写入 `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`；启用 `IntelAccelerator+0xf42 bit 0`（`_WA_TABLE+0x14 bit 0`）使 `AddPipeFlushCmd` 分配 12-dword 双包空间（`endOffDw = 95, totalDw = 151`）；
  - 挂钩 `IntelMTLComputeFunctions::execute`（仅针对计算编码器提交 token `eToken == 0x40001U` 调用 `hpSanitizeComputeEncoder`）：
    - **前导净化与 `PIPELINE_SELECT` 前后 `RT_CACHE_FLUSH` 解耦（`ResetPreambleCmds` `dw[0..32]`，`PCFIX27` 核心突破）**：保留 `dw[+12] PIPELINE_SELECT = GPGPU` 之前的 Packet 1（`dw[+1] = 0x001010a0U` = `CS_STALL | RT_CACHE_FLUSH | FLUSH_ENABLE | DC_FLUSH_ENABLE`）在 EU 空闲态排空并引退 3D/ring Render Target Cache；为 Packet 2（`dw[+7]`）与 Packet 4（`dw[+25]`）补齐 `CS_STALL`（`0x00100480U`）；将 `dw[+15..+17]` 的非法 `LRI 0xb134` 就地替换为 `MEDIA_STATE_FLUSH`（`0x70040000U, 0U`）+ `MI_NOOP`（`0U`）；并将紧随 `MEDIA_STATE_FLUSH` 之后（已处于 GPGPU 模式）的 **Packet 3（`dw[+19]`）从 `0x001010a0U` 改写为 `0x001000a0U`**（剥离 `0x1000 RT_CACHE_FLUSH`），使 `CSFLTRK bit 28`（`0x10000000`）在进入 `GPGPU_WALKER` 前彻底引退为 `0`；
    - **末尾刷新双包解耦（`AddPipeFlushCmd` `dw[83..94]`）**：解耦写刷新 Packet 0（`0x001000a0U` = `CS_STALL | FLUSH_ENABLE | DC_FLUSH_ENABLE`）与读缓存失效 Packet 1（`0x00100480U` = `CS_STALL | TEXTURE_CACHE_INVALIDATE | FLUSH_ENABLE`）；
  - **Tiger Lake `_WA_TABLE` 64 位偏移修正与黄金上下文镜像持久化验证（`PCFIX23` ~ `PCFIX27`）**：在 `PCFIX25` / `PCFIX26` 中证实通过 `that[0xf5f] |= 0x80U`（`0x7010 = 0x20002000`）与 `that[0xf68] |= 0x01U`（`0x20d8 = 0x00100010`）将 `CS_DBG1 = 0x00000010` 与 `CHKN3 = 0x00002000` 烘焙进 `_safeHardwareContextBufferRCS` 即可跨数千次上下文切换 100% 持久保留（`PCFIX25` 首次将 `CSFLTRK bits 31..1` 清零至 `0x00000001`），并在 **`R32-PCFIX27`** 中回退会产生副作用的 `0x7010`/`0x20d8`/`0x2050` 至干净 `PCFIX20` 基底，仅凭 `dw[+1]=0x001010a0U` + `MEDIA_STATE_FLUSH` + `dw[+19]=0x001000a0U` + 双包 `AddPipeFlushCmd` 实现 `CSFLTRK bits 28..25 = 0000b` 全清零，**100% 零挂死通过全部三阶段实机耐力测试（`705,024` 个计算编码器）**。

| 实机版本 | 补丁文件 | 核心验证结果 | 硬件验证结论 |
| --- | --- | --- | --- |
| `R32-PCFIX2` | [`nootedgreen-pcfix2-20261105.patch`](graphics/patches/nootedgreen-pcfix2-20261105.patch) | 单轮基准 **100% 零挂死通关** | 首版就地净化，单轮 Geekbench 6 Metal 8/8 全通 |
| `R32-PCFIX6` | [`nootedgreen-pcfix6-20261105.patch`](graphics/patches/nootedgreen-pcfix6-20261105.patch) | 验证 `HP-SINGLEPORT-RCS` | 100% 消除 `Port1`、`LITE_RESTORE` 与 `0x40002098` 冻结 |
| **`R32-PCFIX27`** | **[`nootedgreen-pcfix27-20261106.patch`](graphics/patches/nootedgreen-pcfix27-20261106.patch)** | **三阶段耐力全通（`705,024` 编码器，`0` 挂死）** | **保留 `dw[+1]=0x001010a0` + 将 GPGPU 后 `dw[+19]` 改为 `0x001000a0`，`CSFLTRK bits 28..25 = 0000b`** |
| `R32-PCFIX31` | [`nootedgreen-pcfix31-backlight-20261107.patch`](graphics/patches/nootedgreen-pcfix31-backlight-20261107.patch) | 原生 eDP 亮度滑块 + HUD | `AppleBacklightDisplay` 挂载 + PCH PWM `0xc8254` 占空比同步 |
| `R32-PCFIX32..34` | [`nootedgreen-pcfix34-s0ix-drm-20261108.patch`](graphics/patches/nootedgreen-pcfix34-s0ix-drm-20261108.patch) | `51m 37s` Deep Idle `S0ix` 睡眠唤醒 | `HP-S0IX-IDLE` / `HP-S0IX-DRM` GT 与显示管线挂起/恢复 |
| `R32-PCFIX35` | [`nootedgreen-pcfix35-blitalign-20261108.patch`](graphics/patches/nootedgreen-pcfix35-blitalign-20261108.patch) | `420v` NV12 视频零绿边/花屏 | `HP-BLITALIGN` 64 字节行距对齐与 BCS0 Blit2D / SIMD16 修正 |
| `R32-PCFIX36..38` | [`nootedgreen-pcfix38-wakecolor-20261111.patch`](graphics/patches/nootedgreen-pcfix38-wakecolor-20261111.patch) | 保留原生 10-bit `XRGB_2101010` 桌面与唤醒色彩归一化 | `xeNormalizePlane1AColor` 无损保留 `0x82000400` 10-bit 像素格式并置 `0x701CC -> 0x2000`、`0x4A480 -> 0` |
| `R32-PCFIX39..41` | [`nootedgreen-pcfix41-fastboot-20261112.patch`](graphics/patches/nootedgreen-pcfix41-fastboot-20261112.patch) | `~18.5s` 极速冷启动、零 `Camellia` Panic、512 MiB 孤儿池 | `HP-CAMELLIA-NULLGUARD` + `HP-ORPHAN-CAP` + `HP-QUIET-HOTPATH` + `HP-FASTBOOT` |
| `R32-PCFIX42..47` | [`nootedgreen-pcfix47-hdmi-20261113.patch`](graphics/patches/nootedgreen-pcfix47-hdmi-20261113.patch) | 机载 HDMI `DDI-B` 首次点亮 `2560×1440@59.875Hz` | `ConnectorHDMI` + GMBUS `busId=2` + `hpGetStreamAccessAUX` + `0xC5108` GMBUS2 轮询 |
| `R32-PCFIX49-HDMI` | [`nootedgreen-pcfix49-hdmi-20261114.patch`](graphics/patches/nootedgreen-pcfix49-hdmi-20261114.patch) | 双屏扩展（eDP 1080p + HDMI `2560×1440@60Hz`）消除超出范围 | 24-bit 8bpc RGB 过滤 + `0xf3518` DPLL 表重定位至 TGL ComboPHY `0x164284..0x164298` |
| **`R32-PCFIX50-HDMI`** | **[`nootedgreen-pcfix50-hdmi-20261114.patch`](graphics/patches/nootedgreen-pcfix50-hdmi-20261114.patch)** | **机载 HDMI 2.0b `600 MHz` `2560×1440@60/120/144Hz` 全通** | **扩展 `IOFBTimingRange` 至 `600 MHz` + GMBUS2 SCDC `0x54`/`0x20` 加扰与 1/40 时钟比 + `TRANS_DDI_FUNC_CTL_B` `HIGH_TMDS_CHAR_RATE`（`593.700000 MHz`，`0` Panic）** |

### 修复三：内置 SSD 启动 `pmap_recycle_page: page 0x101310000 is referenced` 内核崩溃根治（`PMAPFIX`）

- **根因定位**：
  - 用户观察到从内置 SSD 启动 macOS 后约 6–7 分钟锁屏黑屏后按任意键无响应。通过读取 EFI NVRAM 变量并编写 7-bit 无损解包器还原 `AAPL,PanicInfo0000..0003`（`panic-decoded.txt` SHA256 `d1c3e3018b832b524cd3a7df730de77428f372222540c8a42e6d29ec11b628e6`），查明系统从未进入睡眠（`Last Sleep: 0`），而是在开机 **394.46 秒（6 分 34 秒）** 触发了：
    `panic(cpu 6 caller 0xffffff800046709b): pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511`
  - 故障物理页 `0x101310000` 与此前 GA416/GA419 四次加速图形启动在 252–340 秒触发的 `pmap_recycle_page` 崩溃页（`0x101304000`、`0x10130e000`、`0x101313000`，详见 [`docs/GRAPHICS-STABILITY.md`](docs/GRAPHICS-STABILITY.md) 与 [`evidence/README.md`](evidence/README.md)）100% 落在同一个 **128 KiB 物理内存窗口（`0x101304000..0x10131c000`）**；同时 `boot-args` 中的 `debug=0x100100` 置位了 `DB_HALT`（`0x100`），使内核在打印 panic 后死循环停机在 `_kdp_i386_trap` 而不自动重启。
- **修复机制**：
  1. 在 OpenCore `config.plist` 的 `UEFI -> ReservedMemory` 中新增 `4 MiB` 物理内存保留条目（`Address = 0x101000000`、`Size = 0x00400000`、`Type = Reserved`、`Enabled = true`），使 XNU `pmap` 永不分配 `0x101000000..0x101400000` 物理页；
  2. 将 `boot-args` 中的 `debug=0x100100` 改为 `debug=0x100000`（去掉 `DB_HALT = 0x100`）。
- **实机验证效果**：在随后的 **连续 28 轮实机高负载压测及日常多日运行** 中，**`pmap_recycle_page` 崩溃发生率为 0%**。

### 修复四：Modern Standby `S0ix`、全外设驱动、蓝牙 `decmpfs` 锁页防崩与可复现 Nix Flake 工程体系

- **Nix Flake 持久化构建与发布校验**：基于 [`flake.nix`](flake.nix)、[`flake.lock`](flake.lock) 与 [`mac-for-elitebook/scripts/verify_release_artifacts.py`](mac-for-elitebook/scripts/verify_release_artifacts.py)，一键校验核心清单哈希、`436` 项部署包一致性、`111` 项 EFI 引导文件与 **`11` 项核心组件净室源码确定性重编译**。
- **ACPI 与外设全栈基线**：
  - [`EFI/ACPI/SSDT-DEEPIDLE.dsl`](EFI/ACPI/SSDT-DEEPIDLE.dsl)（Modern Standby `S0ix` + Darwin `\USWE = Zero` 禁 USB 唤醒）、[`EFI/ACPI/SSDT-EC0-ITLB.dsl`](EFI/ACPI/SSDT-EC0-ITLB.dsl)（修复 `PT04` 条件反转与 `EC12` 下限解决 `ICCMAX/PL4` 锁死）、[`EFI/ACPI/SSDT-EC-USBX-HP.dsl`](EFI/ACPI/SSDT-EC-USBX-HP.dsl)、[`EFI/ACPI/SSDT-RHUB-HP.dsl`](EFI/ACPI/SSDT-RHUB-HP.dsl)、[`EFI/ACPI/SSDT-PNLF-HP-GA419.dsl`](EFI/ACPI/SSDT-PNLF-HP-GA419.dsl)、[`mac-for-elitebook/acpi/SSDT-PLUG.dsl`](mac-for-elitebook/acpi/SSDT-PLUG.dsl)（另附早期归档参考 [`EFI/ACPI/SSDT-HP-Hotkeys.dsl`](EFI/ACPI/SSDT-HP-Hotkeys.dsl)）；
  - 机载原生 HDMI 2.0b `2560×1440@60/120/144Hz`（`R32-PCFIX50-HDMI`）、内置四扬声器/耳麦（`ALC285` + `SimpleHDA 1.0.1` + `AppleALC 1.9.8` + `hp-alc285-ampinit.sh`）、内置四通道数字麦克风（`TGLDmic.kext v0.5.0`）、eDP 原生亮度与事件驱动全套 Fn 热键（`PCFIX31` + `hp-cb-shim-loader.sh` + `hp-bridge` v3）、Wi-Fi 6（`AirportItlwm 2.4.0` AX201 原生 `en0` + 开机 `20s` 登录前 Tailscale 自连）、蓝牙（`mlock()` 锁页 + 48s DarkWake 根治 + idle HCI 自愈）、I²C 触控板（`SYNA30B6` 单指双击拖动与三/四指切换桌面）、`WACF4233` 触摸屏/手写笔（`PenBridge`）、PS/2 键盘、电池状态、Quanta `0408:5349` 720p 摄像头、`RidgeKey 1.0.0`（Synaptics `06cb:00f0` USB 指纹传感器）以及 `com.hp.syslogger` 跨关机持久化日志均已完成实机验证（详见 [`docs/STATUS.md`](docs/STATUS.md) 与 [`mac-for-elitebook/README.md`](mac-for-elitebook/README.md)）。

---

## 项目入口

| 内容 | 入口 |
| --- | --- |
| **全新重装与一键部署操作手册（2026-11-14）** | **[`mac-for-elitebook/docs/clean-install-guide.md`](mac-for-elitebook/docs/clean-install-guide.md)** |
| **从零源码净室重编译完整指南（2026-11-14）** | **[`mac-for-elitebook/docs/from-source-rebuild-guide.md`](mac-for-elitebook/docs/from-source-rebuild-guide.md)** |
| **安装、S0ix、声卡/DMIC、视频对齐与持久化日志主文档** | **[`mac-for-elitebook/README.md`](mac-for-elitebook/README.md)** |
| **2026-11-06 GPU Metal 加速、单端口 RCS 与 `PMAPFIX` 技术总结** | **[`mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md`](mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)** |
| **2026-11-05 Geekbench 6.5.0 Metal 8/8 全通记录（`R32-PCFIX2`）** | **[`mac-for-elitebook/docs/repair32-pcfix2-20261105.md`](mac-for-elitebook/docs/repair32-pcfix2-20261105.md)** |
| **2026-11-05 Horizon Detection 突破记录（`R32-ELSQWAIT`）** | **[`mac-for-elitebook/docs/repair32-elsqwait-20261105.md`](mac-for-elitebook/docs/repair32-elsqwait-20261105.md)** |
| 当前硬件支持矩阵与功能状态 | [`docs/STATUS.md`](docs/STATUS.md) |
| 实测图形源码（`NootedGreen` + `HookCase`）、补丁链与 SHA-256 清单 | [`graphics/README.md`](graphics/README.md) |
| OpenCore 配置示例与 ACPI 源码 | [`EFI/README.md`](EFI/README.md) |
| 外设适配现状与驱动深度调研（2026-11-04 早期归档） | [`mac-for-elitebook/docs/peripheral-adaptation-status-20261104.md`](mac-for-elitebook/docs/peripheral-adaptation-status-20261104.md)、[`mac-for-elitebook/docs/peripheral-driver-research-20261104.md`](mac-for-elitebook/docs/peripheral-driver-research-20261104.md) |
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
- **内屏：** IVO8596 `X133NVFF R0`，1920×1080@60Hz eDP（pipe A / DDI A / PHY A，2 lane，2.7 Gbps/lane，原生 10-bit）
- **外接显示：** 机载 HDMI 2.0b（`DDI-B / PHY B`, GMBUS `busId=2`），实测双屏扩展连接 ASUS VG27AQ5A `2560×1440@60/120/144Hz`（`593.70 MHz` SCDC + TGL ComboPHY DPLL）
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
