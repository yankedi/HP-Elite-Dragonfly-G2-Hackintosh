# 外设适配现状分析（2026-11-04）

## 范围与证据口径

- 对象：HP Elite Dragonfly G2（board `8716`，i5-1135G7），macOS 26.6.2 / 25G83。
- 主要运行态证据：R28 完整 macOS 启动 `E439D465-83D0-416F-AAC1-E24FCFFA7E1C`，日志目录
  `.local/driver-repair-20261103/repair28-mmio-only/trial-r28/run/`；GA419 用户实测反馈；
  PCH RHUB 启动的 USB 恢复证据。
- 本文的“适配”指 **macOS 下有驱动且对应功能实际可用**。设备枚举、kext 加载或
  IORegistry 节点存在，都不等于功能通过。
- 本文只分析已有日志和本地证据；未连接 EliteBook，未写 USB，未改 EFI/驱动。

## 结论

目前真正还没有适配的，核心是 5 项：

1. **内置音频**：扬声器、耳机、内置麦克风/DMIC 都没有 macOS 驱动链；蓝牙音频和 USB 音频可用。
   最新调研发现 **SimpleHDA 1.0.0 + AppleALC 1.9.8** 是当前最好的现成方案，但无 HP 8716 专用 layout。
2. **亮度调节**：`AppleBacklightDisplay` 和 `BrightnessKeys` 已加载，但没有实际 PWM/背光控制。
   最新调研发现 **NP550XDA NootedGreen fork 的 `-ngreenblr`** 已有 real TGL 可用实现，需集成到 R28 基线。
3. **指纹**：Synaptics `06cb:00f0` 能枚举，但没有原生驱动；macOS Touch ID 绑定 Apple SEP，原生不可行。
   但 **RidgeKey 1.0.0** 提供了非 SEP 的用户态指纹解锁/`sudo` 替代，值得试用。
4. **ISH 传感器**：ALS、加速度计、陀螺仪、hinge、自动旋转、自动亮度都没有驱动。
   唯一参考 **IntelISH** 只支持 Skylake `8086:9d35`，不是 Tiger Lake `a0fc`。
5. **Thunderbolt 4 / USB4**：NHI `8086:9a1b` 没有 Apple Thunderbolt 驱动匹配，雷电扩展坞/显示器/SSD 不可用。

其余主要外设——Wi-Fi、蓝牙、电池、RGB 摄像头、触控板、键盘、NVMe、PCH USB——已有运行态证据，
其中多项有用户实测确认。触屏、笔、JIS 键盘、睡眠唤醒和无线高级功能仍需单独验证。
详细的现有驱动/补丁、版本和 URL 见 [`peripheral-driver-research-20261104.md`](peripheral-driver-research-20261104.md)。

## 已适配且可用

| 设备/功能 | 当前证据 | 边界 |
|---|---|---|
| Wi-Fi AX201 | `AirportItlwm 2.4.0` 已加载，`en0` up，SSH 可用 | 仅证明联网；AirDrop/AWDL/Handoff 未验证 |
| 蓝牙 | `IntelBluetoothFirmware 2.5.2` + `BlueToolFixup 2.7.2`；固件下载成功；用户确认蓝牙音频双向可用 | 配对/唤醒/高级配置文件未逐一验证 |
| 电池 | `SMCBatteryManager` + `ECEnabler`；`AppleSmartBattery` 已注册并轮询；用户确认能看到电池 | 充电阈值、续航估算、睡眠唤醒未验证 |
| RGB 摄像头 | `HP HD Camera 0408:5349` 枚举；`UVCService`/`UVCAssistant` 绑定；用户确认相机可用 | IR 接口另列；UVC 控制端点曾出现 pipe stalled |
| 触控板 | `SYNA30B6` / `06cb:cd74`；`VoodooI2C 2.9.1` + `VoodooI2CHID`；R28 中断模式为 **GPIO**；用户确认指针可移动 | 手势、力度触控/震动反馈未逐一验证 |
| 键盘 | PS/2；`VoodooPS2Controller`/`PS2Keyboard` 已加载；用户已用 Terminal 输入 | JIS 实体键位与 macOS 映射未验证 |
| NVMe | Micron 2210 `MTFDHBA512QFD`；`IONVMeFamily`；`disk0` | 睡眠/错误恢复/长期写入未验证 |
| PCH USB | RHUB 补丁后 12 个 USB2 + 3 个 USB3 端口；Lexar、摄像头、蓝牙、指纹、外接鼠标均枚举；外接 USB 鼠标实测 47287 次输入报告 | 15/16 端口上限；TXHC/雷电控制器仍 0 端口 |

## 仍未适配/未解决

| 优先级 | 项目 | 日志证据 | 可行性与说明 |
|---|---|---|---|
| P0 | **内置音频**：扬声器、耳机、内置麦克风 | R28 `kextstat` 中 `AppleHDA`/`AppleALC`/`VoodooHDA` 均为 0；`ioreg` 只有 `HDAS@1F,3` 这个 `IOPCIDevice`，没有 `AppleHDAController`/`IOAudioEngine` 子节点；GA419 用户实测内置声音无、内置麦克风失败 | 现成方案 **SimpleHDA 1.0.0 + AppleALC 1.9.8**（OpenCore 注入 AppleHDA，不需要 KDK/root patch）；无 HP `103c:8716` 专用 layout，最接近 layout 71。HP 功放初始化是 Linux 的 `msleep(100); coef 0x65=0`，未移植。内置 DMIC 是 SOF 路径，SimpleHDA 不解决；蓝牙/USB 音频是替代 |
| P0 | **亮度调节** | R28 `AppleBacklightDisplay` 有 `bklt` 参数（value=65535），`BrightnessKeys` 和 `AppleBacklight` 已加载；dmesg 有 `AGDCBacklightControl: Didn't find DPMicro.` 和 `EFI using a different backlight frequency`；GA419 用户实测不能调亮度 | 现成实现：**NP550XDA NootedGreen fork 的 `-ngreenblr`**（real TGL 已工作）+ `-ngreenbldiag` 测 `ngreenblmax`；当前 R28 的 XE-BLR 被 `-ngreenxefix` 门控，HP GA47 又在 real TGL 禁用 xefix，所以需把该拆分补丁集成到 R28 基线。不是新驱动 |
| P1 | **指纹** | R28 `IOUSBHostDevice@14700000` = `06cb:00f0`，无子驱动；dmesg `ACMT... Biometric driver not detected.` | 原生 Touch ID 依赖 Apple SEP，第三方 USB 指纹没有原生驱动；但 **RidgeKey 1.0.0**（2026-10-31）已明确支持 `06cb:00f0`，在 HP EliteBook 840 G8 + Tahoe 实测锁屏/`sudo`/管理员对话框。不是 Touch ID，未签名 pkg，登录密码存 System keychain；Dragonfly G2 需实测 |
| P1 | **ISH 传感器**：ALS、加速度、陀螺、hinge、自动旋转、自动亮度 | `ISHD@12` / `8086:a0fc` 存在；`Apple16X50PCI` dext 两次 `start(ISHD) fail`；`IOPlatformSensor` 计数 0；无传感器子节点 | 没有已知 macOS PC ISH 驱动；自动旋转/自动亮度基本不可用。可关注 `VoodooI2CSensorHub` 或 SMC ALS 方案，但当前无实现 |
| P2 | **Thunderbolt 4 / USB4** | `TDM0@D,2` / `8086:9a1b` 存在，但 `AppleThunderbolt` 未加载；`TRP0/TRP1` 只有 PCIe bridge；TXHC 0 端口 | Apple 原生 plist 不匹配 `9a1b`；即使强行匹配，TB4/USB4 隧道也未验证；低可行性 |
| P2 | **CPU 温度/风扇/SMC 传感器读数** | 只有 `VirtualSMC` + `SMCBatteryManager`；无 `SMCProcessor`/`SMCSuperIO`；`powermetrics --samplers smc` 返回 `Invalid key` | 可尝试补 `SMCProcessor`/`SMCSuperIO`，但 HP EC 兼容性未验证；风扇本身由 EC 固件控制，不等于停转 |
| P2 | **触屏笔压感/倾斜** | `VoodooI2CTouchscreenHIDEventDriver` 已实例化；`VoodooI2CStylusHIDEventDriver` 未实例化；`VoodooI2CDigitiserStylus` 计数 1 | 基本触摸可能可用；笔压感/倾斜没有事件驱动。可研究 VoodooI2C stylus 匹配，但未验证 |
| P3 | **IR 摄像头/面容解锁** | `HP IR Camera@2` UVC 接口存在，`UVCAssistant` 绑定 | macOS 没有 Windows Hello 对应功能；IR 视频节点或可被第三方应用读取，但面容解锁不可行 |
| P3 | **键盘背光** | 没有专门驱动；未做实际按键/背光测试 | 可能由 EC/WMI 控制；低优先级，未验证 |
| P3 | **HDMI/外接显示** | R28 `display.txt` 只有内屏；未做 HDMI 实测 | 受当前 GPU hang/图形栈影响，需单独测试；不是独立外设驱动缺口 |

## 部分适配/待验证

| 项目 | 已确认 | 尚未确认 |
|---|---|---|
| 触屏 | `WACF4233` / `056a:4924`；`VoodooI2CTouchscreenHIDEventDriver` 已加载；APIC 模式 | 用户“触控有了”是否专指触屏不明确；多点触控、掌拒、边缘手势未逐一验证 |
| 触控板手势 | 指针移动可用；GPIO 中断 | 三指/四指手势、力度触控、震动反馈、睡眠唤醒 |
| JIS 键盘 | PS/2 键盘可用 | JIS 实体键位、修饰键、输入法切换与 macOS 布局映射 |
| Wi-Fi 高级功能 | 联网、SSH 可用 | AirDrop/AWDL、Handoff、Continuity、WPA3-only、mandatory PMF、睡眠恢复 |
| 蓝牙高级功能 | 蓝牙音频双向可用 | AirDrop/Continuity、BLE HID、唤醒、配对稳定性 |
| 睡眠/唤醒/合盖 | 未测试 | 睡眠、唤醒、合盖、显示器休眠与恢复 |
| USB 端口映射 | PCH 15 个端口已建，已知设备可用 | 第 16 个端口未建；TXHC/雷电口 0 端口；具体 USB-C 口的功能未逐一确认 |

## USB 当前状态（只读）

- 挂载点：`/run/media/yan/Yan`，exFAT，117G，已用约 44G，可用约 73G。
- 现有相关文件：
  - `ISO/linux/HP-Tahoe-Recovery-GA410-CSR0.img`（恢复镜像）
  - `ISO/linux/Tahoe-26.6.2-Offline-App.hfs`（离线安装 App）
  - Linux/Windows 安装 ISO、`GA410-Recovery/` 等
- `ISO/HP-Tahoe-GA419-Bluetooth-Peripherals.img.sha256` 仍在，但 **对应 `.img` 不在 U 盘上**，
  只剩校验文件。
- U 盘上 **没有** 音频、指纹、ISH 传感器、Thunderbolt 的 kext/驱动包；当前 R28 镜像也不在 U 盘上。
- 当前 R28 镜像本身已包含已知外设 kext（`AirportItlwm`、`IntelBluetoothFirmware`、
  `BlueToolFixup`、`SMCBatteryManager`、`ECEnabler`、`BrightnessKeys`、`VoodooI2C` 系列、
  `XHCI-unsupported` 等），所以“已适配”的部分不需要再补包；缺的是上表 P0–P3 的新驱动/补丁。

## 建议的下一步（尚未执行）

1. **音频**：先确认是否接受 OCLP Tahoe modern audio 补丁这种系统级改动；若接受，再核对
   AppleHDA 版本、AppleALC layout 与 ALC285 `103c:8716` 功放 GPIO。内置 DMIC 单独评估。
2. **亮度**：在不动 GPU 稳定性的前提下，单独做一次只读/可回滚的背光参数实验；先确认
   `bklt` 写入是否到达硬件，再决定 WhateverGreen/PNLF/NootedGreen 路线。
3. **指纹/IR 面容**：按“基本不可行”处理，不占用主线时间。
4. **ISH 传感器/雷电**：保持低优先级；除非有明确的外设需求，否则不建议先投入。
5. **触屏笔/JIS/睡眠**：作为功能验收项逐项测试，不要和 GPU hang 混为一谈。

## 相关记录

- 现有驱动/补丁调研（版本、URL、测试方案）：[`peripheral-driver-research-20261104.md`](peripheral-driver-research-20261104.md)
- 历史外设证据与来源核查：[`peripherals.md`](peripherals.md)
- Recovery 输入适配：[`input-recovery.md`](input-recovery.md)
- 硬件清单与接口：[`hardware.md`](hardware.md)
- 路线图：[`roadmap.md`](roadmap.md)
