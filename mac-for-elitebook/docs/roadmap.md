# Tahoe 适配路线图

> 当前状态：Tahoe 26.6.2 / 25G83 已安装。四次实验性 TGL 加速启动在约 252–340 秒后 panic；一次软件显示对照运行约 62 分 35 秒且无用户报告冻结，但不能据此证明因果。当前状态见[公开续接入口](continuation.md)；下文阶段状态与待办是早期规划，勿当成当前队列重放。

## 目标与执行边界

目标：在 HP Elite Dragonfly G2（实测 `8086:9a49`）上启动原生 Intel 版 macOS 26 Tahoe，逐步完成内屏、输入、网络、音频、电池与电源管理，最后独立推进 Xe GPU 加速。

用户要求无人值守，常规采集/来源核查委派 GPT-6 Luna max；仅遇到真实阻塞或用户要求时报告。目标机保持在线，禁止自动关机、重启、休眠、修改 BIOS/内置 EFI/NVRAM。用户可以手动设置 BIOS，但这不等于已授权上述操作。

**无需启动目标 macOS 就能继续推进在线硬件基线、来源锁定、离线分析、配置静态校验及组件逻辑的 host tests。** 受控 AML 也可在本机解释器中验证部分分支；这些工作不依赖首次整机启动。实际安装、真实驱动加载、链路和电源行为的验收需要可执行的实机测试窗口。

## 技术决策

1. **最初研究候选为 Tahoe 26.6 / 25G72**，因为 Latitude 7320 的 framebuffer 研究针对该版本；随后实际取得并核验的 Recovery/完整离线输入是 **26.6.2 / 25G83**，见安装交接与来源 manifest。图形研究基线与实际安装输入分别记录；`macrecovery -os latest` 不保证固定 build。
2. 从固定版 OpenCore Sample 配置逐项建 HP 配置，不整包套用 Dell 或 Samsung EFI。CPU spoof、SMBIOS、XCPM、CFG Lock、ACPI 及 kernel quirks 每项记录依据。
3. 图形实验分为 `vesa-baseline`、`tgl-framebuffer`、`xe-acceleration` 三条互斥配置。每次只改变一个有解释的变量；保留上一可复现状态。
4. 驱动优先顺序：HP/Intel 原始资料 → 上游 Linux 硬件行为 → 同型号源码 → 同代硬件项目。厂商 Windows 驱动仅作为协议/固件行为参考，不作为 macOS kext 安装。
5. 所有构建、ACPI 反编译和分析在本地开发主机。按项目实际依赖选择工具链；本工程已在 Linux 交叉构建 patched WEG，不能一概把 Xcode 当作前置。不在 EliteBook 上临时堆编译环境。

## M0 — 实机资料与版本库

状态：**核心采集完成；验证结果见 [verification.md](verification.md)**。

- [x] 本地 `main` Git 仓库、项目约束和忽略规则。
- [x] SSH 只读采集脚本；私有原始资料与可提交脱敏清单分开保存。
- [x] PCI/USB、DMI、NVMe、Codec、输入、BIOS 当前值、传感器与电池记录。
- [x] DSDT/静态及动态 SSDT、DMAR/NHLT、VBT/opregion、EDID、HID report descriptor。
- [x] 62 个证据文件 SHA-256 验证；ACPI 长度/校验和、EDID 校验和与 VBT 签名验证。
- [x] 本机反编译 32 张 AML；保留 HP namespace 警告，不修改 OEM AML。
- [x] 本机 Lexar 介质总容量及 Ventoy 布局记录，无介质写入。
- [ ] 物理 USB 全端口、Type-C 正反插及外接显示拓扑：需要外设与交互测试。
- [ ] GPIO runtime 资源、BIOS CFG Lock 状态及显示寄存器基线：只采用可证明只读的采集方式，按 framebuffer 研究需要补充，不写隐藏 UEFI 变量。

完成条件：能从清单追溯至原始哈希；明确本机设备、BIOS、已知路径和未证实项；不包含序列号或 Windows 密钥。

## M1 — 可审计的 VESA 基础 EFI（离线）

状态：**VESA 原型已离线组装并通过静态检查，部署前审阅未完成；不能宣称已可启动**。详见 [原型说明](vesa-prototype.md)。

- [x] OpenCore 1.0.8 / Lilu 1.7.2 / VirtualSMC 1.3.8 / stock WEG 1.7.1 / VoodooPS2 2.3.7 固定资产。
- [x] 本机运行匹配验证器，检查引用文件、EFI/Mach-O 体系结构和 kext 依赖顺序。
- [x] 按实机 `\_SB.PR00` 编译 Darwin-only SSDT-PLUG；不修改真实 EC 或 OEM 表。
- [ ] EC/USBX、完整端口图、私有身份、安装器网络与部署介质审阅：仍是首次启动前置项。

### 工作包

1. 固定 OpenCore、Lilu、VirtualSMC、图形插件和输入 kext 的版本/提交/资产哈希，核对 Darwin 25 范围与依赖加载顺序。参考项目 commit 和许可证见 `manifests/`。
2. 本机准备匹配 OpenCore 的 `ocvalidate`；若编译工具来自固定源代码，记录编译器与构建命令。生成镜像与配置都只进入 `build/`。
3. 审阅 Tahoe 可用 SMBIOS 及 CPU spoof：以同代项目启动经验作依据，核对实际 CPUID、拓扑和内核版本，不把 `lilucpu=12` 误认为 CPUID spoof。
4. 按实机 `PC00`、EC0、CPU namespace 设计最小必要 SSDT；先从真实 EC/USBX/CPU 插件需求入手，不预先堆入 HPET、RTC、IRQ、GPIO 和电池补丁。
5. 保守图形参数：VESA 路线，保留 verbose/debug 日志。禁用 framebuffer 实验参数和 Xe 加速插件。无网络时应有完整离线安装资料或经过验证的有线网络路径。
6. 安装介质网络单列：Recovery 需要可用网络；不能假定 AX201 在安装器中即插即用，也不能仅依赖 GUI 的 HeliPort。确认 UEFI/GOP 输出和 USB 基础输入后才进行安装器测试。
7. 外部启动介质先在本机以文件形式准备。保留现有 Ventoy，不能直接覆盖 32MiB VTOYEFI 或假设复制 DMG/ISO 到 exFAT 就能引导 macOS。

### 验收

- 精确版本 `ocvalidate` 通过；配置引用的 ACPI/kext/driver 文件均存在、体系结构正确，依赖关系明确。
- SSDT 编译无错误；配置 diff、资产 SHA-256、工具版本和实验说明完整。
- 不含实验性 framebuffer/Xe 混装、不含默认第三方 SMBIOS 身份、不指向内置 EFI 写入。
- **这些检查只证明离线一致性，不证明能进入安装器。**

## M2 — 首次外部启动与基础桌面

状态：**外部 IMG 已进入实机 Recovery；键盘可输入、触控板卡顿，USB 阻塞尚未解决；安装目标区已由用户准备但尚未格式化/安装。**

### 前置条件

- 确认外部介质启动路径和 macOS 安装目标。当前内置盘有多个系统，既有 U 盘要求保留数据；不能自行选择覆盖分区。
- 用户手动处理固件 Secure Boot/Fast Boot 策略，记录修改前后值和恢复步骤。UEFI Secure Boot 与 `SecureBootModel` 分开讨论；不远程更改密钥或开关。
- 现有系统和数据的回退入口可用；Windows 加密状态/恢复材料如涉及其启动链则先核实，不采集或提交密钥。
- USB 完整映射仍未完成，避免依赖已失效的 `XhciPortLimit` 万能绕过；先确保启动盘/键鼠所在端口可用。

### 逐步验收

1. 外部 OpenCore picker 可见且能够返回原系统。
2. Tahoe 安装器到达交互界面；保存完整启动日志、panic、GOP/内屏表现与设备可见性。
3. 仅向已确定目标安装，完成桌面首次登录；记录 `sw_vers`、ioreg、kext 版本与硬件清单。
4. VESA 桌面可操作，基础键鼠和至少一条网络路径可用。记录频率/温度与系统稳定性，不以此通过 GPU 加速验收。

任何一次失败先分类为固件/OC/ACPI/内核/图形/存储/USB，不同时加入多个不相关补丁。

## M3 — Tiger Lake framebuffer-only 内屏

状态：**离线研究；实机实验依赖 M2**。

离线里程碑：固定 WEG 及 0001–0003 补丁顺序应用、资源生成、23 对象交叉编译和真实 `MH_KEXT_BUNDLE` 链接已完成；VBT/EDID、GMS/BDSM 与 PPS 时序已建立 HP 对照。详见 [构建核查](framebuffer-build-readiness.md)。仍没有 HP 的 framebuffer 运行结果。

后续新增 [非启动组件验证](nonboot-graphics-validation.md)：在 Linux 中直接运行提取的原始映射/背光/时序方法，7 组测试及两种故障注入验证通过。后续可继续拓展组件测试，首次启动受阻不再作为软件单元验证的前置条件。

无安装路线已完成 [真实虚拟 UEFI driver 实验](nonboot-vm-validation.md)：OpenCore/OpenRuntime/OpenHfsPlus 的正例和两个对照通过；[两份 HID descriptor 的上游 parser 验证](nonboot-hid-validation.md)完成。后续已解决 Recovery 截断，取得签名通过的 **26.6.2 / 25G83**，在独立 TCG VM 中实际运行 XNU、进入 BaseSystem 单用户 shell，并检查 Lilu、VirtualSMC 和分开的 stock/patched WEG；[加载、初始化与反例证据](recovery-kext-validation.md)另列。这不替代 HP framebuffer、I²C 或 Metal 的实机验收。

- 从固定 Latitude 7320 源码重建最小 framebuffer 补丁，比较 GPU `9a40` 与本机 `9a49 rev01/B0` 的 fuse、DDI、transcoder 与 MMIO 映射。
- VBT/EDID 实机基线：IVO8596、2-lane DDI A、138.8MHz 像素时钟。先解码 VBT，再决定 connector、eDP link training、DVMT 与背光补丁。
- Dell 的 `igfxtglmap=0xA83F`、`igfxtglblmax=0xAD9`、device/platform spoof 仅作为实验文献。未核对 HP 寄存器和补丁实现前不写进默认配置。
- 分项验证原生分辨率、内屏识别、10 档亮度、黑屏恢复；显示器睡醒、合盖和整机睡眠分别记结果。合盖测试需另获测试窗口，防止目标机自动挂起断联。
- 发生 GPU hang、画面损坏或不可恢复黑屏时回退上一外部 EFI，不动内置启动链。

完成条件：固定 build + 固定源码补丁 + 固定 EFI 可复现内屏输出、亮度与显示恢复；明确 Metal 仍未实现。

## M4 — 整机基础功能

依次实施，逐项独立验收：

1. **USB 与输入**：补全物理端口；VoodooPS2 键盘/JIS；Synaptics I²C 触控板及多指手势；运行时 GPIO/IRQ 对照。Wacom 触屏/笔单列后续任务。
2. **网络**：AX201 固定 Tahoe fork/构建，安装器与桌面分别验证；蓝牙与内建 USB 映射联调。连接、断开、重连、2.4/5GHz 和唤醒后状态分别记录，不承诺 AWDL/AirDrop。
3. **音频**：ALC285 的 GPIO amp fixup 与 pin 配置；Tahoe 的 AppleHDA 替代路线单独分支，禁止同时加载冲突音频栈。扬声器、耳机、耳麦、内建数字麦克风各自验收。
4. **电池/电源/摄像头**：基于真实 EC 字段选择实现；验证插拔电源、电量读数、充电状态、CPU idle/温度、RGB 摄像头。系统睡眠仅在可恢复的测试窗口开展。

完成条件：每个功能有具体测试步骤、日志、已知缺陷及回退版本，而不是仅列“驱动已加载”。

## M5 — 独立 Xe 加速研发与转换形态

- WhateverXe 当前 Big Sur 支持与 Latitude Tahoe Gen11→Gen12 路线分别建实验分支，先做源码与接口差异分析，不混装它们的图形插件。
- 先确保 framebuffer 与 accelerator attach 可共存，再检查 GPU command submission、context/CSB、shader ISA、同步/缓存与 hang recovery。
- Metal device 枚举、窗口合成、长期 GPU 压测、OpenGL 与视频硬解是不同验收项目。显示容量变成“1536MB”或出现色块不算成功。
- Wacom 触屏/笔、ISH 旋转/hinge、360°键盘屏蔽和 Sure View 热键另设任务。指纹/IR 登录不作为达到基础可用桌面的前置条件。

完成条件：存在可复现的正常加速桌面和稳定性证据；在此之前始终标记为研究中，不估计必然完成日期。

## 早期首轮优先队列（历史）

1. 完成来源/许可证清单与 M0 记录，提交本地 Git 检查点。
2. 审阅 HP ACPI namespace 和固定版 Sample，准备 M1 离线构建及校验工具。
3. U 盘只读访问与可用空间已解决（92.40GiB）；继续研究保留 Ventoy 的介质方案，最终安装目标仍未指定。
4. 到达需要手动 BIOS/外部启动的边界时停下并仅报告阻塞。没有新授权时，不自动重启以“继续推进”。

补充：已尝试 Apple 官方 mesu/gdmf 元数据入口，当前分别遇到 HTTP 403 和证书链/transport 错误，没有关闭 TLS 验证。候选 build 仍只来自固定研究来源，未取得或验证安装镜像；见 [安装介质状态](../manifests/installer-readiness.json)。
