# Tiger Lake 9A49 图形适配来源核查

审阅基准：2026-10-16。本文整理来源、Framebuffer-only 技术路线和待核实差异，不是可启动 EFI。
实机基线来自 2026-10-15 只读采集，证据清单及 SHA-256 校验见 [`hardware/elite-dragonfly-g2.json`](../hardware/elite-dragonfly-g2.json)、[`docs/hardware.md`](hardware.md)、[`docs/verification.md`](verification.md)。本轮文档工作未重新访问实机；macOS 尚未启动验证。
固定源码快照、文件链接、API provenance、版本和许可证另见 [`manifests/graphics-sources.json`](../manifests/graphics-sources.json)。本次图形来源审阅未额外下载二进制；官方项目 release 缓存状态按主代理记录列于清单及 [`manifests/core-sources.json`](../manifests/core-sources.json)。

## 实机资料状态

以下为已采集并脱敏的实机事实；`make verify-evidence` 已核对私有采集目录 62 个文件的长度与 SHA-256，ACPI/EDID 校验和及 VBT 签名通过。原始采集留在 `.local`，不在本公开库存中。

| 字段 | 当前记录 | 核验状态 |
|---|---|---|
| 平台 / BIOS | HP Elite Dragonfly G2，board 8716；T90 01.25.00，BIOS date 原始记录 `06/05/2026` | DMI 文本 SHA-256 `b9b5ae1b197910f933e1938af75c8e8d7d7a3a1e8079ca88c97c35cf44f3d343`；固件设置文本 SHA-256 `5152508f6636e840be064abc73860933b3d4538e00aa2702662ee2f64d9f1a99` |
| CPU | i5-1135G7；family 6 / model 140 (`0x8C`) / stepping 1；8 logical processors | `text/system.txt` SHA-256 `f8f7fe1ac5fdd0938df6eacc9c82b0aa2803bcfb48c035f3c59ee60be2375de0`；与参考补丁 `0x8C/0x8D` CPU gate 相符 |
| iGPU | `0000:00:02.0`，8086:9A49 rev 01，subsys 103C:8716；Linux i915 旧采集报告 B0、80 EU、5 subslice；后续运行态观察为 80 EU / 10 subslices（见[当前状态](../configs/install-preparation.json)） | PCI / graphics SHA-256 分别为 `bc73d7f1deeebb0689deca97f3e46b18053a8f0bb0ded0534a9459c27834a2be` / `c7d60c98f4292d329a186b21bc282b24e115bb12ac1125a6490146a6d47941e9`；GT fuse 原始寄存器值尚未采集 |
| 内屏与时钟 | IVO8596 `X133NVFF R0`，1920×1080；pipe A / DDI A / PHY A / eDP-1，2 lanes；port clock 270000 kHz (=270 MHz)，pixel clock 138800 kHz (=138.8 MHz)，约 60 Hz | EDID 128 B SHA-256 `229597c3c0f0577d85202c7928c8ad4718a7624558e41afde1f8b7dce15adba5`；时钟单位已确认。i915 仅给出 DPCD revision 1.2 汇总，没有完整 AUX/DPCD dump |
| 固件图形设置 | Video Memory Size 512 MB；host/GPU GGC 均 `0x10c1`；VMD disabled；Secure Boot enabled | 后续 GMS/BDSM 解码与内核预留范围交叉确认 512MiB，不再仅依赖 BIOS 菜单；见 [运行态补充](runtime-display-notes.md) |
| VBT / ACPI / HID | 原始 VBT 8704 B；DSDT、23 张静态 SSDT、8 张动态 CPU SSDT（共 32 张 AML）；触控板/触屏 HID report descriptors 已取得 | VBT SHA-256 `715772cebbc951aef00ddec4bc76fe571c5f4f5dc5c0c26b8171a53f6333241d`；代表 ACPI hashes：DSDT `7afb4e662e79265a1a7c42c1af7ad448c003e8dbfa735b354e77dbb82f1ab343`、DMAR `2ca3fa2c612c438a8bd5a9f2583596f7c680202a4fc2212933c20db63963aa9b`、NHLT `a5778dc31aa1a8788ce91f0dd78dc112cb0135a1251fc818db3f77d11b76c096`；HID 原始文件哈希已在私有采集验证 |
| 背光 / fuses | Linux `intel_backlight/max_brightness=19200` | 不是 PWM MMIO 上限；firmware PWM 频率/占空比、`0xC2014` 与 GT fuse 寄存器仍未完成采集 |

## 可复用的 framebuffer-only 路线

固定参考是 [latitude 仓库快照 `1010490d…`](https://github.com/holdmysocks/latitude-7320-detachable-hackintosh/commit/1010490d3421628c9d6fd0bd518b6c4b6f8ee33c)，提交于 2026-10-08 18:20:19Z。其 LAYER3 自述在 Dell 9A40、Tahoe 26.6 build 25G72、Apple framebuffer 24.0.5 上工作；这是作者的单机记录，不是本机验证。原始 run log / snapshots 可从固定提交的 [`research/LAYER3.md`](https://github.com/holdmysocks/latitude-7320-detachable-hackintosh/blob/1010490d3421628c9d6fd0bd518b6c4b6f8ee33c/research/LAYER3.md)、[`research/RESULTS.md`](https://github.com/holdmysocks/latitude-7320-detachable-hackintosh/blob/1010490d3421628c9d6fd0bd518b6c4b6f8ee33c/research/RESULTS.md)、[`research/data/layer3/runs.csv`](https://github.com/holdmysocks/latitude-7320-detachable-hackintosh/blob/1010490d3421628c9d6fd0bd518b6c4b6f8ee33c/research/data/layer3/runs.csv) 查验。

路线的边界与组件：

1. 先以 VESA 为实验基线；编译 WhateverGreen 1.7.1 固定源 `0762cecc2a70054cd4dc3cf4d08979aca6acd9bb`，依次应用仓库的 `0001`、`0002`、`0003`。`0003` 依赖前两项；其中 0001/0002 是开发诊断钩子，0003 提供显示寄存器映射，是作者正常内屏路线的核心。仓库不分发编译后的 kext。
2. `lilucpu=12` 令 WhateverGreen 走 Ice Lake 支路；补丁另外检查真实 CPU model `0x8C/0x8D`。本机已采集到 family 6、model `0x8C`、stepping 1，满足该 model 条件；这不等于 macOS 下补丁已加载或显示工作。
3. `0003` 不是泛化的 Tiger Lake 驱动：它为 DDI A 将 ICL 的 DP_TP_CTL/STATUS、DDI select、clock select、DPLL CFGCR 和 eDP transcoder 访问映射到 TGL；另在 link enable 前设置 transcoder A。i915 采集到的本机 DDI A/PHY A/pipe A 与其固定路径相符，是有利线索，不等于 macOS 链路已实测成功。
4. Dell 示例用 `device-id=8A5A`、`AAPL,ig-platform-id=8A5C0002`、`lilucpu=12` 和 `igfxtglmap=0xA83F`。这些是针对其 Tahoe 26.6 驱动表、Dell DDI A、PWM 和 ACPI 的实验值，不能直接写入 HP 配置。Tahoe 26.6 的 Apple 驱动/平台表本轮未通过本机安装或 Apple 来源二进制独立核对。
5. 后续只读观察将 GGC `0x10c1`（普通 GMS `0x10`）、Gen11+ BDSM 和内核预留范围交叉确认为 512MiB，未呈现特殊 `0xf0+` 编码。当前不把 `-igfxdvmt` 加入基线；Apple 驱动下是否仍有其他内存解释问题需实测。`-igfxcdc` 与 `-igfxdbeo` 在参考实验未单独隔离；`dc6config=0` 后来被证明不是显示睡醒修复的必要条件。OpenCore `Kernel/Block` 对 Apple system kernel collection 中的 ICL accelerator 未能阻止其加载。
6. 本机目前只有 Linux backlight 标尺 `max_brightness=19200`，未测 firmware PWM 频率/占空比及 SFUSE_STRAP `0xC2014`；不能据此选择 map bit `0x8000` 或照抄 Dell `igfxtglblmax=0xAD9`。PNLF `_UID=15`、`SSDT-DOSI` 也属 Dell OSID/EC 路径专用，不应直接移植。

### 9A40 → 9A49 的实机差异采集清单

- 已采集 PCI BDF/ID/revision/subsystem、CPU CPUID、BIOS 设置、原始 VBT、EDID、32 张 AML ACPI 表和 HID report descriptors；相应证据 SHA-256 已校验。时钟单位已由 i915 记录确认。
- GMS/stolen size 和 BDSM base 已补齐；仍需完整 DPCD/AUX dump、Apple framebuffer 对内存的实际解释、firmware PWM 与 `0xC2014`、以及 accelerator 研究所需的 forcewake GT fuse `0x9134`、`0x9138`、`0x913C`、`0x9120`、`0x9140`。i915 的 80 EU/5 subslice 不可替代 fuse 原始值；参考 `igfxtglss=6` 是 Apple 驱动 SKU workaround，不能按本机 subslice 数直接换算。
- 若后续进行 macOS 验证，记录精确 Tahoe build、`AppleIntelICLLPGraphicsFramebuffer` 版本/UUID、IGPU ioreg、内核显示日志，以及 modeset 前后 transcoder/DP_TP/DDI/DPLL、`0xC8250/54/58`、`0xC2014`、DSSM 快照。
- 当前已核实 Linux 硬件状态、GMS/BDSM、面板 PPS 时序、OpRegion 与相关采集文件完整性；尚无完整 AUX/DPCD、PWM/fuse 原始读数或 macOS build/kext UUID/显示日志。原始 ACPI 表独立反编译均有 DSL 输出，但 DSDT/SSDT6 仍有 namespace 警告，不能视为完整 namespace 已验证或可直接重编译固件 DSDT。

## 源码获取、许可与构建约束

- 对照 [`WhateverGreen-patches/README.md`](https://github.com/holdmysocks/latitude-7320-detachable-hackintosh/blob/1010490d3421628c9d6fd0bd518b6c4b6f8ee33c/WhateverGreen-patches/README.md) 和 [`build-weg-clt.sh`](https://github.com/holdmysocks/latitude-7320-detachable-hackintosh/blob/1010490d3421628c9d6fd0bd518b6c4b6f8ee33c/WhateverGreen-patches/build-weg-clt.sh)：WhateverGreen 1.7.1 固定源上应用 0001–0003；构建需 MacKernelSDK 与 Lilu bundle 内的 resources/headers、`plugin_start.cpp`。主代理报告已取得并校验官方 release 缓存 OpenCore 1.0.8、Lilu 1.7.2、VirtualSMC 1.3.8、VoodooPS2 2.3.7；版本、提交、官方来源/许可证及可用 release digest 见 [`manifests/core-sources.json`](../manifests/core-sources.json)。这不证明 Lilu bundle 与该脚本所要求的 DEBUG/resource 布局兼容，也不表示 patched WhateverGreen 已编译。
- 图形审阅子任务本身未下载额外二进制。工程优先采用可靠上游、锁定版本与哈希；社区开源 kext release 或官方 SDK 归档不是一概禁止。对 MacKernelSDK 固定快照中的 `Library/x86_64/libkmod.a`，应核实来源、摘要及适用许可证，不能把它列为用户设定的政策阻塞。
- 后续已用 Python 资源转换器、MacKernelSDK/Lilu headers、LLVM 21 clang 与 Linux 版 ld64 956.6 完成 patched WEG 的 23 对象编译和真实 `MH_KEXT_BUNDLE` 链接，没有依赖 Apple SDK/Xcode。见 [构建就绪度与链接证据](framebuffer-build-readiness.md)。内核导入、macOS loader、HP framebuffer 和 Metal 仍未验证，不能将本机构建成功外推到全部 kext。
- WhateverGreen 衍生补丁的上游代码保留 BSD-3-Clause 条款；holdmysocks `LICENSE` 的 MIT 范围按其文本只涵盖自有文档、脚本、ACPI、配置、研究数据等，GitHub API 同时标 `NOASSERTION`。不要把整个衍生补丁/第三方树统称 MIT。

## 不纳入 framebuffer 路线的实验

- LAYER4/patch `0004` 是独立 accelerator 研究：9A40 上仍无可用桌面，shader 部分转换后仍 GPU hang；它报告测试于 Tahoe 26.6，但**不证明 Metal 可用**。需要 GT fuse、revision、CSB、Apple accelerator 与 GPU hang 研究，风险/依赖显著高于内屏 modeset，不移植进本次 framebuffer-only 评估。
- [WhateverXe `0.2.3`](https://github.com/b00t0x/WhateverXe/tree/61a449255d385aeb468f64e5d5042e126f387b90) 是另一项目：源表含 9A49 backend，但 README 的当前目标为 Big Sur 20G1443；Metal 实测描述为外接显示器，Tahoe 和内屏仍列计划。需 Xe root patch；不替代 0003 的 Tahoe eDP 路线，也不与 WhateverGreen 同时启用。
- [Samsung NT750XDA-KF59U](https://github.com/lshbluesky/Samsung-NT750XDA-KF59U-Hackintosh/tree/bb72f964baffb36a23153f211c9c0c5880826d1a/README.md) 只作同代 i5-1135G7/Tiger Lake 背景参考：README 称 QE/CI 不可用，版本列至 Sonoma；GitHub API 未识别许可证（null）。不复制其 EFI/二进制，也不把它当 Tahoe 9A49 成功案例。

## 阶段结论

当前证据支持把 0001–0003 作为 **后续 9A49 内屏 framebuffer-only 的研究基线**：本机 DDI A 路由及 CPU model `0x8C` 与补丁条件相符，VBT/EDID/ACPI/HID 有校验记录，GMS/BDSM 已交叉确认512MiB。Linux 上 patched WEG 编译及真实链接已完成；仍缺完整 AUX/DPCD、PWM/fuses、macOS loader/内核 ABI 和 Tahoe 实机验证。Metal/QE/CI 与可启动性均未证明；本轮未改 BIOS、EFI 或 Lexar/Ventoy。
