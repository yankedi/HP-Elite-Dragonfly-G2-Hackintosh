# 外设驱动/适配调研（2026-11-04）

## 范围与方法

- 目标机：HP Elite Dragonfly G2，i5-1135G7，macOS 26.6.2 / 25G83；当前完整日志为 R28
  启动 `E439D465-83D0-416F-AAC1-E24FCFFA7E1C`。
- 原则：**优先寻找已有的驱动、补丁、fork 或用户态工具**；不自行编写新驱动。
- 检索：GitHub 仓库/Release/Issue、上游源码、Dortania、InsanelyMac、Reddit、Olarila、
  中文论坛索引；并用 Perplexity Pro 的 GPT-5.6 Terra / Gemini 3.1 Pro 做交叉检索。
- 本文只写调研结果和待验证方案；**未连接 EliteBook、未写 USB、未改 EFI/驱动**。
- 删除临时文件将使用 `trash`，不使用 `rm`（按用户要求）。

## 结论速览

| 项目 | 最佳现有方案 | 是否可直接用 | 关键限制 |
|---|---|---|---|
| 内置音频（扬声器/耳机） | **SimpleHDA 1.0.0 + AppleALC 1.9.8** | 机制可用，**无 HP 8716 专用 layout** | 需逐个测试 ALC285 layout；HP 功放初始化 `coef 0x65=0` 未移植 |
| 内置麦克风/DMIC | 无现成方案 | **否** | ALC285/AppleHDA 路径与 SOF DMIC 是两条链；SimpleHDA 不解决 DMIC |
| 亮度调节 | **NP550XDA NootedGreen fork 的 `-ngreenblr` + `-ngreenbldiag`** | 代码已存在，**需集成到 R28 基线** | 当前 R28 的 XE-BLR 被 `-ngreenxefix` 门控；HP GA47 又在 real TGL 禁用 xefix |
| 指纹 | **RidgeKey 1.0.0** | **可试用**（用户态，不是 Touch ID） | 未签名的 pkg；登录密码存 System keychain；Dragonfly G2 未逐台验证 |
| CPU 温度 | **VirtualSMC 1.3.8 + SMCProcessor** | **可直接加** | 仅温度读数；风扇 RPM 另说 |
| 风扇 RPM/控制 | SMCSuperIO / YogaSMC 1.5.3 | **不建议依赖** | HP EC 未验证；YogaSMC 的 HP 键盘背光仍标 TBD |
| ISH 传感器（ALS/加速度/陀螺/hinge） | **IntelISH**（仅 Skylake 9d35） | **否** | 不是 Tiger Lake `a0fc`；移植属于驱动开发 |
| Thunderbolt 4 / USB4（NHI 9a1b） | 无 | **否** | 没有可用的 AppleThunderbolt 匹配/补丁；改 ID 不够 |
| 触屏基本触摸 | 当前 VoodooI2C 2.9.1 已工作 | 已可用 | 笔压感/倾斜未实例化 |
| 触屏笔/手势 | `xe-toque`（XPS/NP550 用户态工具） | 可研究 | 为其他机型写的，未在 HP 验证 |
| HDMI / USB-C DP 外接显示 | NP550XDA fork 的 HDMIEMU/HDMIOUT + USB-C DP | 代码存在，**非直接移植** | 连接器表/ACPI 因机型而异 |
| IR 面容解锁 | 无 | **否** | macOS 没有 Windows Hello 对应功能 |
| 键盘背光 | YogaSMC（实验性 HP） | **否** | 上游标 TBD；无 Dragonfly G2 证据 |

## 1. 内置音频：SimpleHDA 是当前最好的现成方案

### 1.1 为什么不是普通 AppleALC

Tahoe 从 26 DP2 起不再提供 `AppleHDA.kext`；AppleALC 只是给 AppleHDA 打补丁，单独加载没有
音频引擎。R28 日志里 `AppleHDA`/`AppleALC`/`VoodooHDA` 均为 0，`HDAS@1F,3` 没有子驱动，
与此一致。

### 1.2 SimpleHDA

- 仓库：<https://github.com/laobamac/SimpleHDA>
- 最新正式版：**v1.0.0**，2026-10-14；RELEASE/Debug 两个 zip。
- 作用：Lilu 插件，通过 OpenCore 注入原版 AppleHDA 栈，**不修改系统卷、不重建 KC、不需要 KDK**。
- 要求：macOS Tahoe 26 / Darwin 25.x、x86_64、OpenCore、Lilu ≥ 1.7.1、AppleALC、
  有效的 `alcid` 或 `layout-id`、`keepsyms=1`。
- 加载顺序：**Lilu → AppleALC → SimpleHDA**。
- 与其他 AppleHDA 恢复方案/根补丁不能同时使用。

**已有真实 Tiger Lake 成功案例：** Samsung NP550XDA（i7-1165G7，real TGL）的公开 EFI 使用
Lilu 1.7.2 + AppleALC 1.9.8 + SimpleHDA 1.0.0，音频工作；该机 codec 是 ALC256，使用
`layout-id 38`，不是 ALC285。它证明 SimpleHDA 在 real TGL + Tahoe 上能工作，但不证明
HP ALC285 的 layout。

项目：<https://github.com/joaovitoraramo/NootedGreen-NP550XDA>，`tools/mk-efi.py` 中可见
`AppleALC.kext`、`SimpleHDA.kext`、`SMCProcessor.kext` 和 `layout-id 38`。

### 1.3 ALC285 layout 候选

AppleALC 1.9.8 的 `Resources/ALC285/Info.plist` 只有这些 layout：

| layout | 来源机型 |
|---:|---|
| 11 | ThinkPad X1 Carbon 6th |
| 21 | ThinkPad X1 Carbon 6th（EAPD/JackSense 修正） |
| 31 | ThinkPad X1 Extreme |
| 33 | ASUS ROG Zephyrus G14 |
| 52 | ThinkPad P52 |
| 61 | Lenovo Yoga C740 |
| 66 | Lenovo Legion S740 |
| 71 | **HP Spectre x360 13-ap0xxx** |
| 88 | Lenovo Yoga S740 |

**没有 HP Elite Dragonfly G2 / `103c:8716` 专用 layout。** 最接近的是 71（同为 HP ALC285），
但不是本机验证；21 在旧 HP EliteBook 840 G7 配置中出现过，也不是 Tahoe/SimpleHDA 证据。

### 1.4 HP 功放初始化

Linux `sound/hda/codecs/realtek/alc269.c` 对 `103c:8716` 绑定
`ALC285_FIXUP_HP_GPIO_AMP_INIT`。其实际函数体不是 GPIO mask/direction/data，而是：

```c
msleep(100);
alc_write_coef_idx(codec, 0x65, 0x0);
```

即初始化后等待 100 ms，把 Realtek coefficient `0x65` 写为 0。Linux 补丁说明提到右声道/
功放问题；这是 Linux HDA 成功，不等于 macOS 已移植。

**当前没有公开的 AppleALC layout 包含这个 `0x65=0` 初始化。** 如果测试中出现“有设备但
一个声道无声/声音很轻”，这个 coefficient 写就是首要怀疑点。可选做法（按侵入性排序）：

1. 先确认 layout 71/21 是否已经能出正确声音；不要先改代码。
2. 如果只差 `0x65=0`，研究 AppleALC layout 的 `ConfigData` 是否能表达 `SET_COEF_INDEX 0x65`
   + `SET_PROC_COEF 0x0`；AppleALC 支持 `ConfigData`/`WakeConfigData` 和 `alc-delay`，
   但没有现成的 HP 8716 布局。
3. 若 AppleALC 的 verb 时序不够，再考虑用户态在启动后发送 HDA verb（不是 kext）。

### 1.5 内置麦克风/DMIC

ALC285 是 HDA codec；HP 的三麦克风阵列在 Linux 上走 `sof-audio-pci-intel-tgl` 的 DMIC/SOF
路径。SimpleHDA 恢复的是 AppleHDA，能处理 ALC285 的模拟输入/耳机，但**不解决 SOF DMIC**。
因此现实预期是：

- 扬声器/耳机：有希望，取决于 layout + HP 功放初始化。
- 内置 DMIC：大概率仍不可用；蓝牙麦克风/USB 麦克风是可用替代。
- 不要把“蓝牙音频成功”算作内置 ALC285/DMIC 成功。

### 1.6 备选方案

| 方案 | 版本 | 优点 | 缺点 |
|---|---|---|---|
| OCLP-CustoMac Modern Audio | 3.0.3（2026-09-07） | 真正 root patch AppleHDA，原生质量 | 需要匹配 KDK；每次 Tahoe 小版本更新可能暂时失效；侵入性最高 |
| VoodooHDA-Tahoe | chris1111 fork，最后 push 2026-04-03 | 独立通用 HDA，不需要 KDK | 音质/音量较差；需放宽 SIP；HP 8716 无验证；可能与 USB 音频冲突 |
| BlackHole / USB DAC / BT | 现成 | 零风险绕开内置 codec | 不是“修好内置音频” |

OCLP-CustoMac：<https://github.com/kgp-macPro/OCLP-CustoMac/releases/tag/v3.0.3>。
VoodooHDA-Tahoe：<https://github.com/chris1111/VoodooHDA-Tahoe>。

## 2. 亮度：NP550XDA fork 已有 real TGL 的可复用实现

### 2.1 当前 R28 为什么没生效

R28 的 NootedGreen 源码里已经有 XE-BLR（`ngreenblmax`、`-ngreennoblr`），但它位于
`xeFixFilterWrite()` 内，而该函数在 XE-BLR 之前有：

```c
if (!xeFixEnabled()) return val;
```

`xeFixEnabled()` 只认 `-ngreenxefix`。R28 的 boot-args 没有 `-ngreenxefix`，所以 XE-BLR
从未运行。反过来，HP GA47 的 port 又在 `xeFixEnabled()` 里对 `isRealTGL` 直接返回 false，
因为 `-ngreenxefix` 还包含 display 13（ADL-P/RPL-P）的 DBUF/DPT/GAMMA 修正，不适合原生
Tiger Lake 的 display 12。

日志里的两条关键信息：

```text
[IGFB][ERROR][DISPLAY][AppleIntelController.cpp:7901][hwGetCRTC] EFI using a different backlight frequency
AGDCBacklightControl: Didn't find DPMicro.
```

前者正是 XE-BLR 要处理的“EFI PWM 周期与 Apple 预期不同”；后者通常是 AGDC 找不到 Apple
专用显示微控制器对象，单独出现不一定是根因。

### 2.2 现成实现：NP550XDA 的 `-ngreenblr`

Samsung NP550XDA（real Tiger Lake i7-1165G7）的公开 NootedGreen fork 把 XE-BLR 从
`-ngreenxefix` 中拆出来：

- `-ngreenblr`：只启用背光 PWM 重缩放，不启用 display 13 的 DBUF/GAMMA/DPT 修正。
- `-ngreenbldiag`：在 FB start 前和之后每 10 秒打印
  `CTL/FREQ/DUTY | hw/apple/fw/lastDuty/maxDuty/out`，用来测本机 PWM。
- 该机 boot-args：`-ngreenblr ngreenblmax=17741`；其 panel 的硬件周期是 96000，Apple 最大
  只请求 duty 17741，所以 17741 是“Apple 认为的 100%”，不是硬件周期。
- 该机 README 明确写“Internal panel brightness works”，并列出 `-ngreenfbdpmstgl` 用于
  display sleep（只关背光）。

仓库：<https://github.com/joaovitoraramo/NootedGreen-NP550XDA>（2026-11-03）。
它基于 HP Dragonfly G2 的 NootedGreen 源码，属于同一代码谱系；关键差异就是上述
`-ngreenblr` 拆分和 `-ngreenbldiag`。

### 2.3 对 HP 的落地方式

这不是“新写驱动”，而是把 NP550XDA 已经公开的 XE-BLR 拆分补丁集成到当前 R28 的
NootedGreen 基线（R28 还有 poolguard/stampfix 等 GPU 修复，不能直接整包替换）。步骤：

1. 在 R28 源码的 `xeFixFilterWrite()` 里加入 `-ngreenblr` 独立开关：
   - `-ngreenblr` 时只跑 XE-BLR，不跑 display 13 的 DBUF/GAMMA/DPT。
   - 保留 `-ngreenxefix` 原路径给 RPL/ADL。
2. 加入 `-ngreenbldiag` 的打印（可选但强烈建议）。
3. 用 `-ngreenblr -ngreenbldiag` 启动一次，读取 `FREQ`、`hw`、`apple`、`maxDuty`。
4. 以 `maxDuty` 为 `ngreenblmax` 的首选值；Linux `intel_backlight/max_brightness=19200`
   只是硬件周期线索，不一定是 Apple 的 max duty。
5. 验证滑块 0–100% 与 Fn 亮度键；HP 的 `SSDT-PNLF-HP-GA419.aml` 已在 R28 ACPI 中。
6. 如果亮度键仍不动，再单独查 HP EC `_Qxx` 事件映射；不要把它和 PWM 问题混为一谈。

### 2.4 WhateverGreen 的 `-igfxblr`/`-igfxblt` 是否可用

- `-igfxblr`（`enable-backlight-registers-fix`）主要面向 KBL/CFL/ICL，不是 Tiger Lake 的
  NootedGreen 路径。
- `-igfxblt` 是 macOS 13.4+ 的替代寄存器修复，针对 Apple 内联 `hwSetBacklight()` 的代码
  路径；Tiger Lake/NootedGreen 不是它的目标。
- `applbkl=0/3` 也不是本机方案（0 是禁用 WEG 的 AppleBacklight 补丁，3 是 AMD PWM）。
- 因此优先用 NP550XDA 的 XE-BLR，而不是继续试 WEG 参数。

## 3. 指纹：RidgeKey 1.0.0 是可用的用户态替代

- 仓库：<https://github.com/labrouss/RidgeKey>
- 最新正式版：**v1.0.0**，2026-10-31；`RidgeKey-1.0.0.pkg` 和 tar.gz 都有 SHA-256。
- 支持设备表明确写：**Synaptics `06cb:00f0`，已在 HP EliteBook 840 G8 + macOS Tahoe 实测**；
  还报告 `06cb:00bd` 可用。
- 功能：锁屏解锁、管理员对话框、`sudo`、手指动作（锁屏/Shortcuts）。
- 它不是 Apple Touch ID：没有 SEP，不进入系统“触控 ID”设置，不支持 Apple Pay/iCloud Keychain
  的 SEP 流程。
- 安装：未签名 pkg，首次需右键 Open / Privacy & Security → Open Anyway；安装到
  `/Applications`、`/usr/local/ridgekey`、`/Library/Security/SecurityAgentPlugins`。
- 安全注意：为了实现锁屏自动输入，它会把登录密码存到 System keychain（仅 root 可读），
  并通过 Accessibility 权限在锁屏输入。应审查源码、先在非关键账户测试，并保留密码回退。
- Dragonfly G2 使用同一 `06cb:00f0`，但公开测试机是 840 G8；本机仍需实测。

协议笔记（06cb:00f0，Linux 抓包）：
<https://github.com/labrouss/RidgeKey/blob/main/docs/PROTOCOL-06cb-00f0.md>。

**结论：** 原生 Touch ID 仍然不可能；但 RidgeKey 是目前最现实、最新的指纹适配，值得作为
“非 SEP 的用户态指纹解锁”试用。不要把它宣传成 Touch ID。

## 4. CPU 温度/风扇

### 4.1 CPU 温度：SMCProcessor

- VirtualSMC **1.3.8**（2026-09-27）官方 release 内含 `Kexts/SMCProcessor.kext`。
- NP550XDA（real TGL）的 EFI 已使用 `VirtualSMC 1.3.8 + SMCProcessor`，可作为 real TGL
  可用性的旁证。
- R28 当前只有 `VirtualSMC + SMCBatteryManager`，没有 `SMCProcessor`；这解释了
  `powermetrics --samplers smc` 的 `Invalid key`。
- 添加 `SMCProcessor.kext` 是现成插件，不需要写代码；加载顺序在 VirtualSMC 之后。

### 4.2 风扇 RPM/控制

- `SMCSuperIO` 只探测它支持的 Super-I/O/EC；HP 笔记本风扇通常在 EC/WMI 后面，未必能识别。
- YogaSMC 1.5.3 有实验性 HP 支持，但其文档把 HP 键盘背光标为 TBD，风扇/热键也不完整。
- 建议先只加 `SMCProcessor` 读温度；风扇 RPM/控制保持“未验证”，不要依赖 macOS 工具去
  控制风扇，也不要改 HP 固件风扇策略。

## 5. ISH 传感器：有参考实现，但不是 Tiger Lake

- 唯一找到的 macOS ISH 项目：**IntelISH**，<https://github.com/yjmd2222/IntelISH>。
- 目标：HP Elite x2 1012 G2，Skylake Sunrise Point-LP ISH `8086:9d35`。
- 功能：通过 ISHTP/HID 读 ALS，发布 lux 给 VirtualSMC；配置加速度计并向 IORegistry 暴露
  X/Y/Z；陀螺仪未实现；另有 `IntelISHRotation` 旋转应用。
- **不支持** Tiger Lake `8086:a0fc`。移植需要实现 Tiger Lake ISH 的 PCI/ISHTP/固件客户端，
  属于驱动开发，不符合“不自己造驱动”的原则。
- `SMCLightSensor` 只读 ACPI ALS（ALS0/ALSD），不能读 ISH；本机没有独立 ACPI ALS。
- 结论：ALS、加速度、陀螺、hinge、自动旋转、自动亮度目前没有可用的现成 macOS 方案。
  如果将来愿意投入，IntelISH 是最好的起点，但应视为一个独立的驱动项目。

## 6. Thunderbolt 4 / USB4：没有可用方案

- `8086:9a1b` 是 Tiger Lake-LP 集成 Thunderbolt 4 NHI。
- 没有找到可安装的 AppleThunderbolt/AppleThunderboltNHI 补丁或社区驱动；device-id spoof
  只能改变 IOKit 匹配，不能提供 NHI 寄存器、ACPI 电源/热插、DROM、PCIe/DP 隧道。
- 现有 Hackintosh Thunderbolt 经验主要针对独立 Alpine/Titan/Maple Ridge 卡，且需要
  ACPI/固件/DROM 配套；不能套到 TGL 集成 NHI。
- USB-C 的纯 USB/DP Alt Mode 可能通过 NootedGreen 的 USB-C DP/HDMI 代码实现（见下），
  但 Thunderbolt 扩展坞、TB 显示器、eGPU 不应期待。

## 7. 触屏、笔、外接显示、键盘背光

### 7.1 触屏/笔

- R28 已加载 `VoodooI2C 2.9.1` + `VoodooI2CHID`，`WACF4233` 触屏的
  `VoodooI2CTouchscreenHIDEventDriver` 已实例化；基本触摸驱动在。
- `VoodooI2CStylusHIDEventDriver` 未实例化，笔压感/倾斜没有事件驱动。
- XPS/NP550 项目的 `xe-toque` 是用户态触屏手势/笔工具；可为其他 VoodooI2C 触屏提供
  scroll、右键、边缘手势、pen 等，但不是 HP 验证过的驱动。可作为低优先级试验。

### 7.2 HDMI / USB-C DP

- NP550XDA fork 在 real TGL 上实现了原生 HDMI（`HDMIEMU`/`HDMIOUT`，pipe B/TC1 DDI/Dekel
  PHY/HDMI PLL）和 USB-C DP Alt Mode（DDI B link training）。
- 这些代码与具体连接器表/ACPI 相关，不能直接套 HP；但它是现有、可读、real TGL 的参考。
- R28 目前只验证了内屏；外接显示未测。若外接显示是刚需，可在 GPU 稳定后再评估移植。

### 7.3 键盘背光

- YogaSMC 1.5.3 是唯一相关的 HP 实验项目，但上游把 HP 键盘背光标为 TBD；没有 Dragonfly G2
  证据。
- `BrightnessKeys`/PNLF 只管屏幕背光，不能推断键盘背光。
- 结论：暂无可靠现成方案；低优先级。

### 7.4 IR 摄像头/面容解锁

- HP IR Camera 的 UVC 接口可以枚举；RGB 摄像头已工作。
- macOS 没有 Windows Hello 的第三方 IR 面容认证路径；RidgeKey 也不做面容。
- 结论：面容解锁不可行；IR 视频流最多作为普通 UVC 设备研究。

## 8. 建议的验证顺序（尚未执行）

1. **指纹（风险最低、现成）**：在非关键账户试 RidgeKey 1.0.0，确认 `06cb:00f0` 识别、
   锁屏/sudo/管理员对话框；保留密码回退。
2. **CPU 温度（现成）**：加 `SMCProcessor.kext`，确认温度读数；风扇 RPM 另测。
3. **音频（现成机制 + 需试 layout）**：加 AppleALC 1.9.8 + SimpleHDA 1.0.0，`keepsyms=1`，
   从 `alcid=71` 开始，逐次试 21/11/66；分别测扬声器、耳机、内置麦克风。若单声道/轻，
   再研究 `coef 0x65=0`。
4. **亮度（需集成现有 fork 补丁）**：把 NP550XDA 的 `-ngreenblr`/`-ngreenbldiag` 集成到
   R28 NootedGreen，测 `ngreenblmax`；这是现有代码，不是新驱动。
5. **触屏笔/外接显示/传感器/雷电**：低优先级；没有现成可直接用的方案，除非愿意投入移植。

## 9. 风险与边界

- **SimpleHDA** 的 release 内含 AppleHDA 二进制 payload；它不是开源驱动，分发/再发布需
  自行评估许可。个人测试可以，但不能把 Apple 二进制加入公开仓库。
- **RidgeKey** 是未签名 pkg，且会保存登录密码到 System keychain、通过 Accessibility 输入；
  只应从官方 release 下载并核对 SHA-256，先审查源码/在测试账户使用。
- **NP550XDA fork** 使用 NootedGreen 的 *Thou Shalt Not Profit License 1.0*；集成/分发需遵守
  该许可。它是 real TGL 的成功案例，但不是 HP Dragonfly G2 的验证。
- 所有“可用”结论都需要在目标机、目标 macOS build、具体功能上实测；kext 加载、设备枚举、
  IORegistry 节点存在都不等于功能通过。

## 10. 关键链接

- SimpleHDA：<https://github.com/laobamac/SimpleHDA>（v1.0.0，2026-10-14）
- AppleALC：<https://github.com/acidanthera/AppleALC>（1.9.8，2026-09-27）
- OCLP-CustoMac：<https://github.com/kgp-macPro/OCLP-CustoMac>（3.0.3）
- VoodooHDA-Tahoe：<https://github.com/chris1111/VoodooHDA-Tahoe>
- NP550XDA / NootedGreen real TGL：<https://github.com/joaovitoraramo/NootedGreen-NP550XDA>
- RidgeKey：<https://github.com/labrouss/RidgeKey>（v1.0.0，2026-10-31）
- VirtualSMC：<https://github.com/acidanthera/VirtualSMC>（1.3.8）
- IntelISH：<https://github.com/yjmd2222/IntelISH>
- YogaSMC：<https://github.com/zhen-zen/YogaSMC>（1.5.3）
- VoodooI2C：<https://github.com/VoodooI2C/VoodooI2C>（2.9.1）
- Linux ALC285 quirk：<https://github.com/torvalds/linux/blob/master/sound/hda/codecs/realtek/alc269.c>
- 现有状态报告：[`peripheral-adaptation-status-20261104.md`](peripheral-adaptation-status-20261104.md)
