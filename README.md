# HP Elite Dragonfly G2 Hackintosh (macOS 26 Tahoe)

**macOS 26 Tahoe (`26.6.2` / `25G83`) on HP Elite Dragonfly G2 (`8716`, Intel Core i5-1135G7 / Iris Xe Graphics G7 `8086:9a49` GT2 80 EU / 5 DualSubslices, 16 GiB LPDDR4X-4266) — OpenCore 1.0.8 configuration, Tiger Lake Gen12LP Metal compute & scheduler adaptations, Nix Flake reproducible build toolchain, and verified hardware telemetry.**

这是 HP Elite Dragonfly G2 的 macOS 26 Tahoe 完整移植与内核/图形驱动逆向工程仓库，整合了安装与外设/图形耐力工程 [`mac-for-elitebook`](mac-for-elitebook/README.md)、已发布图形驱动源码与补丁链 [`graphics`](graphics/README.md) 以及历代 Tiger Lake 图形实验与工具集 [`tgl26-usb`](tgl26-usb/README.md)。

---

## 核心实机成果总览（2026-11-11）

1. **完整 macOS 26.6.2 (`25G83`) 系统安装、内置 NVMe SSD 独立引导与一键重装/净室重编译闭环**：
   - 原生 macOS 26 Tahoe（`26.6.2`，Build `25G83`，Darwin `25.6.0` / `xnu-12377.161.14~5`）已完整安装至内置 Micron 2210 NVMe SSD，并通过内置盘 `disk0s1` `/boot/EFI/OC`（OpenCore `1.0.8` `config.plist` `60,234` B SHA256 `f1f6b95569b7167ce3b166ca38b3f6bac7f8570dd14938187ebdb22090d3cf6b` + `R32-PCFIX37` `NootedGreen.kext` `540,944` B SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3`、UUID `4C4C44A8-5555-3144-A16C-16F349CEF835`，内置 ESP `/EFI/OC` `111/111` 文件及恢复镜像 `112/112` 文件均经回读逐字节核验一致）独立引导运行；完整全新重装流程与从零源码净室重编译指南见 [`mac-for-elitebook/docs/clean-install-guide.md`](mac-for-elitebook/docs/clean-install-guide.md) 与 [`mac-for-elitebook/docs/from-source-rebuild-guide.md`](mac-for-elitebook/docs/from-source-rebuild-guide.md)。
2. **Intel Iris Xe 80 EU Metal 硬件加速、三阶段耐力测试 100% 零挂死通关（[`R32-PCFIX27`](graphics/patches/nootedgreen-pcfix27-20261106.patch)）与 `420v` NV12 视频零绿屏渲染（[`R32-PCFIX35`](graphics/patches/nootedgreen-pcfix35-blitalign-20261108.patch)）**：
   - 在实机上 **100% 通过 GPU 三阶段稳定性与耐力实机测试计划**（`Trial 27` 与 `Trial 28`，全程净化并执行 **`705,024` 个计算编码器**，**全程 `0` 次 `GPU hang:`、`0` 次 `GPURestart`、`0` 次内核 panic**）：
     - **Stage 1（连续 3 轮完整 Geekbench 6.5.0 `--gpu Metal` 共 24 项计算工作负载）**：`enc=25,088 -> 50,176 -> 75,264`（`rc=0`，`hang_count=0`）；
     - **Stage 2（90 秒 4 线程 `metal-concurrent-stress` Blit+Compute 并发压测 + `WindowServer` 合成）**：`67,430` 批次、`404,570` 个编码器（`errors=0`，推进至 `enc#547,328`）；
     - **Stage 3（60 秒 RC6 深度休眠静置 + 30 秒 4 线程唤醒突发压测）**：`22,513` 批次、`135,068` 个编码器（`errors=0`，推进至 **`enc#705,024`**，详见 [`mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md`](mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)）。
   - **`HP-BLITALIGN`（[`R32-PCFIX35`](graphics/patches/nootedgreen-pcfix35-blitalign-20261108.patch)）+ `xe-h264sw-fixd`**：修复 Tiger Lake `420v` NV12 `IOSurface` 64 字节行距对齐与 Blit2D/SIMD16 路由，配合 `xe-h264sw-fixd` 热修补 `AppleH264SW` 双切片间隙拷贝并彻底省略不稳定 VDBOX 插件，消除 Safari / Bilibili / QuickTime 视频绿屏与花屏。
3. **Modern Standby `S0ix` 深度休眠唤醒（`51m 37s` 实测通过）、禁用 USB 误唤醒与唤醒零绿屏（[`SSDT-DEEPIDLE.dsl`](EFI/ACPI/SSDT-DEEPIDLE.dsl) + `S0ixStandby v0.4.4` + [`R32-PCFIX37`](graphics/patches/nootedgreen-pcfix37-wakergb-20261111.patch)）**：
   - 通过 [`SSDT-DEEPIDLE.dsl`](EFI/ACPI/SSDT-DEEPIDLE.dsl)（`371` B AML SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`：注入 `_SB.LID`/`_SB.SLPB` GPE `0x6E` 唤醒、`_SB.LPS0` / `PEPD._STA` 并在 Darwin 下置 `\USWE = Zero` 禁用 USB/XDCI/TBT `_PRW` 唤醒，仅保留开盖与电源键唤醒）、`S0ixStandby.kext`（`v0.4.4`，`74,584` B SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`：解除 PCI `PME_EN` + 屏蔽 GPE `0x6D`/`0x69` + 静默 `CNVW` BAR0/PCICMD）、[`R32-PCFIX32`..`PCFIX37`](graphics/patches/nootedgreen-pcfix37-wakergb-20261111.patch)（`ngreen-wake-plane-rgb-fix`：在睡眠/唤醒边界将 `PLANE_CTL_1_A [0x70180]` 从 Gen11 `0x82000400` 归一化为 Gen12 RGB `0x84000400`、置 `PLANE_COLOR_CTL_1_A [0x701CC] = 0x2000` 并清零 `CSC_MODE_A [0x4A480] = 0`）以及 `hp-wake-helper` `820 ms` 背光保持 + ColorSync/Gamma 重刷，打通 XNU `sleepType=7`（`acpi_idle_kernel()`）深度休眠与干净 RGB 唤醒（`PCFIX37` + `S0ixStandby v0.4.4` + `SSDT-DEEPIDLE` 新版已同步内置 ESP 待下次冷启动载入）。
4. **全外设驱动、守护进程稳固与持久化日志闭环**：
   - **声卡与四阵列数字麦克风**：Realtek ALC285 四扬声器 + 3.5 mm 耳麦自动切换（`SimpleHDA 1.0.1` + `AppleALC 1.9.8` `layout-id = 71` + `hp-alc285-ampinit.sh` + `hp-wake-helper`）与自研 Tiger Lake Intel cAVS 2.5 DSP（`sof-tgl.ri`）四通道麦克风驱动 `TGLDmic.kext v0.5.0`（`1,199,424` B SHA256 `b0d0715dfb49b6ea15208cdfa0f99373e2e62ee4e2a02448462252ef6721b416` + `TGLDmic.driver` CoreAudio HAL）；
   - **原生屏幕亮度与全套 Fn 热键**：[`R32-PCFIX31`](graphics/patches/nootedgreen-pcfix31-backlight-20261107.patch)（`AppleBacklightDisplay` + PCH PWM `0xc8254` 占空比同步）+ `hp-cb-shim-loader.sh` + 统一守护 `hp-bridge`（原生控制中心滑块、OSD HUD 与顶排 `Fn+F1`..`Fn+F11` 全覆盖；[`SSDT-HP-Hotkeys.dsl`](EFI/ACPI/SSDT-HP-Hotkeys.dsl) 作为早期 ACPI 方案归档留存，生产配置保持禁用）；
   - **内置 `06cb:00f0` 指纹解锁、蓝牙 `decmpfs` 锁页防崩、网络共存与持久化日志**：`RidgeKey 1.0.0`（`ridgekeyd` + `pam_ridgekey.so` + `RidgeKey.app` / `RidgeKeyAgent.app`）原生驱动内置 Synaptics `06cb:00f0` USB 指纹传感器，支持 `sudo`、系统认证弹窗与锁屏指纹解锁；`AirportItlwm 2.4.0` 原生 `en0` Wi-Fi 6；`hp-syslogger.py` 对 `/usr/sbin/bluetoothd` 执行 `MAP_PRIVATE | PROT_READ` + `mlock()` 锁页彻底消除 `BlueToolFixup` 热补丁页与 APFS `decmpfs` 16 KB 压缩簇换页校验冲突导致的 `error 94` (`EBADMSG`) `SIGBUS` 崩溃循环；配置 Unified Log `persist:info`、跨关机 `/var/log/hp/boot-<STAMP>-<UUID8>/` 归档与 `/etc/newsyslog.d/com.hp.conf` 轮转；完成 Clash Verge（`find-process-mode: 'off'`）与 Tailscale TUN/DNS/系统代理无损共存。
5. **内置 SSD 引导长稳运行零 Panic（`PMAPFIX` 根治 `pmap_recycle_page`）与可复现 Nix Flake 工具链**：
   - 隔离物理内存窗口 `0x101000000..0x101400000`（`4 MiB`）+ `debug=0x100000`，`pmap_recycle_page` 崩溃发生率 **0%**；基于 [`flake.nix`](flake.nix) / [`flake.lock`](flake.lock) 与 [`verify_release_artifacts.py`](mac-for-elitebook/scripts/verify_release_artifacts.py) 实现 `431` 文件部署包、`111` 文件内置 ESP（恢复镜像 `112` 文件）对等性及 `9/9` 核心组件净室重编译逐字节确定性核验。

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
- **修复机制**（[`graphics/src/NootedGreen/kern_gen11.cpp`](graphics/src/NootedGreen/kern_gen11.cpp)，计算耐力补丁 [`graphics/patches/nootedgreen-pcfix27-20261106.patch`](graphics/patches/nootedgreen-pcfix27-20261106.patch)，最新累积补丁 [`graphics/patches/nootedgreen-pcfix37-wakergb-20261111.patch`](graphics/patches/nootedgreen-pcfix37-wakergb-20261111.patch)）：
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
| **`R32-PCFIX36..37`** | **[`nootedgreen-pcfix37-wakergb-20261111.patch`](graphics/patches/nootedgreen-pcfix37-wakergb-20261111.patch)** | **唤醒立即归一化 Plane 1A RGB 与背光保持** | **`ngreen-wake-plane-rgb-fix` 将 `PLANE_CTL_1_A [0x70180]` `0x82000400 -> 0x84000400`、`0x701CC -> 0x2000`、`0x4A480 -> 0`（已同步内置 ESP）** |

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

- **Nix Flake 持久化构建与发布校验**：基于 [`flake.nix`](flake.nix)、[`flake.lock`](flake.lock) 与 [`mac-for-elitebook/scripts/verify_release_artifacts.py`](mac-for-elitebook/scripts/verify_release_artifacts.py)，一键校验核心清单哈希、`431` 项部署包一致性、`112` 项 EFI 引导文件与 `9` 项核心组件净室源码确定性重编译。
- **ACPI 与外设全栈基线**：
  - [`EFI/ACPI/SSDT-DEEPIDLE.dsl`](EFI/ACPI/SSDT-DEEPIDLE.dsl)（Modern Standby `S0ix` + Darwin `\USWE = Zero` 禁 USB 唤醒）、[`EFI/ACPI/SSDT-EC-USBX-HP.dsl`](EFI/ACPI/SSDT-EC-USBX-HP.dsl)、[`EFI/ACPI/SSDT-RHUB-HP.dsl`](EFI/ACPI/SSDT-RHUB-HP.dsl)、[`EFI/ACPI/SSDT-PNLF-HP-GA419.dsl`](EFI/ACPI/SSDT-PNLF-HP-GA419.dsl)、[`mac-for-elitebook/acpi/SSDT-PLUG.dsl`](mac-for-elitebook/acpi/SSDT-PLUG.dsl)（另附早期归档参考 [`EFI/ACPI/SSDT-HP-Hotkeys.dsl`](EFI/ACPI/SSDT-HP-Hotkeys.dsl)）；
  - 内置四扬声器/耳麦（`ALC285` + `SimpleHDA 1.0.1` + `AppleALC 1.9.8` + `hp-alc285-ampinit.sh`）、内置四通道数字麦克风（`TGLDmic.kext v0.5.0`）、eDP 原生亮度与全套 Fn 热键（`PCFIX31` + `hp-cb-shim-loader.sh` + `hp-bridge`）、Wi-Fi 6（`AirportItlwm 2.4.0` AX201 原生 `en0`）、蓝牙（含 `hp-syslogger.py` `MAP_PRIVATE | PROT_READ + mlock()` 锁页消除 APFS `decmpfs` `error 94` 崩溃）、I²C 触控板、PS/2 键盘、电池状态、Quanta `0408:5349` 720p 摄像头、`RidgeKey 1.0.0`（Synaptics `06cb:00f0` USB 指纹传感器）以及 `com.hp.syslogger` 跨关机持久化日志均已完成实机验证（详见 [`docs/STATUS.md`](docs/STATUS.md) 与 [`mac-for-elitebook/README.md`](mac-for-elitebook/README.md)）。

---

## 项目入口

| 内容 | 入口 |
| --- | --- |
| **全新重装与一键部署操作手册（2026-11-11）** | **[`mac-for-elitebook/docs/clean-install-guide.md`](mac-for-elitebook/docs/clean-install-guide.md)** |
| **从零源码净室重编译完整指南（2026-11-11）** | **[`mac-for-elitebook/docs/from-source-rebuild-guide.md`](mac-for-elitebook/docs/from-source-rebuild-guide.md)** |
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
