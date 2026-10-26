# HP Elite Dragonfly G2 peripherals — evidence status

核查基准：2026-10-16。对象为 HP Elite Dragonfly G2（DMI board `8716`，SSH 清单记录 i5-1135G7）。
实机数据来自主代理于 2026-10-15 完成的只读 SSH 采集与本地 AML 分析；本页作者没有再次连接/复采。

## 证据口径

- **实机观察**：主代理只读 SSH 采集，经脱敏后汇总在硬件 inventory；不是本页作者独立复采。
- **上游事实**：固定到 40 位 commit 的 Linux/项目源文件中可直接看到的内容。
- **项目自述**：上游项目文档、发行说明或维护者支持声明；不等同于 Dragonfly G2 实测。
- **未核实**：当前没有足够的源代码、官方资料或同机实测证明；“未发现”不代表绝对不存在。
- 厂商/Windows/Linux 驱动可用于识别设备与协议线索，不能直接作为 macOS kext 安装或兼容性证明。

## 摘要

- 最明确的平台限制是 Tiger Lake 核显不受 macOS 支持；这会影响内屏图形加速，不能由外围设备 kext 补足。[S11]
- Linux 上游能确认普通 G2 subsystem 的 ALC285 功放 GPIO quirk，也能确认 Tiger Lake 的 SOF/DMIC 软件路径；两者都不是 AppleHDA/AppleALC 支持证明。[S1–S3]
- 无线、I2C、键盘、相机、指纹、传感器和 NVMe 的实机枚举不代表对应 macOS 功能已可用。所有“可用”结论都需要目标版本、对应设备和具体功能的实测。

## 主代理 SSH 采集快照

以下硬件细节以脱敏 inventory 及对应采集 SHA-256 为依据；其 macOS 驱动可用性另行判断。

| 设备 | SSH 采集结果 | 证据边界 |
|---|---|---|
| 音频 codec | Realtek ALC285 `10ec:0285`，subsystem `103c:8716`；SOF 驱动 `sof-audio-pci-intel-tgl`，控制器 `8086:a0c8` | Linux 绑定；不等于 macOS 声音/麦克风已工作 |
| 触控板 | `SYNA30B6` / `06cb:cd74`，Linux `hid-multitouch`；`_SB.PC00.I2C0.TPD0`，控制器 `8086:a0e8` | ACPI/I2C 资源已分析；未验证 VoodooI2C/设备组合 |
| 触屏与笔 | `WACF4233` / `056a:4924`，Linux `wacom`；`_SB.PC00.I2C1.TPL0`，控制器 `8086:a0e9` | TPL0 资源来自 SSDT17；macOS 触控、压感、笔功能未实测 |
| Wi-Fi | Intel AX201，PCI ID `8086:a0f0` | 上游兼容表列 AX201；并非本机 macOS 实测 |
| Bluetooth | `8087:0026`，USB HS10 | 与 Wi-Fi 分离评估；本机配对/唤醒未验证 |
| 摄像头 / IR | Quanta `0408:5349`，共用 HS02，四个接口 | USB 拓扑已采集；macOS 摄像头/IR 功能未核实 |
| 指纹 | `06cb:00f0`，USB HS07 | 设备已枚举；未发现可核验的 macOS 驱动/实测 |
| 键盘 | i8042/PS2，AT translated set 2；JIS 键位用户说明、按键未测 | PS/2 路线已采集；JIS 实际键位及 macOS 映射待验证 |
| 传感器 | Intel ISH 暴露 10 个 IIO 设备：`incli_3d`、`dev_rotation`、`magn_3d`、`als`、`accel_3d`、`gyro_3d`、`geomagnetic_orientation`、`gravity`、`relative_orientation`、`hinge` | 设备名已采集；具体传感器芯片尚未确认，macOS 支持未核实 |
| SSD | Micron `MTFDHBA512QFD-1AX1AABHA`，固件 `HPS1022`，PCI `1344:5404`，直接 PCIe/NVMe、非 VMD remap | 型号与映射已采集；没有可靠证据支持“该 SSD 不兼容 macOS” |
| BIOS / 板卡 | DMI board `8716`；HP BIOS T90 `01.25.00`；Secure Boot 开、VMD 关、DVMT video 512 MB | BIOS/板卡读取值；本任务未改固件设置 |

## SSH 采集与证据索引

- 主代理于 `2026-10-15T17:40:49.365004+00:00` 只读采集 62 个文件；验证记录称文件长度与 SHA-256 一致。[H1][H2]
- 主代理用 `iasl -dl` 独立反编译 32 张 AML，所有命令退出码 0；保留 DSDT 与 SSDT6 诊断，不能称为完整 namespace 验证。
- [脱敏硬件 inventory](../hardware/elite-dragonfly-g2.json) 汇总身份、设备和证据 SHA；[采集/验证记录](verification.md) 记录流程与边界。
- 本页作者没有 SSH 连接、重新采集或独立运行 AML 工具；以下 SHA 引用已采集文件或原始 AML，不声称生成 DSL 文件具有相同哈希。

| 设备/分析 | 采集证据 SHA-256 |
|---|---|
| 音频与 PCI | `text/audio.txt` `5d31efa8b6da8ab2caf542cf9334adb0c66b752da3020535f20f88e56f7dc048`；`text/pci.txt` `bc73d7f1deeebb0689deca97f3e46b18053a8f0bb0ded0534a9459c27834a2be` |
| 输入、ACPI device、I2C | `text/inputs.txt` `a97b501384dafc390feb3175c6b38784d5aaaf443bece2a31d16981bc6a18ba1`；`text/acpi-devices.txt` `bf2381e36b88c9d8177ac8905a9f5340748e3ee131b1d475fab73e73767bb790`；`text/i2c.txt` `30f38f24cf24d5a5ab55e9af4a6a0ad260a48c5ef136b50136a053eeb5aa29f1` |
| TPD0/TPL0 原始 ACPI | DSDT `7afb4e662e79265a1a7c42c1af7ad448c003e8dbfa735b354e77dbb82f1ab343`；SSDT17 `5d0760079a8d6b5c175884332d20b5b3dea49fdc732fa5c9972f678099255072` |
| HID report descriptors | SYNA `0ee8e6bddf6ee6adf071cdb72983bb0970e2b20e5363ee64bcccc208762cec86`；Wacom `5ad4378537251bc2c6bdf43cec57b542aba7b709028ab02906a80afeb6bcc217` |
| USB、传感器 | `text/usb.txt` `39857b234db948e22e94b904110d1596d5a3f742c077c7b63b84e2e399d633b0`；`text/sensors.txt` `510125293e7c9694cf8b7d223c48c8c915d07c81b460f229b453ab16dae978ba` |
| NVMe 与 BIOS | `text/storage.json` `94e20fbfbbe347112e72d05aea840a5fdc99e29918fc67cbd4747ea671a6788e`；`text/firmware.txt` `5152508f6636e840be064abc73860933b3d4538e00aa2702662ee2f64d9f1a99` |

## 音频：ALC285、功放 GPIO 与数字麦克风

- Linux 上游 `alc269.c` 固定版本中，HP subsystem `103c:8716` 的表项明确绑定 `ALC285_FIXUP_HP_GPIO_AMP_INIT`。该 fixup 是 ALC285 扬声器功放 GPIO 初始化；它是 **Linux HDA 证据**，不自动转化为 AppleALC layout、AppleHDA fixup 或本机扬声器支持。[S1]
- commit `fcf57d066444dfa5cb46080b1b61cde517249530` 的提交本身新增的是 Dragonfly **Max** G2 `103c:8890` 项；提交说明讲述其右扬声器功放 GPIO 未初始化。`103c:8716` 对应普通 G2 的表项已存在于该提交所固定的源文件中。不要把 Max G2 的新增 quirk 误写成普通 G2 的原始引入提交。[S1]
- 脱敏 inventory 记录 SOF 驱动 `sof-audio-pci-intel-tgl` 绑定；固定版 Tiger Lake SOF 驱动源包含 `sof-tgl.ri` 固件与 topology 配置，ACPI machine 表也有 DMIC capture endpoint 示例。[H1][S2][S3]
- **数字麦克风边界：** `snd_sof_pci_intel_tgl` 在 Linux 中加载，只能说明 SOF 驱动路径已绑定；它不证明此机内部麦克风对应哪个 SOF topology、ALSA 录音已成功，更不证明 AppleHDA/AppleALC 能驱动。ALC285 GPIO speaker fixup 与 DMIC capture 是两条不同证据链。实机录音、实际 topology/codec 路由及 macOS 麦克风均未核实。[S1–S3]
- SOF PCI 源文件中的固件文件名、ACPI machine 表中的 topology/endpoint 是平台通用机制；不能据此认定某一条 generic TGL profile 就是本机当前选择的 profile。
- 本次未获得可与 `103c:8716` 绑定的 G2 专属 SOF topology、麦克风录音日志或 macOS 录音实测。数字麦克风路径因此保留为未核实。

## Tahoe、AppleHDA 与 OCLP 3.0.0-rc.3

- Dortania Tahoe 指南称 macOS 26 中 AppleHDA.kext 不再存在，因而 AppleALC 无法提供常规 Realtek 模拟音频；这是 **项目文档陈述**，不是 Apple 官方公告。现有核查未找到可靠 Apple 原始资料确认“从 beta 2 开始移除”这一精确时间点，故该 beta 边界标为未核实。[S9]
- OCLP 官方 GitHub 将 `3.0.0-rc.3` 标为 prerelease，并提示可能存在不稳定、崩溃或数据丢失。固定到该标签实际解析出的 commit `238a876f9a08d405745ae25ef0fd563af6bc28e1` 后，`modern_audio.py` 确实定义 Tahoe 音频 patch：要求 KDK，并在非 Tahoe Beta 1 build `25A5279m` 情形下以 `26.0 Beta 1` 的 AppleHDA.kext 覆盖系统扩展。[S7]
- OCLP 同一固定版本的支持模型文档写明支持对象为列出的 Intel-based **Mac**，未列 PC/HP；其代码存在不能证明 Dragonfly G2 可用。不得把 RC3 的 patch 直接当作本机 AppleHDA 兼容性或已验证方案。[S7]

## Wi-Fi 与 Bluetooth

- OpenIntelWireless 官方兼容表列有 Intel Wi-Fi 6 AX201 160 MHz（MVM Gen 2/IWX）。这是项目兼容表的支持声明，不覆盖 Tahoe，也不是本机测试。[S4]
- `laobamac/itlwm` 的官方 release tag `v2.4.0-alpha` 当前解析到 `bbe368ec7d55a5395d08c729e88eeaabebae8255`。该固定版本 README 自称支持 Tahoe 原生 Wi-Fi；release 明确称 development build、日常使用前须作硬件验证。README 还说硬件支持沿用上游表、需按适配器验证，且 Wi-Fi 6/HE 默认关闭。[S5]
- 因此 AX201 在上游表中的列名是有出处的，Tahoe fork 的支持也是项目自述；**AX201 8086:a0f0 在该 G2 上运行 Tahoe 未实测**。GitHub release 标记为 prerelease 且可变；manifest 同时记录已解析 commit，避免只凭可变 tag 追溯。[S5]
- Bluetooth 独立于 Wi-Fi。IntelBluetoothFirmware 的 commit `a414375505fa3b014be32f8fca31b5bbfdf9f10f` 只把项目允许的最高 KernelVersion 从 Sequoia 提高到 Tahoe；该 diff 不包含 AX201/G2 专项验证，不能据此保证 USB `8087:0026` 蓝牙可用。[S6]
- AX201 的 Linux PCI ID 和 USB Bluetooth ID 来自两个不同的枚举接口；Wi-Fi 在 itlwm 兼容表中出现，不会自动覆盖 BluetoothFirmware 的兼容范围。
- Intel 官方 AX201 页面用于确认硬件规格/平台信息；其操作系统列表没有 macOS 项。该列表不能单独证明绝无第三方驱动，但不构成厂商 macOS 支持承诺。[S12]
- Tahoe fork 的 README 还记载 HE 默认关闭及功能限制。即使成功关联 Wi-Fi，也不应外推 AirDrop/AWDL、WPA3-only、mandatory PMF 或完整 Wi-Fi 6 能力。[S5]

## I2C、触控、键盘、摄像头与传感器

后续实机已进入 Recovery，但指针均无响应。新增固定 VoodooI2C 2.9.1/HID、
Tiger Lake 精确 ID 和轮询请求的候选已交付，实机效果仍待验证；源码与验证细节见
[Recovery 输入适配](input-recovery.md)。以下保留首轮来源核查的证据口径。

- VoodooI2C 固定版 README 列出的 Intel I2C 控制器代际到 Ice Lake，并列出 I2C-HID、ELAN、FTE 设备类别；未列出采集到的 Tiger Lake 控制器 `8086:a0e8/a0e9`。这是“当前文档未列出”，不是证明绝无可用实现。[S8][H1]
- SSH inventory 中 Linux `hid-multitouch` 对 SYNA 触控板、`wacom` 对 Wacom 触屏/笔的绑定不能证明 macOS 控制器驱动、设备 satellite、手势或笔压感匹配；未找到该 G2 组合的可靠实测。[S8][H1]
- VoodooI2C 项目结构区分 I2C 控制器 core 与设备类别 satellite；控制器能枚举与具体 HID/Wacom 设备可用是不同的验证项。
- TPD0 `_INI` 在采集到的 DSDT DSL 中将 I²C 地址设为 `0x2c`、HID descriptor 地址设为 `0x20`；不得改写成静态猜值。[H1][H2]
- GPIO/IRQ 经 `GNUM(GPDI)` / `INUM(GPDI)` 动态求值。资源模板中的 `0x0000` 是占位值，不是可复制到 SSDT/EFI 的实机 GPIO pin。[H1][H2]
- TPL0 的 I²C/HID 资源补充来自 SSDT17（INTTPL）；触屏基本对象在 DSDT。SSDT17 原始 AML SHA 在上方证据表中给出。[H1][H2]
- PS/2 键盘由 inventory 和输入日志确认；JIS 是用户提供的布局信息，实体按键仍待验证。VoodooI2C 文档不能证明 PS/2/JIS 映射。[H1]
- Quanta 摄像头/IR、Synaptics 指纹与 ISH/IIO 传感器是 SSH 采集到的 Linux/USB 枚举。没有据此推断 macOS 摄像头、红外、人脸认证、指纹或传感器插件可用；ISH 芯片身份仍未确认。[H1]
- 摄像头/IR 共用 HS02 且暴露四个接口只是 USB 拓扑事实；未据接口数量推断其中哪些接口是 RGB、红外、深度或 HID。
- HP 文档列举的传感器类别是机型/配置规格，不是 SSH inventory 中十个 IIO 名称的芯片级识别结果；也不证明 ISH 数据在 macOS 可枚举。[S10][H1]
- HP 维护手册列出部分机型配置的摄像头、触控板与传感器类别，但不提供上述实机 ID 的 macOS 驱动证明。[S10]

## 显示与存储边界

- i5-1135G7 属 Intel 第 11 代 Tiger Lake；Dortania GPU 指南把 Tiger Lake/Rocket Lake Xe 系列 iGPU 列为不受任何 macOS 版本支持。对依赖内屏的笔记本，这是关键平台限制；不应把 EFI 能启动或 framebuffer 输出写成 Xe/Metal 加速。[S11]
- Micron 官方 2210 产品简表描述 M.2 2280、PCIe Gen3 x4、NVMe 1.3。SSH inventory 记录固件 HPS1022、PCIe/NVMe 直连且非 VMD remap；未找到可靠来源证明该 SSD 型号本身不兼容，因此保留为“兼容性未核实”，不凭型号下结论。[S12][H1]
- Direct PCIe/NVMe 与 VMD 映射的区分是本机当前配置观察；SSD 产品简表没有说明 macOS 安装器/内核对该具体盘固件或该 BIOS 映射的实测结果。
- Secure Boot、VMD 与 DVMT 数值同样是快照，不是建议改动项，也不能单独预测启动、睡眠或图形加速结果。

## 当前未核实项

- 同机型可复核的公开 EFI、Tahoe 完整实测及 AppleALC 对 `10ec:0285 / 103c:8716` 的有效 layout：本次未发现。
- AppleHDA 被移除的精确 Tahoe beta 边界；OCLP RC3 对 HP PC/该 codec 的适用性；SOF 数字麦克风真实录音路径：未核实。
- Tahoe itlwm fork 在该 AX201 上的功能与稳定性、独立 Bluetooth、I2C 触控板/笔、摄像头/IR、指纹、ISH 传感器及 JIS 键盘：均未核实。
- Micron 2210 在此机型/目标 macOS 版本上的行为：未实测；没有可靠的型号级不兼容证据。
- “本次未发现”仅描述这次公开来源核查结果，不等于证明社区项目、私有配置或其他测试绝对不存在。
- 任何未来测试都应分别记录 macOS build、kext/驱动版本、设备 ID、功能级结果和日志；仅有 EFI 文件或系统启动截图不足以填补上述空白。

## 功能级状态矩阵

以下是目前证据可以支持的最细粒度结论；每项都需要对应 macOS build 上的实际功能验证才能升级状态。

| 功能 | 当前证据可确认 | 尚不能确认 |
|---|---|---|
| 内置扬声器 | Linux 设备身份与上游 GPIO quirk | macOS 左右声道、功放初始化、音量与耳机切换 |
| 内置麦克风 | SSH inventory 记录 Linux SOF 驱动绑定；TGL 有通用 DMIC 表 | 本机 DMIC 拓扑、录音路径和 Tahoe 录音 |
| Wi-Fi | AX201 在上游 itlwm 表出现；Tahoe fork 有项目自述 | 本机 Tahoe 连接、漫游、睡眠恢复和稳定性 |
| Bluetooth | 实机 USB ID 与固件项目 Tahoe 版本上限变更 | 配对、音频外设、唤醒及 AX201/本机专项支持 |
| 触控板 | SYNA30B6 与 Linux HID 绑定 | I2C controller attach、手势、多点触控与睡眠唤醒 |
| 触屏 / 笔 | Wacom ID 与 Linux 驱动绑定 | macOS 触控、笔压感、倾斜和 palm rejection |
| 摄像头 / IR | Quanta USB 设备及四接口拓扑 | macOS 视频接口、红外流、IR 人脸认证 |
| 指纹 | Synaptics USB 设备 ID | macOS 登录/解锁或 Secure Enclave 集成 |
| 传感器 | Linux ISH 暴露 10 项 IIO，见上表及 inventory | 芯片身份、macOS 传感器服务与功能映射 |
| 键盘 | PS/2 总线；JIS 为用户报告 | 实际 JIS 键位、修饰键和输入源布局 |
| NVMe | Micron 2210 规格和 PCIe 映射信息 | 安装、休眠唤醒、错误恢复及目标版本行为 |
| 核显 / 内屏 | 1135G7 属 Tiger Lake；指南标注 iGPU 不支持 | 不把 VESA/framebuffer 输出解释成 Xe 或 Metal 加速 |

HP 维护手册和规格页可佐证机型配置范围，但配置可能因地区、订购项而异；它们不是针对本台序列号的出厂 BOM，也不是 macOS 兼容表。[S10]

## 固定来源

- **S1 — Linux Realtek HDA**：固定源码 commit `fcf57d066444dfa5cb46080b1b61cde517249530`；GPL-2.0-or-later。
  [源文件](https://github.com/torvalds/linux/blob/fcf57d066444dfa5cb46080b1b61cde517249530/sound/hda/codecs/realtek/alc269.c) ·
  [提交说明](https://github.com/torvalds/linux/commit/fcf57d066444dfa5cb46080b1b61cde517249530)。
- **S2 — Linux Tiger Lake SOF PCI**：commit `24df03e2b43c8a66c0f235320177f7199dca47a9`；GPL-2.0-only OR BSD-3-Clause。
  [固定源文件](https://github.com/torvalds/linux/blob/24df03e2b43c8a66c0f235320177f7199dca47a9/sound/soc/sof/intel/pci-tgl.c)。
- **S3 — Linux Tiger Lake ACPI/DMIC machine 表**：commit `3588b76db7ba798f54dee39a55708b16e1c61de4`；GPL-2.0-only。
  [固定源文件](https://github.com/torvalds/linux/blob/3588b76db7ba798f54dee39a55708b16e1c61de4/sound/soc/intel/common/soc-acpi-intel-tgl-match.c)。
- **S4 — OpenIntelWireless AX201 兼容表**：静态文档 commit `57cf4ac34fd0028c883e007722a8b84ca1f526b1`；CC BY-NC-ND 4.0。
  [固定页面](https://github.com/OpenIntelWireless/OpenIntelWireless.github.io/blob/57cf4ac34fd0028c883e007722a8b84ca1f526b1/itlwm/Compat.html)。
- **S5 — laobamac/itlwm Tahoe fork**：README commit `bbe368ec7d55a5395d08c729e88eeaabebae8255`；GPL-2.0。
  [固定 README](https://github.com/laobamac/itlwm/blob/bbe368ec7d55a5395d08c729e88eeaabebae8255/README.md) ·
  [release tag](https://github.com/laobamac/itlwm/releases/tag/v2.4.0-alpha)。
- **S6 — IntelBluetoothFirmware Tahoe 版本提交**：commit `a414375505fa3b014be32f8fca31b5bbfdf9f10f`；GPL-3.0。
  [固定提交](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/commit/a414375505fa3b014be32f8fca31b5bbfdf9f10f)。
- **S7 — OCLP 3.0.0-rc.3**：官方 prerelease；tag 解析到 commit `238a876f9a08d405745ae25ef0fd563af6bc28e1`。
  [release](https://github.com/dortania/OpenCore-Legacy-Patcher/releases/tag/3.0.0-rc.3) ·
  [modern_audio.py](https://github.com/dortania/OpenCore-Legacy-Patcher/blob/238a876f9a08d405745ae25ef0fd563af6bc28e1/opencore_legacy_patcher/sys_patch/patchsets/hardware/misc/modern_audio.py) ·
  [支持模型](https://github.com/dortania/OpenCore-Legacy-Patcher/blob/238a876f9a08d405745ae25ef0fd563af6bc28e1/docs/MODELS.md)。
  `LICENSE.txt` 是 BSD-4-Clause 风格许可，包含广告与不背书条款。
- **S8 — VoodooI2C**：README commit `f266cb1b806e094b0412273c6b37e2430c39b080`；repo LICENSE.txt 为 GPLv3 文本。
  [固定 README](https://github.com/VoodooI2C/VoodooI2C/blob/f266cb1b806e094b0412273c6b37e2430c39b080/README.md)。
- **S9 — Tahoe 音频项目指南**：commit `a4b2ab54e5ec628871dec26596f587d89c01d44e`；CC BY-NC-SA 4.0。
  [固定指南](https://github.com/dortania/OpenCore-Install-Guide/blob/a4b2ab54e5ec628871dec26596f587d89c01d44e/extras/tahoe.md)，属于项目文档而非 Apple 原始公告。
- **S10 — HP 官方资料**：[维护手册 PDF](https://kaas.hpcloud.hp.com/pdf-public/pdf_12594923_en-US-1.pdf) ·
  [产品规格页](https://support.hp.com/ph-en/document/c06994777)。非 Git 来源；资料页未声明的许可标为未核实。
- **S11 — Dortania Intel GPU 指南**：commit `88c1bf01bbb247fd5eb5805943a86927681d166d`。
  [固定指南](https://github.com/dortania/GPU-Buyers-Guide/blob/88c1bf01bbb247fd5eb5805943a86927681d166d/modern-gpus/intel-gpu.md)。
  [License 文件](https://github.com/dortania/GPU-Buyers-Guide/blob/88c1bf01bbb247fd5eb5805943a86927681d166d/License)仅显示版权/All rights reserved。
- **S12 — 厂商规格**：[Micron 2210 产品简表 PDF](https://assets.micron.com/adobe/assets/urn:aaid:aem:dc6eafec-7157-48df-9c75-fd4ee77711b1/original/as/2210-qlc-ssd-product-brief.pdf) ·
  [Intel AX201 官方规格](https://www.intel.com/content/www/us/en/products/sku/130293/intel-wifi-6-ax201-gig/specifications.html)。非 Git 来源；许可未核实。

机器观察、每项状态、40 位 commit、文件 blob SHA、许可和核验边界以 [`manifests/peripheral-sources.json`](../manifests/peripheral-sources.json) 为机器可读索引。
[H1]: ../hardware/elite-dragonfly-g2.json "脱敏硬件 inventory"
[H2]: verification.md "只读 SSH 采集与验证记录"

两者汇总的是主代理已完成的 SSH/本地分析，本页作者未自行复采。
