# HP Tiger Lake (Elite Dragonfly G2 / EliteBook 840 G8) 全新安装 macOS Tahoe 26 完整指南

本文档系统梳理在 **HP Tiger Lake-UP3 轻薄本平台**上从零开始全新安装原生 `x86_64` 版 **macOS Tahoe 26（`26.6.2` / `25G83`，兼容 `25A354` / `25G241`）** 并完成 **Intel Iris Xe (`8086:9a49`) Metal 硬件加速、板载 `ALC285` 音频与四阵列数字麦克风 (`TGLDmic`)、控制中心原生亮度滑块、全键位快捷键、蓝牙/Wi-Fi、指纹 (`RidgeKey`) 及 S0ix Modern Standby 现代待机睡眠唤醒** 的完整可复现流程。

> [!NOTE] **硬件基线与同架构机型说明**
> - **本仓库实机验证基线**：**HP Elite Dragonfly G2 Notebook PC**（主板号 `8716`，BIOS `T90 Ver. 01.25.00`，`11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz` `4C/8T` `2.40–4.20 GHz`，原生 CPUID `0x806C1` Model `140` / OpenCore 仿冒 `0x706E5` Model `126` 激活 `MacBookPro16,2` `J214k` XCPM `39` 档 P-States `400..4200 MHz`，Iris Xe `8086:9a49` rev `0x01` B0 80 EU / 5 DualSubslices，13.3" FHD eDP `IVO8596` `X133NVFF R0`）。全部配置、内核补丁与实机证据归档于 [README.md](../README.md)、[docs/continuation.md](continuation.md)、[configs/install-preparation.json](../configs/install-preparation.json)、[manifests/experiment-history.json](../manifests/experiment-history.json)、[hardware/elite-dragonfly-g2.json](../hardware/elite-dragonfly-g2.json) 及全外设实机审计报告 `peripheral-audit-report.json` / `peripheral-audit-report.md`。
> - **同代同平台参考机型**：**HP EliteBook 840 G8**（主板号 `880D`，`11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz` `4C/8T` Turbo 最高 `4.70 GHz` / `i5-1135G7` Tiger Lake-UP3 `0x8C`，Iris Xe `8086:9a49` rev `0x01`，14" FHD eDP `LGD0693`，Realtek `ALC285` + Intel cAVS 2.5 四阵列 PDM 麦克风），与 Elite Dragonfly G2 共享相同的 Tiger Lake-LP PCH（`8086:a082`/`a0c8`/`a0ed`/`a0f0`）、EC/WMI 架构、NHLT 拓扑与 S0ix PEPD 电源管理（上游 `TGLDmic`、`RidgeKey`、`S0ixStandby` 均原生面向 EliteBook 840 G8 `880D` 与 Dragonfly G2 `8716`）。下文在给出本机实测配置的同时，明确标注 `EliteBook 840 G8` (`880D`) 的对应参数差异（如 `layout-id` `71`/`31` vs `11`/`71`、面板 `IVO8596` vs `LGD0693`、EU 数量 `80` vs `96`）。

---

## 1. 硬件配置与当前适配状态总览 (Hardware & Adaptation Matrix)

### 1.1 硬件规格对照表

| 硬件子系统 | 本仓库实机 (HP Elite Dragonfly G2 `8716`) | 同平台参考机型 (HP EliteBook 840 G8 `880D`) | PCI / USB / ACPI 与实机核验标识 |
| --- | --- | --- | --- |
| **处理器与 XCPM (CPU & XCPM)** | `11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz` (`4C/8T`, `2.40–4.20 GHz`) | `11th Gen Intel(R) Core(TM) i7-1165G7 @ 2.80GHz` (`4C/8T`, Turbo up to `4.70 GHz`) | Tiger Lake-UP3 原生 CPUID `0x806C1` (Model `140` / `0x8C`, Stepping `1` B0)；OpenCore `Cpuid1Data` 仿冒 Ice Lake-LP `0x706E5` (Model `126`) 匹配 `MacBookPro16,2` (`J214k` / `Mac-5F9802EFE386AA28.plist`) `X86PlatformPlugin` **`39` 档 P-States (`400..4200 MHz`)** |
| **内存 (RAM)** | 16 GiB 板载 LPDDR4x-4267 (`Samsung K4UBE3D4AA-MGCR`) | 16 / 32 GiB DDR4-3200 SO-DIMM | 双通道 64-bit / 四控制器通道 |
| **核显 (iGPU)** | Intel Iris Xe Graphics G7 (80 EU / 5 DualSubslices) | Intel Iris Xe Graphics G7 (96 EU / 80 EU) | PCI `8086:9a49` (rev `0x01`), 子系统 `103c:8716` (或 `103c:880d`), `PciRoot(0x0)/Pci(0x2,0x0)` |
| **内置显示屏** | 13.3" FHD (`1920×1080@60Hz`) eDP `IVO8596` (`X133NVFF R0` Sure View) | 14.0" FHD (`1920×1080@60Hz`) eDP `LGD0693` | eDP-1, `pipe A / DDI A / PHY A`, 2 lanes @ 2.7 Gbps |
| **音频输出与双麦克风 (`ALC285` + `TGLDmic`)** | Realtek `ALC285` (Bang & Olufsen) + 屏幕顶部 4 阵列 PDM 数字麦克风 | Realtek `ALC285` (Bang & Olufsen) + 屏幕顶部 4 阵列 PDM 数字麦克风 | HDA `8086:a0c8` (`PCI0@0/HDEF@1F,3`), Codec `10ec:0285` (`103c:8716` `layout-id = 71`/`31`；840 G8 `103c:880d` `layout-id = 11`/`71`) + NHLT Endpoint 2 (`8086:ae20`, `TGLDmic v0.5.0` `sof-tgl.ri`)；枚举 **`5` 个 CoreAudio `bltn` `48 kHz` 设备**（`Built-in Speaker` 默认输出、`Built-in Headphones` / `Built-in Output`、`Built-in Microphone` 2ch 3.5mm 耳麦麦克风、`Built-in Line Input` 标称 `44.1 kHz`、`Internal Microphone (TGLDmic)` 4ch 默认输入） |
| **无线网卡 (Wi-Fi)** | Intel Wi-Fi 6 AX201 (CNVi, 160 MHz) | Intel Wi-Fi 6 AX201 (CNVi, 160 MHz) | PCI `8086:a0f0` (`00:14.3`) |
| **蓝牙 (Bluetooth)** | Intel AX201 Integrated Bluetooth 5.2 | Intel AX201 Integrated Bluetooth 5.2 | USB `0x8087:0x0026` (`8087:0026`, 挂载于 PCH XHCI `HS10@14a00000`) |
| **内置存储 (NVMe)** | Micron 2210 `MTFDHBA512QFD-1AX1AABHA` (`512.11 GB` PCIe Gen3 x4, 固件 `HPS1022`) | PCIe Gen3/Gen4 NVMe M.2 SSD | `PCI0@0/RP09@1D/PXSX@0`, PCI `1344:5404` (非 VMD 直通, NVMe 1.30, TRIM 开启, `ASPM L1` via `NVMeFix.kext`) |
| **雷雳 4 / USB4 与 XHCI** | 双 Type-C Thunderbolt 4 / USB4 + USB-A 3.2 Gen 1 | 双 Type-C Thunderbolt 4 / USB4 + 双 USB-A 3.2 Gen 1 | TBT4 Root Port `TRP0@7` (`8086:9a23`) + CPU `XHCI@D` / `TXHC@0d000000` (`8086:9a13`, `AppleUSBXHCIPCI`) + PCH `XHCI@14` / `XHCI@14000000` (`8086:a0ed`, `AppleUSBXHCISPT`) + TBT4 DMA `TDM0@D,2` (`8086:9a1b`, 由 `S0ixStandby.kext v0.4.4` 置入 PCI `D3hot`) |
| **键盘、触控板与触控屏 (Input & Touchscreen)** | PS/2 JIS/ANSI 键盘 (`24` 条顶排/JIS 映射) + Synaptics `SYNA30B6` 触控板 + Wacom `WACF4233` 触控屏 | PS/2 键盘 (`24` 条顶排映射) + Synaptics `SYNA30B6` 触控板 + 可选触控屏 | 键盘 `ApplePS2Keyboard`; 触控板 `SYNA30B6` (`06cb:cd74` PS/2 + SMBus/I²C `TPD0`, 经 `VoodooPS2SynapticsTouchPad` / `VoodooI2C` + `VoodooInput` 仿真 `Magic Trackpad 2`, `VoodooGPIOTigerLakeLP` `INT34C5` GPIO 中断); 触控屏 Wacom `WACF4233` (`056a:4924` `TPL0` on `VoodooI2CHIDDevice`) |
| **指纹识别器 (`RidgeKey`)** | Synaptics Match-On-Chip USB 指纹传感器 | Synaptics Match-On-Chip USB 指纹传感器 | USB `06cb:00f0` (挂载于 PCH XHCI `HS03`/`HS07`, `ridgekeyd 1.0.0`) |
| **摄像头 (`HP HD Camera`)** | Quanta `HP HD Camera` (USB 2.0 UVC RGB) + `HP IR Camera` | Quanta `HP HD Camera` (USB 2.0 UVC RGB) + 可选 `HP IR Camera` | USB `0408:5349` (挂载于 PCH XHCI `HS02@14200000`)，`UVCAssistant` + `AVFoundation` 原生支持（`13` 种格式最高 `1280x720@30fps` MJPEG `420v`, `VTDecoderXPCService` 软件 MJPEG 解码平均延迟 `5 ms`；伴生 `HP IR Camera` `640x360` Windows Hello IR 流自动忽略） |
| **SMC 硬件遥测、电池与现代待机** | HP Primary Li-ion 电池 + `VirtualSMC` (`118` 键) + Intel PEP (`PNP0D80`) | HP Primary Li-ion 电池 + `VirtualSMC` (`118` 键) + Intel PEP (`PNP0D80`) | `VirtualSMC 1.3.7` + `SMCProcessor` + `SMCBatteryManager` 注册 **`118` 个 SMC 键**（`111` 可读、`6` 只写 `0x85`、`1` `EFBS`；温度 `TC0P`/`TC1C..TC4C`、功耗 `PC0C`/`PCPT`、电池 `B0RM`/`B0FC`/`B0AV`/`B0CT`/`BRSC`）；ACPI `\_SB.PEPD` (`PNP0D80`), `S0ixStandby v0.4.4` |

### 1.2 macOS Tahoe 26 (`25G83` / `25A354`) 子系统适配状态矩阵

| 子系统 | 核心驱动 / Kext / 守护进程 | 版本 / 补丁级别 | 实机验证状态 (macOS Tahoe `25G83`) | 关键证据与补丁文件 |
| --- | --- | --- | --- | --- |
| **OpenCore 引导与内存保护** | `OpenCore.efi` + `OpenRuntime.efi` + `PMAPFIX` | `1.0.8` (匹配 `ocvalidate`) | **已完美验证**：`slide=0` + `DevirtualiseMmio` + 预留 `0x101000000..0x101400000` (`4 MiB`)，连续 28+ 轮压测与 8+ 小时通宵运行 `0` 次 `pmap_recycle_page` panic | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist` |
| **CPU XCPM 变频 (`39` P-States)** | OpenCore `Kernel -> Emulate` (`0x706E5` 仿冒) + `SSDT-PLUG.aml` (`plugin-type = 1`) + `X86PlatformPlugin` | `MacBookPro16,2` (`J214k` / `Mac-5F9802EFE386AA28.plist`) | **已完美验证**：`i5-1135G7 @ 2.40GHz`（原生 `0x806C1` Model `140` / 840 G8 `i7-1165G7 @ 2.80GHz`）通过仿冒 Ice Lake-LP `0x706E5` (Model `126`) 加载 `machdep.xcpm.vectors_loaded_count = 1`、**`39` 档 P-States (`400..4200 MHz`)** 与 `2` 个 `FrequencyVectors` 向量表；`S0ixStandby.kext` 通过原生 `cpuid(1)` 识别 Model `140` | `xcpm-cpu-topology.txt`、`peripheral-audit-report.json` |
| **Iris Xe 图形加速与 Metal 2** | `NootedGreen.kext` + `AppleIntelTGLGraphics*` (`16.0.32` 移植包) + `HookCase.kext` + `libxedrv.dylib` + `xe-h264sw-fixd` | `R32-PCFIX37-WAKERGB` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16` (`NootedGreen` `540,944` B SHA256 `00982625...`, `LC_UUID` `4C4C44A8-5555-3144-A16C-16F349CEF835`；`libxedrv.dylib` SHA256 `312ecf60...`；`xe-h264sw-fixd` SHA256 `4e388dfd...`) | **已完美验证**：Metal 2 硬件加速、三阶段耐力压测连续执行 `705,024` 个计算编码器 `0` 挂死、10 轮混合并发压测（`644,116` 编码器 + MPS `195.79 GFLOPS`）及 **Phase 8 超两百万编码器耐力压测**（最终 10 轮 TCC 套件 `111.02s` 完成 `71,972` 批次 = `575,694` 编码器，两轮 10-round 共 `1,006,546` 编码器，`HP-PCFIX` 跨 5 次运行累计推进 `+1,435,904` 编码器至 **`enc#2,341,120`** / `pf=2,005,579` + `250` `CARenderer` + `300` `CoreImage` + `600` `MPS` `166.0–182.4 GFLOPS` + 全双工 `ALC285` / `TGLDmic` 音频）全程 **`0` 故障（`rf=0`, `wsk=0`, `sigCnt=0`, `recoveryCount=0`）**；在 `isRealTGL && Tahoe` 分支启用 `HP-BLITALIGN`、`HP-BLITFIX`、`HP-BLIT16` 与 `xe-h264sw-fixd`，将软解 `420v` 32B 非 64B 对齐 `IOSurface` 平面路由至 `BCS0` `XY_SRC_COPY_BLT` 2D 拷贝并强制剩余 `Blit3D` PS 为 `SIMD16`，配合 `PCFIX37` `xeNormalizePlane1ARgb` 彻底根治视频绿屏与唤醒绿屏 | [patches/nootedgreen-r32-pcfix27-20261106.patch](../patches/nootedgreen-r32-pcfix27-20261106.patch)、[patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch](../patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch)、`endurance-1m-report.md` |
| **内屏显示与原生亮度滑块** | `XE-BLR` (`NootedGreen`) + `SSDT-PNLF-HP-GA419.aml` + `libhp_cb_shim.dylib` + `hp-bridge` | `R32-PCFIX37-WAKERGB` + `hp-cb-shim 1.0` | **已完美验证**：`1920×1080@60Hz` 原生点亮，右上角控制中心与系统设置“显示器”亮度滑块圆点完整可用，键盘 `F3`/`F4` 16 级线性调光联动 | [docs/display-analysis.md](display-analysis.md)、[docs/continuation.md](continuation.md) |
| **音频输出与双麦克风输入 (`5` 路 CoreAudio)** | `SimpleHDA.kext` + `AppleALC.kext` + `hp-alc285-ampinit.sh` + `TGLDmic.kext` + `TGLDmic.driver` | `SimpleHDA 1.0.1` + `AppleALC 1.9.8` (`layout-id 71`/`31` 或 `11`) + `TGLDmic v0.5.0` (`sof-tgl.ri`) | **已完美验证**：完整枚举 **`5` 个 CoreAudio `bltn` `48 kHz` 设备**（`Built-in Speaker` `ID=48` 默认输出、`Built-in Headphones` / `Built-in Output` `ID=57`、`Built-in Microphone` `ID=67` 2ch 3.5mm 耳麦麦克风、`Built-in Line Input` `ID=76` 标称 `44.1 kHz`、`Internal Microphone (TGLDmic)` `ID=84` 4ch 默认输入），通过 `kAudioUnitSubType_DefaultOutput` 渲染回调（`99` 次回调 / `50,688` 帧 `0` 欠载）与 `kAudioUnitSubType_HALOutput` Bus 1 输入采集回调（`TGLDmic` 4ch + `ALC285` 2ch，`0` 错误）双重验证 | `coreaudio_probe.m`、`coreaudio-probe.log` |
| **内置 UVC 摄像头 (`HP HD Camera`)** | Quanta USB 2.0 UVC (`0408:5349`) + `UVCAssistant` + `AVFoundation` + `VTDecoderXPCService` | macOS 原生 UVC (`bcdDevice 0x0007`, `HS02@14200000`) | **已完美验证**：`AVFoundation` 枚举 **`13` 种格式**（`5` 种 `yuvs` + `8` 种 `420v` MJPEG 最高 `1280x720@30fps`），实机连续捕获 `8/8` 帧 `1280x720` `420v`（`0` 丢帧，`VTDecoderXPCService` 软件 MJPEG 解码平均延迟 **`5 ms`**；伴生 `HP IR Camera` `640x360` Windows Hello IR 流自动忽略，`ridgekeyd` `libusb` 被动 `AppleUSBHostDeviceUserClient` 零干扰） | `avf_camera_test.m`、`avf-camera-test.log` |
| **Wi-Fi 无线网络 (`AX201`)** | `AirportItlwm.kext` | `2.4.0` (Tahoe 专版) | **已完美验证**：原生挂载为 `en0` Wi-Fi 接口，控制中心 Wi-Fi 开关、DHCP/IPv6、SSH/SFTP 均高速稳定 | [docs/recovery-network.md](recovery-network.md) |
| **蓝牙与持久化日志 (`8087:0026`)** | `IntelBluetoothFirmware.kext` + `IntelBTPatcher.kext` + `BlueToolFixup.kext` + `hp-bt-compat-check.sh` + `hp-syslogger.py` | `2.5.2` + `2.7.2` + `hp-syslogger v1.1` (`mlock` + `/var/log/hp/`) | **已完美验证**：固件 `v8787 c8787` 加载成功，蓝牙开关、外设配对与 A2DP/HFP 双向音频正常；`hp-syslogger.py` 常驻锁定 `/usr/sbin/bluetoothd` `[0x0..0xab0000)` 防止 `BlueToolFixup` 就地补丁页与 APFS `decmpfs` 部分逐出触发 `error 94` (`SIGBUS`)，并跨关机持久归档系统日志 | [docs/peripheral-adaptation-status-20261104.md](peripheral-adaptation-status-20261104.md)、[docs/continuation.md](continuation.md) |
| **键盘、触控板与 Wacom 触控屏** | `VoodooPS2Controller.kext` (`VoodooPS2SynapticsTouchPad`) + `VoodooI2C.kext` + `VoodooI2CHID.kext` + `VoodooInput.kext` + `hp-bridge` | `VoodooPS2 2.3.7` + `VoodooI2C 2.9.1` | **已完美验证**：Synaptics `SYNA30B6` (`06cb:cd74` PS/2 + SMBus/I²C 触控板，`VoodooGPIOTigerLakeLP` `INT34C5` GPIO 中断，`Magic Trackpad 2` 多指手势) 与 Wacom `WACF4233` (`056a:4924` I²C 触控屏 `TPL0`) 正常；PS/2 键盘 `24` 条 JIS/顶排自定义映射及静音橙色 GPIO LED 正常 | [docs/input-recovery.md](input-recovery.md)、`pcie-nvme-tb4-input-ridgekey.txt` |
| **NVMe 存储与雷雳 4 / USB4** | `IONVMeFamily` (+ `NVMeFix.kext`) + `AppleUSBXHCIPCI` (`XHCI@D`) + `AppleUSBXHCISPT` (`XHCI@14`) + `S0ixStandby` | Micron 2210 (`1344:5404`) + TGL TBT4 (`8086:9a13` / `8086:9a1b`) | **已完美验证**：Micron 2210 `MTFDHBA512QFD-1AX1AABHA` (`512.11 GB` on Dragonfly G2 `8716`, `ASPM L1` via `NVMeFix.kext`, TRIM 开启, SMART `Verified`)；CPU `XHCI@D` (`8086:9a13`) 与 PCH `XHCI@14` (`8086:a0ed`) 正常，`TDM0@D,2` (`8086:9a1b` TBT4 DMA) 由 `S0ixStandby.kext v0.4.4` 置入 PCI `D3hot` | `pcie-nvme-tb4-input-ridgekey.txt` |
| **SMC 硬件遥测与智能电池 (`118` 键)** | `VirtualSMC.kext` + `SMCProcessor.kext` + `SMCBatteryManager.kext` + `ECEnabler.kext` + `SSDT-EC0-ITLB.aml` | `VirtualSMC 1.3.7` (`SMCProcessor 1.3.7` / `SMCBatteryManager 1.3.7`) + `ECEnabler 1.0.6` | **已完美验证**：枚举 **`118` 个注册 SMC 键**（`111` 可读、`6` 只写返回 `0x85` [`DPLM`, `DUSR`, `LDLG`, `LDSP`, `MSDW`, `NTOK`]、`1` `EFBS` `attr=0x90`），实时上报封装/核心温度（`TC0P`, `TC1C..TC4C`）、CPU/封装功耗（`PC0C`, `PCPT`）与智能电池遥测（`B0RM`, `B0FC`, `B0AV`, `B0CT`, `BRSC`）；冷启动 `BEC29211-881D-4E0E-99CC-5EE3C76A6FF5` 全程 **`0` 次 ACPI Error/Exception** | `smc_sensor_probe.c`、`smc-sensor-probe.log`、`dmesg-acpi-zeroerr-bec29211.txt` |
| **USB 指纹解锁 (`06cb:00f0`)** | `RidgeKey` (`ridgekeyd` + `RidgeKey.app` + `RidgeKeyAgent.app`) | `1.0.0` (已录入 `right-thumb` / `right-index` `2` 枚指纹) | **已完美验证**：支持指纹录入 (`ridgekeyctl enroll`)、锁屏指纹自动解锁、`sudo` (`pam_ridgekey.so`) 及管理员弹窗指纹认证 | [docs/continuation.md](continuation.md)、`peripheral-audit-report.md` |
| **S0ix 现代待机睡眠与唤醒** | `S0ixStandby.kext` + `SSDT-DEEPIDLE.aml` + `NootedGreen` (`R32-PCFIX37-WAKERGB`) + `hp-wake-helper` | `S0ixStandby v0.4.4` (`74,584` B, SHA256 `be55592c...`) + `SSDT-DEEPIDLE.aml` (`371` B, SHA256 `280e3a4a...`) + `R32-PCFIX37-WAKERGB` (`00982625...`) | **已完美验证 (`B004F99C` 单次连续 `51.6 分钟` S0ix Deep Idle 休眠，`CC7 = 99%`, `PC3 = 99%`, `0` 次伪 `DarkWake`)**：`IOPMDeepIdleSupported = Yes`，执行完整 `PEPD._DSM` Intel fn `3/5/6/4` (`EC0.SLPT = 6`) 并经 `pmCPUHaltHook` 排空闭盖非唤醒电池 SCI，默认禁用 USB/TBT 唤醒（`\USWE = Zero` + PCI `PME_EN` 清零 + `GPE 0x6D/0x69` 屏蔽），`CNVW` `BAR0` 静默复位 + `D3hot` + `XSQD` 清除，睡眠关断 `PLANE_CTL_1_A` DRAM DMA 扫描并在唤醒时强制归一化 `0x70180 = 0x84000400` RGB 消除唤醒绿屏 | [patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch](../patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch)、[patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch](../patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch) |

---

## 2. 第一阶段：BIOS / UEFI 固件设置 (BIOS Prerequisites)

在引导安装介质前，开机连续按 `F10` 进入 HP Computer Setup (BIOS)，核对并配置以下固件选项（参考本机脱敏固件清单 [hardware/elite-dragonfly-g2.json](../hardware/elite-dragonfly-g2.json) 与 [docs/runtime-display-notes.md](runtime-display-notes.md)）：

| BIOS 菜单路径 / 选项名称 | 推荐设置值 | 作用与工程依据 |
| --- | --- | --- |
| **Security -> Sure Start -> Sure Start BIOS Settings Protection** | **`Disable`** | 防止 HP Sure Start 在重启时自动回滚 BIOS 设置或锁定 NVRAM 启动项变更 |
| **Security -> Secure Boot Configuration -> Secure Boot** | **`Disable`** | 允许加载自定义交叉编译签名的 `OpenCore.efi`、`NootedGreen.kext` 与 Linux `systemd-boot` |
| **Advanced -> Boot Options -> Fast Boot** | **`Disable`** (安装期推荐) | 确保固件完整初始化 USB XHCI 控制器与 PCIe 总线；实机安装稳定后开启亦不影响内置盘引导 |
| **Advanced -> Boot Options -> USB Storage Boot** | **`Enable`** | 允许从外置 USB 安装盘或 Ventoy 介质引导 |
| **Advanced -> System Options -> Configure Storage Controller for VMD** | **`Disable`** | **极其关键**：关闭 Intel Volume Management Device (VMD) 重映射，使内置 NVMe SSD 以标准 PCIe NVMe (`00:1d.0 -> 55:00.0`) 暴露给 macOS 原生 `IONVMeFamily` |
| **Advanced -> System Options -> Virtualization Technology (VTx)** | **`Enable`** | 开启硬件虚拟化支持，供 macOS Hypervisor.framework 使用 |
| **Advanced -> System Options -> Virtualization Technology for Directed I/O (VTd)** | **`Enable`** | 保持开启（配合 OpenCore `Kernel -> Quirks -> DisableIoMapper = true` 屏蔽 DMAR 冲突，同时不影响 Linux/Windows 使用 IOMMU） |
| **Advanced -> Built-In Device Options -> Video Memory Size** | **`64 MB`** 或 **`512 MB`** | 预分配 DVMT 显存大小：标准 OpenCore Tiger Lake 配置推荐设为 `64 MB`；本机实测设为 `512 MB`（`GGC = 0x10c1`）同样 100% 正常引导并运行 Metal 加速 |
| **Advanced -> Built-In Device Options -> Force enable HP Sure View** | **`Disable`** | 防止开机默认强制打开电子防窥雾化膜，交由系统内快捷键 `F2` / `hp-bridge` 按需切换 |
| **Advanced -> Port Options -> Thunderbolt Mode / Thunderbolt Type-C Ports** | **`Enable`** | 启用 Type-C 端口供电与 DisplayPort Alt-Mode |
| **Advanced -> Port Options -> USB Type-C Connector System Software Interface (UCSI)** | **`Enable`** | 保持 Type-C UCSI 状态机启用 |
| **Advanced -> Power Management Options -> Wake on Lid Open** | **`Enable`** | 允许在 S0ix 现代待机下通过开盖（EC `_Q0A` GPE `0x6E`）或电源键唤醒系统（注：macOS 下由 `SSDT-DEEPIDLE.aml` `\USWE = Zero` 与 `S0ixStandby` 默认屏蔽 USB 外设误唤醒） |

---

## 3. 第二阶段：磁盘分区与多系统共存规划 (Disk Partitioning & Dual-Boot Layout)

### 3.1 推荐 ESP 与 APFS 多系统分区布局

若在一块内置 NVMe SSD（如本机 512 GB Micron 2210 `nvme0n1` / `disk0`）上实现 **Windows + NixOS + macOS Tahoe 26** 三系统安全共存，推荐规划如下 GPT 分区结构（实机布局详见 [hardware/elite-dragonfly-g2.json](../hardware/elite-dragonfly-g2.json) 与 [docs/internal-boot.md](internal-boot.md)）：

- **全新规划建议**：
  - **EFI 系统分区 (ESP)**：建议至少 **`512 MB` ~ `1 GB`**（`FAT32` / `vfat`，GPT 类型 `EF00`），避免多系统内核与 OpenCore 资源共享时空间不足。
  - **macOS APFS 容器分区**：建议至少 **`100 GB` 以上**（GPT 类型 `AF0A0000` / `Apple_APFS`）。
- **本机实测多系统分区表（512 GB NVMe `disk0` / `nvme0n1`）**：

| Linux 设备名 | macOS 标识符 | 分区类型 / 文件系统 | 容量 | 挂载点与用途 |
| --- | --- | --- | --- | --- |
| `nvme0n1p1` | `disk0s1` | `EFI System` (`FAT32`) | `314.6 MB` | NixOS `/boot` 主引导分区：存放 `systemd-boot` 与内置 OpenCore (`/boot/EFI/OC/`) |
| `nvme0n1p2` | `disk0s2` | `Microsoft Reserved` (`MSR`) | `134.2 MB` | Windows GPT 保留分区（切勿删除） |
| `nvme0n1p3` | `disk0s3` | `Microsoft Basic Data` (`NTFS`) | `251.6 GB` | Windows 主数据卷“系统”（含跨系统只读诊断目录 `/hpdiag`） |
| `nvme0n1p4` | `disk0s4` | `Windows Recovery` (`NTFS`) | `1.2 GB` | Windows WinRE 恢复分区（注意：macOS `diskutil` 分区时可能改写其 GPT 类型，操作前后需用 `sfdisk -d` 备份） |
| `nvme0n1p5` | `disk0s5` | `Linux Filesystem` (`Btrfs`) | `137.7 GB` | NixOS 根文件系统 (`/`, `/nix/store`, `/home`) |
| `nvme0n1p6` | `disk0s6` | `EFI System` (`FAT32`) | `1.0 GB` | 第二 ESP 备用引导分区 |
| `nvme0n1p7` | `disk0s7` | `Apple_APFS` (`Container disk1`) | `115.9 GB` | **macOS Tahoe 26.6.2 (`25G83`) APFS 容器**（自动合成 `Tahoe`、`Tahoe - Data`、`Preboot`、`Recovery`、`VM` 卷） |
| `nvme0n1p8` | `disk0s8` | `Linux Swap` (`swap`) | `3.1 GB` | NixOS 交换分区 |

### 3.2 创建 APFS 容器与保护 Windows / Linux 引导

1. **在 Linux / NixOS 下预先腾出未分配空间或目标分区并备份 GPT 表**：
   ```sh
   sudo sfdisk -d /dev/nvme0n1 > gpt-backup-before-macos.sfdisk
   ```
2. **进入 macOS Recovery 后将目标分区格式化为 APFS 容器**：
   ```sh
   # 先用 diskutil list 确认目标分区标识符（如本机为 disk0s7），切勿误选 NTFS 或 Linux 分区！
   diskutil list
   diskutil apfs create /dev/disk0s7 "Tahoe"
   ```
3. **配置 NixOS `systemd-boot` 链式加载 OpenCore（零侵入固件 NVRAM）**：
   - 将验证通过的 `EFI/OC` 目录部署至 `/boot/EFI/OC`（即 `nvme0n1p1`）。
   - 在 NixOS 的 `/boot/loader/entries/macos-opencore.conf` 中创建启动项（参见 [docs/internal-boot.md](internal-boot.md)）：
     ```text
     title   macOS (OpenCore)
     efi     /EFI/OC/OpenCore.efi
     ```
   - 在 OpenCore `config.plist` 中确保：
     - `Booter -> Quirks -> SyncRuntimePermissions = true`
     - `UEFI -> Quirks -> RequestBootVarRouting = true`
     - `Misc -> Boot -> LauncherOption = Disabled`
     这样 OpenCore 不会篡改主板固件的 `BootOrder`（默认仍保持 `Linux Boot Manager` / NixOS 优先，Windows `Bootmgfw.efi` 独立并存），在 NixOS 下可通过以下命令安全触发单次引导进入 macOS：
     ```sh
     sudo bootctl set-oneshot macos-opencore.conf && sudo reboot
     ```

### 3.3 内置硬盘引导必配：`pmap_recycle_page` 脏页隔离 (`PMAPFIX`)

从内置 NVMe SSD（经固件或 `systemd-boot` 链式加载 OpenCore）启动进入 macOS 后约 `252s ~ 394s`（6 分 34 秒），若未做物理内存隔离，XNU 虚拟机页面回收器在 `_vm_page_free_list -> pmap_recycle_page` 会必现内核断言崩溃：
```text
panic(cpu 6 caller 0xffffff800046709b): pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511
```
- **根因**：HP 固件与链式引导阶段在物理内存窗口 **`0x101304000..0x10131c000`**（4 GiB + 约 19 MiB 处）遗留了未释放的 DMA/页表引用（详见 [docs/repair32-gpu-stability-and-pmapfix-20261106.md](repair32-gpu-stability-and-pmapfix-20261106.md)）。
- **根治方法 (`PMAPFIX`)**：在 `config.plist` 的 `UEFI -> ReservedMemory` 中将 **`0x101000000..0x101400000`**（共 `4 MiB`）标记为 `Reserved`（可配置为单条 `Address = 4311744512 (0x101000000), Size = 4194304 (0x00400000)`，或如 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist` 所示按 64 KiB 块 + `0x101300000..0x10131f000` 逐 4 KiB 页精确保留）。

---

## 4. 第三阶段：制作安装介质与 OpenCore 1.0.8 引导配置 (Installer USB / Ventoy & OpenCore Setup)

### 4.1 制作 macOS Tahoe 安装介质（标准 USB 或 Ventoy 离线镜像方案）

本仓库支持两种安装介质制备方式（所有本地构建均在 `nix develop` 环境下完成，参见 [flake.nix](../flake.nix) 与 [docs/offline-installer-inputs.md](offline-installer-inputs.md)）：

1. **方案 A：Ventoy U 盘 + OpenCore Recovery `.img` + 离线 HFS+ 安装卷（本仓库实机采用方案，无需抹除已有 U 盘）**：
   - 下载并校验 Apple 官方 `InstallAssistant.pkg`（`18,384,624,402` 字节，SHA256 `376923d7494cfa32b69f383bcfdce46aeedb609fe6a242ea12a6e015bfb77ba4`）：
     ```sh
     nix develop -c python3 scripts/fetch_install_assistant.py --help
     nix develop -c python3 scripts/verify_install_assistant.py --help
     ```
   - 使用打了 4 GiB 大文件偏移修复补丁 [patches/xpwn-large-volume-offset.patch](../patches/xpwn-large-volume-offset.patch) 的 `hfsplus` 与 [scripts/build_offline_app_volume.py](../scripts/build_offline_app_volume.py) 重建完整 `19,922,944,000` 字节离线 HFS+ 映像 `Tahoe-26.6.2-Offline-App.hfs`（内含完整 `Install macOS Tahoe.app` 及 `SharedSupport.dmg`）。
   - **最新全功能引导与恢复合一镜像 (`HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`)**：
     - 本地构建路径：`.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`
     - 镜像大小与校验值：`1,343,225,856` 字节，SHA256 `4ab8aff3a2f65cfc126faf19c9334798ef623a8dfbbe534ec78ede7f968850c9`
     - 内置组件：在分区偏移 `@@1048576` 的 FAT32 ESP 中同时包含完整 **111 个文件**的 `/EFI/OC`（含 OpenCore 1.0.8、`config.plist` `60,234` 字节 SHA256 `f1f6b95569b7167ce3b166ca38b3f6bac7f8570dd14938187ebdb22090d3cf6b`、`SSDT-DEEPIDLE.aml` `371` 字节 SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`、`SSDT-EC0-ITLB.aml` `1,572` 字节 SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8`、`NootedGreen.kext` `R32-PCFIX37-WAKERGB` `Contents/MacOS/NootedGreen` `540,944` 字节 SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3` & `Contents/Info.plist` `3,700` 字节 SHA256 `b5fd1d0fe125a48f6045c3b07a8f5894f76fc406caf5065f126830a63ea4738e`、`S0ixStandby.kext` `v0.4.4` `74,584` 字节 SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`、`TGLDmic.kext` `v0.5.0` 等，经 `fsck.vfat -n` 零错误通过）以及 `/com.apple.recovery.boot/BaseSystem.dmg`（`960,530,321` 字节，macOS Tahoe 26.6.2 `25G83` Recovery）与 `BaseSystem.chunklist`（`3,604` 字节）。
     - 可同步写入 Lexar Ventoy U 盘 `/Volumes/Yan/ISO/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`；Stage 1 初装系统时也可配合 `HP-Tahoe-VESA-XHCI-RHUB.img` 与 `/Volumes/Yan/ISO/linux/Tahoe-26.6.2-Offline-App.hfs` 使用。
2. **方案 B：独立 FAT32/HFS+ 安装 U 盘**：
   - 将 U 盘格式化为 GPT 分区表，第 1 分区为 `>= 512 MB` FAT32 `EFI` 分区（放入下述 `/EFI/BOOT/BOOTx64.efi` 与 `/EFI/OC/`），第 2 分区放入 macOS BaseSystem Recovery 或使用 `createinstallmedia` 写入 `Install macOS Tahoe.app`。

### 4.2 `/EFI/OC` 目录结构

基于 **OpenCore 1.0.8**（每次修改 `config.plist` 后必须通过同版本 `ocvalidate` 静态校验零告警）：

```text
EFI/
├── BOOT/
│   └── BOOTx64.efi
└── OC/
    ├── OpenCore.efi
    ├── config.plist
    ├── ACPI/
    │   ├── SSDT-PLUG.aml              # (或 SSDT-PLUG-ALT.aml)
    │   ├── SSDT-EC-USBX-HP.aml        # (或 SSDT-EC-USBX.aml)
    │   ├── SSDT-RHUB-HP.aml
    │   ├── SSDT-PNLF-HP-GA419.aml     # (或 SSDT-PNLF.aml)
    │   ├── SSDT-DEEPIDLE.aml          # S0ix Modern Standby (LPS0/LXEN/PEPD + LID/SLPB GPE 0x6E Wake + \USWE=Zero)
    │   └── SSDT-EC0-ITLB.aml          # 早期启动 EC 16-bit 字段 (BDC/BFC/BDV/ACPR) 8-bit 拆分
    ├── Drivers/
    │   ├── OpenRuntime.efi
    │   └── OpenHfsPlus.efi
    └── Kexts/
        ├── Lilu.kext
        ├── AppleALC.kext
        ├── SimpleHDA.kext
        ├── NootedGreen.kext           # Stage 1 设为 false, Stage 2 设为 true (R32-PCFIX37-WAKERGB)
        ├── VirtualSMC.kext
        ├── SMCProcessor.kext
        ├── SMCBatteryManager.kext
        ├── WhateverGreen.kext         # Stage 1 配合 -igfxvesa 使用, Stage 2 必须设为 false!
        ├── VoodooPS2Controller.kext   # 内含 PlugIns/VoodooPS2Keyboard.kext (含自定义 ADB 映射)
        ├── VoodooI2C.kext             # 内含 VoodooGPIO, VoodooI2CServices, VoodooInput
        ├── VoodooI2CHID.kext
        ├── AirportItlwm.kext
        ├── XHCI-unsupported.kext      # (或 USBToolBox.kext + UTBMap.kext)
        ├── DebugEnhancer.kext
        ├── ECEnabler.kext
        ├── BrightnessKeys.kext
        ├── IntelBluetoothFirmware.kext
        ├── IntelBTPatcher.kext
        ├── BlueToolFixup.kext
        ├── TGLDmic.kext               # Tiger Lake cAVS 2.5 四阵列数字麦克风驱动 (v0.5.0)
        └── S0ixStandby.kext           # Modern Standby (S0ix) 电源管理驱动 (v0.4.4)
```

### 4.3 ACPI SSDTs、OEM 表删除 (`ACPI -> Delete`) 与二进制重命名 (`ACPI -> Patch`) 详解

详情参见 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist`、[docs/acpi-preflight.md](acpi-preflight.md)、[.local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.dsl](../../EFI/ACPI/SSDT-DEEPIDLE.dsl) 与 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.dsl`：

| ACPI 表 / 补丁名称 | 实机启用状态 | 作用与技术细节 |
| --- | --- | --- |
| **`SSDT-PLUG.aml`** (或 `SSDT-PLUG-ALT.aml`) | **必选 (`Enabled`)** | 在 `\_SB.PC00.PR00` 注入 Darwin 专属 `plugin-type = 1`，激活 XNU `X86PlatformPlugin` 原生 CPU 睿频与电源管理 |
| **`SSDT-EC-USBX-HP.aml`** (或 `SSDT-EC-USBX.aml`) | **必选 (`Enabled`)** | 为 macOS 暴露虚拟 `EC` 控制器与 `USBX` 供电电流属性，确保 `AppleBusPowerController` 正常加载 |
| **`SSDT-RHUB-HP.aml`** + **`ACPI -> Delete` 丢弃 OEM `SSDT13` (`HP_XHC_P`)** | **必选 (`Enabled`)** | 1. 针对 Tiger Lake PCH XHCI (`8086:a0ed`) 在 Darwin 下置 `\_SB.PC00.XHCI.RHUB._STA = Zero`，恢复全部 12 个 USB2 + 3 个 USB3 端口（含内置摄像头 `HS02`、指纹 `HS07`、蓝牙 `HS10` 及外置 USB 口，详见 [docs/input-recovery.md](input-recovery.md)）；<br>2. 配合 `ACPI -> Delete` 丢弃 OEM `SSDT13`（`TableSignature = 53534454` `"SSDT"`, `OemTableId = 48505F58 48435F50` `"HP_XHC_P"`, `TableLength = 2362`），彻底消除开机早期 `RHUB.HS09` 尚未由 `DSDT` 模块级 `If` 块创建时触发的 `ACPI Error: [\_SB_.PC00.XHCI.RHUB.HS09] Namespace lookup failure, AE_NOT_FOUND` |
| **`SSDT-PNLF-HP-GA419.aml`** (或 `SSDT-PNLF.aml`) | **必选 (`Enabled`)** | 在 `\_SB.PC00.GFX0` 下定义背光设备 `PNLF`（`_UID = 0x13 = 19`），使 `AppleBacklightDisplay` 挂载到内屏连接 |
| **`SSDT-DEEPIDLE.aml`** + **`MS-SSDT` `_STA -> XSTA` 重命名** | **必选 (`Enabled`)** | 编译自 [.local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.dsl](../../EFI/ACPI/SSDT-DEEPIDLE.dsl)（`2,793` 字节，SHA256 `1f569b6bbb0d4305a27fcadeedf69a463c18f47b581d5140fb8acb2ecccfb1b9` -> 二进制 `SSDT-DEEPIDLE.aml` `371` 字节，SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`）：<br>1. 在 Darwin 下定义 `\_SB.LPS0` 与 `\_GPE.LXEN` 返回 `One`，使 `AppleACPIPlatform` 发布 `IOPMDeepIdleSupported = Yes` 并选择睡眠类型 7 (`kIOPMSleepTypeDeepIdle`)；<br>2. 配合 `ACPI -> Patch` 中限定 `TableSignature = SSDT`、`OemTableId = 4D532D5353445400` (`MS-SSDT`) 的唯一重命名 `Find: 14275F53544100` (`FCdfU1RBAA==`) -> `Replace: 14275853544100` (`FCdYU1RBAA==`, `Count = 1`)，在 Darwin 下置 `S0ID = One` 并令 `\_SB.PEPD._STA` 返回 `0x0F`，无需全局 `XOSI` 补丁即可挂载 `PNP0D80` 供 `S0ixStandby.kext` 绑定；<br>3. 为 `\_SB.LID` 与 `\_SB.SLPB` 注入 `_PRW`/`PRW0` (`Package (0x02) { 0x6E, 0x04 }`) 与 `_S0W` (`0x04`)，使 `AppleACPIPlatform` 在 S0ix Deep Idle 进入前保持 GPE `0x6E` 唤醒掩码使能，实现开盖（EC `_Q0A`）即刻触发硬件 SCI 唤醒；<br>4. 在 Darwin 下置 `\USWE = Zero`，从 ACPI `GPRW` 层面阻断 `XHCI`、`TXHC`、`TRP0..3`、`XDCI`、无线与 PCIe 根端口的 `0x6D`/`0x69` USB/PCI PME 唤醒能力 |
| **`SSDT-EC0-ITLB.aml`** + **4 项早期 EC 16-bit 方法重命名 (`ITLB`/`EC12`/`EC13`/`ODVP`)** | **必选 (`Enabled`)** | 编译自 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.dsl`（二进制 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.aml`，`1,572` 字节，SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8`）：<br>1. `AppleACPIEC::start` 在开机早期 `t ~ 1.93s` 执行 `EC0._REG(3, 1) -> ECRI()`，比 `ECEnabler.kext` 在 `t ~ 2.57s` 完成 `ecSpaceHandler` hook 早约 `640 ms`。当 `ECRI()` 执行时，依次调用 `ITLB()`（读 16-bit `BFC` @ `0x8D`）、`SBTN()` 及 `PRIT()`（调用 `SSDT2` `NVTEC` 的 `EC12()` 读 16-bit `ACPR` @ `0xF9`、`EC13()` 读 16-bit `BDC` @ `0x89` 与 `BDV` @ `0x95`，并触发 `SSDT14` `DptfTabl` 的 `\_SB.IETM.ODVP()` 同步读取 `ACPR`/`BDC`/`BDV`）；<br>2. 通过 4 个 `EmbeddedControl` 8-bit 拆分区域（`BDCL`/`BDCH`、`BFCL`/`BFCH`、`BDVL`/`BDVH`、`ACPL`/`ACPH`）重写 `EC0.{ITLB,EC12,EC13}` 与 `\_SB.IETM.ODVP`，配合 4 条 `Count = 1` 精确重命名（`DSDT` `49544C42 00 -> 58544C42 00`、`SSDT` `NVTEC` `45433132 00 -> 58433132 00` 与 `45433133 00 -> 58433133 00`、`SSDT` `DptfTabl` `4F445650 08 -> 58445650 08`），在实机冷启动 `BEC29211-881D-4E0E-99CC-5EE3C76A6FF5` 上验证 **`AE_NOT_FOUND = 0`、`AE_BAD_PARAMETER = 0`（整机 `dmesg` 0 次 ACPI Error/Exception）** |
| `SSDT-HP-FixAudioIRQ.aml` / `SSDT-SBUS-MCHC.aml` / `SSDT-GPRW.aml` / `SSDT-HP-FixLidSleep.aml` | 机型可选 (840 G8 参考) | - **`SSDT-HP-FixAudioIRQ.aml`**：在部分 HP EliteBook 840 G8 (`880D`) BIOS 上，传统 `TIMR` (`PNP0100`)、`RTC` (`PNP0B00`) 与 `HPET` (`PNP0103`) 占用了 `IRQNoFlags {0, 8, 11}`，导致 `HDAS`/`ALC285` 控制器中断冲突无声；通过移除 `TIMR`/`RTC` 的冗余 IRQ 并将 `IRQ 0/8/11` 释放给 `HPET`/`HDAS` 解决。<br>- 在 Dragonfly G2 (`8716`) 上，原生 `DSDT` 无该 IRQ 冲突，且盒盖/开盖唤醒与 USB 误唤醒屏蔽已由 `SSDT-DEEPIDLE.aml` (`\_SB.LID` / `\_SB.SLPB` `_PRW` `0x6E` + `\USWE = Zero`) + `S0ixStandby.kext` (`v0.4.4`) 原生接管，无需额外注入 `SSDT-GPRW` 或 `SSDT-HP-FixLidSleep`。<br>- **注意**：切勿在 DSDT 中对 `GVWE` / `_Q86` / `_Q87` 做全局二进制重命名（`SSDT-HP-Hotkeys.aml`），否则 `\_SB.AC._PSR` 在开机 `PMRD: PowerChangeDone` 阶段可能发生同步阻塞停滞（详见 [docs/continuation.md](continuation.md)）。 |

### 4.4 Kexts 加载顺序与功能配置

在 `config.plist -> Kernel -> Add` 中共包含 **25 项条目**（**24 项 `Enabled = true` + 1 项 `Enabled = false` 的 `WhateverGreen.kext`**），**严格按照以下依赖顺序**排列（详见 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist`）：

1. **`Lilu.kext`** (`Enabled = true`, `MinKernel = 25.0.0`)：内核与用户态动态修补核心基底，必须排在第 1 位。
2. **`AppleALC.kext`** (`1.9.8`, `Enabled = true`)：紧随 `Lilu` 加载，提供 Realtek `ALC285` 布局（含 `0xa0c8` 控制器匹配与 `layout-id 71` / `11`）。
3. **`SimpleHDA.kext`** (`1.0.1`, `Enabled = true`)：在已移除原生 `AppleHDA` 的 macOS Tahoe 26 上恢复 HDA 音频引擎栈，无需修改系统根卷。
4. **`NootedGreen.kext`** (`R32-PCFIX37-WAKERGB`, `Enabled = true`)：Tiger Lake Iris Xe (`8086:9a49`) 核心内核修补驱动（**注意：Stage 1 初装系统时设为 `false`，Stage 2 安装完 `/Library/Extensions` 驱动后设为 `true`**）。
5. **`VirtualSMC.kext`** (`1.3.7`, `Enabled = true`)：SMC 仿真核心，排在所有 SMC 插件之前（兼容 `1.3.8`，实机在线加载 `1.3.7` 并注册 `118` 个 SMC 键）。
6. **`SMCProcessor.kext`** (`1.3.7`, `Enabled = true`)：读取 Tiger Lake CPU 核心温度（`TC0P`, `TC1C..TC4C`）与 RAPL 封装功率（`PC0C`, `PCPT`）。
7. **`SMCBatteryManager.kext`** (`1.3.7`, `Enabled = true`)：配合 `ECEnabler.kext` 与 `SSDT-EC0-ITLB.aml` 提供 `AppleSmartBattery` 与 `B0RM`/`B0FC`/`B0AV`/`B0CT`/`BRSC` 电池状态遥测。
8. **`WhateverGreen.kext`** (**`Enabled = false`**)：仅在 Stage 1 VESA 安全引导时临时配合 `-igfxvesa` 使用；**当启用 `NootedGreen.kext` 时必须设为 `false`**，否则两者抢占 IGPU 钩子会导致启动崩溃。
9. **`VoodooPS2Controller.kext`** + **`VoodooPS2Keyboard.kext`**（占第 9–10 项，`Enabled = true`）：驱动内置 i8042 PS/2 键盘，并在 `VoodooPS2Controller.kext/Contents/PlugIns/VoodooPS2Keyboard.kext/Contents/Info.plist` 的 `Custom ADB Map` 中内置 24 条 HP 顶排快捷键与 JIS 键位映射。
10. **`VoodooI2C.kext` 组件群**（占第 11–15 项，`Enabled = true`）：按固定顺序依次加载：
    - `VoodooI2C.kext/Contents/PlugIns/VoodooGPIO.kext`
    - `VoodooI2C.kext/Contents/PlugIns/VoodooI2CServices.kext`
    - `VoodooI2C.kext/Contents/PlugIns/VoodooInput.kext`
    - `VoodooI2C.kext`
    - `VoodooI2CHID.kext`
    用于驱动 Synaptics `06cb:cd74` (`SYNA30B6`) GPIO 中断精确触控板与 Wacom `056a:4924` (`WACF4233`) I²C 触屏。
11. **`AirportItlwm.kext`**（第 16 项，`2.4.0` Tahoe Alpha, `Enabled = true`）：驱动 Intel AX201 Wi-Fi 并仿真为原生 IO80211 `en0` 接口。
12. **`XHCI-unsupported.kext`**（第 17 项，`Enabled = true`）：注入 `8086:a0ed` -> `AppleUSBXHCISPT` 属性匹配（或在 EliteBook 840 G8 上配合 `USBToolBox.kext` + `UTBMap.kext` 完成 15 端口定制；本机通过 `SSDT-RHUB-HP.aml` + `XHCI-unsupported.kext` 已完整恢复全部内置与外置 USB 端口）。
13. **`DebugEnhancer.kext`**（第 18 项，`1.1.1`, `Enabled = true`）：扩大内核日志缓冲区，便于 `dmesg` 全量取证。
14. **`ECEnabler.kext`**（第 19 项，`Enabled = true`）：允许 macOS 直接读取超过 8-bit 宽度的 HP EC 电池寄存器字段，免除繁琐的 DSDT 电池拆分补丁。
15. **`BrightnessKeys.kext`**（第 20 项，`Enabled = true`）：辅助监听 ACPI 显示器亮度通知。
16. **`IntelBluetoothFirmware.kext`** (`2.5.2`) + **`IntelBTPatcher.kext`** (`2.5.2`) + **`BlueToolFixup.kext`** (`2.7.2`)（占第 21–23 项，`Enabled = true`, `MinKernel = 21.0.0`）：为 Intel `8087:0026` 蓝牙控制器上传固件并修补 macOS Tahoe `bluetoothd` 兼容性。
17. **`TGLDmic.kext`**（第 24 项，`0.5.0`, `Enabled = true`）：驱动 Intel Tiger Lake cAVS 2.5 DSP (`8086:a0c8`)，提供内置 4 阵列 PDM 数字麦克风 DMA 采集。
18. **`S0ixStandby.kext`**（第 25 项，`0.4.4`, `Enabled = true`, `MinKernel = 25.0.0`）：驱动 `PNP0D80` (`PEPD`)，执行完整 S0ix Modern Standby `_DSM` 睡眠/唤醒序列（fn `3/5/6/4` + `pmCPUHaltHook` 排空闭盖非唤醒电池 SCI）、LPIT 计数器监控、未绑定 PCI 设备 `D3hot` 门控、默认 USB/TBT 唤醒抑制（清零 PCI `PME_EN` 并屏蔽 `GPE 0x6D/0x69`）、`-s0ixcnvwd3` 对 `CNVW` `00:14.3` 执行 `BAR0` 软复位 + `D3hot` + `XSQD` 清除，以及睡眠/唤醒 `PLANE_CTL_1_A` RGB 规范化。
19. *(可选)* **`NVMeFix.kext`**：开启第三方/OEM NVMe SSD（如本机 Micron 2210 `MTFDHBA512QFD-1AX1AABHA` `1344:5404`）的 `ASPM L1` 与 APST 电源管理。

### 4.5 `DeviceProperties` 设备属性注入、XCPM CPUID 仿冒 (`0x706E5`) 与早期 EC 16-bit 字段拆分 (`SSDT-EC0-ITLB.aml`)

在 `config.plist -> DeviceProperties -> Add` 中配置核显与声卡属性（参见 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist`）：

```xml
<key>DeviceProperties</key>
<dict>
	<key>Add</key>
	<dict>
		<key>PciRoot(0x0)/Pci(0x2,0x0)</key>
		<dict>
			<!-- 原生 Tiger Lake NootedGreen 平台 ID: <0000499a> (Base64: AABJmg==) -->
			<key>AAPL,ig-platform-id</key>
			<data>AABJmg==</data>
		</dict>
		<key>PciRoot(0x0)/Pci(0x1F,0x3)</key>
		<dict>
			<!-- Dragonfly G2 (103c:8716) 使用 layout-id = 71 (<47000000>, Base64: RwAAAA==) -->
			<!-- 若为 EliteBook 840 G8 标准布局，可设为 layout-id = 11 (<0B000000>, Base64: CwAAAA==) -->
			<key>layout-id</key>
			<data>RwAAAA==</data>
			<key>alc-verbs</key>
			<data>AQAAAA==</data>
		</dict>
	</dict>
</dict>
```

> [!TIP] **关于 `AAPL,ig-platform-id`、`Kernel -> Emulate` CPUID 仿冒 (`0x706E5`) 与 `SSDT-EC0-ITLB.aml` 的关键配置要点**
> 1. **原生 Gen12LP 显示管道与背光缩放 (`AAPL,ig-platform-id = <0000499a>`)**：在使用本仓库 **`NootedGreen.kext` (`R32-PCFIX37-WAKERGB`)** 的原生 Tiger Lake 方案中，`PciRoot(0x0)/Pci(0x2,0x0)` 必须注入 **`AAPL,ig-platform-id = <0000499a>`**（`AABJmg==`），使 `AppleIntelTGLGraphicsFramebuffer` 走原生 Gen12LP 显示管道，同时由 `NootedGreen` 内置的 `XE-BLR`（`xeFixFilterWrite`）自动完成 PCH 背光寄存器 `0xC8254`/`0xC8258` 频率与占空比缩放，并在唤醒期将 `PLANE_CTL_1_A` (`0x70180`) 强制归一化为 Gen12 RGBX8888 (`0x84000400`)。旧式 Ice Lake 核显仿冒属性（如 `07009B3E` 或 `WhateverGreen` 的 `enable-backlight-registers-fix`）在启用原生 TGL + `NootedGreen` 时无需且不应混用。
> 2. **`Kernel -> Emulate` CPUID 仿冒（`Cpuid1Data = E5060700...` Ice Lake-LP `0x706E5` 激活 `X86PlatformPlugin` `J214k` `39` 档 P-States）**：Tiger Lake-UP3（`i5-1135G7` / `i7-1165G7`）的真实硬件 CPUID 为 **`0x806C1`**（Model `140` / `0x8C`），而 macOS XNU 内核 XCPM 表最高仅内置到 Ice Lake-LP **`0x706E5`**（Model `126` / `0x7E`）。通过在 `Kernel -> Emulate` 中配置 `Cpuid1Data = <E5060700 00000000 00000000 00000000>` 与 `Cpuid1Mask = <FFFFFFFF 00000000 00000000 00000000>`，XNU 将 CPU 识别为 Model `126` 并配合 `MacBookPro16,2`（`J214k` / `Mac-5F9802EFE386AA28.plist`）与 `SSDT-PLUG.aml`（`plugin-type = 1`）完整加载原生 `X86PlatformPlugin`（`machdep.xcpm.vectors_loaded_count = 1`，**`39` 档 `CPUPStates` `400..4200 MHz`** 与 `2` 个 `FrequencyVectors` 向量表）；与此同时，`S0ixStandby.kext v0.4.4` 直接调用硬件 `cpuid(1)` 指令读取真实 `"CPU model" = 140`（`0x806C1`），实现 XCPM 变频与 Tiger Lake S0ix 电源管理完美兼得（详见 `xcpm-cpu-topology.txt`）。
> 3. **已部署 `SSDT-EC0-ITLB.aml` 早期启动 EC 16-bit 字段 (`BDC`/`BFC`/`BDV`/`ACPR`) 8-bit 拆分补丁**：虽然运行态电池遥测由 `ECEnabler.kext` + `SMCBatteryManager.kext`（共枚举 `118` 个 `VirtualSMC` 键）完整驱动，但 `AppleACPIEC::start` 在开机 `t ~ 1.93s` 触发 `EC0._REG(3, 1) -> ECRI()` 比 `ECEnabler.kext` 在 `t ~ 2.57s` 完成 hook 早约 `640 ms`。已部署的 `SSDT-EC0-ITLB.aml`（`1,572` 字节，SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8`，源码 `SSDT-EC0-ITLB.dsl`）将 `BDC` (`0x89`)、`BFC` (`0x8D`)、`BDV` (`0x95`) 与 `ACPR` (`0xF9`) 四个 16-bit EC 字段拆分为 8-bit 字节对并在 `EC0.{ITLB,EC12,EC13}` 与 `\_SB.IETM.ODVP` 中合成 16-bit 值，配合 4 条 OpenCore `ACPI -> Patch` 唯一重命名，在 `ECEnabler` 介入前零报错完成 `ECRI()` -> `ITLB()`/`SBTN()`/`PRIT()` 全链路初始化（冷启动 `BEC29211-881D-4E0E-99CC-5EE3C76A6FF5` 实测 `0` 次 `AE_BAD_PARAMETER`，详见 `dmesg-acpi-zeroerr-bec29211.txt`）。

### 4.6 Booter / Kernel Quirks 与 NVRAM `boot-args` 参数详解

#### 4.6.1 关键 Booter 与 Kernel 配置
- **`Booter -> Quirks`**：
  - `DevirtualiseMmio = true`：**极其关键**。移除 HP 固件中 `0xc0000000` / `0xff000000` 两段共 272 MiB MMIO 区域的 `EFI_MEMORY_RUNTIME` 属性，解决 `boot.efi` 在 `EB.MM.AKM` 申请 `0x110b2000` 字节时触发 `STOP 0x16` (`StartImage failed - Aborted`) 的致命启动失败（详见 [docs/install-handoff.md](install-handoff.md)）。
  - `ProvideCustomSlide = true`、`ProvideMaxSlide = 0`、`EnableSafeModeSlide = true`、`RebuildAppleMemoryMap = true`、`SyncRuntimePermissions = true`、`AvoidRuntimeDefrag = true`、`ProtectUefiServices = true`、`SetupVirtualMap = false`。
- **`Kernel -> Emulate`（Tiger Lake `0x806C1` -> Ice Lake-LP `0x706E5` CPUID 仿冒，激活 `J214k` `39` 档 P-States）**：
  - XNU 内核原生不支持 Tiger Lake `0x806C1`（Model `140`）的 XCPM 电源管理表，必须仿冒为 Ice Lake-LP `0x706E5`（Model `126`），从而在 `MacBookPro16,2`（`J214k` / `Mac-5F9802EFE386AA28.plist`）下启用原生 `X86PlatformPlugin`（`machdep.xcpm.vectors_loaded_count = 1`，`39` 档 P-States `400..4200 MHz`）：
    - `Cpuid1Data = <E5060700 00000000 00000000 00000000>` (`5QYHAAAAAAAAAAAAAAAAAA==`)
    - `Cpuid1Mask = <FFFFFFFF 00000000 00000000 00000000>` (`/////wAAAAAAAAAAAAAAAA==`)
- **`Kernel -> Quirks`**：
  - `AppleXcpmCfgLock = true`、`AppleXcpmExtraMsrs = true`、`DisableIoMapper = true`、`DisableLinkeditJettison = true`、`DisableRtcChecksum = true`、`PanicNoKextDump = true`、`ProvideCurrentCpuInfo = true`。

#### 4.6.2 NVRAM `boot-args` 逐项说明
在 `NVRAM -> Add -> 7C436110-AB2A-4BBB-A880-FE41995C9F82` 中，实机最终稳定运行的 `boot-args` 为（总长控制在 255 字符 `BOOT_LINE_LENGTH - 1` 限制以内，详见 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist`）：

```text
-v keepsyms=1 debug=0x100000 slide=0 -ngreentglwithgfx ngreenSched=3 ngreen-dmc=tgl -ngreenfixbootmode IGLogLevel=3 amfi_get_out_of_my_way=1 -allow3d -disablegfxfirmware ngreen-eu=80 ngreen-l3=6 -tgldmic -s0ixd3 -s0ixdbg -s0ixnogpureset -s0ixcnvwd3
```

各启动标志的具体作用如下表所示：

| 启动参数 (`boot-args`) | 所属组件 | 作用说明 |
| --- | --- | --- |
| `-v` | XNU | 开启详细文本引导模式（Verbose Boot），便于观察启动门控日志 |
| `keepsyms=1` | XNU | 在内核 Panic 报告中保留完整函数符号名 |
| `debug=0x100000` (或 `debug=0x100`) | XNU | **注意**：推荐使用 `debug=0x100000`（开启符号化而不置位 `0x100 DB_HALT`）；若使用 `debug=0x100`，内核在发生 Panic 时会停留在 `_kdp_i386_trap` 而不自动重启（若在关屏时触发则表现为假死黑屏） |
| `slide=0` | `boot.efi` / OC | 固定内核 KASLR 偏移为 `0`，配合 `DevirtualiseMmio` 确保低地址连续物理内存分配成功 |
| `-ngreentglwithgfx` | `NootedGreen` | 在真实 Tiger Lake 硬件上同时启用 `AppleIntelTGLGraphicsFramebuffer` 与 `AppleIntelTGLGraphics` 完整 3D/Compute 加速 |
| `ngreenSched=3` | `NootedGreen` | 将 `AppleIntelTGLGraphics` 调度器固定为模式 `3`（**原生硬件 Execlist 门铃直提模式**，绕过不兼容的 Apple GuC 固件调度） |
| `-disablegfxfirmware` | `NootedGreen` / TGL | 禁止 Apple 驱动加载不兼容的 GuC/HuC 图形微码，配合 `ngreenSched=3` 使用 Execlist 提交 |
| `ngreen-dmc=tgl` | `NootedGreen` | 为 Tiger Lake 显示引擎加载匹配的 Display DMC 固件（`program 0x0b004040`） |
| `-ngreenfixbootmode` | `NootedGreen` | 修复从 GOP 引导帧缓冲向 `AppleIntelTGLGraphicsFramebuffer` 切换时的模式过渡 |
| `ngreen-eu=80 ngreen-l3=6` | `NootedGreen` | 声明 GPU 拓扑为 `80 EU`、`6` 组 L3 bank（i5-1135G7 实载 80 EU；i7-1165G7 亦可稳定运行于 `ngreen-eu=80` 或 `96`） |
| `-allow3d` | TGL / Metal | 显式启用 Metal 3D 与 Compute 硬件加速管线 |
| `amfi_get_out_of_my_way=1` | XNU AMFI | 允许加载本地 ad-hoc 签名的 `/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle`、`libxedrv.dylib` 与 `libhp_cb_shim.dylib` |
| `IGLogLevel=3` | Framebuffer | 开启图形驱动运行态诊断日志 |
| `-tgldmic` | `TGLDmic.kext` | 启用 Tiger Lake cAVS 2.5 四阵列数字麦克风驱动 |
| `-s0ixd3` | `S0ixStandby.kext` | 在睡眠前自动将未绑定驱动的空闲 PCI 设备置入 `D3hot`，消除 SLP_S0 阻塞源 |
| `-s0ixdbg` | `S0ixStandby.kext` | 开启 S0ix 睡眠/唤醒过程详细诊断日志 |
| **`-s0ixnogpureset`** | `S0ixStandby.kext` | **极其关键**：禁止 `S0ixStandby` 在唤醒时对 `00:02.0` 执行粗暴的 `GDRST=1` 全量 GPU 硬复位，保护存活的 GT `HWS_PGA` 与 `GFX_MODE` 状态 |
| **`-s0ixcnvwd3`** | `S0ixStandby.kext` | **生产必选**：在 `onSleep()` 时对 `CNVW` (`00:14.3` `8086:a0f0`) 执行 `BAR0` MMIO 软复位（清零 `CSR_GP_CNTRL`、`FH_TX_CHICKEN` 与中断掩码）、置入 `D3hot` (`PMCSR=0x000B`) 并调用 `\_SB.PC00.CNVW.XSQD()`，唤醒时恢复 `D0` (`0x0008`)，释放 PCH `SLP_S0` 门控 |
| `-s0ixusbwake` *(可选)* | `S0ixStandby.kext` | 可选启动参数：**默认不传**（默认启用 `noUsbWake`，配合 `\USWE = Zero` 清零 `XHCI`/`TXHC`/`TBT` 的 PCI `PME_EN` 并屏蔽 `GPE 0x6D/0x69` 防止 USB 外设误唤醒）；仅在确需外置 USB 键鼠唤醒时传入 |
| `s0ixfn=<mask>` *(可选诊断)* | `S0ixStandby.kext` | 可选诊断参数：**生产默认不传**（执行完整 Intel `PEPD._DSM` fn `3/5/6/4` `EC0.SLPT = 6`，并由 `pmCPUHaltHook` 排空闭盖非唤醒电池 SCI，在 `B004F99C` 实测 `51.6 分钟` 连续深度 S0ix 休眠） |
| `alcid=71` / `alcid=11`、`alcverbs=1` | `AppleALC.kext` | 可通过 `DeviceProperties`（推荐，节省 `boot-args` 字节长度）或 `boot-args` 传入声卡 Layout ID 与 `alc-verb` 支持 |
| `-ngfxsubmit` / `-ngfxgl` | 传统 WEG 参数 | 仅在使用 `WhateverGreen` 时有效；在使用 `NootedGreen` 时由 `-ngreentglwithgfx` 与 `-allow3d` 替代 |

### 4.7 SMBIOS 机型身份生成 (`MacBookPro16,2`)

在 `config.plist -> PlatformInfo -> Generic` 中，统一使用 **`MacBookPro16,2`**（2020 款 13 英寸四核 Ice Lake MacBook Pro，其电源管理曲线、Thunderbolt/USB-C 拓扑与内屏属性最契合 Tiger Lake 轻薄本）：

```xml
<key>Generic</key>
<dict>
	<key>AdviseFeatures</key>
	<false/>
	<key>MLB</key>
	<string>&lt;GENERATED_MLB&gt;</string>
	<key>MaxBIOSVersion</key>
	<false/>
	<key>ProcessorType</key>
	<integer>0</integer>
	<key>ROM</key>
	<data>&lt;GENERATED_ROM_BASE64&gt;</data>
	<key>SpoofVendor</key>
	<true/>
	<key>SystemMemoryStatus</key>
	<string>Auto</string>
	<key>SystemProductName</key>
	<string>MacBookPro16,2</string>
	<key>SystemSerialNumber</key>
	<string>&lt;GENERATED_SERIAL&gt;</string>
	<key>SystemUUID</key>
	<string>&lt;GENERATED_SYSTEM_UUID&gt;</string>
</dict>
```

> [!WARNING] **隐私与安全红线（遵循 `AGENTS.md`）**
> 必须在本地使用 `macserial`（OpenCorePkg 自带工具）独立生成唯一的 `<GENERATED_SERIAL>`、`<GENERATED_MLB>`、`uuidgen` 生成 `<GENERATED_SYSTEM_UUID>`，以及 6 字节网卡 MAC 或随机字节编码为 `<GENERATED_ROM_BASE64>`。**绝不能将真实序列号、MLB、UUID、ROM、DMI/MSDM 表或密码提交至公开 Git 仓库。**

---

## 5. 第四阶段：两步法全新安装流程 (Two-Stage Clean Installation Procedure)

由于 macOS Tahoe 26 原生系统镜像（`BaseSystem` / `SharedSupport.dmg`）不包含完整的 Tiger Lake 用户态 Metal 补丁栈（`/Library/GPUBundles` 与 `/System/Library/Caches/xe.bundle`）及 `HookCase.kext`，全新安装**必须严格采用“两步法”**：先以 **VESA 安全帧缓冲模式**完成基础系统安装与首次设置向导（Stage 1），进入桌面后再**部署 Tiger Lake Iris Xe 驱动包、重建 AuxKC 并开启 `NootedGreen` 硬件加速**（Stage 2）。

### 5.1 Step 4.1 — Stage 1：VESA 安全模式下安装基础 macOS Tahoe 系统

1. **配置 Stage 1 引导参数（VESA 模式）**：
   - 在安装引导用的 `config.plist` 中：
     - 将 `NootedGreen.kext` 的 `Enabled` 设为 **`false`**（或在 `boot-args` 中加入 **`-igfxvesa`** 强制走 VESA GOP 帧缓冲，避免在未安装 `/Library/Extensions/AppleIntelTGLGraphics*.kext` 与 `HookCase.kext` 时触发图形初始化阻塞）。
     - 保持 `DevirtualiseMmio = true`、`slide=0`、`SSDT-RHUB-HP.aml`、`VoodooPS2Controller.kext`、`VoodooI2C.kext`、`AirportItlwm.kext` 与 `PMAPFIX` (`ReservedMemory`) 启用。
2. **启动进入 macOS Recovery 并挂载离线安装包**：
   - 从 Ventoy U 盘选择 `HP-Tahoe-VESA-XHCI-RHUB.img`（或安装 U 盘）进入 `macOS Recovery`。
   - 打开 `Utilities -> Terminal`，若使用离线 HFS+ 安装映像（详见 [docs/offline-installer-inputs.md](offline-installer-inputs.md)），执行：
     ```sh
     sh /Volumes/Yan/ISO/linux/attach_hp_offline_installer.sh \
       /Volumes/Yan/ISO/linux/Tahoe-26.6.2-Offline-App.hfs
     ```
3. **启动系统安装 (`startosinstall` 或 GUI 安装器)**：
   - 确认目标 APFS 卷为空卷 `/Volumes/Tahoe`（注意：macOS 26.6.2 的 `startosinstall` 中 `--eraseinstall` 与 `--volume` 参数互斥，对新建的空 APFS 卷直接使用 `--volume` 或 GUI 安装器，详见 [docs/install-handoff.md](install-handoff.md)）：
     ```sh
     "/Volumes/OfflineInstaller/Install macOS Tahoe.app/Contents/Resources/startosinstall" \
       --agreetolicense \
       --volume /Volumes/Tahoe
     ```
4. **完成多次自动重启与 Setup Assistant 初始设置**：
   - 安装器将自动重启 2–3 次（依次引导 `macOS Installer` -> `Tahoe`）。
   - 在 VESA 模式下顺利走完国家/地区、键盘、Wi-Fi、创建本地管理员账户（如 `yan`）等初始设置向导并进入 macOS 桌面，开启 `System Settings -> General -> Sharing -> Remote Login (SSH)`。

### 5.2 Step 4.2 — Stage 2：部署 Tiger Lake Iris Xe Metal 驱动栈与重建 AuxKC

#### 5.2.0 方式一（推荐）：使用外置 U 盘或内置 `/Volumes/系统/hpdiag` 自包含全套后置适配包一键自动安装 (`HP-Tahoe-PostInstall-20261108`)

在随附的 Lexar Ventoy U 盘数据卷 **`/Volumes/Yan/HP-Tahoe-PostInstall-20261108/`** 以及内置 NTFS 分区 **`/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`**（本地构建归档路径 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/`，压缩包 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108.tar.gz` SHA256 `2f22d03e886773194337281491433b22ea87af1395b26d5e54eb8289020177aa`，`125,569,879` 字节）中，已预置从实机完美运行会话提取并脱敏的 **431 个文件**及自动化安装与验收脚本：

| 目录 / 脚本名称 | 用途说明 | SHA256 校验值 (脚本 / 清单) |
| --- | --- | --- |
| `EFI-OC/` | 完整 **111 文件**生产级 `OC/` 目录树（含 `R32-PCFIX37-WAKERGB` `NootedGreen.kext` SHA256 `00982625...`、`S0ixStandby.kext` `v0.4.4` SHA256 `be55592c...`、`TGLDmic.kext`、`SSDT-DEEPIDLE.aml` `371` B SHA256 `280e3a4a...`、`SSDT-EC0-ITLB.aml` 与 `config.plist` SHA256 `f1f6b95569b7167ce3b166ca38b3f6bac7f8570dd14938187ebdb22090d3cf6b`）与 `BOOT/BOOTx64.efi`，可直接拷入内置 NVMe ESP (`/EFI/`) | 见 `SHA256SUMS.txt` |
| `stage2-gpu/` | Stage 2 Iris Xe (`0x9a49`) 全量组件：`Library-Extensions/`（全部 8 个 kext/bundle，含 `AppleIntelTGLGraphics.kext`、`AppleIntelTGLGraphicsFramebuffer.kext`、`HookCase.kext`、`AppleIntelGraphicsShared.bundle` 等）、`Library-GPUBundles/`（仅部署 `AppleIntelTGLGraphicsMTLDriver.bundle` 内含 `libxedrv.dylib` SHA256 `312ecf60...` 与 `AppleIntelGraphicsShared.bundle`，主动清理 `VADriver`/`VAME` 避免 Gen12 VDBOX 硬解挂起）、`System-Library-Caches/xe.bundle` 以及软解零拷贝守护进程 `usr-local-libexec/xe-h264sw-fixd`（`24,496` B，SHA256 `4e388dfd...`）+ `com.elitebook.h264swfix.plist` | 见 `SHA256SUMS.txt` |
| `stage3-audio/` | Stage 3 音频与唤醒快速恢复组件：`Library-Audio-Plug-Ins-HAL/`（`TGLDmic.driver` 与 `AppleHDAHALPlugIn.bundle`）、`Library-Audio-Plug-Ins-SimpleHDA/AppleHDAHALPlugIn.bundle`、`alc-verb`、`hp-alc285-ampinit.sh`、`hp-wake-helper`（`50,112` B，SHA256 `b592620b...`）、`hp-select-speaker`、`hp-select-dmic.py`、`tgldmic-probe` 与 `com.hp.alc285.ampinit.plist` / `com.hp.wake-helper.plist` | 见 `SHA256SUMS.txt` |
| `stage3-brightness-hotkeys/` | Stage 3 原生亮度滑块与快捷键组件：`libhp_cb_shim.dylib` (`hp-cb-shim.dylib`)、`hp-cb-shim-loader.sh`（`4,617` B，SHA256 `a3de1c66...`）、`hp-bridge`（`70,192` B，SHA256 `3854aabe...`）、`hp-brightness` 及 S0ix 诊断脚本 | 见 `SHA256SUMS.txt` |
| `stage3-bluetooth/` | Stage 3 蓝牙 `--Compat` 与 `decmpfs` `SIGBUS` 自愈守护：`com.apple.bluetoothd-nocompat.plist`、`hp-bt-compat-check.sh`（`2,647` B，SHA256 `2959d4b8...`）与 `com.hp.bt-compat-check.plist` | 见 `SHA256SUMS.txt` |
| `stage3-logging/` | Stage 3 跨关机持久化日志与 `bluetoothd` 内存页锁定守护：`usr-local-bin/hp-syslogger.py`（`v1.1`，`13,043` B，SHA256 `9f223484...`）、`LaunchDaemons/com.hp.syslogger.plist` 与 `etc-newsyslog-d/com.hp.conf`（自动管理 `/var/log/hp/boot-*` 15 次启动留存与 `/var/log/hp-*.log` 轮转） | 见 `SHA256SUMS.txt` |
| `stage3-ridgekey/` | Stage 3 指纹识别组件（已剔除个人指纹模板，预置空 `var/` 目录与制表符分隔的 `0600` `etc/trusted-clients`）：`/usr/local/ridgekey/`、`RidgeKey.app`、`RidgeKey.bundle`、`io.github.labrouss.ridgekey.plist` | 见 `SHA256SUMS.txt` |
| `install-all-postinstall.sh` | **一键全量安装封装脚本**：按顺序自动执行 `install-stage3-peripherals.sh` 与 `install-stage2-gpu.sh` | `1d6401cf7dc2637454ca14d98b9c54f3c9f1dc541a975c7788f1612960e62b35` |
| `install-stage2-gpu.sh` | **Stage 2 GPU 自动安装脚本**：自动部署 `/Library/Extensions`、`/Library/GPUBundles`（仅保留 `MTLDriver` + `Shared` 并移除残留 `VADriver`/`VAME`）、`/System/Library/Caches/xe.bundle` 与 `/usr/local/libexec/xe-h264sw-fixd`，修正 `root:wheel` 及 `755`/`644` 权限，执行 `codesign -f -s -`，并运行 `kmutil load`、`kmutil install --volume-root / --update-all --force` 与 `kcditto` | `ddaaea8f8e754f9a7c459c5b8541dee0edfb099ba79279fc391edd5d9579b9ce` |
| `install-stage3-peripherals.sh` | **Stage 3 外设与持久化日志自动安装脚本**：自动部署音频、亮度/快捷键、蓝牙、RidgeKey 指纹套件及 `hp-syslogger` 持久化日志与 `/etc/newsyslog.d/com.hp.conf`，配置 Unified Log `persist:info`，清理遗留重复 plist，设置 `trusted-clients` 为 `0600 root:wheel`，并加载全部 LaunchDaemons / LaunchAgents | `81fbce36338984841ea2d1b0435274cb802cf972dd0da623a7f44c89e1156947` |
| `verify-postinstall.sh` | **非破坏性一键全系统验收脚本**（`8,852` B）：自动核查 AuxKC/OpenCore 核心 Kext、Metal (`0x9a49`) + `xe-h264sw-fixd`、`corebrightnessd` 亮度垫片、ALC285 + `TGLDmic` 音频、`en0` Wi-Fi、蓝牙、RidgeKey 指纹、`S0ixStandby` (`USB wake disabled` / `CNVW D3`)、`HP-BLITALIGN` 420v 零绿屏及 `hp-syslogger` 持久化日志状态（全部通过返回退出码 `0`） | `499ac36510ffa2c67bf492330377dc7577dc719853fe8280a94ed00e19319387` |
| `verify-phase10-lidwake-and-video.sh` & `test_420v_blitalign` | **Phase 10 专项验收脚本与 `420v` 32B 非对齐 Blit 测试工具**（`7,639` B & `51,680` B）：核查 GPE `0x6E` 唤醒、非对齐 `IOSurface` `BCS0` 2D 拷贝与 `RGB(185,121,49)` 金色像素 | `eeebfac56d8e79b59fc42db33e3672112d9eeb8bf136148018ac5024762ea218` / `887743ebd0b11797fa46553fa2420df21adf266c76ce6d0d540ac51e415e75bf` |
| `SHA256SUMS.txt` | 包内全部 431 个文件的逐文件 SHA256 校验清单 (`64,420` 字节) | `65ff4c05fd4f90f0895deed5de3068bd5db62f069318c7ab13b23e4427a5e8e6` |

在 Stage 1 进入 macOS 桌面后，插入 U 盘（或直接从内置 `/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz` 解压至 `/tmp`）打开终端，即可**一键完成完整性校验与 Stage 2 + Stage 3 全量部署**：

```sh
# 1. 校验适配包全部 431 个文件的 SHA256 完整性
#    （若在外未插 U 盘，可先运行: tar -xzf /Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz -C /tmp && cd /tmp/HP-Tahoe-PostInstall-20261108）
cd /Volumes/Yan/HP-Tahoe-PostInstall-20261108
shasum -a 256 -c SHA256SUMS.txt

# 2. 一键执行 Stage 3 外设 + Stage 2 GPU 驱动安装与 AuxKC 重建
#    （也可分别单独执行 sudo ./install-stage3-peripherals.sh 与 sudo ./install-stage2-gpu.sh）
sudo /Volumes/Yan/HP-Tahoe-PostInstall-20261108/install-all-postinstall.sh

# 3. 可选：将包内预置的完整 Stage 2/3 OpenCore 引导树直接同步至内置 NVMe ESP (如 disk0s1)
#    注意：覆盖前请确保将您自己生成的 PlatformInfo (SMBIOS) 填入 config.plist
sudo diskutil mount disk0s1
sudo rsync -av /Volumes/Yan/HP-Tahoe-PostInstall-20261108/EFI-OC/ /Volumes/EFI/EFI/

# 4. 重启进入启用了 NootedGreen + S0ixStandby + TGLDmic 的完整桌面后，运行一键验收脚本：
/Volumes/Yan/HP-Tahoe-PostInstall-20261108/verify-postinstall.sh
```

若需要了解底层每一步的手工部署细节或单独调试某个组件，可参考下方第 `5.2.1`–`5.2.4` 节与第 `6` 章的分步手工命令。

#### 5.2.1 SIP (`csr-active-config`) 与安全策略要求
在写入 `/Library/Extensions`、`/Library/GPUBundles` 并重建 Auxiliary Kernel Collection (AuxKC) 前，必须确保 OpenCore `config.plist` 中已放行未签名/自签名 kext 与文件系统修改：
- **本机实测 `csr-active-config`**：`<03020000>`（Base64: `AwIAAA==`，对应 `CSR_ALLOW_UNTRUSTED_KEXTS | CSR_ALLOW_UNRESTRICTED_FS | CSR_ALLOW_EXECUTABLE_FOR_PID`）或 `<03080000>`（Base64: `AwgAAA==`，额外开启 `CSR_ALLOW_KERNEL_DEBUGGER`）。
- **`Misc -> Security -> SecureBootModel`**：`Disabled`
- **`boot-args`**：包含 `amfi_get_out_of_my_way=1`

#### 5.2.2 方式二（分步手工安装）：必需安装的内核扩展与用户态 GPU Bundles 清单
Tiger Lake 硬件加速栈（源自 `NootedGreen` `sle_Internal` `16.0.32` 移植包与本仓库交叉编译修复组件，安装脚本见 `install-stage2-gpu.sh`）共需部署以下四个位置：

1. **`/Library/Extensions/`（内核扩展与关联 Bundles）**：
   - `AppleIntelTGLGraphics.kext`（**关键修改**：将其 `Contents/Info.plist` 中的 `IOKitPersonalities.Gen7.IOPCIPrimaryMatch` 设为 `0x9a498086`，`CFBundleVersion` 提升为 `16.0.2`）
   - `AppleIntelTGLGraphicsFramebuffer.kext`（`CFBundleVersion = 16.0.0`）
   - `HookCase.kext`（`org.smichaud.HookCase`，`AppleIntelTGLGraphics*` 符号链接依赖项）
   - `AppleIntelTGLGraphicsMTLDriver.bundle`
   - `AppleIntelTGLGraphicsGLDriver.bundle`
   - `AppleIntelTGLGraphicsVADriver.bundle`
   - `AppleIntelTGLGraphicsVAME.bundle`
   - `AppleIntelGraphicsShared.bundle`
2. **`/Library/GPUBundles/`（用户态 Metal 驱动与 `libxedrv.dylib` 钩子库 — 仅部署 2 个 Bundle）**：
   - `AppleIntelTGLGraphicsMTLDriver.bundle`（内含修复了 `VTDecoderXPCService` `initport_wrapper` 空指针 `SIGSEGV` 与 `/private/tmp/xedrv-*` 沙盒拒绝刷屏的 `Contents/MacOS/libxedrv.dylib`，`65,280` 字节，SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`，编译自 `libxedrv.m` SHA256 `ea4b9ec3c14a902863c1ce41fc3a6e40c54eb350d747833ad702087a69429406`，详见 [docs/continuation.md](continuation.md)）
   - `AppleIntelGraphicsShared.bundle`
   - **重要说明**：**切勿**将 `AppleIntelTGLGraphicsVADriver.bundle` 或 `AppleIntelTGLGraphicsVAME.bundle` 放入 `/Library/GPUBundles/`（若存在需移除），使 macOS Tahoe `VTDecoderXPCService` 稳定走 `AppleH264SW` / `AppleHEVCSW` 软件解码并经 `NootedGreen` `HP-BLITALIGN` (`BCS0` 2D 拷贝) + `xe-h264sw-fixd` 零绿屏高速上屏，彻底规避 Gen11/Gen12 VDBOX 媒体引擎指令不兼容引发的解码器挂死。
3. **`/System/Library/Caches/`（可写 Firmlink 下的着色器编译器）**：
   - `/System/Library/Caches/xe.bundle`
4. **`/usr/local/libexec/xe-h264sw-fixd` 与 `/Library/LaunchDaemons/com.elitebook.h264swfix.plist`（软解 `420v` 64B 行距对齐守护进程）**：
   - 监听并修补新建 `VTDecoderXPCService` 进程内存中的 `AppleH264SW` 对齐表，与内核态 `HP-BLITALIGN` 构成双重零绿屏保障（二进制 `24,496` 字节，SHA256 `4e388dfd1720d25e73d5701b4be0919cac190cca38ee03fc7ee9a7532048d5af`）。

#### 5.2.3 属性修补、签名、权限归正与 AuxKC 重建手工命令
若未使用 `sudo /Volumes/Yan/HP-Tahoe-PostInstall-20261108/install-stage2-gpu.sh`，可在 macOS 终端中**严格按以下顺序**手工执行（**注意：`plutil -replace` 必须在修复 `/Library/Extensions` 属主与权限之前执行**，避免 `plutil` 原子重写 `Info.plist` 时更改文件属主）：

```sh
# 1. 先修正 AppleIntelTGLGraphics.kext 的 PCI 匹配 ID 与版本号
sudo plutil -replace IOKitPersonalities.Gen7.IOPCIPrimaryMatch -string 0x9a498086 \
  /Library/Extensions/AppleIntelTGLGraphics.kext/Contents/Info.plist
sudo plutil -replace CFBundleVersion -string 16.0.2 \
  /Library/Extensions/AppleIntelTGLGraphics.kext/Contents/Info.plist

# 2. 确保 /Library/GPUBundles 仅包含 MTLDriver 与 Shared 两个 Bundle（移除可能残留的 VADriver/VAME）
sudo rm -rf /Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle \
            /Library/GPUBundles/AppleIntelTGLGraphicsVAME.bundle
sudo /usr/bin/codesign -f -s - /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle
sudo /usr/bin/codesign -f -s - /Library/GPUBundles/AppleIntelGraphicsShared.bundle

# 3. 归正所有 Kext 与 Bundle 属主为 root:wheel，并确保 /Library/Extensions/*.kext 满足 AuxKC 严格权限要求 (目录/二进制 755, plist 644)
for kext in \
  /Library/Extensions/AppleIntelTGLGraphics.kext \
  /Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext \
  /Library/Extensions/HookCase.kext; do
  sudo chown -R root:wheel "$kext"
  sudo find "$kext" -type d -exec chmod 755 {} +
  sudo find "$kext" -type f -name "*.plist" -exec chmod 644 {} +
  sudo find "$kext" -type f -path "*/Contents/MacOS/*" -exec chmod 755 {} +
done

for bundle in \
  /Library/Extensions/AppleIntelTGLGraphicsMTLDriver.bundle \
  /Library/Extensions/AppleIntelTGLGraphicsGLDriver.bundle \
  /Library/Extensions/AppleIntelTGLGraphicsVADriver.bundle \
  /Library/Extensions/AppleIntelTGLGraphicsVAME.bundle \
  /Library/Extensions/AppleIntelGraphicsShared.bundle \
  /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle \
  /Library/GPUBundles/AppleIntelGraphicsShared.bundle \
  /System/Library/Caches/xe.bundle; do
  sudo chown -R root:wheel "$bundle"
done

# 4. 安装并启动 xe-h264sw-fixd 守护进程
sudo install -d -o root -g wheel -m 755 /usr/local/libexec
sudo install -o root -g wheel -m 755 stage2-gpu/usr-local-libexec/xe-h264sw-fixd /usr/local/libexec/xe-h264sw-fixd
sudo install -o root -g wheel -m 644 stage2-gpu/LaunchDaemons/com.elitebook.h264swfix.plist /Library/LaunchDaemons/com.elitebook.h264swfix.plist
sudo launchctl bootout system /Library/LaunchDaemons/com.elitebook.h264swfix.plist 2>/dev/null || true
sudo launchctl bootstrap system /Library/LaunchDaemons/com.elitebook.h264swfix.plist

# 5. 注册 Kext（若 System Settings -> Privacy & Security 弹出系统扩展审批提示，点击 Allow）
sudo /usr/bin/kmutil load -z --load-style match-only \
  -p /Library/Extensions/AppleIntelTGLGraphics.kext \
  -p /Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext \
  -p /Library/Extensions/HookCase.kext || true

# 6. 强制重建 Auxiliary Kernel Collection (AuxKC) 并同步至 Preboot 卷
sudo kmutil install --volume-root / --update-all --force
sudo kcditto
```

随后挂载内置 ESP（或从 NixOS 写入 `/boot/EFI/OC`），将 **`R32-PCFIX37-WAKERGB` 版 `NootedGreen.kext`** 放入 `/EFI/OC/Kexts/NootedGreen.kext`，并在 `config.plist` 中启用 `NootedGreen.kext`（`Enabled = true`，同时确保 `WhateverGreen.kext` 为 `Enabled = false`），移除 `-igfxvesa`，写入第 4.6.2 节的完整 `boot-args`。

#### 5.2.4 `NootedGreen.kext` (`R32-PCFIX37-WAKERGB` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`) 内存级核心修补原理

本仓库编译的 `NootedGreen.kext`（`Contents/MacOS/NootedGreen` `540,944` 字节，SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3`，`LC_UUID` `4C4C44A8-5555-3144-A16C-16F349CEF835`，对应核心源码 `kern_gen11.cpp` SHA256 `6c42d019445988feb826ac6581f2c0c90a34f0e1266436ef81eed35f03f2d240` 与补丁 [patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch](../patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch)，技术演进详见 [docs/repair32-gpu-stability-and-pmapfix-20261106.md](repair32-gpu-stability-and-pmapfix-20261106.md)）在内核态与用户态对 TGL 图形栈实施了六层关键修补：

1. **Gen12 GuC 绕过、Execlist 门铃排空与无损单端口 RCS 调度 (`ELSQWAIT` + `PCFIX5` + `PCFIX6`)**：
   - 通过 `ngreenSched=3` 与 `-disablegfxfirmware` 绕过 GuC 微码，使用硬件 Execlist 门铃直提。
   - **无条件 `elsqWait`**（[patches/nootedgreen-r32-elsqwait-20261105.patch](../patches/nootedgreen-r32-elsqwait-20261105.patch)）：在 `xePrepSubmit` 与 `xeCs5Submit` 中，只要 `GFXREG_RCS_EXECLIST_STATUS [0x2234]` bit 30 (`0x40000000`) 置位即轮询等待硬件排空提交队列，消除 39 微秒高频重入导致的 `0x4000219a` (`ExecListQueueFull`) 抢占挂死。
   - **阻断软件 mid-batch 抢占**（[patches/nootedgreen-r32-pcfix5-20261105.patch](../patches/nootedgreen-r32-pcfix5-20261105.patch)）：挂钩 `IGScheduler5::updateOptions` (`0x385e0`) 与 `allowPreemption` (`0x3d9a6`) 清零 `cs[0x1c50]`、`cs[0x1c5d]` 与 `sched[0x0c] bit 2`，编程 `GFXREG_CS_CHICKEN1 [0x2580] = 0x00020002` 并清除 `0x20e0` bit 14。
   - **无损单端口 RCS 策略 `HP-SINGLEPORT-RCS`**（[patches/nootedgreen-r32-pcfix6-20261105.patch](../patches/nootedgreen-r32-pcfix6-20261105.patch)）：在 `xeDequeueExecList`、`evalWorkQueues` (`f_rcs1_hp` at `0x3d5d0`) 与 `evalWaitQueue` (`f_wait1_hp` at `0x3b971`) 中阻止填充 `Port1` (`EL[1]`) 并将未消费的 ring 读指针写回 `workQueue+0x4040`，100% 消除 `WindowServer` (`0xa0`) 与 Metal 计算 (`0x5c0`) 并发时的 `LITE_RESTORE` (`0x8002`) 及 `0x3098 -> 0x40002098` (`NO ACTIVE ELEMENTS`) 硬件仲裁冻结。
2. **`COCLGen8CommandTransport` 计算编码器就地净化与 `RING_MI_MODE` 嵌套故障抑制 (`PCFIX27` / `PCFIX33`)**：
   - 启用 `IntelAccelerator+0xf42 bit 0`（`_WA_TABLE+0x14 bit 0`）使 `AddPipeFlushCmd` 分配 12-dword 双包空间（每编码器 `151` dwords，页内最多合并 5 个编码器）。
   - 挂钩 `IntelMTLComputeFunctions::execute`（针对 `eToken == 0x40001U` 调用 `hpSanitizeComputeEncoder`，详见 [patches/nootedgreen-r32-pcfix27-20261106.patch](../patches/nootedgreen-r32-pcfix27-20261106.patch)）：
     - 在 `ResetPreambleCmds` (`dw[0..32]`) 中保留 `dw[+1] = 0x001010a0U` 排空 3D RT cache，为 `dw[+7]`/`dw[+25]` 补齐 `CS_STALL` (`0x00100480U`)，将原 Gen8 `LRI 0xb134` (`dw[+15..+17]`) 替换为 `MEDIA_STATE_FLUSH (0x70040000U)`，并将紧随其后的 `dw[+19]` 改为 **`0x001000a0U`**（剥离 GPGPU 模式下重新锁存 `CSFLTRK bit 28` 的 `0x1000 RT_CACHE_FLUSH`）；
     - 在 `AddPipeFlushCmd` (`dw[83..94]`) 中剥离虚拟 `0x4000 POST_SYNC_OP` 并拆分为写刷新 `0x001000a0U` + 读失效 `0x00100480U` 双包，使 `CSFLTRK [0x2208]` 的 `bits 28..25` 实现 **`0000b` 全清零**，同时抑制 `RING_MI_MODE` 嵌套故障与 `SubmitCCSResolve` (`R4/NOCCS3`) 页错误。
3. **`XE-FBDPMS` 睡眠/唤醒事件路由与 `hwSaveNVRAM` 防崩溃保护 (`PCFIX32` + `PCFIX33`)**：
   - 将 `AppleIntelBaseController::hwSaveNVRAM()` (`0x77a5a`) 路由至空返回桩函数（[patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch](../patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch)），彻底消除 macOS Tahoe XNU `25.1.0+` 将 `IODTPlatformExpert` `vtable + 0x9f8` 替换为纯虚陷阱 `_RESERVEDIODTPlatformExpert1` 导致的睡眠 Panic 重启。
   - 在 `Gen11::processKext` 中动态解析 `AppleIntelFramebuffer::prepareToExitSleep` (`0x396ae`) `+0x3dc` 处的调用目标 **`IOFramebuffer::handleEvent`**（`gHpIOFBHandleEvent`），并在 `Gen11::wrapSetFramebufferPowerState` 中对 `FB0`/`FB1`/`FB2` 睡眠（`cur > 0 && state == 0`）调用 `handleEvent(fb, 3, (void *)1)` (`kIOFBNotifyDidSleep`)、唤醒（`cur == 0 && state > 0`）调用 `handleEvent(fb, 4, (void *)1)` (`kIOFBNotifyDidWake`)，使 `IntelAccelerator::systemDidWake()` 与 `IOAccelLegacyDisplayPipe::framebuffer_did_power_on()` 正常恢复桌面扫描输出（[patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch](../patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch)）。
4. **`hpCsResetOnWake` 唤醒期 GT 硬件上下文保留与 CSB 指针同步 (`PCFIX33`)**：
   - 拦截 `IGHardwareCommandStreamer5::resetOnWake` (`0x3a292`)，修正 `fAccelerator` 结构体偏移为 **`cs + 0x10`**（`cs + 0x18` 为 `IOWorkLoop *`），通过 `xeSafeForceWake(accel, true, 1)` 唤醒 Render 域并读取 `HWS_PGA` (`0x2080`)：当 GT 在 S0ix 期间完整保留了 `HWS_PGA`（非零，如 `0x40004000`）时跳过原生 `resetOnWake`（避免其把 `hwsPage[0xbc/4]` 与 `0x23a0` 强行改写为 `7`），并将软件 CSB 读指针 `*(uint32_t *)(cs + 0x1c04)` 同步为 `(*(uint32_t *)(hws + 0xbc)) & 0x7u`。
5. **Phase 10 `isRealTGL && Tahoe` 下启用 `HP-BLITALIGN`、`HP-BLITFIX` 与 `HP-BLIT16`（修复 `420v` 视频播放绿屏与卡顿，`PCFIX35`）**：
   - 在 `kern_gen11.cpp` 的 `isRealTGL && Tahoe` 分支中启用 `HP-BLITALIGN`（`f_ba_src`、`f_ba_dst`、`f_ba_rota`）、`HP-BLITFIX`（`xeBlitFixInstall`）与 `HP-BLIT16`（`f_b16a`、`f_b16b`）钩子：当 `VTDecoderXPCService`（`AppleH264SW`）输出带 32B 头部的 `420v` 非 64B 对齐 `IOSurface` 时，放宽 `blit2d_common_supported` / `blit2d_fast_supported` 的 64B 对齐检查将其路由至 `BCS0` `XY_SRC_COPY_BLT` 2D 拷贝，并强制剩余 `Blit3D` 像素着色器使用 `SIMD16`（同时配合 `libxedrv.dylib` 与 `xe-h264sw-fixd`），彻底根治 `420v` 视频播放绿屏与帧率卡顿。
6. **Phase 17 S0ix 唤醒绿屏根除与 `PLANE_CTL_1_A` Gen12 RGB 强制规范化 (`PCFIX36` + `PCFIX37`)**：
   - `AppleIntelICLGraphicsFramebuffer` 在睡眠切换至全零睡眠帧缓冲时向 `PLANE_CTL_1_A` (`0x70180`) 写入 Gen11 格式编码 `0x82000400`；在 Gen12 Tiger Lake 显示引擎上，该编码被硬件解释为 **YUV 4:2:2 Packed**，全零像素 `(Y=0, U=0, V=0)` 经 YUV->RGB 转换后变成纯绿 `RGB(0, 136, 0)`。
   - `PCFIX37` 新增 **`xeNormalizePlane1ARgb`**（[patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch](../patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch)），在睡眠/唤醒 MMIO 写入拦截点将 `PLANE_CTL_1_A` (`0x70180`) 的 YUV 格式位实时改写为 Gen12 RGBX8888 (`0x84000400`)，同步将 `PLANE_COLOR_CTL_1_A` (`0x701CC`) 设为 `0x2000`、清零 `CSC_MODE_A` (`0x4A480`) 并写触发 `PLANE_SURF_1_A` (`0x7019C`) 立即锁存为纯黑帧；同时维持最长 `820 ms`（桌面新帧翻转后 `120 ms` 提前释放，保底 `450 ms`）的硬件 PWM 背光保持窗口并在 `IGPU` 导出 `ngreen-wake-plane-rgb-fix = 1`。

---

## 6. 第五阶段：外设精调与系统级修复 (Post-Install Peripheral Fixes)

> [!TIP] **一键自动部署 Stage 3 全外设与持久化日志 (`install-stage3-peripherals.sh`)**
> 若已在第 `5.2.0` 节运行 `sudo /Volumes/Yan/HP-Tahoe-PostInstall-20261108/install-all-postinstall.sh`（或单独运行 `sudo /Volumes/Yan/HP-Tahoe-PostInstall-20261108/install-stage3-peripherals.sh`），本章 6.1–6.4 节的全部音频插件、功放解静音与唤醒恢复守护进程 (`hp-wake-helper`)、控制中心亮度垫片 (`libhp_cb_shim.dylib`)、快捷键守护进程 (`hp-bridge` / `hp-brightness`)、蓝牙守护检查器 (`hp-bt-compat-check.sh`)、跨关机持久化系统日志与 `bluetoothd` 内存页锁定守护 (`hp-syslogger.py` + `/etc/newsyslog.d/com.hp.conf`) 以及 `RidgeKey` 指纹组件（含 `0600 root:wheel` 权限的 `trusted-clients`）均已自动安装并加载完毕，只需直接跳至第 `6.4` 节第 3 步执行指纹录入（`ridgekeyctl enroll`）即可。下文保留完整的底层原理与分步手工命令供审计与单独维护。

### 6.1 音频子系统：板载 `ALC285` 扬声器/耳机 + `TGLDmic` 四阵列数字麦克风

HP Tiger Lake 笔记本的音频分为两条独立的硬件通路（详见 [docs/continuation.md](continuation.md)）：

1. **输出通路（内置 Bang & Olufsen 扬声器与 3.5mm 耳机孔 — Realtek `ALC285` HDA Codec）**：
   - **驱动组合**：`AppleALC.kext` (`1.9.8`) + `SimpleHDA.kext` (`1.0.1`)。
   - **Layout ID 选择**：
     - **HP Elite Dragonfly G2 (`103c:8716`)**：使用自定义的 **`layout-id = 71`**（`<47000000>`，内含 `0xa0c8` 控制器匹配与 DAC `0x03` -> Pin `0x17` 内放路由）。
     - **HP EliteBook 840 G8**：可使用 **`layout-id = 11`**（`<0B000000>`）或 **`71`**（配合 `R32-AUDIOFIX`），挂载 `Built-in Speaker` (2ch) 并避免幽灵输出节点抢占默认设备。
   - **HP 外部功放解静音与 3.5mm 耳麦麦克风初始化 (`hp-alc285-ampinit.sh`)**：
     HP `ALC285` 的内置扬声器功放受 Codec Node `0x20` 私有 Processing Coefficient `0x65` 控制（对应 Linux `snd_hda_codec_realtek` 的 `alc285_fixup_hp_gpio_amp_init`），且 3.5mm 耳麦孔麦克风（`Node 0x19 -> Mixer 0x23 -> ADC 0x08`）需显式解静音。需部署 `/usr/local/bin/hp-alc285-ampinit.sh`（配合 `hp-select-dmic.py` 与睡眠唤醒恢复助手 `/usr/local/bin/hp-wake-helper` SHA256 `b592620b3ef2f816b006d0fa6414e206b142da5779ece3b82604b6bf12f7b491`）及 `/Library/LaunchDaemons/com.hp.alc285.ampinit.plist`、`/Library/LaunchDaemons/com.hp.wake-helper.plist`，在开机与每次 S0ix 唤醒后自动下发 HDA 动词并锁定默认输入/输出设备：
     ```sh
     #!/bin/sh
     # Wait up to 30s for ALCUserClientProvider
     for i in $(seq 1 30); do
       if /usr/sbin/ioreg -r -c ALCUserClientProvider -d 1 | /usr/bin/grep -q ALCUserClientProvider; then
         break
       fi
       /bin/sleep 1
     done
     /bin/sleep 1
     # HP ALC285 speaker amp init (coef 0x65 = 0x0000)
     /usr/local/bin/alc-verb 0x20 SET_COEF_INDEX 0x65
     /usr/local/bin/alc-verb 0x20 SET_PROC_COEF 0x0000
     # Unmute headset mic path (Node 0x19 -> Mixer 0x23 -> ADC 0x08) for 3.5mm jack headset
     /usr/local/bin/alc-verb 0x19 SET_PIN_WIDGET_CONTROL 0x24
     /usr/local/bin/alc-verb 0x19 SET_AMP_GAIN_MUTE 0x7002
     /usr/local/bin/alc-verb 0x23 SET_AMP_GAIN_MUTE 0x7000
     /usr/local/bin/alc-verb 0x08 SET_AMP_GAIN_MUTE 0x7030
     # Select Built-in Speaker as default output
     if [ -x /usr/local/bin/hp-select-speaker ]; then
       /usr/local/bin/hp-select-speaker || true
     fi
     # Wait up to 15s for TGLDmic (or fallback input) and select Internal Microphone (TGLDmic) as default input
     if [ -x /usr/local/bin/hp-select-dmic.py ]; then
       /usr/bin/python3 /usr/local/bin/hp-select-dmic.py || true
     fi
     ```
2. **输入通路（屏幕顶部 4 阵列 PDM 数字麦克风 — Intel cAVS 2.5 DSP `8086:a0c8`）**：
   - 屏幕顶部的内置阵列麦克风直连在 Intel Smart Sound DSP 的 PDM 总线上（ACPI `NHLT` Endpoint 2: `vid=0x8086 did=0xae20, 4ch 48kHz S32_LE`），不走 Realtek HDA Codec。
   - **部署步骤**：
     1. 将 `TGLDmic.kext` (`v0.5.0`) 放入 `/EFI/OC/Kexts/` 并在 `config.plist` 启用，在 `boot-args` 中加入 `-tgldmic`；
     2. 将 CoreAudio HAL 插件 `TGLDmic.driver` 安装至 `/Library/Audio/Plug-Ins/HAL/TGLDmic.driver`（`sudo chown -R root:wheel`）并重启 `sudo killall -9 coreaudiod`；
     3. 重启后 `TGLDmic.kext` 会在约 `12 ms` 内加载 Intel 官方签名 `sof-tgl.ri` 固件（`TGLDmicPhase = 4, BootResult = "OK FW_READY"`），并在系统声音输入中自动注册 **`Internal Microphone (TGLDmic)`**（4 声道 48kHz），与 `SimpleHDA` 的 `Built-in Speaker` 完美并存。

### 6.2 原生控制中心亮度滑块与全键位 `Fn` 快捷键 (`libhp_cb_shim.dylib` + `hp-bridge`)

1. **为什么不用 `R32-PCFIX31` (`kextBacklight`) 而采用 `libhp_cb_shim.dylib`**：
   - 在 `NootedGreen` 中强开 `lilu.onKextLoadForce(&kextBacklight)` 会导致 `AppleBacklight` 在 `AppleIntelTGLGraphics` 加速器初始化前的 `PMRD: PowerChangeDone` 阶段提前匹配内屏引发开机同步阻塞。
   - 反编译 `ControlCenter.app` 与 `CoreBrightness.framework`（`createDSIICDevice`）证实：只要 `IODisplayCopyParameters` 对内屏返回包含 `"brightness"`、`"linear-brightness"`、`"usable-linear-brightness"` 与 `"commit"` 四个键的字典，`DisplayServicesCanChangeBrightness(CGMainDisplayID())` 即返回 `1`，右上角控制中心就会原生渲染“显示器”亮度滑块圆点。
   - **部署方案与开机竞态加固**（源码位于 `.local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim.m` 与 `.local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim-loader.sh`，实机核验回执见 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/audit-3b5cd162/cb-shim-loader-fix-verification.txt`）：
     - 将交叉编译的 `/usr/local/lib/libhp_cb_shim.dylib`（SHA256 `e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798`，软链 `/usr/local/lib/hp-cb-shim.dylib`）、`/usr/local/bin/hp-cb-shim-loader.sh`（`4,617` 字节，SHA256 `a3de1c6667ae927ec9f166bcec7cdc27ef721bc9a8e19f31b03c4103f6008fb8`，`0755 root:wheel`）与 `/Library/LaunchDaemons/com.hp.cb-shim-loader.plist` 安装至系统。
     - **关键竞态与 `launchd` 路径校验加固**：
       1. 开机最多等待 60 秒直至 `ioreg -l` 中出现 `AppleBacklightDisplay` **且** `pgrep -x WindowServer` 存在，随后再延迟 2 秒等待 `WindowServer` 完成初始 modeset 及原厂 `corebrightnessd` 完成 XPC 注册（避免在 `WaitForWindowServerPort()` 阻塞期过早执行 `bootout` 触发 `SIGKILL` + 9 秒 `PETRIFIED` 清理窗口）；
       2. 生成 `/usr/local/lib/com.apple.corebrightnessd-shim.plist` 并同步至 `/private/var/run/com.apple.corebrightnessd-shim.plist`（规避 macOS 26 Tahoe `launchd` 对 firmlink 目录 `/usr/local/lib/` 下 `com.apple.*` 系统标签 plist 返回 `Bootstrap failed: 5: Input/output error` 的限制），同时置 `ThrottleInterval=1`、`EnableTransactions=false`、`ExitTimeOut=1`；
       3. 先做幂等检查（若 `system/com.apple.corebrightnessd` 已带 `hp-cb-shim.dylib` 处于 `state = running` 则直接退出 0），再执行 `launchctl bootout` 并进入最多 20 次（每次间隔 1 秒）的 `launchctl bootstrap` + `kickstart -k` 轮询重试循环，最后配有回退加载原厂 `/System/Library/LaunchDaemons/com.apple.corebrightnessd.plist` 的兜底保护：
     ```sh
     # Wait up to 60s for AppleBacklightDisplay in ioreg -l AND WindowServer process
     for attempt in $(seq 1 60); do
         if /usr/sbin/ioreg -l 2>/dev/null | /usr/bin/grep -q "AppleBacklightDisplay" && \
            /usr/bin/pgrep -x WindowServer >/dev/null 2>&1; then
             break
         fi
         /bin/sleep 1
     done
     /bin/sleep 2
     # ... (idempotency check & plist generation at $SHIM_PLIST and $RUNTIME_SHIM_PLIST) ...
     /bin/launchctl bootout system/com.apple.corebrightnessd 2>/dev/null || true
     for attempt in $(seq 1 20); do
         /bin/sleep 1
         PRINT_OUT="$(/bin/launchctl print system/com.apple.corebrightnessd 2>/dev/null || true)"
         if ! echo "$PRINT_OUT" | /usr/bin/grep -q "hp-cb-shim.dylib"; then
             /bin/launchctl bootstrap system "$SHIM_PLIST" 2>/dev/null || \
                 /bin/launchctl bootstrap system "$RUNTIME_SHIM_PLIST" 2>/dev/null || true
             PRINT_OUT="$(/bin/launchctl print system/com.apple.corebrightnessd 2>/dev/null || true)"
         fi
         if echo "$PRINT_OUT" | /usr/bin/grep -q "hp-cb-shim.dylib"; then
             /bin/sleep 1
             /bin/launchctl kickstart -k system/com.apple.corebrightnessd 2>/dev/null || true
             /bin/sleep 1
             PRINT_OUT="$(/bin/launchctl print system/com.apple.corebrightnessd 2>/dev/null || true)"
             if echo "$PRINT_OUT" | /usr/bin/grep -Eq "state = running|pid = [0-9]+"; then
                 REGISTERED=1
                 break
             fi
         fi
     done
     ```
2. **全键位 `Fn` 快捷键与静音指示灯守护进程 (`hp-bridge` & `hp-brightness`)**：
   - 部署 `/usr/local/bin/hp-bridge`（`70,192` 字节，SHA256 `3854aabe44e6fd859111b859e6b9a66f3a82867b086389aa03b6263a0c27cfb7`，支持唤醒后同步刷新控制中心亮度）、命令行包装器 `/usr/local/bin/hp-brightness` 与 `/Library/LaunchAgents/com.hp.bridge.agent.plist`（持久化日志输出至 `/var/log/hp-bridge.log`），配合 `VoodooPS2Keyboard.kext` 的 24 条 `Custom ADB Map`，完整支持顶排 16 键（`F1` 显示镜像切换、`F2` HP Sure View 防窥屏提示、`F3`/`F4` 16 级线性亮度加减、`F5` 扬声器静音 + 同步点亮键帽 ALC285 GPIO `IO[2]` 橙色指示灯、`F6`/`F7` 音量加减、`F8` 麦克风静音 + 同步点亮键帽 ALC285 GPIO `IO[0]` 橙色指示灯、`F11` 飞行模式 Wi-Fi 开关、`F12` 可编程键/Launchpad、`prt scr` 选区截图至剪贴板）以及日版 JIS 专属键（`無変換` 英数、`変換` 假名、`¥ |`、`_ \`）。

### 6.3 macOS Tahoe 蓝牙适配、`decmpfs` 内存页锁定与跨关机持久化日志 (`8087:0026` + `hp-syslogger`)

1. **标准内核与 NVRAM 配置**：
   - 在 `config.plist -> Kernel -> Add` 中按顺序加载 `IntelBluetoothFirmware.kext` (`2.5.2`)、`IntelBTPatcher.kext` (`2.5.2`) 与 `BlueToolFixup.kext` (`2.7.2`)；
   - 在 `NVRAM -> Add -> 7C436110-AB2A-4BBB-A880-FE41995C9F82` 中注入：
     - `bluetoothExternalDongleFailed = <00>` (`AA==`)
     - `bluetoothInternalControllerInfo = <00000000 00000000 00000000 0000>` (`AAAAAAAAAAAAAAAAAAA=`)
2. **`bluetoothd` `--Compat` 防护与 APFS `decmpfs` 就地补丁页锁定 (`hp-bt-compat-check.sh` + `hp-syslogger.py`)**：
   - 在 macOS Tahoe `26.6.2` (`25G83`) 上，`/usr/sbin/bluetoothd` 为 APFS `UF_COMPRESSED` (`decmpfs`) 压缩二进制，而 `BlueToolFixup.kext` 会在内存中就地修改其代码页（如 `0x33d000`）。长时间运行后若 VM 页面回收仅逐出同一 `16 KiB` 压缩簇 ``0x33c000, 0x340000)` 中的未修改相邻页，下次缺页换入时 `decmpfs_pagein_compressed` 会因压缩簇 SHA 校验与驻留补丁页冲突返回 `error 94` (`EBADMSG`) 并触发 `bluetoothd` `SIGBUS (10)` 循环崩溃。
   - 适配包通过两层机制彻底根除该问题并实现跨关机全系统持久化日志：
     1. **`stage3-logging/usr-local-bin/hp-syslogger.py`**（`v1.1`，`13,043` 字节，SHA256 `9f22348437736568d9ca6906b2934e5358432200615fe4503729b851e2f89f59`，配合 `/Library/LaunchDaemons/com.hp.syslogger.plist`）：开机以 `MAP_PRIVATE | PROT_READ` + `mlock()` 将 `/usr/sbin/bluetoothd` `[0x0..0xab0000)`（`11,206,656` 字节）常驻锁定在物理内存中，从根源阻断 `decmpfs` 簇部分逐出；同时在 `/var/log/hp/boot-<STAMP>-<UUID8>/`（软链 `/var/log/hp/current`，自动保留最近 `15` 次启动）持续归档 `dmesg`、`pmset`、IORegistry 关键状态、流式过滤错误日志（`20 MiB` 自动轮转）及 `SIGTERM` 关机前快照，并由 `/etc/newsyslog.d/com.hp.conf` 自动轮转全部 `/var/log/hp-*.log`。
     2. **`stage3-bluetooth/usr-local-bin/hp-bt-compat-check.sh`**（`2,647` 字节，SHA256 `2959d4b84802e12c6d2f23fd4bc41ae154c4429b799f475ab1bb425232ea09cb`）：开机同时检测 `--Compat` 废弃参数与 `last exit code = 10` (`SIGBUS`)，一旦发现异常即自动执行 `bootout` + `/usr/sbin/purge` + 重新 `bootstrap` 自愈恢复。

### 6.4 USB 指纹识别器 (`RidgeKey` `06cb:00f0`) 部署与录入配置

HP Elite Dragonfly G2 与 EliteBook 840 G8 配备 Synaptics Match-On-Chip USB 指纹识别器（`06cb:00f0`，挂载于 PCH XHCI `HS07`）。通过部署 [`RidgeKey``（`1.0.0`，详见 [docs/continuation.md](continuation.md)）可实现锁屏指纹解锁、`sudo` 指纹鉴权与管理员弹窗认证：

1. **组件部署**：
   - 将 `ridgekeyd`、`ridgekeyctl`、`ridgekey-sudo`、`ridgekey-admin`、`pam_ridgekey.so`、`RidgeKey.app` 与 `RidgeKeyAgent.app` 安装至 `/usr/local/ridgekey/`，并在 `/usr/local/bin/` 创建软链接；
   - 部署 `/Library/LaunchDaemons/io.github.labrouss.ridgekey.plist`（运行 `ridgekeyd` 守护进程）与 `/Library/LaunchAgents/io.github.labrouss.ridgekey.agent.plist`（运行 `RidgeKeyAgent`）。
2. **修复 `/usr/local/ridgekey/etc/trusted-clients` 白名单格式**：
   - `ridgekeyd` 要求 `/usr/local/ridgekey/etc/trusted-clients` 每行严格采用 **`<绝对路径><TAB><40位小写hex cdhash>`**（以制表符 `\t` 分隔，`mode 0600`，`root:wheel`）。可通过 `codesign -dvvv <binary>` 提取 `CDHash` 并写入 `/usr/local/ridgekey/etc/trusted-clients`，确保 `ridgekeyctl`、`RidgeKey.app`、`RidgeKeyAgent.app` 与 `pam_ridgekey.so` 均通过 XPC 客户端校验。
3. **密码托管、指纹录入与 PAM 启用**：
   ```sh
   # 1. 检查传感器连接状态 (应显示 Sensor: 06cb:00f0 connected)
   /usr/local/bin/ridgekeyctl status

   # 2. 保存当前登录密码至 Keychain 供锁屏自动填充解锁
   /usr/local/bin/ridgekeyctl password set
   /usr/local/bin/ridgekeyctl password check

   # 3. 录入手指指纹 (按提示连续轻触传感器 8 次)
   /usr/local/bin/ridgekeyctl enroll right-index

   # 4. 启用终端 sudo 与系统管理员弹窗指纹认证
   sudo /usr/local/bin/ridgekey-sudo enable
   sudo /usr/local/bin/ridgekey-admin enable
   ```

### 6.5 S0ix Modern Standby 睡眠与唤醒全链路协同

在 Tiger Lake 轻薄本上，BIOS 仅提供 **S0ix Modern Standby (`s2idle`)** 而无传统 ACPI `S3` 睡眠。本仓库通过 **`SSDT-DEEPIDLE.aml`（`371` B, SHA256 `280e3a4a...`）+ `S0ixStandby.kext`（`v0.4.4`, `74,584` B, SHA256 `be55592c...`）+ `NootedGreen.kext`（`R32-PCFIX37-WAKERGB`, `540,944` B, SHA256 `00982625...`）+ `hp-wake-helper`** 四方协同，在实机 `B004F99C` 上达成单次连续 **`51.6 分钟` S0ix Deep Idle 深度休眠（`CC7 = 99%`, `PC3 = 99%`, `0` 次伪 `DarkWake`）** 与开盖零绿屏秒醒（详见 [docs/continuation.md](continuation.md)）：

1. **进入睡眠阶段 (S0ix Entry)**：
   - 用户合盖或点击菜单“睡眠” -> `IOFramebuffer::systemWork` 调用 `framebuffer_will_power_off()`；`NootedGreen` 的 `xeNormalizePlane1ARgb` 实时拦截 `PLANE_CTL_1_A` (`0x70180`) 写入，将 Gen11 `0x82000400`（在 Gen12 上会被误判为 YUV 4:2:2 导致绿屏）强制改写为 Gen12 RGBX8888 (`0x84000400`)；
   - `Gen11::wrapSetFramebufferPowerState` 拦截 `FB0`/`FB1`/`FB2` 电源状态切换至 `0`，保存当前 `SBLC_PWM_FREQ` (`0xC8254`) 与非零 `SBLC_PWM_DUTY` (`0xC8258`)，关闭 `SBLC_PWM_CTL1` (`0xC8250` bit 31) 背光，调用 **`IOFramebuffer::handleEvent(fb, 3, (void *)1)`** (`kIOFBNotifyDidSleep`)，并由 `hwSaveNVRAM` 桩函数阻断 `_RESERVEDIODTPlatformExpert1` 崩溃；
   - `S0ixStandby.kext`（配置 `-s0ixd3 -s0ixdbg -s0ixnogpureset -s0ixcnvwd3`）：
     1. `dispPlaneSleep()` 清零 `PLANE_CTL_1_A` bit 31 停止显示控制器从 DRAM DMA 取数，允许内存控制器进入自刷新；
     2. 默认启用 `noUsbWake`（配合 `SSDT-DEEPIDLE.aml` 的 `\USWE = Zero`），清零 `XHCI`/`TXHC`/`TBT` 的 PCI `PME_EN` 并屏蔽 `GPE 0x6D/0x69` 阻断 USB 外设误唤醒，仅保留 `\_SB.LID` / `\_SB.SLPB` 的 GPE `0x6E` 唤醒掩码；
     3. 对 `CNVW` (`00:14.3` `8086:a0f0`) 执行 `BAR0` MMIO 软复位、置入 `D3hot` 并调用 `XSQD()`，同时将其余空闲无驱动 PCI 设备置入 `D3hot`；
     4. 执行完整 Intel `PEPD._DSM` fn `3/5/6/4`（置 `EC0.SLPT = 6`），并在 XNU `pmCPUHalt` 钩子 (`pmCPUHaltHook`) 中自动排空合盖状态下的非唤醒 EC 电池状态 SCI，使 CPU 持续驻留深度 S0ix。
2. **开盖 / 按键唤醒阶段 (S0ix Wake)**：
   - 开盖触发 EC `_Q0A` (GPE `0x6E`) SCI 中断立即唤醒 CPU；
   - 因设置了 **`-s0ixnogpureset`**，`S0ixStandby` 不对 `00:02.0` 执行 `GDRST=1` 复位，Tiger Lake GT 完整保留睡眠前的 `HWS_PGA = 0x40004000`、`GFX_MODE = 0x8000` 与 `CSB_PTR`；`NootedGreen` 的 **`hpCsResetOnWake`** 验证 `HWS_PGA != 0` 后跳过原生 `resetOnWake` 并同步软件 CSB 读指针 `cs + 0x1c04`；
   - `S0ixStandby::dispPlaneWake()` 与 `NootedGreen::xeNormalizePlane1ARgb` 确保 `PLANE_CTL_1_A` 维持 `0x84000400` RGB 格式及全零 `CSC_MODE_A`，在 `gXeWakeHoldActive` 保持窗口内待桌面新帧翻转后恢复 `SBLC_PWM_FREQ`/`DUTY`/`CTL1` 硬件背光，并由 `hp-wake-helper` 与 `hp-bridge` 同步刷新音频功放及控制中心亮度。
3. **推荐 `pmset` 电源管理策略配置**：
   - 日常移动办公使用 S0ix 睡眠时：
     ```sh
     sudo pmset -a hibernatemode 0 standby 0 autopoweroff 0 powernap 0 tcpkeepalive 0 womp 0 proximitywake 0 ttyskeepawake 0 lidwake 1
     sudo pmset -b displaysleep 5 sleep 10
     sudo pmset -c displaysleep 10 sleep 15
     ```
   - 远程无人值守 SSH 维护或压测期间（防止机器休眠断联）：
     ```sh
     sudo pmset -a sleep 0 displaysleep 0 disksleep 0 disablesleep 1
     ```

---

## 7. 第六阶段：验收测试清单与故障恢复指南 (Verification Checklist & Recovery)

### 7.1 全系统功能验收测试命令清单

全新安装并完成上述配置后，可直接运行外置 U 盘适配包中的**非破坏性一键全系统验收脚本**（自动检查 10 大子系统并在全部通过时返回退出码 `0`）：

```sh
/Volumes/Yan/HP-Tahoe-PostInstall-20261108/verify-postinstall.sh
```

也可在 macOS 终端中逐项运行以下分步手工命令核验适配状态（参考实机基线输出 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/live-baseline-pcfix33-3b5cd162.txt` 与全外设深度审计报告 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/peripheral-audit-report.json` / `.local/driver-repair-20261103/s0ix-standby-prep-20261107/peripheral-audit-3b5cd162/peripheral-audit-report.md`）：

```sh
# 1. 验证系统版本、启动参数、PMAPFIX 物理页隔离与 X86PlatformPlugin (XCPM 39 P-States)
sw_vers
uname -a
nvram 7C436110-AB2A-4BBB-A880-FE41995C9F82:boot-args
sysctl vm.pages   # 启用 PMAPFIX 后应比未保留时少 1,024~1,033 页（16 GiB 机器约为 4021211）
sysctl machdep.cpu.brand_string machdep.cpu.model machdep.xcpm.mode machdep.xcpm.vectors_loaded_count
# Dragonfly G2 (8716) 应返回:
#   machdep.cpu.brand_string: 11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz
#   machdep.cpu.model: 126 (0x706E5 CPUID 仿冒自真实 0x806C1 model 140；EliteBook 840 G8 880D 为 i7-1165G7 @ 2.80GHz)
#   machdep.xcpm.mode: 1
#   machdep.xcpm.vectors_loaded_count: 1
ioreg -rd1 -n PR00 | grep -E '"plugin-type"'
ioreg -rn X86PlatformPlugin | grep -E '"ResourceName"|"CPUPStates"|"FrequencyVectors"'
# PR00@0 应显示 "plugin-type" = 1；X86PlatformPlugin 应加载 Mac-5F9802EFE386AA28.plist (MacBookPro16,2 / J214k) 2 个 FrequencyVectors 并枚举 39 档 P-States (400..4200 MHz)

# 2. 验证 AuxKC 与 OpenCore 核心 Kext 加载状态及 UUID
kmutil showloaded | grep -E "NootedGreen|AppleIntelTGL|HookCase|AppleALC|SimpleHDA|TGLDmic|S0ixStandby|AirportItlwm|VirtualSMC|SMCProcessor|SMCBatteryManager|NVMeFix"

# 3. 验证 NootedGreen R32-PCFIX37-WAKERGB 关键钩子命中与 GPU 零复位计数
sudo dmesg | grep -E "HP-S0IX|HP-POSH-EXECLIST|HP-SINGLEPORT-RCS|HP-PCFIX|WAKE-RGB"
ioreg -rd1 -n IGPU | grep -i "ngreen-wake-plane-rgb-fix"        # PCFIX37 下应导出 ngreen-wake-plane-rgb-fix
ioreg -r -c IntelAccelerator -d 1 | grep -i '"recoveryCount"'   # 应为 "recoveryCount"=0
system_profiler SPDisplaysDataType                               # 应显示 Metal Support: Metal 2, VRAM: 1536 MB

# 4. 验证 CoreAudio 5 设备枚举（ALC285 扬声器/耳机/耳麦/线路输入 + TGLDmic 四阵列数字麦克风）
system_profiler SPAudioDataType
# CoreAudio 应完整枚举 5 个内置 (bltn) 48 kHz 音频设备（Built-in Line Input 标称 44.1 kHz）：
#   1) Built-in Speaker (ID=48, AppleHDAEngineOutput:1F,3,0,1,3:1, 2ch 48 kHz 默认输出)
#   2) Built-in Headphones / Built-in Output (ID=57, AppleHDAEngineOutput:1F,3,0,1,2:0, 2ch 48 kHz 3.5mm 耳机输出)
#   3) Built-in Microphone (ID=67, AppleHDAEngineInput:1F,3,0,1,1:3, 2ch 48 kHz 3.5mm 耳麦麦克风输入)
#   4) Built-in Line Input (ID=76, AppleHDAEngineInput:1F,3,0,1,0:2, 2ch 44.1 kHz 标称线路输入)
#   5) Internal Microphone (TGLDmic) (ID=84, TGLDmic_InternalMic_UID, 4ch 48 kHz cAVS DMA -> 2ch HAL 默认输入)
ioreg -r -c TGLDmic -d 1 | grep -E "TGLDmicPhase|BootState|BootResult"   # 应为 Phase=4, BootState=1, "OK FW_READY"
/usr/local/bin/tgldmic-probe 3 /tmp/tgldmic-test.wav                     # 实测 3 秒 4 通道录音并检查 RMS/Peak dBFS

# 5. 验证内屏背光桥接、右上角控制中心原生亮度滑块与 UVC 摄像头 (HP HD Camera 0408:5349)
/usr/local/bin/hp-bridge --probe-ds   # 应返回 canChange=1 isBuiltIn=1
system_profiler SPCameraDataType      # 应识别 HP HD Camera (VendorID_1032 ProductID_21321 / 0408:5349)
ioreg -p IOUSB -w0 -l | grep -E "HP HD Camera|HP IR Camera|idVendor|idProduct"

# 6. 验证 Wi-Fi、蓝牙、指纹、触控板/触屏、NVMe/TBT4 与 VirtualSMC 118 键传感器遥测
ifconfig en0
system_profiler SPBluetoothDataType | grep -E "State:|Firmware Version:|Services:"
/usr/local/bin/ridgekeyctl status && /usr/local/bin/ridgekeyctl list     # Synaptics 06cb:00f0 (已录入 right-thumb / right-index 2 枚指纹)
ioreg -rn TPD0 | grep -E '"IOName"|"VoodooInput"|52596'                  # Synaptics SYNA30B6 (06cb:cd74 = 1739:52596) + 24 键 JIS 映射
ioreg -rn TPL0 | grep -E '"IOName"|1386|18724'                           # Wacom WACF4233 (056a:4924 = 1386:18724, VoodooI2CHIDDevice 触屏)
system_profiler SPNVMeDataType | grep -E "Model:|Capacity:"              # Micron 2210 MTFDHBA512QFD-1AX1AABHA (512.11 GB, ASPM L1)
ioreg -rc AppleSMC -d1 | grep -E "AppleSMC|virtualsmc"                   # VirtualSMC 1.3.7 注册 118 个 SMC 键
pmset -g batt
ioreg -rn AppleSmartBattery | grep -E "CurrentCapacity|MaxCapacity|CycleCount|Temperature"

# 7. 验证 S0ix Modern Standby (Deep Idle) 就绪状态、USB 唤醒屏蔽、CNVW D3 与持久化日志守护进程
ioreg -lw0 | grep '"IOPMDeepIdleSupported"'   # 应为 "IOPMDeepIdleSupported" = Yes
ioreg -r -c S0ixStandby -d 1 | grep -E "LPIT status|DSM enabled|USB wake disabled|CNVW D3 enabled|D3 devices|8086:9a1b"
ls -la /var/log/hp/current/ && sudo launchctl print system/com.hp.syslogger | head -n 20
```


### 7.2 故障恢复与应急回滚指南 (Recovery Guide)

若在升级 `NootedGreen.kext`、修改 `config.plist` 或重建 AuxKC 后出现无法进入 macOS 桌面或启动停滞，严禁盲目重装系统，请按以下两条已验证通道恢复：

#### 通道一：通过内置 NixOS 双系统恢复 `/boot/EFI/OC` 并离线审计 Panic（首选）
1. **开机进入 NixOS**：由于 `systemd-boot` 默认启动项保持为 NixOS（测试新 EFI 时仅使用 `bootctl set-oneshot macos-opencore.conf` 单次引导），强制重启或正常重启后机器会自动回到 NixOS（可通过本地终端或 Tailscale SSH `<user>@<nixos-host>` 登录）。
2. **先只读归档 EFI NVRAM 变量（遵循 `AGENTS.md` 取证规则）**：
   ```sh
   sudo tar -cf /tmp/efivars-post-boot.tar -C /sys/firmware/efi/efivars .
   ```
   将该归档拉回开发机检查是否存在新增的 `AAPL,PanicInfo0000..` 分片并执行 7-bit 解码，区分究竟是内核 Panic 还是启动同步停滞。
3. **一键回滚 `/boot/EFI/OC` 配置与驱动**：
   每次部署前均在 `.local/` 与 `/boot/` 留有完整备份包（如最新生产引导归档 `.local/driver-repair-20261103/s0ix-standby-prep-20261107/post-wake-ebaba2ee/after-lidwake-greenfix-boot-oc.tar` 或回滚前备份），在 NixOS 下直接还原即可立即恢复上一次已知良好的 OpenCore 引导：
   ```sh
   sudo rm -rf /boot/EFI/OC
   sudo tar -xf /path/to/after-lidwake-greenfix-boot-oc.tar -C /boot/EFI/
   sync
   ```

#### 通道二：通过外置 Ventoy U 盘 VESA 安全镜像引导修复 AuxKC / `/Library/Extensions`
若因修改了 macOS 卷内的 `/Library/Extensions` 或 AuxKC 损坏导致内置 OpenCore 无法进入桌面：
1. 插入 Lexar Ventoy U 盘，开机按 `F9` 选择 USB 引导，在 Ventoy 菜单中选择预置的 VESA 恢复镜像 **`HP-GA420C-AUTO-RECOVERY.img`**（自带 `boot-args: -igfxvesa` 且禁用 `NootedGreen`）或 **`HP-Tahoe-VESA-XHCI-RHUB.img`**。
2. 以 VESA 软件显示模式进入 macOS 桌面或 Recovery Terminal：
   - 若需挂载并修复内置盘 ESP：
     ```sh
     sudo diskutil mount disk0s1
     # 替换 /Volumes/NO\ NAME/EFI/OC/config.plist 或 Kexts/NootedGreen.kext
     ```
   - 若需回滚 `/Library/Extensions` 并重建干净的 AuxKC：
     ```sh
     # 移除问题第三方 kext 或使用预先保存的 rollback-stage.tar 还原
     sudo kmutil install --volume-root / --update-all --force
     sudo kcditto
     ```
3. 在开发机运行仓库一致性检查与全量重编译校验确认所有文档、哈希与产物无误：
   ```sh
   make check && nix develop -c make verify-release
   ```

---

## 8. 自定义组件源码索引与从源码重编译指南 (Custom Component Source Index & From-Source Rebuild Guide)

本节完整列出本机型（HP Elite Dragonfly G2 `8716` / 同平台 HP EliteBook 840 G8 `880D`）在 **macOS Tahoe 26（`26.6.2` / `25G83`）** 下所使用的全部自定义内核扩展（Kexts）、ACPI SSDT 热补丁（`.dsl` -> `.aml`）、用户态守护进程/动态库 Shim、音频/背光/蓝牙/持久化日志脚本以及 GPU 辅助组件的**精确源码路径、SHA256 校验值与从源码重编译命令**（独立单册版同步维护于 [docs/from-source-rebuild-guide.md](from-source-rebuild-guide.md)）。所有本地交叉编译、链接、签名与 IASL 编译均可在 Linux 开发机（`/srv/mac-for-elitebook`）通过仓库根目录的 [flake.nix](../flake.nix)（`nix develop`）零外部依赖复现，亦可在 macOS 本机使用 Xcode Command Line Tools 原生编译。

---

### 8.1 核心内核扩展 (Kexts) 源码与重编译流程

| 内核扩展名称 | 版本 / 补丁标识 | 源码目录与核心源文件 | 仓库跟踪补丁 / 构建脚本 | 产物二进制路径与 SHA256 |
| --- | --- | --- | --- | --- |
| **`NootedGreen.kext`** | `1.0.0` (`com.StezzaPilot.NootedGreen`, `R32-PCFIX37-WAKERGB` + `PCFIX36` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`, `LC_UUID` `4C4C44A8-5555-3144-A16C-16F349CEF835`) | 源码树：`.local/driver-repair-20261103/repair32-readback/source/`<br>核心实现：`kern_gen11.cpp` (`707,888` B, SHA256 `6c42d019445988feb826ac6581f2c0c90a34f0e1266436ef81eed35f03f2d240`)、`kern_green.cpp` (`50,913` B, SHA256 `eb0f7c9a3b379c6cb77641bfd3f3beacd9c8c5e4fbd176934914a3db49fd3db5`)、`kern_gen11.hpp` (`86,202` B)、`kern_green.hpp` (`10,703` B)、`kern_start.cpp` (`1,877` B) | 完整累积补丁：[patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch](../patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch) (`95,341` B, SHA256 `d7b02ea9405468109fa755e4b4321768ef0c0ce722c183306529cc4d2ae1d4ea`)<br>历史演进补丁：[nootedgreen-r32-pcfix27-20261106.patch](../patches/nootedgreen-r32-pcfix27-20261106.patch)、[nootedgreen-r32-pcfix31-backlight-20261107.patch](../patches/nootedgreen-r32-pcfix31-backlight-20261107.patch)、[nootedgreen-r32-pcfix32-s0ix-20261107.patch](../patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch)、[nootedgreen-r32-pcfix33-s0ix-20261108.patch](../patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch)、[nootedgreen-r32-pcfix34-s0ix-drm-20261108.patch](../patches/nootedgreen-r32-pcfix34-s0ix-drm-20261108.patch)、[nootedgreen-r32-pcfix35-blitalign-20261108.patch](../patches/nootedgreen-r32-pcfix35-blitalign-20261108.patch)、[nootedgreen-r32-pcfix36-wakecolor-20261109.patch](../patches/nootedgreen-r32-pcfix36-wakecolor-20261109.patch)<br>构建脚本：`build.py` + `offline-wrapper.py` | `NootedGreen` (`540,944` B, SHA256 `00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3`)<br>`Info.plist` (`3,700` B, SHA256 `b5fd1d0fe125a48f6045c3b07a8f5894f76fc406caf5065f126830a63ea4738e`)<br>回执：`build-receipt.json` |
| **`S0ixStandby.kext`** | `v0.4.4` (`com.labrouss.S0ixStandby`, commit `8b37bb4` + Phase 17 USB 唤醒屏蔽、`CNVW` BAR0 MMIO 静默与 `dispPlaneSleep`/`dispPlaneWake` RGB 规范化) | 源码仓库：`.local/peripheral-prep-20261105/S0ixStandby-repo/`<br>核心实现：`S0ixStandby.cpp` (`71,761` B, SHA256 `4eefd1a5e70e1416445c2adf517068386f7b6bc9616ec954ca1fde81c1dc756d`)、`S0ixGPU.cpp` (`30,611` B, SHA256 `2309664fb9f08d8a554999c20b5e41f0549a83bf68459d9302938fec17b92199`)、`S0ixStandby.hpp` (`11,312` B, SHA256 `b86ce7be109ff0025e9734d87b3129174f7a862a41c2ce0a0f551494cde4e6ae`)、`kmod_info.c` (`733` B) | `Makefile` (`2,805` B, SHA256 `c963731d0467504b32f27da6d2b1e893b8a4378863ee0cfe18872b68f9e0a14d`) | 预备包：`.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext`<br>二进制：`S0ixStandby` (`74,584` B, SHA256 `be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184`)<br>`Info.plist` (`4,668` B, SHA256 `4e82da9599fb42a99fdd2e317e29587f0343d661397ec2907a5dfbf5f18d473e`) |
| **`TGLDmic.kext` & `TGLDmic.driver`** | `v0.5.0` (`com.labrouss.TGLDmic` & `com.labrouss.TGLDmic.driver`, commit `d13dafa`) | 源码仓库：`.local/peripheral-prep-20261105/TGLDmic-repo/`<br>Kext 源码：`TGLDmic.cpp` (`19,556` B)、`DspBoot.cpp` (`20,788` B)、`Capture.cpp` (`18,737` B)、`TGLDmicUserClient.cpp` (`4,089` B)、`IpcReplay.hpp`、`Regs.hpp`、`DmaBuffer.hpp`、`TGLDmicShared.h`、`sof-tgl.ri`<br>HAL 插件与工具：`TGLDmicDriver.cpp` (`42,856` B, SHA256 `4d1caf88cae4a0a550945c4e80b712806434baad603293492d30ae98d20cf4e8`)、`tgldmic-probe.c` (`3,980` B) | Kext：`kext/Makefile` (`1,890` B) + `tools/gen-fw.py`<br>HAL：`hal/Makefile` (`915` B) + `hal/install-hal.sh` | Kext 预备包：`TGLDmic.kext`（二进制 `TGLDmic` `1,199,424` B, SHA256 `b0d0715dfb49b6ea15208cdfa0f99373e2e62ee4e2a02448462252ef6721b416`；`Info.plist` `1,646` B, SHA256 `ea026bd65b79ed171615f5df3f8a1cd72f6d76b97c3a01be9c2a5b523f3471f0`）<br>HAL 插件：`TGLDmic.driver`（二进制 `TGLDmic` `48,352` B, SHA256 `6e75f82f6a0237a40f20810df591b90e9c2161e34c389c5eb5e7534180eddca0`） |
| **`SimpleHDA.kext` & `AppleALC.kext`** | `SimpleHDA 1.0.1` (commit `18a16d4`) + `AppleALC 1.9.8` (`0xa0c8` + `layout-id 71`) | `SimpleHDA` 源码树：`.local/peripheral-prep-20261105/SimpleHDA-repo/`<br>`AppleALC` 定制包：`.local/driver-repair-20261103/audio-ridgekey-fix-20261107/stage-oc/Kexts/AppleALC.kext` | `prepare_audio_config.py` | `SimpleHDA` (`4,458,280` B, SHA256 `5a1beec91f121a018072ac085c51543d5eaea85347e6417cd2e37d254d9383c1`)<br>`AppleALC` (`3,810,852` B, SHA256 `690b96189491b9d6f64aa552da6684714d80ade4ad4ec9027251c3257a2d16e8`) |

#### 1. `NootedGreen.kext` (`R32-PCFIX37-WAKERGB` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`) 源码补丁应用与本地交叉编译

1. **从上游干净基线应用跟踪补丁（或直接使用已就绪源码树）**：
   - 本地源码树位于 `.local/driver-repair-20261103/repair32-readback/source/`（上游基线 `ChefKissInc/NootedGreen` / `NootedGreen-NP550XDA` commit `6f03560`；核心文件 `kern_gen11.cpp` `707,888` B，SHA256 `6c42d019445988feb826ac6581f2c0c90a34f0e1266436ef81eed35f03f2d240`）。
   - 仓库跟踪的统一 diff 补丁 [patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch](../patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch)（`95,341` B，SHA256 `d7b02ea9405468109fa755e4b4321768ef0c0ce722c183306529cc4d2ae1d4ea`）包含 `R32-PCFIX37` 及此前各阶段全部核心改动：
     - **单端口 Execlist 串行化与 `ELSQWAIT`**：拦截 `submitToRing` 与 `processExeclist`，读取 `RING_EXECLIST_STATUS_LO` (`0x2234`) 确保 RCS0 硬件空闲后再写 `ELSQ`，消除跨上下文抢占覆盖；
     - **内核级 `hpSanitizeComputeEncoder` (`PCFIX27`)**：在内核提交前原地净化 3D/Compute 批处理缓冲，修补 `0x7a000004` `PIPE_CONTROL` 尾刷新位并在 `endOffDw` 追加读写缓存屏障，禁用 POSH (`cs + 0x10` `fAccelerator`)；
     - **内屏 eDP 硬件 PWM 背光缩放 (`XE-BLR` / `-ngreenblr`)**：拦截 `0xC8254` (`SBLC_PWM_FREQ`) 与 `0xC8258` (`SBLC_PWM_DUTY`) 全部 3 条 MMIO 写入路径；
     - **macOS 26 Tahoe S0ix 睡眠/唤醒全链路修复 (`PCFIX32` + `PCFIX33` + `PCFIX34`)**：将 `AppleIntelBaseController::hwSaveNVRAM()` 路由为空操作（消除 `IODTPlatformExpert::_RESERVEDIODTPlatformExpert1` 内核 Panic）；在 `Gen11::wrapSetFramebufferPowerState` 中同时拦截 `FB0`/`FB1`/`FB2` 并在睡眠/唤醒转换时显式调用 `IOFramebuffer::handleEvent(fb, 3/4, (void *)1)`；路由 `IGHardwareCommandStreamer5::resetOnWake()` 至 `hpCsResetOnWake`，在 `HWS_PGA` (`0x2080`) 非零时跳过硬件状态页清零并同步软件读指针 `*(cs + 0x1c04)`；
     - **Phase 10 `isRealTGL && Tahoe` 启用 `HP-BLITALIGN`、`HP-BLITFIX` 与 `HP-BLIT16` (`PCFIX35`)**：放宽 `blit2d_common_supported` / `blit2d_fast_supported` 的 64B 对齐检查，将软解 `420v` 32B 非 64B 对齐 `IOSurface` 平面路由至 `BCS0` `XY_SRC_COPY_BLT` 2D 拷贝，并强制剩余 `Blit3D` 像素着色器使用 `SIMD16`，根治 `420v` 视频播放绿屏与卡顿；
     - **Phase 17 S0ix 唤醒绿屏根除与 `PLANE_CTL_1_A` RGB 强制规范化 (`PCFIX36` + `PCFIX37`)**：新增 `xeNormalizePlane1ARgb`，拦截 `AppleIntelICLGraphicsFramebuffer` 在睡眠入口写入 `PLANE_CTL_1_A` (`0x70180`) 的 Gen11 格式位 `0x82000400`（Gen12 Tiger Lake 硬件将其解码为 YUV 4:2:2 Packed 导致纯绿闪屏），实时改写为 Gen12 RGBX8888 (`0x84000400`)，同步将 `PLANE_COLOR_CTL_1_A` (`0x701CC`) 设为 `0x2000`、`CSC_MODE_A` (`0x4A480`) 清零，通过 `gXeWakeHoldActive` 维持最长 `820 ms`（桌面新帧翻转后 `120 ms` 提前释放，保底 `450 ms`）的硬件 PWM 背光保持，并在 IORegistry 导出 `ngreen-wake-plane-rgb-fix = 1`。

2. **一键交叉编译命令（使用 `build.py` 与 `offline-wrapper.py`）**：
   ```sh
   cd /srv/mac-for-elitebook
   # 验证源码与补丁 SHA256
   sha256sum \
     patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch \
     .local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_gen11.cpp \
     .local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_green.cpp

   # 在 Nix 开发环境中执行交叉编译、$LD64_LLD 链接与 rcodesign 签名
   nix develop -c python3 .local/driver-repair-20261103/repair32-readback/build.py

   # 核验生成的 NootedGreen 二进制哈希 (应为 540,944 B, SHA256 00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3, LC_UUID 4C4C44A8-5555-3144-A16C-16F349CEF835)
   sha256sum .local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/MacOS/NootedGreen
   ```

3. **底层 `$CLANG_APPLE` + `$LD64_LLD` + `rcodesign` 等价编译命令明细**：
   `offline-wrapper.py` 在内部对 `info.c`、`src/NootedGreen/` 下的 12 个 C++ 编译单元（`DisplayMergeNub.cpp`、`DYLDPatches.cpp`、`Firmware.cpp`、`FirmwareADLP.cpp`、`HDMI.cpp`、`IntelDPLinkTraining.cpp`、`kern_gen11.cpp`、`kern_genx.cpp`、`kern_green.cpp`、`kern_patcherplus.cpp`、`kern_start.cpp`、`kern_xepm.cpp`）及 `Lilu` 插件入口 `plugin_start.cpp` 执行的精确编译、链接与签名参数如下（仓库内亦归档了独立内核头文件与静态库副本 `.local/build-readiness/isolated/WhateverGreen/MacKernelSDK/` 与 `.local/build-readiness/isolated/WhateverGreen/Lilu.kext/Contents/Resources/`）：
   ```sh
   nix develop -c bash -c '
     SRC="/srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen"
     OBJ="/srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/objects/snapshot/NootedGreen"
     OUT="/srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext"
     OLD="/srv/tgl26-usb/GA43-AppleTGL-Tahoe/inputs/upstream/nootedgreen"

     # 编译单个 C++ 内核源文件 (以 kern_gen11.cpp 为例)
     "$CLANG_APPLE" -target x86_64-apple-macos13.0 -mkernel -nostdinc \
       -fno-builtin -fno-common -fno-stack-protector -mmmx -msse -msse2 \
       -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -DDEBUG=1 \
       -isystem "$OLD/MacKernelSDK/Headers" -I"$SRC" -O2 -g \
       -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit \
       -mllvm -disable-atexit-based-global-dtor-lowering \
       -fno-asynchronous-unwind-tables \
       -DAPPLE_KEXT_ASSERTIONS=1 -DPRODUCT_NAME=NootedGreen -DMODULE_VERSION=1.0.0 \
       -I"$OLD/Lilu.kext/Contents/Resources" \
       -std=gnu++17 -nostdinc++ -fno-exceptions -fno-rtti -fapple-kext \
       -Wno-deprecated-declarations -Wno-inconsistent-missing-override -Wno-unused-parameter \
       -c "$SRC/kern_gen11.cpp" -o "$OBJ/kern_gen11.o"

     # 使用支持 -kext 的 $LD64_LLD 链接生成 Mach-O MH_KEXT_BUNDLE 并执行 Ad-hoc 签名
     "$LD64_LLD" -kext -arch x86_64 -platform_version macos 13.0 26.5 -export_dynamic \
       -o "$OUT/Contents/MacOS/NootedGreen" \
       "$OBJ"/*.o "$OLD/MacKernelSDK/Library/x86_64/libkmod.a"

     "$RCODESIGN" sign --config-file /dev/null --timestamp-url none "$OUT"
   '
   ```

#### 2. `S0ixStandby.kext` (`v0.4.4`) 源码与重编译流程

- **源码位置**：`.local/peripheral-prep-20261105/S0ixStandby-repo/`（包含 `Makefile`、`S0ixStandby/S0ixStandby.cpp` `71,761` B SHA256 `4eefd1a5e70e1416445c2adf517068386f7b6bc9616ec954ca1fde81c1dc756d`、`S0ixStandby/S0ixGPU.cpp` `30,611` B SHA256 `2309664fb9f08d8a554999c20b5e41f0549a83bf68459d9302938fec17b92199`、`S0ixStandby/S0ixStandby.hpp` `11,312` B SHA256 `b86ce7be109ff0025e9734d87b3129174f7a862a41c2ce0a0f551494cde4e6ae`、`S0ixStandby/kmod_info.c` `733` B、`S0ixStandby/Info.plist` 及诊断脚本 `macos/s0ix-status.sh`）。
- **重编译命令**（支持在 Linux 开发机通过 `nix develop` 交叉编译，或在 macOS 本机调用 `Makefile` 的 `SDK` / `COMMON` / `CXXFLAGS` / `CFLAGS` / `LDFLAGS` 构建）：
  ```sh
  # 方式 A：在本地 Linux 开发机通过 nix develop + MacKernelSDK 交叉编译 S0ixStandby.kext (v0.4.4)
  nix develop -c bash -c '
    set -e
    SDK="/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK"
    REPO="/srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo"
    TMP=$(mktemp -d)
    trap "rm -rf $TMP" EXIT

    COMMON="-target x86_64-apple-macos10.13 -mkernel -nostdinc -fno-builtin -fno-common -fno-stack-protector -mmmx -msse -msse2 -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -I$SDK/Headers -Wall -Wextra -Wno-unused-parameter -Os -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit -mllvm -disable-atexit-based-global-dtor-lowering -fno-asynchronous-unwind-tables"
    "$CLANG_APPLE" $COMMON -std=gnu++17 -fapple-kext -fno-rtti -fno-exceptions -c "$REPO/S0ixStandby/S0ixStandby.cpp" -o "$TMP/S0ixStandby.o"
    "$CLANG_APPLE" $COMMON -std=gnu++17 -fapple-kext -fno-rtti -fno-exceptions -c "$REPO/S0ixStandby/S0ixGPU.cpp" -o "$TMP/S0ixGPU.o"
    "$CLANG_APPLE" $COMMON -std=gnu11 -DKEXT_BUNDLE_ID=com.labrouss.S0ixStandby -DKEXT_VERSION=\"0.4.4\" -c "$REPO/S0ixStandby/kmod_info.c" -o "$TMP/kmod_info.o"
    "$LD64_LLD" -kext -arch x86_64 -platform_version macos 10.13 26.5 -export_dynamic \
      "$TMP/S0ixStandby.o" "$TMP/S0ixGPU.o" "$TMP/kmod_info.o" \
      "$SDK/Library/x86_64/libkmod.a" "$SDK/Library/universal/libkmodc++.a" \
      -o "$TMP/S0ixStandby"
    "$LLVM_BIN/llvm-nm" -gU "$TMP/S0ixStandby" | grep -E "kmod_info|_start"
  '

  # 方式 B：在 macOS Xcode Command Line Tools 环境下直接运行上游 Makefile
  # cd /srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo
  # make SDK=/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK

  # 核验已部署预备包二进制 SHA256 (应为 74,584 B, SHA256 be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184)
  sha256sum /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext/Contents/MacOS/S0ixStandby
  ```

#### 3. `TGLDmic.kext` (`v0.5.0`) 与 `TGLDmic.driver` CoreAudio HAL 插件重编译流程

- **源码位置**：`.local/peripheral-prep-20261105/TGLDmic-repo/`，分为内核驱动目录 `kext/`（`kext/Makefile`）与用户态 CoreAudio AudioServerPlugIn 目录 `hal/`（`hal/Makefile`）。
- **从源码重编译步骤**（支持在本地 Linux 开发机通过 `nix develop` 全量交叉编译 `TGLDmic.kext`、`TGLDmic.driver` 与 `tgldmic-probe`，或在 macOS 本机执行 `make`）：
  ```sh
  # 方式 A：在本地 Linux 开发机通过 nix develop 交叉编译 TGLDmic.kext + TGLDmic.driver + tgldmic-probe
  nix develop -c bash -c '
    set -e
    SDK="/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK"
    DMIC_REPO="/srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo"
    TMP=$(mktemp -d)
    trap "rm -rf $TMP" EXIT

    # 1) 生成内置 Intel SOF 固件源文件 Firmware.c 并交叉编译 TGLDmic.kext
    python3 "$DMIC_REPO/tools/gen-fw.py" \
      --tgl "$DMIC_REPO/firmware/intel/sof-tgl.ri" \
      --cml "$DMIC_REPO/firmware/intel/sof-cml.ri" \
      -o "$TMP/Firmware.c"

    DMIC_COMMON="-target x86_64-apple-macos10.15 -mkernel -nostdinc -isystem $SDK/Headers -fno-builtin -fno-common -fno-stack-protector -mmmx -msse -msse2 -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -O2 -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit -mllvm -disable-atexit-based-global-dtor-lowering -fno-asynchronous-unwind-tables"
    for f in TGLDmic DspBoot Capture TGLDmicUserClient; do
      "$CLANG_APPLE" $DMIC_COMMON -std=gnu++17 -Wall -Wno-unused-private-field \
        -fapple-kext -fno-rtti -fno-exceptions -I"$DMIC_REPO/kext/TGLDmic" \
        -c "$DMIC_REPO/kext/TGLDmic/$f.cpp" -o "$TMP/$f.o"
    done
    "$CLANG_APPLE" $DMIC_COMMON -std=gnu11 -c "$TMP/Firmware.c" -o "$TMP/Firmware.o"
    "$CLANG_APPLE" $DMIC_COMMON -std=gnu11 -c "$DMIC_REPO/kext/TGLDmic/kmod_info.c" -o "$TMP/kmod_info.o"
    "$LD64_LLD" -kext -arch x86_64 -platform_version macos 10.15 26.5 -export_dynamic \
      "$TMP/TGLDmic.o" "$TMP/DspBoot.o" "$TMP/Capture.o" "$TMP/TGLDmicUserClient.o" \
      "$TMP/Firmware.o" "$TMP/kmod_info.o" \
      "$SDK/Library/x86_64/libkmod.a" "$SDK/Library/universal/libkmodc++.a" \
      -o "$TMP/TGLDmic.kext.bin"

    # 2) 交叉编译用户态 CoreAudio HAL 插件 TGLDmic.driver 与诊断工具 tgldmic-probe
    "$CLANG_APPLE" -target x86_64-apple-macos10.15 -isysroot "$SDKROOT" \
      -isystem "$SDKROOT/usr/include/c++/v1" -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
      -c "$DMIC_REPO/hal/TGLDmicDriver.cpp" -o "$TMP/TGLDmicDriver.o"
    "$LD64_LLD" -bundle -arch x86_64 -platform_version macos 10.15 26.5 -syslibroot "$SDKROOT" \
      "$TMP/TGLDmicDriver.o" -lSystem -lc++ \
      -framework CoreAudio -framework CoreFoundation -framework IOKit \
      -o "$TMP/TGLDmic.driver.bin"

    "$CLANG_APPLE" -target x86_64-apple-macos10.15 -isysroot "$SDKROOT" -std=c11 -O2 -Wall \
      -c "$DMIC_REPO/hal/tgldmic-probe.c" -o "$TMP/tgldmic-probe.o"
    "$LD64_LLD" -arch x86_64 -platform_version macos 10.15 26.5 -syslibroot "$SDKROOT" \
      "$TMP/tgldmic-probe.o" -lSystem -framework IOKit -framework CoreFoundation \
      -o "$TMP/tgldmic-probe"
  '

  # 方式 B：在 macOS Xcode Command Line Tools 环境下直接运行上游 Makefile
  # make -C /srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext SDK=/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK
  # make -C /srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal

  # 3) 核验已部署预备包二进制 SHA256
  sha256sum \
    /srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/tgldmic-prep-20261107/TGLDmic.kext/Contents/MacOS/TGLDmic \
    /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/Library-Audio-Plug-Ins-HAL/TGLDmic.driver/Contents/MacOS/TGLDmic
  ```

---

### 8.2 ACPI SSDT 热补丁源码 (`.dsl` -> `.aml`) 与 `iasl` 编译命令

本机 `/EFI/OC/ACPI/` 下挂载的全部 6 张生产环境热补丁表（及 1 张归档备查表）均配有完整的 `.dsl` ASL 源码，在本地开发机通过 `nix develop -c iasl -ve`（ACPICA ASL Optimizing Compiler）实现 **`0` Errors、`0` Warnings** 确定性编译：

| SSDT 表名称 | `.dsl` 源码路径、字节数与 SHA256 | `.aml` 产物路径、字节数与 SHA256 | 配套 `config.plist` `ACPI -> Patch / Delete` 与功能说明 |
| --- | --- | --- | --- |
| **`SSDT-EC0-ITLB.aml`** | `SSDT-EC0-ITLB.dsl`<br>`7,231` B<br>SHA256 `30dd9d79d501cb83cab902fe9acc3f46553ef6efafc5878641fe1174387186ed` | `SSDT-EC0-ITLB.aml`<br>`1,572` B<br>SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8` | 配合 4 条 `Count=1` 精确重命名（`DSDT`: `ITLB\0 -> XTLB\0`；`NVTEC`: `EC12\0 -> XC12\0`、`EC13\0 -> XC13\0`；`DptfTabl`: `ODVP\x08 -> XDVP\x08`）+ 1 条 `ACPI -> Delete`（丢弃 `OemTableId="HP_XHC_P"` `TableLength=2362` 的 `SSDT13`），将 `ECEnabler` 挂载前（`t=1.93s`）访问的 4 个 16-bit EC 寄存器（`BDC`/`BFC`/`BDV`/`ACPR`）拆分为 8-bit 字节对，实现冷启动 **`0` 次 ACPI Error/Exception** 并完整走通 `ECRI -> ITLB -> SBTN -> PRIT` |
| **`SSDT-DEEPIDLE.aml`** | [SSDT-DEEPIDLE.dsl](../../EFI/ACPI/SSDT-DEEPIDLE.dsl)<br>`2,793` B<br>SHA256 `1f569b6bbb0d4305a27fcadeedf69a463c18f47b581d5140fb8acb2ecccfb1b9` | `SSDT-DEEPIDLE.aml`<br>`371` B<br>SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1` | 配合 `OemTableId="MS-SSDT"` 限定重命名 `14275F53544100 -> 14275853544100`（`PEPD._STA -> XSTA`, `Count=1`），在 Darwin 下注入 `\_SB.LPS0 = One`、`\_GPE.LXEN = One`、`\_SB.PEPD._STA` 置 `S0ID = One` 返回 `0x0F`，置 `\USWE = Zero` 全局屏蔽 USB/XDCI/Thunderbolt `_PRW` 唤醒（支持 `-s0ixusbwake` 动态覆盖），并为 `\_SB.LID` 与 `\_SB.SLPB` 注入 `_PRW`/`PRW0` (`Package (0x02) { 0x6E, 0x04 }`) 与 `_S0W` (`0x04`)，激活 `IOPMDeepIdleSupported = Yes`、`S0ixStandby.kext` 与 GPE `0x6E` 开盖/电源键唤醒 |
| **`SSDT-PLUG.aml`** | `SSDT-PLUG.dsl`<br>`1,355` B<br>SHA256 `b49fccae93979f77d61f34b3b0ed22920d93ac4ed87dfe73bdb42c2f9743654a` | `SSDT-PLUG.aml`<br>`113` B<br>SHA256 `24956a41669b37fce98f09b9b6d28475a099693bb3522391d35609415e0ffed2` | 在 `\_SB.PR00` 注入 `plugin-type = 1`，配合 `Cpuid1Data` 仿冒 `0x706E5` 挂载 `X86PlatformPlugin`（`39` 档 P-States） |
| **`SSDT-EC-USBX-HP.aml`** | `SSDT-EC-USBX-HP.dsl`<br>`2,602` B<br>SHA256 `6ef5245418774d2bb84c177065f6294eeac7d57cd6202866b0be5f0bda400b45` | `SSDT-EC-USBX-HP.aml`<br>`372` B<br>SHA256 `296212e084666dfc9ed0ab69fbbecaaa3525da71f528526c2d22d0d81d7f6781` | 导出伪 `\_SB.PCI0.LPCB.EC` 与 `\_SB.USBX` USB 供电属性（`kUSBSleepPowerSupply = 5100`、`kUSBWakePowerSupply = 5100`） |
| **`SSDT-RHUB-HP.aml`** | `SSDT-RHUB-HP.dsl`<br>`1,050` B<br>SHA256 `6c0c75476502328fba31c6b77d8b144ac5dde53ed29eb3eea3fdaa33759c9498` | `SSDT-RHUB-HP.aml`<br>`108` B<br>SHA256 `4cf78eacb8f2529a3a93a3bb9406ad4cc5446fe19828c49241130ab0503daec9` | 在 Darwin 下为 `\_SB.PC00.XHCI.RHUB` 注入 `_STA = 0`，强制 `AppleUSBXHCISPT` 直接从硬件寄存器枚举 PCH XHCI 端口 |
| **`SSDT-PNLF-HP-GA419.aml`** | `SSDT-PNLF-HP-GA419.dsl`<br>`1,297` B<br>SHA256 `a442ccf1ed4f563e691c0a96b1c431fc9c0b07314615f89af1c19a76ba980911` | `SSDT-PNLF-HP-GA419.aml`<br>`142` B<br>SHA256 `72ec07163115d8c327f1c7f143b0375b7b0262adc9422c2628ab2177cc71414e` | 在 `\_SB.PC00.GFX0` 下注入 `PNLF` 背光设备（`_HID = "APP0002"`，`_UID = 0x13`） |
| **`SSDT-HP-Hotkeys.aml`** *(归档备查)* | `SSDT-HP-Hotkeys.dsl`<br>`3,389` B<br>SHA256 `a02df811c0ce77f01b0d5e9c6a4aecfec17fd432b3f08f802b0beb35d5d7e445` | `SSDT-HP-Hotkeys.aml`<br>`692` B<br>SHA256 `ba463a93a38fd9a8b8a79850d4c9fab184f1603ff07b6ee8a555d220863577f8` | 早期 EC `_Q86`/`_Q87` 与 WMI `GVWE` 队列排空转 `PS2K` 通知实验表；因实机顶排 16 键已通过原生 `i8042` 扫描码 + `VoodooPS2Keyboard` `24` 条 `Custom ADB Map` 完整驱动，生产环境 `config.plist` 不加载此表 |

#### 从 `.dsl` 源码重编译全部 `.aml` 并执行 OpenCore `ocvalidate` 校验

```sh
cd /srv/mac-for-elitebook

# 1. 使用 nix develop 中的 iasl 编译器重编译全部 6 张生产环境 SSDT
nix develop -c iasl -ve \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PLUG.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC-USBX-HP.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-RHUB-HP.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PNLF-HP-GA419.dsl

# 2. 校验生成的 .aml 二进制 SHA256
sha256sum \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PLUG.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC-USBX-HP.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-RHUB-HP.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PNLF-HP-GA419.aml

# 3. 使用与 OpenCore 1.0.8 版本严格匹配的 ocvalidate 校验 config.plist (应输出 No issues found.)
.local/opencore-1.0.8/Utilities/ocvalidate/ocvalidate.linux \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist
```

---

### 8.3 用户态守护进程、Shim 与音频/背光/指纹辅助工具源码索引

本机型所有用户态组件均支持在本地 Linux 开发机通过 `nix develop`（使用 `$CLANG_APPLE` / `clang` + `ld64.lld` + `rcodesign` 配合本地轻量级 TBD 桩库目录 `.local/driver-repair-20261103/brightness-fix-20261107/stubs/` 或 `$SDKROOT`）直接交叉编译，或在目标机 macOS 终端下使用系统 `clang` 编译。

#### 1. 用户态组件源码与部署路径总表

| 组件名称与目标机安装路径 | 源码文件、大小与 SHA256 | 预备产物路径与 SHA256 | 核心职责与运行机制 |
| --- | --- | --- | --- |
| **`libhp_cb_shim.dylib` / `hp-cb-shim.dylib`**<br>`/usr/local/lib/libhp_cb_shim.dylib`<br>`/usr/local/lib/hp-cb-shim.dylib` | `hp-cb-shim.m`<br>`19,545` B<br>SHA256 `14e276f659660bda1926e1b3b0f622c2f1fae87f2112f16142270fbfdf85327a` | `libhp_cb_shim.dylib` / `hp-cb-shim.dylib`<br>`35,456` B<br>SHA256 `e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798` | 通过 Mach-O `__DATA,__interpose` 与 `CoreBrightness.framework` GOT 补丁拦截 `IODisplayCopyParameters` 与 `IODisplayGet/SetIntegerRangeParameter`，将 `corebrightnessd` 所需的 `"brightness"` / `"linear-brightness"` / `"usable-linear-brightness"` / `"commit"` 字典实时桥接至内核 `AppleBacklightDisplay` 的 `"bklt"` (`600..65535`)，恢复右上角控制中心与系统设置原生亮度滑块 |
| **`hp-cb-shim-loader.sh`**<br>`/usr/local/bin/hp-cb-shim-loader.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.cb-shim-loader.plist` | `hp-cb-shim-loader.sh`<br>`4,617` B<br>SHA256 `a3de1c6667ae927ec9f166bcec7cdc27ef721bc9a8e19f31b03c4103f6008fb8`<br>Plist：`com.hp.cb-shim-loader.plist` (`610` B, SHA256 `12795cbacc89b36bf3828925f4a498d4f488a426519a362c9b58b1a7a883a9eb`) | `stage3-brightness-hotkeys/usr-local-bin/hp-cb-shim-loader.sh`<br>`4,617` B<br>SHA256 `a3de1c6667ae927ec9f166bcec7cdc27ef721bc9a8e19f31b03c4103f6008fb8` | 开机等待 `AppleBacklightDisplay` 与 `WindowServer` 就绪后，在 `/private/var/run/com.apple.corebrightnessd-shim.plist` 生成带 `DYLD_INSERT_LIBRARIES=/usr/local/lib/hp-cb-shim.dylib` 的服务定义并热切换原厂 `/usr/libexec/corebrightnessd`（保留 `CS_PLATFORM_BINARY`，日志落盘 `/var/log/hp-cb-shim-loader.log`），规避 macOS 26 `/usr/local/lib` firmlink `Bootstrap failed: 5` 与 `PETRIFIED` 竞态 |
| **`hp-bridge`**<br>`/usr/local/bin/hp-bridge`<br>守护配置：`/Library/LaunchAgents/com.hp.bridge.agent.plist` | 现役源码：`hp-bridge.m` (`79,041` B, SHA256 `68dff6624aa8e8b938b65335618c4a6874bfffaefb026a98891fb12ed656dcc5`；初版：`hp-bridge.m` `76,495` B)<br>Plist：`com.hp.bridge.agent.plist` (`596` B, SHA256 `514a849a596dfea3fe0000be896a12ba323c8bd4389f6f32eb3269630e80ff20`) | `stage3-brightness-hotkeys/usr-local-bin/hp-bridge`<br>`70,192` B<br>SHA256 `3854aabe44e6fd859111b859e6b9a66f3a82867b086389aa03b6263a0c27cfb7` | 用户态全功能热键、背光、音频与菜单栏常驻桥接守护进程：注册 11 项 Carbon 全局热键（无需 TCC 权限）与 `IOHIDManager` Consumer 监听，双向同步 `CoreDisplay` / `DisplayServices` 与硬件 `"bklt"` (`600..65535`)，驱动 `ALC285` AFG `0x01` GPIO `IO[2]` (`f5` 扬声器静音橙色 LED) 与 `IO[0]` (`f8` 麦克风静音橙色 LED)，日志持久化输出至 `/var/log/hp-bridge.log` |
| **`hp-brightness`**<br>`/usr/local/bin/hp-brightness` | 包装脚本：`hp-brightness` (`449` B, SHA256 `8396b8330bd683e8d78c879df29d6c5db005f18a9f07481ac82fe0ff1bf5de6c`)<br>独立前身源码：`hp-brightness-daemon.m` (`35,403` B, SHA256 `0752fb097833423643061cc9c638e9dddcff71dcf73dec5b2742a1aa3ac17235`) | `stage3-brightness-hotkeys/usr-local-bin/hp-brightness`<br>SHA256 `8396b8330bd683e8d78c879df29d6c5db005f18a9f07481ac82fe0ff1bf5de6c` | 命令行背光查询与调节入口（支持 `hp-brightness --get`、`hp-brightness --set <0.0..1.0>`、`hp-brightness --up/--down`、`hp-brightness --probe-ds`），转发至 `/usr/local/bin/hp-bridge` |
| **`hp-alc285-ampinit.sh`**<br>`/usr/local/bin/hp-alc285-ampinit.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.alc285.ampinit.plist` | `hp-alc285-ampinit.sh`<br>`2,229` B<br>SHA256 `2c9056f67333717c5d21598a1f51c2f9d43d4b5717ddf3f985fd86932e2af41c`<br>Plist：`com.hp.alc285.ampinit.plist` (`606` B, SHA256 `7d964e9e6d9d1c5ddc267f92a056d80c6c9b7eb9f0027360c4afeee403090503`) | `stage3-audio/usr-local-bin/hp-alc285-ampinit.sh`<br>`2,229` B<br>SHA256 `2c9056f67333717c5d21598a1f51c2f9d43d4b5717ddf3f985fd86932e2af41c` | 开机或 S0ix 唤醒后等待 `ALCUserClientProvider` 就绪，下发 Bang & Olufsen 功放初始化动词（`0x20 SET_COEF_INDEX 0x65`、`SET_PROC_COEF 0x0000`）与 3.5mm 耳麦麦克风通路增益（`0x19`/`0x23`/`0x08`），并依次调用 `hp-select-speaker` 与 `hp-select-dmic.py` |
| **`hp-wake-helper`**<br>`/usr/local/bin/hp-wake-helper`<br>守护配置：`/Library/LaunchDaemons/com.hp.alc285.ampinit.plist` (`KeepAlive`) | 现役源码：`hp-wake-helper.m` (`26,516` B, SHA256 `c215d14ead47f760eaa81e6cbd5c01ba2f022885928341f62cc8f15e7745b343`；初版：`hp-wake-helper.m` `10,582` B)<br>Plist：`com.hp.alc285.ampinit.plist` (`606` B, SHA256 `7d964e9e6d9d1c5ddc267f92a056d80c6c9b7eb9f0027360c4afeee403090503`) | `stage3-audio/usr-local-bin/hp-wake-helper`<br>`50,112` B<br>SHA256 `b592620b3ef2f816b006d0fa6414e206b142da5779ece3b82604b6bf12f7b491` | S0ix 睡眠/唤醒常驻守护进程：监听 `IORegisterForSystemPower` 与 `IODisplayWrangler`（忽略 `wps==3` halfdim，仅在真正 `wps <= 2` 灭屏时预存背光并遮黑），唤醒阶段配合内核 `ngreen-wake-plane-rgb-fix` 执行 `820 ms` `bklt=16/0` 背光保持、刷新 ColorSync/Gamma，并重初始化 `ALC285` B&O 功放、`TGLDmic` 与 `AirportItlwm` Wi-Fi（日志 `/var/log/hp-alc285-ampinit.log`） |
| **`hp-select-speaker`**<br>`/usr/local/bin/hp-select-speaker` | `hp-select-speaker.m`<br>`4,354` B<br>SHA256 `550b57c570c55983c19137ed02e72af80bf42db226224c72bd62ab4b4718c95c` | `stage3-audio/usr-local-bin/hp-select-speaker`<br>`27,360` B<br>SHA256 `7badbe2d61eeaccf632ac2a84a580ae7572bd9bf1b3319f656a2367c3e10849a` | 枚举 CoreAudio `'dev#'` 列表，匹配 UID 含 `"1F,3,0,1,3"` 的 `Built-in Speaker` 并将其设为系统默认输出（`'dOut'`）与系统音效输出（`'sOut'`） |
| **`hp-select-dmic.py`**<br>`/usr/local/bin/hp-select-dmic.py` | `hp-select-dmic.py`<br>`2,513` B<br>SHA256 `c636d9cf2ce4c33ada6493801722f6e3b385db2a22f40883ee9491982c330f22` | `stage3-audio/usr-local-bin/hp-select-dmic.py`<br>SHA256 `c636d9cf2ce4c33ada6493801722f6e3b385db2a22f40883ee9491982c330f22` | 检测 `ioreg` 中 `TGLDmic` 激活后，通过 `ctypes` 调用 `AudioObjectSetPropertyData` 将 `TGLDmic_InternalMic_UID`（`Internal Microphone (TGLDmic)`）设为系统默认输入设备（`'dIn '`） |
| **`libxedrv.dylib`**<br>`/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib` | `libxedrv.m`<br>`51,712` B<br>SHA256 `ea4b9ec3c14a902863c1ce41fc3a6e40c54eb350d747833ad702087a69429406` | 本地构建：`libxedrv.dylib` (`65,280` B, SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`)<br>安装套件同步版：`libxedrv.dylib` (`65,280` B, SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`) | 注入 `AppleIntelTGLGraphicsMTLDriver`（`16.0.32`）的 Metal ABI 适配层（`xedrv17`）：转换 Tahoe `MTLRenderPipelineDescriptorPrivate` 结构体偏移与 `misc` 位域，重写 `newTextureViewWithPixelFormat:` 避免 `RCS0` `fmt=123` Blit3D 挂死，配合内核 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16` 处理 `420v` 纹理视图，并在 `VTDecoderXPCService` 中安全返回 `nil` |
| **`xe-h264sw-fixd`**<br>`/usr/local/libexec/xe-h264sw-fixd`<br>守护配置：`/Library/LaunchDaemons/com.elitebook.h264swfix.plist` | `xe-h264sw-fixd.c`<br>`10,549` B<br>SHA256 `7c268fbb7b18a2f5bd5ba1b69bf7efcb89ad2f30b96d89f72a895d28efba2507`<br>Plist：`com.elitebook.h264swfix.plist` (`612` B, SHA256 `a94459225efeb6eed418475c6d16a2bb82be2ff913889fa16a47eb3c2973c9cf`) | `stage2-gpu/usr-local-libexec/xe-h264sw-fixd`<br>`24,496` B<br>SHA256 `4e388dfd1720d25e73d5701b4be0919cac190cca38ee03fc7ee9a7532048d5af`<br>`LC_UUID` `4C4C44B3-5555-3144-A1E7-A919CC286F49` | 监听 `VTDecoderXPCService` 进程并原地修复 macOS 26 `AppleH264SW` 软件解码路径的 `fill_frame_num_gap` 补帧异常（配合生产环境 `/Library/GPUBundles/` 故意省略实验性 `VADriver.bundle` / `VAME.bundle`，确保 H.264/HEVC 视频由软解 + `BCS0` `HP-BLITALIGN` 零绿屏零挂死渲染；日志 `/var/log/hp-xe-h264sw-fixd.log`） |
| **`hp-bt-compat-check.sh`**<br>`/usr/local/bin/hp-bt-compat-check.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.bt-compat-check.plist` | `hp-bt-compat-check.sh`<br>`2,647` B<br>SHA256 `2959d4b84802e12c6d2f23fd4bc41ae154c4429b799f475ab1bb425232ea09cb`<br>Plist：`com.hp.bt-compat-check.plist` (`614` B, SHA256 `156950587f27a14b52fb56dfcce88a7198607ff22fdebd103583acc47847f208`) | `stage3-bluetooth/usr-local-bin/hp-bt-compat-check.sh`<br>`2,647` B<br>SHA256 `2959d4b84802e12c6d2f23fd4bc41ae154c4429b799f475ab1bb425232ea09cb` | 开机检测剥离废弃 `--Compat` 参数并核验 Intel AX201 蓝牙（`8087:0026`，Firmware `v8787 c8787`）控制器在线状态；若检测到 `bluetoothd` 发生 APFS `decmpfs` 簇缺页崩溃循环则自动执行 `bootout` + `/usr/sbin/purge` + `bootstrap` 自愈（日志 `/var/log/hp-bt-compat-check.log`） |
| **`hp-syslogger.py` (`v1.1`)**<br>`/usr/local/bin/hp-syslogger.py`<br>守护配置：`/Library/LaunchDaemons/com.hp.syslogger.plist` + `/etc/newsyslog.d/com.hp.conf` | `hp-syslogger.py`<br>`13,043` B<br>SHA256 `9f22348437736568d9ca6906b2934e5358432200615fe4503729b851e2f89f59`<br>Plist：`com.hp.syslogger.plist` (`687` B, SHA256 `a9cdc00c697e9de435473f9798f203b6f4d719c6ba6332bc5d531003bc7f78f7`)<br>轮转配置：`com.hp.conf` (`673` B, SHA256 `147ee168926622c2f5567c99bd602c1a15dea4f55d47f59946af4f7fa87ba374`) | `stage3-logging/usr-local-bin/hp-syslogger.py`<br>`13,043` B<br>SHA256 `9f22348437736568d9ca6906b2934e5358432200615fe4503729b851e2f89f59` | 跨重启持久化日志与 `/usr/sbin/bluetoothd` 页锁定常驻守护进程：通过 `mmap` + `mlock` 锁定 `bluetoothd` ``0x0..0xab0000)` 防止 `BlueToolFixup.kext` 内存补丁页与 `decmpfs` 16KB 压缩簇部分逐出引发 `EBADMSG (error 94)` `SIGBUS`；按每次启动 UUID 在 `/var/log/hp/boot-<STAMP>-<UUID8>/`（`/var/log/hp/current` 软链，保留最近 15 次启动）持续归档 `dmesg`、`pmset`、Unified 错误流（过滤 `symptomsd` `"Out of range RSSI value"` 噪声并支持 `20 MiB` 单备份滚动轮转）、`STOP_EVENT.wait()` 零空闲唤醒轮询与 `SIGTERM` 关机快照 |
| **`va` (`AppleIntelTGLGraphicsVADriver.bundle` 归档补丁脚本)** *(生产环境不部署)* | 自包含安装脚本：[.local/driver-repair-20261103/vadriver-build/va` (`7,242` B, SHA256 `2f373a56d389a80ba4056d162dd15327c2baec225a740097f2c7ecc7d465e559`)<br>模块化补丁脚本集：`.local/clean-upstream-20261102/source/macos/vadriver/` (`build-vadriver.sh` `3,369` B, SHA256 `1e4ca0a8d0980670f6801c991a65440c02a50580655c8e4fee4745806482562f`)<br>回执：`deploy-receipt.json` | 原版未修补：`AppleIntelTGLGraphicsVADriver` (`8,450,544` B, SHA256 `d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129`)<br>补丁后未签名 SHA256：`b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0`<br>套件归档备查版：`AppleIntelTGLGraphicsVADriver` (`8,463,472` B, SHA256 `6291f574afa064ed2dd56f6787cd92bcf79750b16cc13ef6d07a49e599934dff`) | 对 Big Sur 11.4 原版 `AppleIntelTGLGraphicsVADriver`（`16.0.32`）应用 8 个机器码修补脚本的实验性归档产物；**注意：生产环境 `/Library/GPUBundles/` 仅部署 `AppleIntelTGLGraphicsMTLDriver.bundle` 与 `AppleIntelGraphicsShared.bundle` 2 个核心 Bundle（`install-stage2-gpu.sh` 会自动清理残留的 `VADriver.bundle` 与 `VAME.bundle`）**，由软解 + `xe-h264sw-fixd` + `HP-BLITALIGN` 保障全场景稳定播放 |
| **`RidgeKey` (`06cb:00f0` 指纹认证套件)**<br>`/usr/local/ridgekey/` & `/Applications/RidgeKey.app` | 源码仓库：`.local/peripheral-prep-20261105/RidgeKey-repo/` (HEAD commit `4968672`；预编译发行包 `BUILDINFO.txt` CI commit `dcd9e47`)<br>构建定义：`src/meson.build` (`3,215` B)、`app/Package.swift`、`scripts/build-app.sh`、`scripts/build-pkg.sh`、`scripts/install.sh`<br>防全擦除补丁：`patches/libfprint/` | 安装套件目录：`stage3-ridgekey/`<br>`ridgekeyd` (SHA256 `f20da2a091aef6d65feaa55b3501c246d364d9b54ff78e723b7a0a50201cc6f4`)<br>`ridgekeyctl` (SHA256 `6577e8d3260d24b30372cc66497d77ff112a8175fddfa82c64bdc0d5e8a5a4e3`) | 基于 `libfprint-2` 的用户态 Synaptics `06cb:00f0` Match-On-Chip 指纹守护进程（`ridgekeyd`）、CLI（`ridgekeyctl`）、`sudo` PAM 模块（`pam_ridgekey.so`）、锁屏代理（`RidgeKeyAgent.app`）、管理员授权插件（`RidgeKey.bundle`）与 SwiftUI 管理应用（`RidgeKey.app`） |

#### 2. 背光、热键、音频、软解守护与 Metal 垫片本地交叉编译命令（`nix develop`）

在 `/srv/mac-for-elitebook` 下，使用 `nix develop` 与 `$SDKROOT`（或本地桩库目录 `.local/driver-repair-20261103/brightness-fix-20261107/stubs/`）即可直接从 `.m`/`.c` 源码交叉编译并签名 `libhp_cb_shim.dylib`、`libxedrv.dylib`、`xe-h264sw-fixd`、`hp-wake-helper`、`hp-bridge` 与 `hp-select-speaker`（其中 `libhp_cb_shim.dylib` 与 `libxedrv.dylib` 产生与仓库预备产物 **逐字节完全一致** 的 SHA256，`xe-h264sw-fixd` 的 Mach-O 代码/数据段 `[0x0000..0x47b0)` 与 `LC_UUID` 逐字节完全一致）：

```sh
cd /srv/mac-for-elitebook
STUBS=".local/driver-repair-20261103/brightness-fix-20261107/stubs"

# 1. 编译并签名 corebrightnessd 动态注入库 libhp_cb_shim.dylib (hp-cb-shim.m)
# 精确复现 35,456 B 与 SHA256 e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798
nix develop -c bash -c "
  clang -target x86_64-apple-macos13.0 -O2 -fPIC -c \
    .local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim.m \
    -o /tmp/hp-cb-shim.o
  ld64.lld -dylib -arch x86_64 -platform_version macos 13.0 13.0 \
    -install_name /usr/local/lib/libhp_cb_shim.dylib \
    /tmp/hp-cb-shim.o \
    \"$STUBS/libSystem.tbd\" \"$STUBS/CoreFoundation.tbd\" \
    \"$STUBS/IOKit.tbd\" \"$STUBS/CoreDisplay.tbd\" \
    -o /tmp/libhp_cb_shim.dylib
  rcodesign sign /tmp/libhp_cb_shim.dylib
  sha256sum /tmp/libhp_cb_shim.dylib
  rm -f /tmp/hp-cb-shim.o /tmp/libhp_cb_shim.dylib
"

# 2. 交叉编译并签名 Metal ABI 适配层 libxedrv.dylib (libxedrv.m，必须使用 -fno-objc-arc)
# 精确复现 65,280 B 与 SHA256 312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2
nix develop -c bash -c '
  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -O2 -fPIC -fno-objc-arc -c \
    .local/driver-repair-20261103/vt-audio-fix-20261106/libxedrv.m \
    -o /tmp/libxedrv.o
  "$LD64_LLD" -dylib -arch x86_64 -platform_version macos 15.0 26.5 -syslibroot "$SDKROOT" \
    -install_name /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib \
    /tmp/libxedrv.o -lSystem -framework Foundation -framework CoreFoundation \
    -lobjc -framework Metal -framework IOSurface \
    -o /tmp/libxedrv.dylib
  rcodesign sign /tmp/libxedrv.dylib
  sha256sum /tmp/libxedrv.dylib
  rm -f /tmp/libxedrv.o /tmp/libxedrv.dylib
'

# 3. 交叉编译并签名 H.264 软解修复守护进程 xe-h264sw-fixd (xe-h264sw-fixd.c)
# 精确复现 24,496 B、Mach-O 主体 [0..0x47b0) 与 LC_UUID 4C4C44B3-5555-3144-A1E7-A919CC286F49
nix develop -c bash -c '
  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -fuse-ld=lld --ld-path="$LD64_LLD" -O2 \
    .local/driver-repair-20261103/s0ix-standby-prep-20261107/live-846ba6e6/xe-h264sw-fixd.c \
    -o /tmp/xe-h264sw-fixd
  rcodesign sign /tmp/xe-h264sw-fixd
  rm -f /tmp/xe-h264sw-fixd
'

# 4. 交叉编译并签名现役睡眠/唤醒与背光/音频守护进程 hp-wake-helper 及热键桥接守护进程 hp-bridge
nix develop -c bash -c '
  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -fuse-ld=lld --ld-path="$(which ld64.lld)" -O2 -fobjc-arc \
    -framework Foundation -framework CoreWLAN -framework CoreAudio \
    -framework CoreGraphics -framework IOKit -framework CoreFoundation \
    .local/driver-repair-20261103/s0ix-standby-prep-20261107/live-846ba6e6/hp-wake-helper.m \
    -o /tmp/hp-wake-helper
  rcodesign sign /tmp/hp-wake-helper

  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -fuse-ld=lld --ld-path="$(which ld64.lld)" -O2 -fobjc-arc \
    -F"$SDKROOT/System/Library/PrivateFrameworks" \
    -framework Cocoa -framework Carbon -framework CoreAudio -framework CoreFoundation \
    -framework CoreGraphics -framework IOKit -framework DisplayServices \
    -framework CoreDisplay -framework AppKit -framework Foundation \
    .local/driver-repair-20261103/s0ix-standby-prep-20261107/live-846ba6e6/hp-bridge.m \
    -o /tmp/hp-bridge
  rcodesign sign /tmp/hp-bridge
  rm -f /tmp/hp-wake-helper /tmp/hp-bridge
'

# 5. 编译并签名扬声器默认输出切换工具 hp-select-speaker (hp-select-speaker.m)
nix develop -c bash -c "
  clang -target x86_64-apple-macos13.0 -O2 -c \
    .local/driver-repair-20261103/audio-ridgekey-fix-20261107/hp-select-speaker.m \
    -o /tmp/hp-select-speaker.o
  ld64.lld -arch x86_64 -platform_version macos 13.0 26.5 \
    /tmp/hp-select-speaker.o \
    \"$STUBS/CoreAudio.tbd\" \"$STUBS/CoreFoundation.tbd\" \"$STUBS/libSystem.tbd\" \
    -o /tmp/hp-select-speaker
  rcodesign sign /tmp/hp-select-speaker
  rm -f /tmp/hp-select-speaker.o /tmp/hp-select-speaker
"
```

> [!TIP] **在目标机 macOS 原生编译等价命令**
> 若在目标机 macOS 终端（已安装 Xcode Command Line Tools）直接编译上述工具，可使用系统框架直接编译签名：
> ```sh
> clang -dynamiclib -O2 -arch x86_64 -mmacosx-version-min=13.0 \
>   -install_name /usr/local/lib/libhp_cb_shim.dylib \
>   -framework CoreFoundation -framework IOKit -F/System/Library/Frameworks -framework CoreDisplay \
>   hp-cb-shim.m -o libhp_cb_shim.dylib && codesign -f -s - libhp_cb_shim.dylib
>
> clang -O2 -fobjc-arc -arch x86_64 \
>   -framework Foundation -framework CoreWLAN -framework CoreAudio \
>   -framework CoreGraphics -framework IOKit -framework CoreFoundation \
>   hp-wake-helper.m -o hp-wake-helper && codesign -f -s - hp-wake-helper
>
> clang -O2 -fobjc-arc -arch x86_64 \
>   -framework Cocoa -framework Carbon -framework CoreAudio -framework CoreFoundation \
>   -framework CoreGraphics -framework IOKit -F/System/Library/PrivateFrameworks \
>   -framework CoreDisplay -framework DisplayServices \
>   hp-bridge.m -o hp-bridge && codesign -f -s - hp-bridge
>
> clang -O2 -arch x86_64 xe-h264sw-fixd.c -o xe-h264sw-fixd && codesign -f -s - xe-h264sw-fixd
>
> clang -O2 -arch x86_64 -mmacosx-version-min=13.0 \
>   -framework CoreAudio -framework CoreFoundation \
>   hp-select-speaker.m -o hp-select-speaker && codesign -f -s - hp-select-speaker
>
> clang -dynamiclib -O2 -fno-objc-arc -arch x86_64 -mmacosx-version-min=15.0 \
>   -install_name /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib \
>   -framework Foundation -framework CoreFoundation -framework Metal -framework IOSurface \
>   libxedrv.m -o libxedrv.dylib && codesign -f -s - libxedrv.dylib
> ```

#### 3. `AppleIntelTGLGraphicsVADriver.bundle` 8 个模块化修补脚本与自包含脚本（`va`，归档备查）技术明细

> [!NOTE] **生产环境说明**
> 在 macOS Tahoe `26.6.2` (`25G83`) 生产环境中，`/Library/GPUBundles/` **不安装** `AppleIntelTGLGraphicsVADriver.bundle` 与 `AppleIntelTGLGraphicsVAME.bundle`（由 `install-stage2-gpu.sh` 自动移除残留），使 VideoToolbox 稳定走软件解码 + `/usr/local/libexec/xe-h264sw-fixd` + 内核 `HP-BLITALIGN` 2D 拷贝路径。以下 8 个机器码修补脚本及归档产物保留在仓库与安装套件目录中供硬件解码研究备查。

上游模块化补丁脚本集位于 `.local/clean-upstream-20261102/source/macos/vadriver/`（主控构建脚本 `build-vadriver.sh`，`3,369` B，SHA256 `1e4ca0a8d0980670f6801c991a65440c02a50580655c8e4fee4745806482562f`），而 `.local/driver-repair-20261103/vadriver-build/va`（`7,242` B，SHA256 `2f373a56d389a80ba4056d162dd15327c2baec225a740097f2c7ecc7d465e559`）将这 **8 个 Python 机器码修补阶段**合并为单文件自包含脚本。对 Big Sur 11.4 移植版原版 `AppleIntelTGLGraphicsVADriver`（`8,450,544` B，未修补 SHA256 `d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129`）依次执行以下 8 项修补后，确定性产出未签名 SHA256 `b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0`（本地 `codesign` 签名版 SHA256 `cb82639fb7b6af838d36e70a7bfc83bb9cc17ae87cf56e15752594c1104c659b`）：

1. **`patch-vadriver.py`**（`1,832` B，SHA256 `1f7736935da713295aafd1a47046f0e0c9b53524103bbea37413de2ccb5020f2`）：
   - `0x130aa` (`CreateDriverContext` 清理分支)：`e8 e3 d0 4d 00` -> `90 90 90 90 90`（NOP 掉清理分支中因 Tahoe 结构体布局变化导致崩溃的 `vtable+0x30` 调用）；
   - `0x13172` (`CreateContext` 版本号检查)：`0f 85 17 01 00 00` -> `90 90 90 90 90 90`（移除 `ctx+0x8 == 0x201` 版本强校验，兼容 Tahoe AppleGVA 传入的 `0x202`）；
   - `0x15456` (`CodecHalDecodeCreate` 分配失败检查)：`74 61` -> `90 90`（当 `0x2b8` 处为空时继续执行而非直接中止）；
   - `0x1545c` (`CodecHalDecodeCreate` 返回值覆写)：`e8 e9 4e 4b 00 41 89 c6` -> `31 f6 90 90 90 90 90 90`（强制 `r14d = 0` 返回成功）；
   - `0x1623c` (`DestroyContext`)：`48 8b 07 ff 50 20` -> `90 90 90 90 90 90`（当 Decoder 对象为空时跳过 `vtable+0x20` 析构调用）。
2. **`patch_nodes.py`**（`2,784` B，SHA256 `1082da6644052bf3616dc9d964a508da03c7605e9a2c039f14b4d0edeaf22f4f`）：
   - `0x24361f` & `0x24364f`：将两处 `80 7c 08 58 00`（检查 88B 步长的 `[rax+rcx+0x58]` 字节）修补为 `80 3c 08 00 90`（检查 `[rax+rcx+0x00]` 处的 surface node ID），并配合后续步长修补适配 Tahoe AppleGVA 的 80B Surface Node。
3. **`patch_nodelayout.py`**（`9,138` B，SHA256 `34a99cd183039dfd4fe33001902e0ea6aeacca1b4643501ed56c35abe262e612`）：
   - `0x2bbe7`：将 `add rcx, 0x58`（88B 步长）改为 `add rcx, 0x50`（80B 步长）；
   - `0x2bc7e .. 0x2be1b`：在 `GetSurfaceInfo` 中重写 11 处 `imul reg, reg, 0x58` 为 `0x50`，并将旧 88B Node 偏移 `+0x1a`/`+0x18`/`+0x08` 重映射至 Tahoe 80B Node 的 `+0x08` (width) / `+0x0a` (height) / `+0x10` (bo_ptr)。
4. **`patch_payloadhdr.py`**（`1,419` B，SHA256 `680fa20e0d6be7b63eb2b18e4e5682c35695913f063ac2c8a67c302ad57c8d0b`）：
   - 在 `__TEXT` 头部空洞写入三段跳板机器码：`0x0d00`（`GetSurfaceInfo` 入口转换器：将 Tahoe 88B 新式 Node 头部 `hdr == 0x00010002` 原地转换为 Big Sur 驱动期望的字段布局）、`0x0b00`（`os_resource` 对象填充器）、`0x1100`（`gmm_res_info` 伪对象构造器，使 `[gmm+0x120]` 返回 TileY `1`、vtable 槽位返回有效对齐与尺寸），并将 `0x2bb2a` 重定向至 `0x0d00`。
5. **`patch_pitchdelta.py`**（`2,414` B，SHA256 `35bdcbf2c2266a96ff020fc2b3fe9de99edc8db9e9b93ba2d27370dc73a75c2d`）：
   - 在 `0x0e00` 注入 `SendSurfaceState` 循环前置修正跳板（当 `os_res+0x28` 的 pitch/height/Y-offset 为 `0` 时，从 `frame_desc` 动态回填对齐后的 pitch、height 及 UV 平面偏移 `aligned_h`），并将 `0x6453c` 跳转至 `0x0e00`、在 `0x64a15` 将 `lea r8, [r15+rax*8]` 修补为 `mov r8, r15; nop`。
6. **`patch_spsshift.py`**（`1,729` B，SHA256 `e6f1f7950d9ac10f1c60397a56301f650527d7d7dac9da27055359a691f3b92a`）：
   - 修复 Tahoe AppleGVA HEVC SPS 参数缓冲区偏移右移 `+4` 字节的 ABI 差异：在 `0x228e3f` 注入 `add r12, 4`（跳转至 `0x0f00` 跳板并在 `0x193543` 挂载），并在 `0x229740`（PicWidth/PicHeight 读取）与 `0x229655`（ChromaFormat 读取）同步修正 `+4` 偏移。
7. **`patch_hcpsurface.py`**（`2,202` B，SHA256 `7f6dc846ad86a73c0c375824084e6545c74674e0e12b3a906bc1f0f392ca0491`）：
   - 在 `0x0f00` 写入 `AddHcpSurfaceCmd` 跳板（当 `[rcx+0x10]` 处的 `YPlaneOffset.iYOffset == 0` 时，自动从 `params+0x08` 读取 `recon_surface` 的高度补齐 UV 偏移，防止 `HCP_SURFACE_STATE` DW2 全零导致色度平面与亮度平面重叠绿屏）。
8. **`patch_hevclastslice.py`**（`2,704` B，SHA256 `761f298ba1bd634bc1e97b4e2ac1a6d508c6d32902036df4659bf3201444fc10`）：
   - 在 `0x13fee0` 拦截 `IsHevcLastSlice` 判定并跳往 `0x0f40` 跳板（强制 `al = 1`，解决 Tahoe AppleGVA 单 Slice 帧缓冲缩减 4 字节导致 `[r8+0x73]` 恒为 `0`、从不写入 `HCP_BSD_OBJECT` 进而引发 `VDBOX` 解码超时的问题）。

在本地开发机从原版二进制重现上述 8 步修补并验证未签名 SHA256 的命令如下：

```sh
cd /srv/mac-for-elitebook
cp .local/clean-upstream-20261102/build/install-stage/sle/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver /tmp/va_repro
for s in patch-vadriver.py patch_nodes.py patch_nodelayout.py patch_payloadhdr.py patch_pitchdelta.py patch_spsshift.py patch_hcpsurface.py patch_hevclastslice.py; do
  python3 ".local/clean-upstream-20261102/source/macos/vadriver/$s" /tmp/va_repro
done
sha256sum /tmp/va_repro
# 输出: b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0  /tmp/va_repro
rm -f /tmp/va_repro
```

#### 4. `RidgeKey` (`06cb:00f0`) 源码结构与构建命令

- **源码树**：`.local/peripheral-prep-20261105/RidgeKey-repo/`（上游 `labrouss/RidgeKey` `v1.0.0`，本地仓库 HEAD commit `4968672`；安装套件预编译产物见 `BUILDINFO.txt`，对应上游 CI commit `dcd9e47`）：
  - **C 守护进程与安全插件（Meson 构建系统，`src/meson.build`）**：
    - `ridgekeyd` 根守护进程：`src/daemon/ridgekeyd.c`、`store.c`、`secret.c`、`console.c`、`peer.c`、`prompt.c`、`actions.c`（依赖 `libfprint-2`、`glib-2.0`、`gio-2.0`）；
    - `ridgekeyctl` 命令行客户端：`src/ctl/ridgekeyctl.c`（仅依赖 macOS 系统 SDK XPC + `libdispatch`）；
    - `pam_ridgekey.so`（`sudo` PAM 模块）：`src/pam/pam_ridgekey.c`（依赖 `libpam` + `CoreFoundation`）；
    - `ridgekey-agent`（`RidgeKeyAgent.app` 锁屏解锁代理）：`src/agent/ridgekey-agent.c`（依赖 `CoreFoundation`、`CoreGraphics`、`Security`、`ApplicationServices`、`Carbon`、`HIToolbox`、`SkyLight`）；
    - `RidgeKey.bundle`（`authorizationhost` 管理员弹窗插件）：`src/authplugin/ridgekey-authplugin.c`（依赖 `Security`、`CoreFoundation`）。
  - **SwiftUI 设置应用（`RidgeKey.app`）**：`app/Package.swift` 与 `scripts/build-app.sh`。
  - **`libfprint` 安全补丁**：`patches/libfprint/`（移除全传感器擦除指令，保护同芯片存储的 Windows Hello 与 BIOS 指纹）。
- **本地 Linux 开发机交叉编译仅依赖 macOS 系统框架的 4 个核心组件（`ridgekeyctl`、`pam_ridgekey.so`、`ridgekey-agent`、`RidgeKey.so`）**：
  ```sh
  cd /srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo
  nix develop /srv/mac-for-elitebook -c bash -c '
    mkdir -p /tmp/rk-build
    CFLAGS="-target x86_64-apple-macos13.0 -isysroot $SDKROOT -O2 -Wall -Wextra -std=c11 -Isrc/common"

    # 1. ridgekeyctl
    "$CLANG_APPLE" $CFLAGS -c src/ctl/ridgekeyctl.c -o /tmp/rk-build/ridgekeyctl.o
    "$LD64_LLD" -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      /tmp/rk-build/ridgekeyctl.o -lSystem -o /tmp/rk-build/ridgekeyctl

    # 2. pam_ridgekey.so
    "$CLANG_APPLE" $CFLAGS -fPIC -c src/pam/pam_ridgekey.c -o /tmp/rk-build/pam_ridgekey.o
    "$LD64_LLD" -dylib -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      /tmp/rk-build/pam_ridgekey.o -lpam.2 -framework CoreFoundation -lSystem -o /tmp/rk-build/pam_ridgekey.so

    # 3. ridgekey-agent
    "$CLANG_APPLE" $CFLAGS -Wno-deprecated-declarations -c src/agent/ridgekey-agent.c -o /tmp/rk-build/ridgekey-agent.o
    "$LD64_LLD" -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      -F"$SDKROOT/System/Library/PrivateFrameworks" \
      -F"$SDKROOT/System/Library/Frameworks/Carbon.framework/Frameworks" \
      /tmp/rk-build/ridgekey-agent.o -framework CoreFoundation -framework CoreGraphics \
      -framework Security -framework ApplicationServices -framework Carbon -framework HIToolbox \
      -framework SkyLight -lSystem \
      -o /tmp/rk-build/ridgekey-agent

    # 4. RidgeKey.so (RidgeKey.bundle/Contents/MacOS/RidgeKey)
    "$CLANG_APPLE" $CFLAGS -fPIC -c src/authplugin/ridgekey-authplugin.c -o /tmp/rk-build/ridgekey-authplugin.o
    "$LD64_LLD" -bundle -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      /tmp/rk-build/ridgekey-authplugin.o -framework Security -framework CoreFoundation -lSystem \
      -o /tmp/rk-build/RidgeKey.so

    rm -rf /tmp/rk-build
  '
  ```
- **在目标机 macOS 环境完整编译全部组件（含依赖 Homebrew `libfprint-2` / `glib-2.0` 的 `ridgekeyd` 与 SwiftUI `RidgeKey.app`）**：
  ```sh
  cd /srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo
  # 1. 编译 ridgekeyd, ridgekeyctl, pam_ridgekey.so, ridgekey-agent, RidgeKey.so
  meson setup build src --buildtype=debugoptimized
  meson compile -C build

  # 2. 编译 SwiftUI 设置应用 RidgeKey.app 并打包 .pkg 安装器
  bash scripts/build-app.sh
  ```

---

### 8.15 一键后置安装套件与急救恢复镜像组装校验 (Post-Install Bundle & Recovery Image Assembly)

完成上述自定义组件重编译后，可将其同步封装至一键后置安装套件 `HP-Tahoe-PostInstall-20261108.tar.gz` 及 Ventoy 急救恢复镜像 `HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`：

| 归档 / 镜像产物 | 本地归档路径与内置预置路径 | 精确字节数与 SHA256 校验值 |
| --- | --- | --- |
| **`HP-Tahoe-PostInstall-20261108.tar.gz`** | 本地：`.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108.tar.gz`<br>内置盘预置：`/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`（NixOS `/mnt/win_sys/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`，待下次开机进入 NixOS 时同步最新归档） | `125,569,879` B（约 `120 MB`），SHA256 `2f22d03e886773194337281491433b22ea87af1395b26d5e54eb8289020177aa` |
| **`SHA256SUMS.txt`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/SHA256SUMS.txt` | `64,420` B（`431` 个打包文件），SHA256 `65ff4c05fd4f90f0895deed5de3068bd5db62f069318c7ab13b23e4427a5e8e6` |
| **`bundle-receipt.json`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/bundle-receipt.json` | `5,310` B，SHA256 `68491a70c925c3e1b1ede2b078c6236a1b72b02e5a3eba7c0eb37417d9212a2e` |
| **`verify-postinstall.sh` / `verify-phase10-lidwake-and-video.sh` / `test_420v_blitalign`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/` | `verify-postinstall.sh`：`8,852` B，SHA256 `499ac36510ffa2c67bf492330377dc7577dc719853fe8280a94ed00e19319387`<br>`verify-phase10-lidwake-and-video.sh`：`7,639` B，SHA256 `eeebfac56d8e79b59fc42db33e3672112d9eeb8bf136148018ac5024762ea218`<br>`test_420v_blitalign`：`51,680` B，SHA256 `887743ebd0b11797fa46553fa2420df21adf266c76ce6d0d540ac51e415e75bf` |
| **`HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`（FAT32 偏移 `@@1048576`） | `1,343,225,856` B（`1.25 GiB`），SHA256 `4ab8aff3a2f65cfc126faf19c9334798ef623a8dfbbe534ec78ede7f968850c9` |
| **`after-lidwake-greenfix-boot-oc.tar`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/post-wake-ebaba2ee/after-lidwake-greenfix-boot-oc.tar`（内置盘 `disk0s1` `/EFI/OC` 回读归档） | `41,838,592` B，SHA256 `a2fe4a561a09dee92baa64558d9a0883cd099f6de765a7d9dee321182237ded2` |
| **`scripts/verify_release_artifacts.py` & `Makefile` (`verify-release`)** | [`scripts/verify_release_artifacts.py`](../scripts/verify_release_artifacts.py)<br>[`Makefile`](../Makefile) | `scripts/verify_release_artifacts.py`：`110,025` B，SHA256 `d66a58b9245f8e03b2a05cc9d2c721828a951b350113e6b34357285aa55ff161`<br>`Makefile`：`2,019` B，SHA256 `8c9cb233f61f5b7265dd83a7dee74ab88c24d9ba395ac85d0c8da22a5d443157` |

- **使用 `nix develop` (`mtools`) 更新急救恢复镜像并回读校验命令**：
  ```sh
  nix develop /srv/mac-for-elitebook -c bash -c '
    IMG="/srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img"
    PART="${IMG}@@1048576"
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.aml ::/EFI/OC/ACPI/SSDT-DEEPIDLE.aml
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/MacOS/NootedGreen ::/EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/Info.plist ::/EFI/OC/Kexts/NootedGreen.kext/Contents/Info.plist
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext/Contents/MacOS/S0ixStandby ::/EFI/OC/Kexts/S0ixStandby.kext/Contents/MacOS/S0ixStandby
    sha256sum "$IMG"
  '
  ```
- **使用 `nix develop -c make verify-release` 执行全仓库端到端发布产物、`9/9` 源码净室重编译与在线 NixOS 实机一致性校验**：
  ```sh
  # 1. 本地全量校验（核心产物 SHA256 + 跨清单一致性、431 文件安装套件与压缩包、112 文件 OpenCore EFI 与恢复镜像、二进制/AML/补丁特征标记、9/9 项源码净室重编译）
  nix develop -c env PYTHONDONTWRITEBYTECODE=1 make verify-release

  # 2. 连同源码净室重编译与在线 NixOS 实机只读核验 /boot/EFI/OC（111 文件 + 5 项关键产物）并生成 JSON 报告
  nix develop -c env PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_release_artifacts.py \
    --check-source-rebuilds \
    --check-live-nixos <user>@<nixos-host> \
    --json-out .local/driver-repair-20261103/s0ix-standby-prep-20261107/post-wake-ebaba2ee/release-verification-report.json
  ```
