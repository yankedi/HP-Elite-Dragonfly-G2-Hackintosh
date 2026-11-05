# HP Elite Dragonfly G2 → macOS Tahoe

基于实机的实验性适配工程。目标是原生 Intel macOS 26 Tahoe（`26.6.2` / `25G83`）。**当前已安装进入完整 macOS 系统并完整修复 Iris Xe 80 EU Metal 计算挂起：2026-11-05 通过无条件 `EXECLIST_STATUS` bit 30 等待（`elsqWait`）、`GEN8_ROW_CHICKEN2`（`0xe4f4 = 0xc100c100`）、`CS_CHICKEN1` 线程组抢占修复，以及对 `COCLGen8CommandTransport` 计算编码器遗留 `PIPE_CONTROL` / `L3ALLOC` 的就地净化（`hpSanitizeComputeEncoder`），在实机上 100% 跑完 Geekbench 6.5.0 Metal 全部 8 项工作负载（`Background Blur`、`Face Detection`、`Horizon Detection`、`Edge Detection`、`Gaussian Blur`、`Feature Matching`、`Stereo Matching`、`Particle Physics`），全程 0 次 `GPU hang:`、0 次 `GPURestart`**（详见 [`docs/repair32-pcfix2-20261105.md`](docs/repair32-pcfix2-20261105.md) 与 [`patches/nootedgreen-r32-pcfix2-20261105.patch`](patches/nootedgreen-r32-pcfix2-20261105.patch)）。

## 入口

- **[新会话续接 / 迁移必读](docs/continuation.md)**；当前状态见 [`configs/install-preparation.json`](configs/install-preparation.json)，追加事件历史见 [`manifests/experiment-history.json`](manifests/experiment-history.json)。
- **[2026-11-05 Geekbench 6 Metal 全部 8 项工作负载通关记录](docs/repair32-pcfix2-20261105.md)**（对应源码补丁：[`patches/nootedgreen-r32-pcfix2-20261105.patch`](patches/nootedgreen-r32-pcfix2-20261105.patch)）
- [2026-11-05 Horizon Detection 突破记录](docs/repair32-elsqwait-20261105.md)（对应源码补丁：[`patches/nootedgreen-r32-elsqwait-20261105.patch`](patches/nootedgreen-r32-elsqwait-20261105.patch)）
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

远端只做在线、只读采集；不关机、不重启、不休眠，不写 BIOS、NVRAM 或内置 EFI。本机 Lexar U 盘已有 Ventoy，保留其文件及分区。编译、反编译和静态检查放在本机。

## 已建立的实机基线

| 项目 | 在线核实结果 |
| --- | --- |
| 机器 / 固件 | HP Elite Dragonfly G2，板号 8716，T90 01.25.00 |
| CPU / 内存 | i5-1135G7，4C/8T；16GiB 板载，SMBIOS 报告 4267MT/s |
| GPU | Iris Xe `8086:9a49`，B0，80EU / 5 subslice；无 PCI 独显枚举 |
| 内屏 | IVO8596，`X133NVFF R0`，1920×1080 约 60Hz |
| eDP 工作状态 | pipe A / DDI A / PHY A，2 lane，2.7Gbps/lane |
| 触控板 / 触屏与笔 | Synaptics `06cb:cd74` / Wacom `056a:4924`，两条独立 I²C 路线 |
| 音频 | ALC285 `10ec:0285`，子系统 `103c:8716`；Linux 使用 SOF |
| 存储 | Micron 2210，HPS1022；SSD 未被 VMD 映射 |
| 当前系统 | NixOS 在线；内置盘保留 NTFS 等现有分区 |
| BIOS | Secure Boot 开，Fast Boot 开，VMD 存储映射关，Video Memory 512MB |

## 本机命令

```sh
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

离线里程碑：VESA EFI 原型通过 OpenCore 1.0.8 静态校验；固定 framebuffer 补丁已在 Linux 编译并链接成真实 x86_64 kext bundle，独立存放于 `.local/framebuffer-build/`。构建依赖固定缓存，来源见 `manifests/`。

实机单独 `slide=0` 重试仍在 runtime 内存申请处失败；保留该参数、开启 `DevirtualiseMmio` 后，用户照片确认已进入 Recovery 工具界面。该次无指针、键盘仅有初步响应的状态为历史基线；后续输入进展见下段。完整 26.6.2 / 25G83 离线 app 数据映像已复制到 USB 并完整回读校验；Recovery 物理 USB 访问、离线安装、内屏驱动与 Metal 仍待验证。

最新 booter 日志已确认到达 EXITBS；新增 VoodooI2C/HID 与 Tiger Lake 精确匹配 ID 的候选实测后，触控板能移动但卡顿，Terminal 可输入命令。两个 XHCI 已绑定，但 USB 设备树没有下游设备，物理 Lexar 未出现在磁盘列表。原 MMIO 实测基线已单独保留。

仅开启 `ReleaseUsbOwnership` 的 USB 接管对照实测仍未出现物理 Lexar。已核对 `a0ed -> AppleUSBXHCISPT` 的社区来源，尚未部署该匹配。随后独立 **WiFi IMG** 已实测 Wi-Fi、root SSH 和 SFTP 成功，内置 NTFS `/hpdiag` 可读；首份完整运行态归档已保存，触控板 Polling、触屏 APIC 模式取得，USB 仍无下游设备。详见[网络交接](docs/recovery-network.md)和[运行态证据](manifests/hp-recovery-runtime-check.json)。Ventoy 是否致因仍未证明。

第一轮图形路线：VESA 基础启动 → framebuffer-only 内屏 → 周边 → 独立 Xe 加速研究。参考项目中的内屏输出不代表 Metal 可用；WhateverXe 的 Big Sur 成果也不代表 Tahoe 已适配。
