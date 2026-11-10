# HP Elite Dragonfly G2 → macOS Tahoe (26.6.2 / 25G83)

针对 **HP Elite Dragonfly G2**（主板号 `8716`，BIOS `T90 01.25.00`，`11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz` `4C/8T` / 真实 CPUID `0x806C1` model `140`、OpenCore 仿冒 `0x706E5` model `126` 启用 `MacBookPro16,2` `J214k` XCPM `39` 档 P-States `400..4200 MHz`，**Intel Iris Xe Graphics G7 `8086:9a49` B0 80 EU / 5 DualSubslices**，16 GiB LPDDR4x-4267；同代同平台参考机型 **HP EliteBook 840 G8** 主板号 `880D`，`11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz` `4C/8T`，睿频最高 `4.70 GHz`）运行原生 Intel 版 **macOS 26 Tahoe（`26.6.2` / `25G83`，Darwin `25.6.0`）** 的实机内核、图形加速、音频/DSP、UVC 摄像头、生物识别与 S0ix 现代待机全栈适配工程。

---

## 当前硬件适配总览 (Current Hardware Adaptation Matrix)

以下矩阵汇总本仓库在 **macOS Tahoe 26.6.2 (`25G83`)** 实机当前运行会话（冷启动零 ACPI 报错核验会话 `kern.bootsessionuuid = BEC29211-881D-4E0E-99CC-5EE3C76A6FF5`，以及 100 万编码器耐力压测与全外设深度审计会话 `3B5CD162-0254-4F60-B63B-17F9E6440352`，内置 Micron 2210 NVMe SSD `/boot/EFI/OC` 独立引导）上的最新在线核验状态（完整审计与压测报告见 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/peripheral-audit-report.json`、`.local/driver-repair-20261103/s0ix-standby-prep-20261107/endurance-1m-3b5cd162/endurance-1m-report.md` 与 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/coldboot-verification-bec29211.txt`）：

| 硬件子系统 | 驱动 / Kext / 用户态组件 | 版本 / 补丁与校验标识 | 实机验证状态 (`25G83`, 会话 `BEC29211` / `3B5CD162`) |
| --- | --- | --- | --- |
| **CPU & XCPM Power Management (`i5-1135G7` / `i7-1165G7`)** | OpenCore `Kernel -> Emulate` (`Cpuid1Data = E5060700...`) + `SSDT-PLUG.aml` (`\_SB.PC00.PR00`, `plugin-type = 1`) + `X86PlatformPlugin` (`ACPI_SMC_PlatformPlugin`) | OpenCore `1.0.8` CPUID 仿冒（真实 Tiger Lake `0x806C1` model `140` → Ice Lake-LP `0x706E5` model `126`）+ `MacBookPro16,2` (`J214k` / `Mac-5F9802EFE386AA28.plist`) | **已实机验证**：Dragonfly G2 (`8716`) 搭载 `11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz` (`4C/8T`)，EliteBook 840 G8 (`880D`) 搭载 `11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz` (`4C/8T`, Turbo 最高 `4.70 GHz`)；仿冒 `0x706E5` 后原生激活 `X86PlatformPlugin` (`J214k`, `machdep.xcpm.mode = 1`, `machdep.xcpm.vectors_loaded_count = 1`, `2` 个 `FrequencyVectors` 向量)，完整枚举 **`39` 档硬件 P-States（`400..4200 MHz`）**（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/xcpm-cpu-topology.txt`） |
| **Graphics & Display (`Intel Iris Xe G7 0x9a49`)** | `NootedGreen.kext` + AuxKC `/Library/Extensions/AppleIntelTGLGraphics*.kext` (`AppleIntelTGLGraphics.kext`, `AppleIntelTGLGraphicsFramebuffer.kext`, `HookCase.kext`) + `/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle` (`libxedrv.dylib`) + `/System/Library/Caches/xe.bundle` + `xe-h264sw-fixd` (`com.elitebook.h264swfix`) | `R32-PCFIX37-WAKERGB`（[`patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch`](patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch) `95,341` B SHA256 `d7b02ea9405468109fa755e4b4321768ef0c0ce722c183306529cc4d2ae1d4ea`；`kern_gen11.cpp` `707,888` B SHA256 `6c42d019445988feb826ac6581f2c0c90a34f0e1266436ef81eed35f03f2d240` → `Contents/MacOS/NootedGreen` `540,944` B SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3`，`LC_UUID` `4C4C44A8-5555-3144-A16C-16F349CEF835`；`libxedrv.m` SHA256 `ea4b9ec3c14a902863c1ce41fc3a6e40c54eb350d747833ad702087a69429406` → `libxedrv.dylib` SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`） | **已实机验证**：eDP 内屏 `IVO8596` (`X133NVFF R0`, `1920×1080@60Hz`, pipe A / DDI A / PHY A) 原生点亮；在 `isRealTGL && Tahoe` 分支启用 `HP-BLITALIGN`、`HP-BLITFIX`、`HP-BLIT16` 与 `xe-h264sw-fixd`（将软解 `420v` 32B 非 64B 对齐 `IOSurface` 平面路由至 `BCS0` `XY_SRC_COPY_BLT` 2D 拷贝并修复 `AppleH264SW` `fill_frame_num_gap`，根治 Safari 视频绿屏与卡顿），并通过 `PCFIX37` `xeNormalizePlane1ARgb` + `S0ixGPU` `PLANE_CTL_1_A` RGB 归一化消除唤醒绿屏；通过三阶段耐力压测（`705,024` 编码器）、5 轮（`381,118` 编码器）、10 轮（`644,116` 编码器）及 **Phase 8 超两百万编码器多子系统并发耐力压测**（最终 TCC 签名 10 轮套件 `111.02s` 完成 **`71,972` 批次 = `575,694` GPU 编码器**，Phase 8 两轮 10-round 套件共 **`1,006,546` 编码器**，`HP-PCFIX` 跨 5 次运行累计推进 `+1,435,904` 编码器达 **`enc#2,341,120`** / `pf=2,005,579`；并完成 `250/250` `CARenderer`、`300/300` `CoreImage`、`600/600` `MPS` `512x512` GEMM @ `166.0–182.4 GFLOPS` `max_abs_err = 0.0` 及全双工 `ALC285` `5,335,040` 帧 + `TGLDmic` 4ch `5,329,408` 帧），全程 **`0` 次 GPU 挂死/故障（`rf=0`, `wsk=0`, `sigCnt=0`, `recoveryCount=0`）** |
| **Backlight & Native Control Center Slider** | `NootedGreen` `-ngreenblr` (`PCFIX28` / `PCFIX30` 硬件 `SBLC_PWM_CTL2` `0xC8254`/`0xC8258` 缩放) + `SSDT-PNLF-HP-GA419.aml` + `hp-cb-shim.dylib` (`libhp_cb_shim.dylib` + `com.hp.cb-shim-loader`) + `hp-bridge` (`com.hp.bridge.agent`) | `hp-cb-shim 1.0`（`libhp_cb_shim.dylib` SHA256 `e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798`，`hp-cb-shim-loader.sh` SHA256 `a3de1c6667ae927ec9f166bcec7cdc27ef721bc9a8e19f31b03c4103f6008fb8`） | **已实机冷启动验证**：`com.hp.cb-shim-loader` 等待 `AppleBacklightDisplay` 与 `WindowServer` 就绪并经 `/private/var/run/com.apple.corebrightnessd-shim.plist` 执行加固的 **20 次 `launchctl bootstrap` 重试循环**，在冷启动会话 `A6D5C08D`（`pid=420`）与 `BEC29211`（`pid=466`）上均于 **`Attempt 1/20`（`runs = 1, last exit code = 0`，`0` 次 `Bootstrap failed: 5`）** 自动完成切换，恢复右上角控制中心与系统设置原生亮度滑块（`canChange=1 isBuiltIn=1`）；`hp-bridge` 提供 `F3`/`F4` 16 级亮度与 `F5`/`F6`/`F7`/`F8` 音量/静音原生 OSD 热键 |
| **Audio Output & Dual Microphone Input (`SimpleHDA` + `AppleALC` + `TGLDmic v0.5.0`)** | `SimpleHDA.kext` + `AppleALC.kext` + `hp-alc285-ampinit.sh` (`com.hp.alc285.ampinit`) + `TGLDmic.kext` + `TGLDmic.driver` (CoreAudio HAL) | `SimpleHDA 1.0.1` + `AppleALC 1.9.8`（Dragonfly G2 `8716` `layout-id = 71` / `31`；EliteBook 840 G8 `880D` `layout-id = 11` / `71`）+ `TGLDmic v0.5.0`（`sof-tgl.ri` DSP 固件） | **已实机验证**：完整枚举 **`5` 个 CoreAudio `bltn` `48 kHz` 设备**（`Built-in Speaker` `ID=48` 默认输出、`Built-in Headphones` / `Built-in Output` `ID=57`、`Built-in Microphone` `ID=67` 2ch 3.5mm 耳麦麦克风、`Built-in Line Input` `ID=76` `44.1 kHz`、以及 `Internal Microphone (TGLDmic)` `ID=84` 4ch 默认输入）；`hp-alc285-ampinit.sh` 下发 `Node 0x20 Coef 0x65 = 0x0000` 解锁扬声器功放并解除耳麦麦克风静音，输出与双麦克风输入（`TGLDmic` 4ch + `ALC285` 2ch）均经 `kAudioUnitSubType_DefaultOutput` 渲染回调与 `kAudioUnitSubType_HALOutput` Bus 1 采集回调实测通过（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/coreaudio-probe.log`） |
| **Webcam (`HP HD Camera`, `0408:5349`)** | `AppleUSBXHCISPT` (`HS02@14200000`) + `UVCAssistant` + `AVFoundation` + `VTDecoderXPCService` + `SSDT-RHUB-HP.aml` | Quanta Computer UVC USB 2.0 摄像头（`0408:5349` / `0x0408:0x5349`），免驱原生支持 | **已实机验证**：通过 `UVCAssistant` + `AVFoundation` 原生枚举 **`13` 种视频格式（最高 `1280x720@30fps` MJPEG `420v`）**，由 `VTDecoderXPCService` 软件 MJPEG 解码器以平均 **`5 ms` 解码延迟**稳定出帧；同复合设备伴生的 `HP IR Camera`（`640x360` Windows Hello 红外流）被干净忽略，不干扰 RGB 摄像头（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/avf-camera-test.log`） |
| **USB Fingerprint Sensor (`Synaptics 06cb:00f0`)** | `RidgeKey` (`ridgekeyd` + `pam_ridgekey.so` + `ridgekeyctl` + `ridgekey-sudo` + `ridgekey-admin` + `RidgeKey.app` + `RidgeKeyAgent.app`) | `RidgeKey 1.0.0`（`/usr/local/ridgekey/etc/trusted-clients` 制表符分隔 `0600 root:wheel` CDHash 白名单） | **已实机验证**：传感器 `06cb:00f0` 已绑定并录入 `2` 枚指纹（`right-thumb`、`right-index`），配合系统钥匙串（Keychain）密码托管，完整支持终端 `sudo`、系统管理员授权弹窗及锁屏界面指纹解锁 |
| **Wi-Fi 6 & Bluetooth (`Intel AX201` / `0x8087:0x0026`)** | `AirportItlwm.kext` + `IntelBluetoothFirmware.kext` + `IntelBTPatcher.kext` + `BlueToolFixup.kext` + `com.hp.bt-compat-check` + `com.hp.syslogger` (`mlock`) | `AirportItlwm 2.4.0` + `IntelBluetoothFirmware 2.5.2` (`ibt-19-0-4.sfi` `v8787`) + `BlueToolFixup 2.7.2` + `hp-syslogger.py` (`MAP_PRIVATE` + `mlock` 锁定 `/usr/sbin/bluetoothd` `11.2 MB` `__TEXT`) | **已实机验证**：Wi-Fi 6 (`802.11ax` 5 GHz) 原生挂载为 `en0`；蓝牙固件 `v8787` 加载成功，配合 Tahoe `bluetoothd` `--Compat` 自动剥离守护（`hp-bt-compat-check.sh`）及 `hp-syslogger.py` 内存页常驻锁定（消除 `BlueToolFixup` 就地补丁页与 APFS `decmpfs_pagein_compressed` 部分逐出导致的 `error 94` / `SIGBUS`）长稳运行，支持蓝牙外设与 A2DP/HFP 双向音频 |
| **Input & Touchscreen (`SYNA30B6` + PS/2 Keyboard + `WACF4233`)** | `VoodooPS2Controller.kext` (`VoodooPS2Keyboard`, `VoodooPS2SynapticsTouchPad`, `VoodooInput`) + `VoodooI2C.kext` (`VoodooGPIOTigerLakeLP` `INT34C5`) + `VoodooI2CHID.kext` | `VoodooPS2 2.3.7`（`24` 条自定义 JIS 顶排 ADB 映射）+ `VoodooI2C 2.9.1` | **已实机验证**：Synaptics `SYNA30B6`（`06cb:cd74` PS/2 + SMBus/I2C `TPD0` 触控板，经 `VoodooPS2SynapticsTouchPad` / `VoodooI2C` + `VoodooInput` 原生 `Magic Trackpad 2` 多指手势）+ PS/2 键盘（`24` 条自定义 JIS 与顶排热键映射）+ Wacom `WACF4233`（`056a:4924` I²C `TPL0` 触屏）全部正常工作（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/pcie-nvme-tb4-input-ridgekey.txt`） |
| **NVMe & Thunderbolt 4 / USB4 (`MTFDHBA512QFD` + `XHCI@D` + `TDM0@D,2`)** | `IONVMeFamily` + `NVMeFix.kext` + `AppleUSBXHCIPCI` (`XHCI@D` / `TXHC@D`) + `AppleUSBXHCISPT` (`XHCI@14`) + `S0ixStandby.kext` | `NVMeFix 1.1.3` + `S0ixStandby v0.4.4` | **已实机验证**：Dragonfly G2 (`8716`) 内置 Micron 2210 `MTFDHBA512QFD-1AX1AABHA` (`512.11 GB`, `1344:5404`) 通过 `NVMeFix.kext` 启用 **`ASPM L1`**；Intel Tiger Lake USB4/TBT4 `XHCI@D` (`8086:9a13`, `AppleUSBXHCIPCI`) 与 PCH `XHCI@14` (`8086:a0ed`, `AppleUSBXHCISPT`) 正常枚举，TBT4 主机路由器 DMA `TDM0@D,2` (`8086:9a1b`) 由 `S0ixStandby.kext v0.4.4` 主动置于 **PCI `D3hot`**（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/pcie-nvme-tb4-input-ridgekey.txt`） |
| **SMC Telemetry & Zero-Error Early ACPI (`VirtualSMC 1.3.7` + `SSDT-EC0-ITLB.aml`)** | `VirtualSMC.kext` + `SMCProcessor.kext` + `SMCBatteryManager.kext` + `ECEnabler.kext` + `SSDT-EC0-ITLB.aml` + OEM `SSDT13` (`HP_XHC_P`) Delete | `VirtualSMC 1.3.7` (`SMCProcessor 1.3.7` / `SMCBatteryManager 1.3.7`，预置 `1.3.8`) + `ECEnabler 1.0.6` + `SSDT-EC0-ITLB.aml` (`1,572` B, SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8`) | **已实机冷启动验证**：共注册 **`118` 个 SMC 键**（`111` 个可读、`6` 个只写 `0x85`、`1` 个 `EFBS`），实时上报 CPU 封装与 4 核温度（`TC0P`, `TC1C..TC4C`）、CPU/Package RAPL 功耗（`PC0C`, `PCPT`）及智能电池遥测（`B0RM`, `B0FC`, `B0AV`, `B0CT`, `BRSC`）；部署 `SSDT-EC0-ITLB.aml`（将 `ITLB` `BFC`、`EC12` `ACPR`、`EC13` `BDC`/`BDV` 与 `IETM.ODVP` 16-bit EC 读取全部拆分为 8-bit 读取）并删除 OEM `SSDT13`（`HP_XHC_P`）后，在冷启动会话 `BEC29211`、`EBABA2EE` 与 `B004F99C` 上实现 **全启动周期 `0` 次 `AE_NOT_FOUND`、`0` 次 `AE_BAD_PARAMETER`、`0` 次 `ACPI Error`/`ACPI Exception`**（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/dmesg-acpi-zeroerr-bec29211.txt`） |
| **S0ix Modern Standby (`S0ixStandby.kext v0.4.4` + `SSDT-DEEPIDLE.aml` + `R32-PCFIX37-WAKERGB`)** | `S0ixStandby.kext` (`-s0ixd3 -s0ixdbg -s0ixnogpureset -s0ixcnvwd3`，默认禁用 USB 唤醒) + `SSDT-DEEPIDLE.aml` (`371` B, `\_SB.LID` & `\_SB.SLPB` `_PRW`/`PRW0`/`_S0W` GPE `0x6E` + `\USWE = Zero`) + `NootedGreen` `XE-FBDPMS` + `PCFIX37` `xeNormalizePlane1ARgb` | `S0ixStandby v0.4.4`（`S0ixStandby.cpp` `71,761` B SHA256 `4eefd1a5e70e1416445c2adf517068386f7b6bc9616ec954ca1fde81c1dc756d` + `S0ixGPU.cpp` `30,611` B SHA256 `2309664fb9f08d8a554999c20b5e41f0549a83bf68459d9302938fec17b92199` → `S0ixStandby` `74,584` B SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`）+ [`SSDT-DEEPIDLE.dsl`](../EFI/ACPI/SSDT-DEEPIDLE.dsl) (`2,793` B, SHA256 `1f569b6bbb0d4305a27fcadeedf69a463c18f47b581d5140fb8acb2ecccfb1b9`) → `SSDT-DEEPIDLE.aml` (`371` B, SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`) + [`patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch`](patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch) | **已实机验证 (`B004F99C` 单次连续 `51.6 分钟` S0ix Deep Idle 休眠，`CC7 = 99%`, `PC3 = 99%`, `0` 次伪 `DarkWake`，开盖 `_Q0A` 即刻唤醒)**：恢复 `PEPD._DSM` Intel fn `3/5/6/4`（`EC0.SLPT = 6`），通过 `pmCPUHaltHook` 排空闭盖非唤醒电池 SCI、禁用 USB/XDCI/TBT 唤醒（`\USWE = Zero` + PCI `PME_EN` 清零 + `GPE 0x6D/0x69` 硬件屏蔽）、`CNVW` `BAR0` 复位 + `D3hot` + `XSQD` 清除、睡眠态关断 `PLANE_CTL_1_A` DRAM DMA 扫描并在唤醒时强制归一化 `0x70180 = 0x84000400` RGB 像素格式 |
| **OpenCore 1.0.8 Boot & `PMAPFIX` Memory Protection** | `OpenCore.efi` + `OpenRuntime.efi` + `DevirtualiseMmio` + `slide=0` + `UEFI -> ReservedMemory` (`0x101000000..0x101400000`) | OpenCore `1.0.8`（当前生产 `config.plist` `60,234` B SHA256 `f1f6b95569b7167ce3b166ca38b3f6bac7f8570dd14938187ebdb22090d3cf6b`，`ocvalidate` 0 错误） | **已实机验证**：隔离固件/链式引导脏物理页窗口 `0x101000000..0x101400000` (`4 MiB`)，在连续 28+ 轮 GPU 压测、8+ 小时通宵长稳运行及 100 万编码器耐力压测中 **`0` 次 `pmap_recycle_page` 内核崩溃** |

---

## 全新安装指南与自包含 U 盘恢复 / 后置驱动套件 (Clean Installation & Self-Contained USB Recovery/Post-Install Kit)

关于从零开始在 **HP Elite Dragonfly G2 (`8716`)** 或 **HP EliteBook 840 G8 (`880D`)** 上全新安装 macOS Tahoe 26.6.2 (`25G83`) 的完整 BIOS 设置、ESP/APFS 多系统分区、OpenCore 1.0.8 配置、外设部署步骤以及从源码重编译全套自定义组件的指南，请查阅完整专篇文档：

- **[HP Tiger Lake (Elite Dragonfly G2 / EliteBook 840 G8) 全新安装 macOS Tahoe 26 完整指南 (`docs/clean-install-guide.md`)](docs/clean-install-guide.md)**
- **[自定义组件源码索引与从源码重编译指南 (`docs/from-source-rebuild-guide.md`)](docs/from-source-rebuild-guide.md)**

### 1. 两阶段全新安装流程 (Two-Stage Installation Workflow)

由于 macOS Tahoe 26 原厂安装镜像不包含 Tiger Lake 用户态 Metal 补丁栈（`/Library/GPUBundles` 与 `/System/Library/Caches/xe.bundle`）及 AuxKC 扩展（`/Library/Extensions/AppleIntelTGLGraphics*.kext` + `HookCase.kext`），全新安装采用标准**两阶段流程**：
1. **Stage 1（VESA 安全帧缓冲模式安装基础系统）**：
   - 在引导 `config.plist` 中保持 `DevirtualiseMmio = true`、`slide=0`、`PMAPFIX` (`0x101000000..0x101400000` `ReservedMemory`)、`SSDT-RHUB-HP.aml`、`VoodooPS2`、`VoodooI2C` 与 `AirportItlwm` 启用，将 `NootedGreen.kext` 设为 `Enabled = false`（或添加 `-igfxvesa`）。
   - 从 Ventoy U 盘引导进入 macOS Recovery，挂载离线安装卷 `Tahoe-26.6.2-Offline-App.hfs`，将 macOS Tahoe 26.6.2 (`25G83`) 安装至目标 APFS 容器并完成 Setup Assistant 初始向导进入桌面。
2. **Stage 2 & Stage 3（部署 Iris Xe Metal 硬件加速栈、重建 AuxKC 与安装全套外设及持久化日志守护进程）**：
   - 进入桌面后直接运行随附 U 盘或内置 Windows `系统` 卷 `/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz` 中的 **431 文件一键后置适配套件**（或按 [`docs/clean-install-guide.md`](docs/clean-install-guide.md) 分步手工执行），自动完成 `/Library/Extensions`、`/Library/GPUBundles`（仅保留 `AppleIntelTGLGraphicsMTLDriver.bundle` 含新版 `libxedrv.dylib` SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2` 与 `AppleIntelGraphicsShared.bundle`，主动清理 `VADriver`/`VAME`）、`/System/Library/Caches/xe.bundle` 与 `/usr/local/libexec/xe-h264sw-fixd`（`24,496` B SHA256 `4e388dfd...`）部署、`codesign -f -s -` 重签名、`kmutil install --volume-root / --update-all --force` + `kcditto` AuxKC 重建，以及 Stage 3 音频（`ALC285` + `TGLDmic` + `hp-wake-helper`）、原生控制中心亮度滑块（`libhp_cb_shim.dylib` + `hp-bridge`）、蓝牙 `--Compat` 与 `decmpfs` 防护（`hp-bt-compat-check.sh`）、跨关机持久化日志与 `bluetoothd` 内存页常驻锁定（`hp-syslogger.py` `v1.1` + `/etc/newsyslog.d/com.hp.conf`）及 `RidgeKey` 指纹套件安装。
   - 将内置 NVMe ESP (`/boot/EFI/OC`) 切换为启用 `R32-PCFIX37-WAKERGB` `NootedGreen.kext`（`540,944` B，SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3`）、`S0ixStandby.kext`（`v0.4.4`，`74,584` B SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`）、`SSDT-DEEPIDLE.aml`（`371` B，SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`）与 `SSDT-EC0-ITLB.aml` 的生产级配置并重启，即可进入完整硬件加速、全外设就绪且零 ACPI 报错的 macOS Tahoe 桌面。

### 2. 全功能 Ventoy 恢复引导镜像 (`HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`)

- **镜像名称与路径**：`HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`（本地归档于 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`，配合 `/Volumes/Yan/ventoy/oneshot.env` SHA256 `5997e0c9cdb86282bf8e82601478a125b0f549271afabde6cd48a43f70bfda20`）。
- **大小与校验值**：`1,343,225,856` 字节，SHA256 **`4ab8aff3a2f65cfc126faf19c9334798ef623a8dfbbe534ec78ede7f968850c9`**（`fsck.vfat -n` 零错误通过）。
- **封装内容**：在 FAT32 ESP 分区（偏移 `@@1048576`）中完整内置经 OpenCore 1.0.8 `ocvalidate` 零问题校验的 **111 个文件 `/EFI/OC` 引导树**（含 `config.plist` `60,234` B SHA256 `f1f6b95569b7167ce3b166ca38b3f6bac7f8570dd14938187ebdb22090d3cf6b`、`SSDT-EC0-ITLB.aml` SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8`、`SSDT-DEEPIDLE.aml` `371` B SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`、`R32-PCFIX37-WAKERGB` `NootedGreen.kext` `540,944` B SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3` `LC_UUID` `4C4C44A8-5555-3144-A16C-16F349CEF835`、`Info.plist` SHA256 `b5fd1d0fe125a48f6045c3b07a8f5894f76fc406caf5065f126830a63ea4738e`、`S0ixStandby.kext v0.4.4` `74,584` B SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`、`TGLDmic.kext v0.5.0`）以及 macOS Tahoe 26.6.2 (`25G83`) 恢复镜像 `/com.apple.recovery.boot/{BaseSystem.dmg,BaseSystem.chunklist}`。

### 3. 自包含 431 文件一键后置安装与验收套件 (`/Volumes/Yan/HP-Tahoe-PostInstall-20261108/` & `/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`)

在随附 Lexar U 盘 `/Volumes/Yan/HP-Tahoe-PostInstall-20261108/`、内置 Windows NTFS `系统` 卷 `/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`（及本地压缩归档 `HP-Tahoe-PostInstall-20261108.tar.gz`，`125,569,879` 字节，SHA256 `2f22d03e886773194337281491433b22ea87af1395b26d5e54eb8289020177aa`；逐文件校验清单 `SHA256SUMS.txt` `64,420` 字节 SHA256 `65ff4c05fd4f90f0895deed5de3068bd5db62f069318c7ab13b23e4427a5e8e6`；套件回执 `bundle-receipt.json` `5,310` 字节 SHA256 `68491a70c925c3e1b1ede2b078c6236a1b72b02e5a3eba7c0eb37417d9212a2e`）中，封装了从实机稳定会话提取并脱敏的全部 **431 个文件**（涵盖 111 文件 `EFI-OC/`、`stage2-gpu/`、`stage3-audio/`、`stage3-brightness-hotkeys/`、`stage3-bluetooth/`、`stage3-logging/`、`stage3-ridgekey/` 以及 `test_420v_blitalign` `51,680` B SHA256 `887743ebd0b11797fa46553fa2420df21adf266c76ce6d0d540ac51e415e75bf` 与 `verify-phase10-lidwake-and-video.sh` `7,639` B SHA256 `eeebfac56d8e79b59fc42db33e3672112d9eeb8bf136148018ac5024762ea218`）：

```sh
# 1. 校验 431 个文件的 SHA256 完整性
cd /Volumes/Yan/HP-Tahoe-PostInstall-20261108 && shasum -a 256 -c SHA256SUMS.txt

# 2. 一键自动安装 Stage 3 外设/持久化日志 + Stage 2 Iris Xe GPU 驱动并重建 AuxKC
#    (install-all-postinstall.sh SHA256: 1d6401cf7dc2637454ca14d98b9c54f3c9f1dc541a975c7788f1612960e62b35)
#    (内部依次调用 install-stage3-peripherals.sh [81fbce36...] 与 install-stage2-gpu.sh [ddaaea8f...])
sudo /Volumes/Yan/HP-Tahoe-PostInstall-20261108/install-all-postinstall.sh

# 3. 运行非破坏性一键全系统验收脚本
#    (verify-postinstall.sh 8,852 B SHA256: 499ac36510ffa2c67bf492330377dc7577dc719853fe8280a94ed00e19319387)
/Volumes/Yan/HP-Tahoe-PostInstall-20261108/verify-postinstall.sh

# 4. 在本地开发机运行端到端发布产物、9/9 无尘源码重编译与实机 NixOS 一致性校验（scripts/verify_release_artifacts.py 110,025 B SHA256: d66a58b9245f8e03b2a05cc9d2c721828a951b350113e6b34357285aa55ff161）
nix develop -c make verify-release
nix develop -c python3 scripts/verify_release_artifacts.py --check-source-rebuilds --check-live-nixos <user>@<nixos-host>
```

---

## 核心技术成果与实机耐久验证摘要

1. **完整 macOS 26.6.2 (`25G83`) 系统安装、内置 NVMe SSD 独立引导与自包含恢复套件**：
   - 已将完整 macOS 26.6.2（`25G83`）安装至内置 Micron 2210 NVMe SSD (`MTFDHBA512QFD-1AX1AABHA`, `512.11 GB`, `ASPM L1`)，并在内置 EFI 分区（`disk0s1` `/boot/EFI/OC`，回读归档 `after-lidwake-greenfix-boot-oc.tar` SHA256 `a2fe4a561a09dee92baa64558d9a0883cd099f6de765a7d9dee321182237ded2`）与外置 Ventoy 恢复镜像（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`，`1,343,225,856` B，SHA256 `4ab8aff3a2f65cfc126faf19c9334798ef623a8dfbbe534ec78ede7f968850c9`）同步部署 111 文件生产级 OpenCore 1.0.8 引导树（`config.plist` `60,234` B SHA256 `f1f6b95569b7167ce3b166ca38b3f6bac7f8570dd14938187ebdb22090d3cf6b`、`SSDT-EC0-ITLB.aml` SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8`、`SSDT-DEEPIDLE.aml` `371` B SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`、`S0ixStandby.kext v0.4.4` `74,584` B SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`）与自定义交叉编译签名的 `R32-PCFIX37-WAKERGB` `NootedGreen.kext`（`kern_gen11.cpp` SHA256 `6c42d019445988feb826ac6581f2c0c90a34f0e1266436ef81eed35f03f2d240` → `Contents/MacOS/NootedGreen` `540,944` B SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3`、UUID `4C4C44A8-5555-3144-A16C-16F349CEF835`，合入 [`patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch`](patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch)）。
   - 全系统外设（XCPM `39` 档 P-States `400..4200 MHz`、eDP 内屏与控制中心原生亮度滑块、`hp-bridge` 顶排 16 键及 24 键 JIS 快捷键、CoreAudio `5` 设备枚举与 `ALC285` 2ch + `TGLDmic v0.5.0` 4ch 双麦克风输入、Quanta `HP HD Camera` `0408:5349` UVC 摄像头、`AirportItlwm` AX201 Wi-Fi 6、蓝牙 `8087:0026` + `hp-syslogger.py` `mlock` 防 `decmpfs` 逐出崩溃与跨重启持久化日志体系、`SYNA30B6` 触控板 + `WACF4233` 触屏、`RidgeKey` `06cb:00f0` 指纹解锁、`VirtualSMC 1.3.7` `118` 键温度/功耗/电池遥测、`NVMeFix` `ASPM L1`、`TDM0@D,2` TBT4 DMA `D3hot` 及 `S0ixStandby v0.4.4` 51.6 分钟连续 S0ix 现代待机）均已在实机完整系统中完成集成与冷启动/S0ix 唤醒验收（冷启动 `BEC29211`、S0ix 唤醒 `EBABA2EE` 与 `B004F99C` 均 `0` ACPI 报错、`0` 内核 Panic、`0` GPU 挂死，详见 [`docs/continuation.md`](docs/continuation.md)）。
2. **Iris Xe 80 EU Metal 硬件加速、三阶段耐力测试与 5 轮 / 10 轮 / Phase 8 超两百万编码器（`enc#2,341,120`）多子系统并发压测 100% 零挂死通关**：
   - **三阶段 GPU 稳定性与耐力测试计划**（[`Trial 27` 与 `Trial 28`](docs/repair32-gpu-stability-and-pmapfix-20261106.md)，对应补丁 [`patches/nootedgreen-r32-pcfix27-20261106.patch`](patches/nootedgreen-r32-pcfix27-20261106.patch)）：单次启动连续净化并执行 **705,024 个 Metal 计算编码器**（Stage 1 连续 3 轮 24 项 Geekbench 6.5.0 Metal 工作负载 + Stage 2 90 秒 4 线程 `metal-concurrent-stress` `67,430` 批次 / `404,570` 编码器 + Stage 3 60 秒 RC6 静置与 30 秒唤醒突发 `22,513` 批次 / `135,068` 编码器），全程 **0 次 `GPU hang:`、0 次 `GPURestart`、0 次内核 panic**。
   - **`R32-PCFIX33-S0IX` 5 轮、10 轮与 Phase 8 超两百万编码器多子系统混合负载压测（会话 `3B5CD162-0254-4F60-B63B-17F9E6440352`）**：
     - **5 轮 Metal 3D+Compute+Blit 压测**：完成 **`47,645` 个命令批次 / `381,118` 个 GPU 编码器**，CPU 读回校验 `0` 错误；
     - **10 轮（`120.4s`）多媒体与计算混合并发压测**：完成 **`80,525` 个批次 = `644,116` 个 GPU 编码器**（`80,525` 3D Render + `483,066` Compute + `80,525` Blit）、`250` 次 CoreImage、`600` 次 MPS `512x512` GEMM（`188.87–195.79 GFLOPS`，`max_abs_err = 0.0`）、`100` 帧 H.264 + `100` 帧 HEVC 1080p 及 `5` 轮 4ch `TGLDmic` 采集，`HP-PCFIX` 累计净化编码器推进至 **`enc#905,216`**；
     - **Phase 8 超两百万编码器多子系统全双工耐力基准压测**（`.local/driver-repair-20261103/s0ix-standby-prep-20261107/endurance-1m-3b5cd162/endurance-1m-report.md`）：最终 TCC 签名 10 轮套件（`111.02s`）单次完成 **`71,972` 个命令批次 = `575,694` 个 GPU 编码器**（`71,972` 3D Render + `431,750` Compute + `71,972` Blit；Phase 8 两轮 10-round 套件共完成 **`1,006,546` 个编码器**，`HP-PCFIX` 跨 5 次运行记录 `5,609` 个连续 256-encoder 里程碑、累计推进 `+1,435,904` 个编码器至 **`enc#2,341,120`** / `pf=2,005,579`）、**`250/250` 帧 `QuartzCore` `CARenderer`（`1024x1024`）**、**`300/300` 次 `CoreImage` 6 级滤镜链（`512x512`）**、**`600/600` 次 `MPSMatrixMultiplication` `512x512` FP32 矩阵乘法（`166.0–182.4 GFLOPS`，`max_abs_err = 0.0`）** 及 **10 轮并发全双工 CoreAudio 回环（`Built-in Speaker` `ID=48` `10,420` 回调 / `5,335,040` 帧 + `Internal Microphone (TGLDmic)` `ID=84` 4ch `10,409` 回调 / `5,329,408` 帧，`99.9978%` 非零采样，`RMS = -32.81 / -34.38 dBFS`）**，全程 **`rf=0`、`wsk=0`、`sigCnt=0`、`recoveryCount=0`、`Swapouts=0`**。
3. **RCS 单端口无抢占 Execlist 调度与 GPU Reset 100% 无损自愈**：
   - 100% 消除了 `WindowServer`（Context `0xa0`）与 Metal 计算上下文（Context `0x5c0` / `0xcc0`）并发时的宿主软件 mid-batch 抢占、Port 0 覆盖（`ExecListQueueFull = 0x4000219a`）、双端口 `Port1`（`EL[1]`）填充、同上下文 `LITE_RESTORE`（`0x8002`）及 `EXECLIST_STATUS` `0x3098 -> 0x40002098`（`NO ACTIVE ELEMENTS`）硬件仲裁冻结。
   - 在极端耐力对照试验触发 Watchdog 时，`XeNG GPUREC: reset RCS ret=1` 实现 **100% 干净自愈恢复**（无需重启系统即可继续高速执行后续数千个计算编码器）。
4. **内置 SSD 引导长稳运行零 Panic（根治 `pmap_recycle_page`）**：
   - 定位并隔离了内置硬盘链式引导遗留的物理内存脏页窗口 `0x101000000..0x101400000`（`4 MiB`），彻底消除了内置盘启动后约 6 分 34 秒必现的 `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511` 内核崩溃；在连续 **28+ 轮**实机高负载耐力测试与长稳运行中 **0 次 `pmap_recycle_page` 崩溃**。
5. **可复现 Nix Flake 工具链与双系统无人值守闭环验证体系**：
   - 基于 [`flake.nix`](flake.nix) 与 [`flake.lock`](flake.lock) 封装完整 LLVM 21 / `ld64` / `rcodesign` / `grub2` / `mtools` 交叉构建环境，配合 NixOS ↔ macOS 身份守卫自动回程、7-bit `AAPL,PanicInfo` 无损往返解码与硬件寄存器快照采集。

---

## 四大核心技术修复详解

完整逆向工程证据、寄存器转储与 **28 轮**对照实验数据（`Trials 1–28`）详见 **[`docs/repair32-gpu-stability-and-pmapfix-20261106.md`](docs/repair32-gpu-stability-and-pmapfix-20261106.md)**，S0ix 现代待机与外设全栈集成详见 **[`docs/continuation.md`](docs/continuation.md)** 与 **[`docs/clean-install-guide.md`](docs/clean-install-guide.md)**。

### 修复一：Tiger Lake (Gen12LP) RCS Execlist 提交队列竞争、跨上下文抢占与无损单端口调度（`ELSQWAIT` + `PCFIX5` + `PCFIX6`）

- **根因定位**：
  1. **ELSQ 门铃重入竞争（`[0x2234] = 0x4000219a` `ExecListQueueFull`）**：`AppleIntelTGLGraphics` 在向 RCS 写 `ELSQ` 并敲击门铃 `0x2550 = 1` 时，若 `GFXREG_RCS_EXECLIST_STATUS [0x2234]` bit 30（`0x40000000`）仍置位，仅 39 微秒后的高频提交就会导致 `[0x2234]` 变为 `0x4000219a`（`ExecListQueueFull`），触发硬件在 `GPGPU_WALKER`（`[0x2148] BB_PREEMPT_ADDR = 0x4ecee114`）中途强制抢占。
  2. **软件 mid-batch 抢占与双端口 `0x3098 -> 0x40002098`（`NO ACTIVE ELEMENTS`）冻结**：当 `WindowServer`（Context `0xa0`）与 Geekbench Metal（Context `0x5c0` / `0xcc0`）并发时，即使关闭软件 mid-batch 抢占（`BB_PREEMPT_ADDR = 0`），只要 `evalWorkQueues` 在 `Port0=0x5c0` 活动期间（`[0x2234] = 0x00003098`）装填双端口 `Port0=0x5c0, Port1=0xa0` 并敲门铃，硬件在 **4 微秒**内即从 `0x00003098` 跌落为 **`0x40002098`**（`CurrentActiveElementStatus = NO ACTIVE ELEMENTS`），产生 `LITE_RESTORE`（`0x8002`）并触发 `Port0 -> Port1` 硬件元素切换（`LastContextSwitchReason = 0x104 ELEMENT_SWITCH | WAIT_ON_SCANLINE`），隐式注入上下文保存刷新锁死于 `CSFLTRK = 0x1c000001`。
- **修复机制**：
  - **无条件 `elsqWait`**（[`patches/nootedgreen-r32-elsqwait-20261105.patch`](patches/nootedgreen-r32-elsqwait-20261105.patch)）：在 `xePrepSubmit` 与 `xeCs5Submit` 中对任意 `([0x2234] & 0x40000000U) != 0` 实施轮询排空等待；
  - **线程组抢占粒度与每上下文控制**：编程 `GFXREG_CS_CHICKEN1 [0x2580] = 0x00020002`（`WaDisableGPGPUMidThreadPreemption`，将 GPGPU 抢占从 mid-thread 改为线程组级 `01b`）并在引擎启动与复位列表中清零 `0x20e0` bit 14（`0x40000000`）；
  - **阻断宿主软件 mid-batch 抢占**（[`patches/nootedgreen-r32-pcfix5-20261105.patch`](patches/nootedgreen-r32-pcfix5-20261105.patch)）：挂钩 `IGScheduler5::updateOptions`（`0x385e0`）、`allowPreemption`（`0x3d9a6`）、`isPreemptionAllowed`（`0x3d9d2`）清零 `cs[0x1c50]`、`cs[0x1c5d]` 与 `sched[0x0c] bit 2`；
  - **无损单端口 RCS 策略 `HP-SINGLEPORT-RCS`**（[`patches/nootedgreen-r32-pcfix6-20261105.patch`](patches/nootedgreen-r32-pcfix6-20261105.patch)）：挂钩 `dequeueExecList`（`0x3b3b6`）在 `Port0` 活动或提交在途（`el[cur][0] != 0 || !cs[0x1c3c]`）时延迟出队（由 `ACTIVE_TO_IDLE` CSB 中断自动触发重出队，零饥饿风险），并通过 `evalWorkQueues`（`0x3d5d0` `f_rcs1_hp` 将第 2 个上下文未消费的 ring 读指针 `%r12` 写回 `workQueue+0x4040`）与 `evalWaitQueue`（`0x3b971` `f_wait1_hp`）阻止填充 `Port1`（`EL[1]`），实现全程 `ELR1 = 0`、`0` 次 `LITE_RESTORE`、`0` 次 `0x40002098` 冻结，以及 `XeNG GPUREC: reset RCS ret=1` 100% 干净恢复。

### 修复二：`AppleIntelTGLGraphicsMTLDriver`（`COCLGen8CommandTransport`）Gen8 遗留计算编码器就地净化与 `CSFLTRK [0x2208]` 刷新跟踪器解耦（`PCFIX2` ~ `PCFIX33`）

- **根因定位**：
  通过 `rea`（Ghidra `12.1.4`）反编译 `IntelMTLComputeFunctions::execute`（`0x6bf20`）、`ResetPreambleCmds`（`0x378e8`）、`BuildPreambleCmds`（`0x38c48`）与 `AddPipeFlushCmd`（`0x37a0e`），查明 macOS Tahoe 的 Metal 计算命令传输层直接沿用了 Gen8 `COCLGen8CommandTransport`。在同一 4 KB 页内合并至多 5 个 151-dword 子分配计算编码器（`endOffDw = 95, totalDw = 151`，编码器 `k=0..4` 位于 `&page[151 * k]`，前一编码器末尾 `dw[150]` 的 `MI_BATCH_BUFFER_END` `0x05000000` 被清零为 `MI_NOOP`）时，存在四处硬件级冲突：
  1. `ResetPreambleCmds`（`dw[0..32]`）发射了两个未置 `CS_STALL`（`0x00100000`）的 `PIPE_CONTROL 0x00000480`（`TEXTURE_CACHE_INVALIDATE`），以及 Gen8 专属的 `MI_LOAD_REGISTER_IMM 0xb134`（`dw[15..17]`，Gen8 `L3ALLOC`，在 Gen12LP Tiger Lake 上破坏 L3/HDC 分配）；且在 `dw[+12]` `PIPELINE_SELECT = GPGPU`（`0x69040001`）之后，Packet 3（`dw[+18..+23]`）再次发射含 `0x1000 RT_CACHE_FLUSH` 的 `0x001010a0U`，在 GPGPU 管线模式下重新锁存 `CSFLTRK bit 28`（`0x10000000`）；
  2. 多个计算编码器串联时均走 `0xac == 1` 慢路径而从不发射 `MEDIA_STATE_FLUSH`（`0x70040000`）；
  3. 编码器末尾 `AddPipeFlushCmd`（`dw[83..94]`）发射了 `7a000004 001044a0 <m_pScratchPage+0x10> 0 0 0`，在同一 `PIPE_CONTROL` 包内同时混用虚拟 `POST_SYNC_OP = Write Immediate`（`0x4000`）、读缓存失效 `TEXTURE_CACHE_INVALIDATE`（`0x400`）与写缓存刷新 `DC_FLUSH_ENABLE`（`0x20`）。
  4. `HP-SLICE` 硬件子切片遥测证实：挂死瞬间全部 5 个活动子切片（80 个 EU）100% 空闲完成（`SC_INSTDONE = 0xffffffff`、`ROW_INSTDONE[0..4] = 0xffffffff`、`SAMPLER_INSTDONE[0..4] = 0xffffffff`、`FAULT_REG = 0x00000000`），死锁 100% 发生在前端 Command Streamer Flush Tracker（`CSFLFLAG [0x2204] = 0x50000000`、`CSFLTRK [0x2208]`）。
- **修复机制**：
  - 在 `nativeRowPrefix` 写入 `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`；
  - 启用 `IntelAccelerator+0xf42 bit 0`（`_WA_TABLE+0x14 bit 0`）使 `AddPipeFlushCmd` 分配 12-dword 双包空间（`endOffDw = 95, totalDw = 151`）；在 `PCFIX25` / `PCFIX26` 中验证了通过 `that[0xf5f] |= 0x80U`（`0x7010 = 0x20002000`）与 `that[0xf68] |= 0x01U`（`0x20d8 = 0x00100010`）将 `CS_DBG1` 与 `CHKN3` 捕获进黄金上下文镜像 `_safeHardwareContextBufferRCS` 实现跨上下文持久化的硬件机制，并在 **`PCFIX27`**（[`patches/nootedgreen-r32-pcfix27-20261106.patch`](patches/nootedgreen-r32-pcfix27-20261106.patch)）及后续 **`PCFIX33-S0IX`**（[`patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch`](patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch)）中回退会产生副作用的 `0x7010`/`0x20d8`/`0x2050`，在干净 `PCFIX20` 基底上完成 `CSFLTRK bits 28..25 = 0000b` 收官；
  - 挂钩 `IntelMTLComputeFunctions::execute`（仅针对计算编码器提交 token `eToken == 0x40001U` 调用 `hpSanitizeComputeEncoder`）：
    - **前导净化（`ResetPreambleCmds` `dw[0..32]`，`PCFIX27` 决定性修复）**：保留位于 `PIPELINE_SELECT = GPGPU`（`dw[+12]`）之前的 Packet 1 `dw[+1] = 0x001010a0U`（`CS_STALL | RT_CACHE_FLUSH | DC_FLUSH_ENABLE | FLUSH_ENABLE`，在 EU 空闲期排空并引退 3D/环级 `commitStampCommand` `0x40105021` 遗留的 Render Target Cache），将 `dw[+7] = dw[+25]` 补齐 `CS_STALL` 为 `0x00100480U`（不含 `0x0800 STATE_CACHE_INVALIDATE`），将 `dw[+15..+17]`（原 Gen8 `LRI 0xb134`）就地替换为 `MEDIA_STATE_FLUSH`（`0x70040000U, 0U`）+ `MI_NOOP`（`0U`），并将紧随 `MEDIA_STATE_FLUSH` 之后的 **Packet 3（`dw[+19]`）从 `0x001010a0U` 改写为 `0x001000a0U`**（剥离 GPGPU 模式下的 `0x1000 RT_CACHE_FLUSH` 重新锁存，严格遵循 `MEDIA_STATE_FLUSH -> PIPE_CONTROL(0x001000a0U)` 顺序定律使 `CSFLTRK bit 28` 引退清零为 `0`）；
    - **尾声净化（`AddPipeFlushCmd` `dw[83..94]`）**：剥离 `0x4000`（虚拟 Scratch 页 `POST_SYNC_OP` 写立即数）并将读写刷新解耦为写刷新 `Packet 0 = 0x001000a0U`（`dw[83..88]`）+ 读失效 `Packet 1 = 0x00100480U`（`dw[89..94]`）双包拆分，将 `GPGPU_WALKER` 周期的 `CSFLTRK bits 27..25` 彻底引退清零，最终实现同一编码器周期内 **`CSFLTRK bits 28..25 = 0000b` 全清零**。

| 代表性版本 | 补丁文件 | `ResetPreambleCmds` (`dw[0..32]`) | `AddPipeFlushCmd` (`dw[83..94]`) 及硬件 / 电源修复 | `CSFLTRK [0x2208]` | 实机验证结果 |
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
| **`R32-PCFIX32-S0IX`** | [`nootedgreen-r32-pcfix32-s0ix-20261107.patch`](patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch) | 同 `PCFIX27` | 新增 `-ngreenblr` (`PCFIX28`/`30`) + `hwSaveNVRAM` 空返回桩 + `FB1`/`FB2` 睡眠拦截 | **N/A (`0` hang)** | 根治 macOS Tahoe 睡眠触发 `IODTPlatformExpert::_RESERVEDIODTPlatformExpert1` 内核 Panic 重启 |
| **`R32-PCFIX33-S0IX`** | [`nootedgreen-r32-pcfix33-s0ix-20261108.patch`](patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch) | 同 `PCFIX27` | 新增 `XE-FBDPMS` `IOFramebuffer::handleEvent` 路由 + `hpCsResetOnWake` (`cs + 0x10` ForceWake & `HWS_PGA` 保留) + **Phase 10 `isRealTGL && Tahoe` 启用 `HP-BLITALIGN` / `HP-BLITFIX` / `HP-BLIT16`** | **N/A (`0` hang, `rf=0`, `recoveryCount=0`)** | 5 轮（`47,645` 批次）、10 轮（`80,525` 批次 = `644,116` 编码器）与 Phase 8 超两百万编码器耐力压测（最终 10 轮 TCC 套件 `71,972` 批次 = `575,694` 编码器，两轮 10-round 共 `1,006,546` 编码器，`HP-PCFIX` 累计至 `enc#2,341,120`）`0` 故障，并在 `isRealTGL && Tahoe` 下启用 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16` 根治 `420v` 非对齐 `IOSurface` 绿屏/卡顿 |
| **`R32-PCFIX37-WAKERGB`** | [`nootedgreen-r32-pcfix37-wakergb-20261111.patch`](patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch) | 同 `PCFIX27` | 继承 `PCFIX33–36` 并新增 `xeNormalizePlane1ARgb()`（全程拦截 `PLANE_CTL_1_A` `0x70180` Gen11 `0x82000400` YUV 编码并归一化为 Gen12 RGB `0x84000400`）+ 真实桌面翻转地址校验背光锁 | **N/A (`0` hang, `rf=0`, `recoveryCount=0`)** | **当前生产版本（`NootedGreen` `540,944` B SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3`, `LC_UUID` `4C4C44A8-5555-3144-A16C-16F349CEF835`）**：协同 `S0ixGPU.cpp` 与 `hp-wake-helper` 根治 S0ix / 熄屏唤醒绿屏 |

### 修复三：内置 NVMe SSD 启动 `pmap_recycle_page: page 0x101310000` 内核 Panic 根治（`PMAPFIX`）

- **根因定位**：从内置硬盘 `/boot/EFI/OC`（经 `systemd-boot` 链式加载）启动进入 macOS 后约 `252s ~ 394s`（6 分 34 秒），XNU VM 页面回收器在 `_vm_page_free_list -> pmap_recycle_page` 必现断言崩溃 `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511`。通过离线解码 EFI NVRAM `AAPL,PanicInfo0000..0003` 确认历次崩溃页（`0x101304000`、`0x10130e000`、`0x101310000`、`0x101311000`、`0x101313000`、`0x10131c000`）100% 集中在同一 **128 KiB 物理内存窗口 `0x101304000..0x10131c000`**（固件/链式引导残留 DMA/页表引用），且 `debug=0x100100` 中的 `0x100`（`DB_HALT`）使内核在锁屏关背光后停留在 `_kdp_i386_trap`，外在表现为“睡眠黑屏死机”。
- **修复机制**：在 OpenCore `config.plist` 的 `UEFI -> ReservedMemory` 中保留 `0x101000000..0x101400000`（`4 MiB`, `Type = Reserved`），并将 `boot-args` 的 `debug=0x100100` 调整为 `debug=0x100000`。实测连续 **28+ 轮**高强度压测与长稳运行中 **`pmap_recycle_page` 崩溃发生率为 0%**。

### 修复四：XCPM 电源管理、显示背光、板载声卡与双麦克风、UVC 摄像头、指纹识别、无线网络、NVMe/TBT4 及 S0ix 现代待机全栈适配

- **CPU 与 XCPM 原生 39 档 P-States 电源管理**：Dragonfly G2 (`8716`) 搭载 `11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz` (`4C/8T`，真实 CPUID `0x806C1` model `140`)，EliteBook 840 G8 (`880D`) 搭载 `11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz` (`4C/8T`，睿频最高 `4.70 GHz`)；通过 OpenCore `Kernel -> Emulate` 仿冒 Ice Lake-LP CPUID `0x706E5` (`model 126`) 配合 `SSDT-PLUG.aml`（为 `\_SB.PR00` 注入 `plugin-type = 1`），原生挂载 `MacBookPro16,2` (`J214k` / `Mac-5F9802EFE386AA28.plist`) `X86PlatformPlugin`（`machdep.xcpm.vectors_loaded_count = 1`，`2` 个 `FrequencyVectors` 向量），完整解锁 **`39` 档 P-States（`400..4200 MHz`）**；
- **显示、硬件 PWM 背光与原生控制中心滑块**：Tiger Lake `8086:9a49` eDP pipe A / DDI A / PHY A 内屏 `1920×1080@60Hz` 原生点亮，`NootedGreen` `-ngreenblr`（`PCFIX28`/`PCFIX30` `SBLC_PWM_CTL2` 硬件缩放）配合 `hp-cb-shim.dylib`（`com.hp.cb-shim-loader` 20 次 `launchctl bootstrap` 重试加固）恢复 macOS 26 Tahoe 控制中心与系统设置原生亮度滑块，并由 `hp-bridge` 提供 `F3`/`F4` 亮度及 `F5`/`F6`/`F7`/`F8` 音量/静音 OSD 快捷键（详见 [`docs/display-analysis.md`](docs/display-analysis.md)、[`docs/runtime-display-notes.md`](docs/runtime-display-notes.md) 与 [`docs/clean-install-guide.md`](docs/clean-install-guide.md)）；
- **板载 `ALC285` 音频与双麦克风输入（`5` 个 CoreAudio `bltn` `48 kHz` 设备）**：`SimpleHDA.kext` + `AppleALC.kext`（Dragonfly G2 `8716` `layout-id = 71` / `31`；EliteBook 840 G8 `880D` `layout-id = 11` / `71`）配合 `hp-alc285-ampinit.sh`（`Node 0x20 Coef 0x65 = 0x0000` 功放解锁与 3.5mm 耳麦麦克风解静音）驱动 `Built-in Speaker` 默认输出、`Built-in Headphones` (`Built-in Output`)、`Built-in Microphone` (2ch 3.5mm 耳麦麦克风) 与 `Built-in Line Input`（标称 `44.1 kHz`）；`TGLDmic.kext v0.5.0`（加载 Intel 官方签名 `sof-tgl.ri` cAVS 2.5 DSP 固件）配合 `TGLDmic.driver` CoreAudio HAL 插件提供 `Internal Microphone (TGLDmic)` 4 通道默认输入，全部经 `kAudioUnitSubType_DefaultOutput` 渲染回调与 `kAudioUnitSubType_HALOutput` Bus 1 采集回调实测验证；
- **内置 UVC 摄像头 (`HP HD Camera`, `0408:5349`)**：Quanta UVC USB 2.0 摄像头（`0408:5349` @ `HS02@14200000`）经 `UVCAssistant` + `AVFoundation` 免驱支持（`13` 种格式最高 `1280x720@30fps` MJPEG `420v`，`VTDecoderXPCService` 软解平均延迟 `5 ms`；伴生 `HP IR Camera` `640x360` Windows Hello 红外流自动忽略）；
- **USB 指纹传感器 (`Synaptics 06cb:00f0`)**：`RidgeKey`（`ridgekeyd 1.0.0` + `pam_ridgekey.so` + Keychain 密码解锁，已录入 `right-thumb` / `right-index` `2` 枚指纹）实现 `sudo`、系统认证弹窗与锁屏指纹认证；
- **Wi-Fi 6、蓝牙常驻防逐出锁定与持久化日志守护 (`Intel AX201` / `0x8087:0x0026` + `hp-syslogger.py`)**：`AirportItlwm.kext`（`802.11ax` 5 GHz 原生 `en0`）+ `IntelBluetoothFirmware.kext`（`ibt-19-0-4.sfi` `v8787`）+ `BlueToolFixup.kext` + Tahoe `bluetoothd` `--Compat` 自动剥离守护（`hp-bt-compat-check.sh`）+ `com.hp.syslogger`（通过 `MAP_PRIVATE | PROT_READ` + `mlock` 常驻锁定 `/usr/sbin/bluetoothd` `11.2 MB` `__TEXT` 段防止 `BlueToolFixup` 就地补丁页与 APFS `decmpfs_pagein_compressed` 部分逐出触发 `error 94` / `SIGBUS`，并在 `/var/log/hp/boot-*` 跨关机/重启持久归档 `dmesg`、`pmset`、S0ix IORegistry 与 Unified Log，详见 [`docs/continuation.md`](docs/continuation.md)）；
- **输入外设、NVMe / Thunderbolt 4 与 VirtualSMC `118` 键遥测**：Synaptics `SYNA30B6` (`06cb:cd74` PS/2 + SMBus/I2C 触控板，`VoodooPS2SynapticsTouchPad` / `VoodooI2C` + `VoodooInput` + `VoodooGPIOTigerLakeLP` `INT34C5`) + PS/2 键盘 (`24` 条自定义 JIS 顶排映射) + Wacom `WACF4233` (`056a:4924` 触屏)；Micron 2210 `MTFDHBA512QFD-1AX1AABHA` (`512.11 GB`, `ASPM L1` via `NVMeFix.kext`)、Tiger Lake `XHCI@D` (`8086:9a13`, `AppleUSBXHCIPCI`) + PCH `XHCI@14` (`8086:a0ed`, `AppleUSBXHCISPT`)、以及 `TDM0@D,2` (`8086:9a1b` TBT4 DMA 置于 PCI `D3hot`)；`VirtualSMC 1.3.7` + `SMCProcessor` + `SMCBatteryManager` 注册 `118` 个 SMC 键（`111` 个可读、`6` 个只写 `0x85`、`1` 个 `EFBS`，上报 `TC0P`/`TC1C..TC4C`、`PC0C`/`PCPT`、`B0RM`/`B0FC`/`B0AV`/`B0CT`/`BRSC`）并预置 `SSDT-EC0-ITLB.aml`；
- **S0ix 现代待机、USB 唤醒屏蔽与唤醒 RGB 归一化 (`S0ixStandby.kext v0.4.4` + `SSDT-DEEPIDLE.aml` + `R32-PCFIX37-WAKERGB`)**：`S0ixStandby.kext v0.4.4`（`74,584` B SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`，`-s0ixd3 -s0ixdbg -s0ixnogpureset -s0ixcnvwd3`，含闭盖 `pmCPUHaltHook` 非唤醒电池 SCI 过滤、USB/PCI `PME_EN` 清零与 `GPE 0x6D/0x69` 硬件屏蔽、`CNVW` `BAR0` 复位 + `D3hot` + `XSQD` 清除、以及睡眠态关断 `PLANE_CTL_1_A` DRAM DMA 扫描并在唤醒时强制归一化 `0x84000400` RGB）+ `SSDT-DEEPIDLE.aml`（`371` B，SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`，注入 `\_SB.LID` / `\_SB.SLPB` `_PRW` `0x6E` 并置 `\USWE = Zero` 屏蔽 USB/雷电唤醒）+ `NootedGreen` `PCFIX37` `xeNormalizePlane1ARgb` + `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`（实机 `B004F99C` 已验证单次连续 `51.6 分钟` S0ix 深度休眠 `CC7=99%, PC3=99%`、`0` 伪唤醒、开盖即刻恢复且零绿屏）；
- **Nix Flake 可复现构建环境**：仓库根目录 [`flake.nix`](flake.nix) 与 [`flake.lock`](flake.lock) 提供标准化 `nix develop` 环境，彻底消除硬编码 `/nix/store` 路径。

---

## 入口

- **[新会话续接 / 迁移必读](docs/continuation.md)**；当前状态见 [`configs/install-preparation.json`](configs/install-preparation.json)，追加事件历史见 [`manifests/experiment-history.json`](manifests/experiment-history.json)。
- **[HP Tiger Lake (Elite Dragonfly G2 / EliteBook 840 G8) 全新安装 macOS Tahoe 26 完整指南](docs/clean-install-guide.md)** 与 **[自定义组件源码索引与从源码重编译指南](docs/from-source-rebuild-guide.md)**（对应 S0ix、背光与唤醒 RGB 补丁：[`patches/nootedgreen-r32-pcfix31-backlight-20261107.patch`](patches/nootedgreen-r32-pcfix31-backlight-20261107.patch)、[`patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch`](patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch)、[`patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch`](patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch)、[`patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch`](patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch)，全外设审计报告：`.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/peripheral-audit-report.json`）
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
- [内置 OpenCore 与旧 Debian 引导清理](docs/internal-boot.md)
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
- [`manifests/`](manifests)：第三方来源、版本、提交与许可记录。

## 固定约束

远端只做在线、只读采集；未经明确许可不关机、不重启、不休眠，不写 BIOS、NVRAM 或固件设置。本机 Lexar U 盘已有 Ventoy，保留其文件及分区。编译、反编译和静态检查全部在本地开发机通过 `nix develop` 执行。

## 已建立的实机基线

| 项目 | 在线核实与实机运行结果 |
| --- | --- |
| 机器 / 固件 | HP Elite Dragonfly G2，板号 `8716`，BIOS `T90 01.25.00`（同平台兼容机型：HP EliteBook 840 G8，板号 `880D`） |
| CPU / XCPM / 内存 | Dragonfly G2 (`8716`)：`11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz`（`4C/8T`，真实 CPUID `0x806C1` model `140`，OpenCore 仿冒 `0x706E5` model `126` 启用 `MacBookPro16,2` `J214k` XCPM `39` 档 P-States `400..4200 MHz`）；EliteBook 840 G8 (`880D`)：`11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz`（`4C/8T`，Turbo 最高 `4.70 GHz`）；16 GiB LPDDR4x-4267 |
| GPU | Iris Xe `8086:9a49`，B0，80EU / 5 DualSubslice；**macOS 26.6.2 (`25G83`) `R32-PCFIX37-WAKERGB`（`NootedGreen` `540,944` B SHA256 `00982625...`, `LC_UUID` `4C4C44A8-5555-3144-A16C-16F349CEF835`，含 `isRealTGL && Tahoe` `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`、`xeNormalizePlane1ARgb` 与 `libxedrv.dylib` SHA256 `312ecf60...`）Metal 硬件加速已启用并 100% 跑通三阶段耐力压测（`705,024` 编码器）、5 轮（`47,645` 批次）、10 轮（`80,525` 批次 = `644,116` 编码器）与 Phase 8 超两百万编码器耐力压测（最终 10 轮 TCC 套件 `71,972` 批次 = `575,694` 编码器，两轮 10-round 共 `1,006,546` 编码器，`HP-PCFIX` 跨 5 次运行累计推进 `+1,435,904` 编码器至 `enc#2,341,120` + `250` `CARenderer` + `300` `CoreImage` + `600` `MPS` GEMM @ `166.0–182.4 GFLOPS` + 全双工 `ALC285` / `TGLDmic` 音频），全程 `0` 挂死（`rf=0`, `wsk=0`, `sigCnt=0`, `recoveryCount=0`）** |
| 内屏与背光 | IVO8596，`X133NVFF R0`，1920×1080 约 60Hz（macOS 原生点亮；`-ngreenblr` `PCFIX28` + `hp-cb-shim.dylib` 控制中心原生滑块 + `hp-bridge` `F3`/`F4` 16 级调光） |
| eDP 工作状态 | pipe A / DDI A / PHY A，2 lane，2.7Gbps/lane |
| 摄像头 (`Webcam`) | Quanta `HP HD Camera`（`0408:5349` @ `HS02@14200000`），通过 `UVCAssistant` + `AVFoundation` 原生支持 `13` 种格式（最高 `1280x720@30fps` MJPEG `420v`，`VTDecoderXPCService` 软解平均延迟 `5 ms`；伴生 `HP IR Camera` `640x360` Windows Hello 红外流自动忽略） |
| 触控板 / 键盘 / 触屏 | Synaptics `SYNA30B6`（`06cb:cd74` PS/2 + SMBus/I2C 触控板，经 `VoodooPS2SynapticsTouchPad` / `VoodooI2C` + `VoodooInput` 已驱动）+ PS/2 键盘（`24` 条自定义 JIS 顶排映射）+ Wacom `WACF4233`（`056a:4924` I²C 触屏已驱动） |
| 无线 / 蓝牙 | Intel AX201 / `0x8087:0x0026`（`AirportItlwm` `802.11ax` 5 GHz Wi-Fi 与 `IntelBluetoothFirmware` `ibt-19-0-4.sfi` `v8787` + `BlueToolFixup` + `hp-syslogger.py` `mlock` 常驻防 `decmpfs` 逐出守护均正常工作） |
| 音频（5 设备与双麦克风输入） | Realtek ALC285 `10ec:0285`（子系统 `103c:8716`）+ Intel cAVS `0xa0c8`/`0x9dc8`：`SimpleHDA` + `AppleALC`（`8716` `layout-id = 71`/`31`；`880D` `layout-id = 11`/`71`）+ `hp-alc285-ampinit.sh` + `TGLDmic.kext v0.5.0`（`sof-tgl.ri` + `TGLDmic.driver`），完整枚举 `5` 个 CoreAudio `bltn` `48 kHz` 设备（`Built-in Speaker` 默认输出、`Built-in Headphones` / `Built-in Output`、`Built-in Microphone` 2ch 3.5mm 耳麦麦克风、`Built-in Line Input` 标称 `44.1 kHz`、`Internal Microphone (TGLDmic)` 4ch 默认输入），经 `kAudioUnitSubType_DefaultOutput` 与 `kAudioUnitSubType_HALOutput` Bus 1 回调实测通过 |
| 指纹、SMC 与现代待机 | Synaptics `06cb:00f0` USB 指纹传感器（`RidgeKey 1.0.0`，已录入 `right-thumb` / `right-index` `2` 枚指纹，支持 `sudo`、系统弹窗与锁屏指纹认证）；`VirtualSMC 1.3.7` + `SMCProcessor` + `SMCBatteryManager` 注册 `118` 个 SMC 键（`111` 可读、`6` 只写 `0x85`、`1` `EFBS`，上报 `TC0P`/`TC1C..TC4C`、`PC0C`/`PCPT`、`B0RM`/`B0FC`/`B0AV`/`B0CT`/`BRSC`）；`SSDT-EC0-ITLB.aml` + OEM `SSDT13` Delete 实现冷启动 `0` ACPI 报错；`S0ixStandby.kext v0.4.4`（`74,584` B SHA256 `be55592c...`）+ `SSDT-DEEPIDLE.aml`（`371` B SHA256 `280e3a4a...`，`_PRW` `0x6E` 开盖唤醒 + `\USWE=0` 禁用 USB 唤醒）+ `R32-PCFIX37-WAKERGB`（`NootedGreen` SHA256 `00982625...`）已实机验证 `51.6m` 连续深睡零伪唤醒 |
| 存储与 Thunderbolt 4 / USB4 | Micron 2210 `MTFDHBA512QFD-1AX1AABHA`（`512.11 GB` on Dragonfly G2 `8716` `1344:5404`，固件 `HPS1022`，通过 `NVMeFix.kext` 启用 `ASPM L1`）；Intel Tiger Lake `XHCI@D` (`8086:9a13`, `AppleUSBXHCIPCI`) + PCH `XHCI@14` (`8086:a0ed`, `AppleUSBXHCISPT`)，以及 `TDM0@D,2` (`8086:9a1b` TBT4 DMA 由 `S0ixStandby.kext v0.4.4` 置于 PCI `D3hot`) |
| 当前系统 | NixOS 与 macOS 26.6.2 (`25G83`) 双系统完备（已按用户指令完成全量日志审计、部署 `/var/log/hp/` 跨重启持久化日志体系并干净关机下电）；本地最新 431 文件后置套件 `HP-Tahoe-PostInstall-20261108.tar.gz` 为 `125,569,879` B（SHA256 `2f22d03e886773194337281491433b22ea87af1395b26d5e54eb8289020177aa`） |
| BIOS | Secure Boot 关（测试期间），Fast Boot 开，VMD 存储映射关，Video Memory 512MB |

## 本机命令

```sh
nix develop -c make check
nix develop -c make verify-release
nix develop -c python3 scripts/verify_release_artifacts.py --check-source-rebuilds --check-live-nixos <user>@<nixos-host>
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

- **离线原型与编译基线**：VESA EFI 原型通过 OpenCore 1.0.8 静态校验；固定 framebuffer 补丁在 Linux 编译并链接成真实 `x86_64` kext bundle，独立存放于 `.local/framebuffer-build/`。构建依赖固定缓存，来源见 [`manifests/`](manifests)。
- **Recovery 引导与 MMIO 突破**：实机单独 `slide=0` 重试在 runtime 内存申请处失败；保留该参数并开启 `DevirtualiseMmio` 后成功进入 Recovery 工具界面。完整 26.6.2 / `25G83` 离线 app 数据映像复制到 USB 并完整回读校验。
- **I²C 输入与内置诊断通道**：新增 `VoodooI2C`/`VoodooI2CHID` 与 Tiger Lake 精确匹配 ID 后，触控板与键盘可用；独立 **WiFi IMG** 实测 Wi-Fi、root SSH 和 SFTP 成功，内置 NTFS `/hpdiag` 可读，首份完整运行态归档见[网络交接](docs/recovery-network.md)和[运行态证据](manifests/hp-recovery-runtime-check.json)。
- **完整系统安装、Xe Metal 硬件加速与全外设闭环**：从 VESA 基础启动 → Framebuffer 内屏 → 完整 macOS 26.6.2 安装 → `NootedGreen` Tiger Lake Iris Xe 80 EU Metal 计算管线、视频播放与唤醒 RGB 归一化修复（`R32-ELSQWAIT` 与 `R32-PCFIX2` ~ `R32-PCFIX37-WAKERGB`）→ 板载 `ALC285` + `TGLDmic v0.5.0` 四阵列麦克风、控制中心原生亮度滑块、`RidgeKey` 指纹认证、`hp-syslogger.py` 蓝牙 `mlock` 防护与跨重启持久化日志、`S0ixStandby v0.4.4` + `SSDT-DEEPIDLE.aml` 现代待机（51.6 分钟深睡零伪唤醒 + 禁用 USB 唤醒 + 开盖即刻唤醒）、早期 ACPI 零报错与 431 文件一键后置安装套件闭环。
