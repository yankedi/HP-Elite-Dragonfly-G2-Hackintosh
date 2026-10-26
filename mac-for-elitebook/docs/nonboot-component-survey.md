# 不启动 macOS 的组件验证范围

核查日期：2026-10-16。范围限于本机已有证据、已安装工具和上游文档；本调查没有启动 macOS、访问远端设备或接触 USB。AcpiExec 实验材料保存在被 Git 忽略的 `.local/nonboot-survey/`。图形补丁原始方法的实际 host tests 另见 [图形组件验证](nonboot-graphics-validation.md)。

## 结论

**首次启动 macOS 不是所有后续工作的唯一入口。** ACPI 源表、HID report descriptor、kext 二进制结构和源代码/依赖的一部分可以在启动前独立检查；AcpiExec 还可安全地执行我们自己的 SSDT 的受控分支。首次在目标机运行 macOS 仍是验证实际驱动加载、设备绑定、输入行为、图形加速、睡眠/唤醒等硬件运行时结论的必要证据，但不是这些离线工作的前置条件。

| 组件 | 不启动 macOS 可验证 | 离线结果不能证明 |
|---|---|---|
| ACPI | ASL/AML 编译和反汇编、对象/方法静态审阅；在隔离命名空间中检查自有 AML 的受控分支、返回对象和合成资源描述符 | OEM 完整 namespace 无冲突、EC/GPIO/I²C 真实资源、设备电源/中断、睡眠唤醒或目标机运行行为 |
| HID | 已采集 report descriptor 的格式、usage、report ID、字段位宽及声明范围 | I²C 控制器绑定、IRQ 实际到达、设备报告值正确、触控手势/笔压/休眠唤醒 |
| kext | 源码和补丁审阅、交叉编译/链接、Mach-O 类型、依赖与可见符号静态比对 | Tahoe 对应内核的实际 ABI、Apple 私有符号解析、加载/匹配/初始化和硬件功能 |
| QEMU/OVMF | 若具备工具，可检查虚拟 UEFI、OpenCore 路径和虚拟 PCI/virtio 设备 | HP 固件/ACPI/EC、Dragonfly G2 的 I²C/HID、Intel `8086:9a49` 原生驱动或真实 Metal 能力 |

## ACPI 与 AcpiExec

### 已有静态证据与安全边界

- 本机 `iasl` 和 `acpiexec` 均为 Intel ACPICA `20260930`。本轮保存了 `acpiexec -h` 的原始输出及 SHA-256：`.local/nonboot-survey/acpi/acpiexec-help.stdout.txt`，`4d03d0a0811f4f05093553bf40835c6b3230916c5550a30ac5c63deefac0ad91`。帮助确认 `-l` 是 “Load tables and namespace only”、`-di` 禁止初始化期间执行 `_STA`/`_INI`、`-do` 禁止 Operation Region 地址模拟。
- `-l` 是避免自动进入常规 namespace 初始化阶段的选项；它**不是“不执行任何 AML”的沙箱**。ACPICA 文档记录，表加载时执行的 module-level AML opcode（例如表外层的 `If`/`Store`）仍会执行。[A1] `-di` 只抑制 `_STA`/`_INI`，也不能当成对任意 OEM AML 的通用保护。本实验因此只加载自有 SSDT 和无方法的本地上下文 fixture，没有加载 OEM 表，也没有调用 OEM EC、`_INI` 或 `_REG`。
- 本机已知的完整表问题仍然存在：此前共享 namespace 的 `iasl -da -dl` 因 `AE_ALREADY_EXISTS` 失败，见 [ACPI 部署前审阅](acpi-preflight.md) 和 [验证记录](verification.md)。逐表反编译成功不等于整套 OEM 表能无冲突装入。`-l` 不会修复重名，也不证明完整 namespace 正确；整套表的 AML module-level code 也不能因为用了 `-l` 就视为未执行。因此本轮不尝试加载 OEM 表集。
- 在只读 inventory 中，`TPD0`/`TPL0` 的 GPIO/IRQ 值由 `GNUM(GPDI)`、`INUM(GPDI)` 等动态求值；AML 模板中的零值不是实机 GPIO pin。静态查看资源模板、或用合成 namespace 让纯 AML `_CRS` 返回预设资源，可以检查资源 descriptor 编码、字段和值的传递；它不能验证实际 pin、IRQ 路由、控制器状态或固件最终选出的资源。[H1] [H2]
- 如果未来要运行某个 OEM 方法，必须逐层确认其调用图和 Operation Region 依赖；本项目当前禁止执行真实 OEM EC、`_INI`、`_REG` 方法。对有硬件副作用或未知调用链的方法只做静态审阅，不以仿真填充值代表硬件。

### 对真实 SSDT-PLUG AML 的有限实验

实验加载的是项目现有 `build/vesa-prototype/EFI/OC/ACPI/SSDT-PLUG.aml`，SHA-256 `24956a41669b37fce98f09b9b6d28475a099693bb3522391d35609415e0ffed2`（ASL 源 `acpi/SSDT-PLUG.dsl` SHA-256 `aab42b4ec4d952cadfe40704a1e561e528f81cb4f9b1fed2fd3aacca84ef570f`）。为满足它声明的 `External (\_SB.PR00, ProcessorObj)`，仅用私有 fixture 建立空的 `\_SB.PR00` Processor namespace 节点；fixture 不含方法、资源或插件实现，未替代被测 SSDT，也不是 OEM 表。

受控 Darwin 分支命令（输入的 UUID buffer 和 package 都是 AcpiExec 测试参数，不是硬件数据）：

```sh
/run/current-system/sw/bin/acpiexec -l -b \
  'Osi Install Darwin; Load build/vesa-prototype/EFI/OC/ACPI/SSDT-PLUG.aml; Namespace \_SB.PR00 5; Methods; Evaluate \_SB.PR00._DSM (01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10) 0x0 0x0 [0x0]; Evaluate \_SB.PR00._DSM (01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10) 0x0 0x1 [0x0]; Quit' \
  .local/nonboot-survey/acpi/SSDT-CPUFIX.aml
```

结果：`acpiexec` 退出码 0；动态加载报告成功，`\_SB.PR00._DSM` 出现在 namespace。Function 0 返回单字节 buffer `03`；Function 1 返回 package `("plugin-type", 1)`，与实际 SSDT-PLUG AML 中的代码一致。对照运行未执行 `Osi Install Darwin`，AcpiExec 默认 OSI 列表没有 `Darwin`，加载后没有 `_DSM` 对象。对照运行退出码同为 0。这证明的是**当前 AML 在 ACPICA 中、指定 synthetic Processor 和 OSI 列表条件下的代码路径/返回值**，不是 OpenCore 实际注入结果、AppleACPIPlatform 行为或 Tiger Lake 电源管理有效性。

可复核材料均在 `.local/nonboot-survey/acpi/`：

| 材料 | SHA-256 / 结果 |
|---|---|
| Darwin 分支命令记录 | `controlled-osi.command.txt`：`123362fecaa0b0d8e662e1b2bd2b808d1de8b7b6e3ffe4ef655742080c2ffb97`，记录 exit 0 |
| Darwin 分支 stdout | `controlled-osi.stdout.txt`：`94350cf7d15bdbea46ff77cc08aa21d07cd8ad005a667ccca3d57d41287b7ab5` |
| 默认 OSI 对照命令记录 | `default-osi.command.txt`：`fb74eb8ba93924d34ea1666090d1a5eea6b757c98f1ffa30ad3ba11cbb24e9d0`，记录 exit 0 |
| 默认 OSI 对照 stdout | `default-osi.stdout.txt`：`c47eeaac6ce3c5181e4fe206a21e6fbd3d63267de0278ec426a0045500fb6436` |
| fixture ASL / AML | `SSDT-CPUFIX.dsl`：`a6aa99744c99a1e06e35cee88b17a21e42bb13352e9140e04da61cff8654eb83`；AML：`2ee6991deebcea56fc5fd481994c562af444eab09f749221471df36d9fbfb6a6`。编译 exit 0，另有 legacy `Processor()` 关键字 warning |

两次运行的 AcpiExec stdout 均在退出时报告 `ACPI Error: 4 ... Outstanding cache allocations`，尽管进程退出码为 0、`_DSM` 返回符合源码预期；该诊断保留在原始日志中，故不把本次描述为“零诊断的整洁退出”。

AcpiExec 的 `Resources`/`Template` 调试命令及合成 `_CRS`/`ResourceTemplate` 可用于核对 ACPI namespace 对象、descriptor 类型/长度/flags 和纯 AML 计算结果；若方法访问 EC、GPIO 或其他 Operation Region，应使用经审阅的隔离 stub 或只看静态模板，不将模拟值表述为实测。当前实验没有另造 `_CRS` toy 实现，也没有拿合成资源替代 TPD0/TPL0。

## HID report descriptor

采集文件已存在于私有硬件 capture，且有对应脱敏 inventory SHA：Synaptics `SYNA30B6` descriptor 700 bytes，SHA-256 `0ee8e6bddf6ee6adf071cdb72983bb0970e2b20e5363ee64bcccc208762cec86`；Wacom `WACF4233` descriptor 843 bytes，SHA-256 `5ad4378537251bc2c6bdf43cec57b542aba7b709028ab02906a80afeb6bcc217`。[H1] Linux HID 文档说明 report descriptor 是描述 report 类型、usage 和字段位布局的固定字节序列，可离线解析；传输层再负责收发实际 reports。[H3]

因此，使用本地 HID parser 可检查 descriptor 是否可解析、usage/collection、report ID、字段长度、逻辑范围和设备宣告的 multitouch/pen 字段。它不证明实机真的发送符合描述的数据，也不能证明 I²C host controller attach、GPIO/IRQ 中断链、macOS satellite 匹配、手势、笔压/倾斜数据实际工作、休眠或唤醒。初始调查只核对长度与 SHA，未安装 parser；后续已使用隔离固定的 hid-tools 0.12 完成 [真实 parser 验证](nonboot-hid-validation.md)，两份输入解析及两个非法输入反例均得到预期结果。

## kext 格式、ABI 与运行时

- macOS kext 是供 XNU/macOS kernel loader 识别的 Mach-O kernel extension bundle；它不是 Linux `.ko`，Linux 内核不会直接加载或执行 macOS kext。[A2] Linux 上可以进行源代码/补丁审阅、交叉编译、真正的 `MH_KEXT_BUNDLE` 链接、解析架构/Load Command/未定义符号，并与固定版本的开源依赖导出表做静态比对。
- 本项目已有 patched WhateverGreen 的 Linux 编译与真实 kext-link 记录：23 个对象、Mach-O filetype 11、x86_64、固定产物 SHA；查询的 18 个 Lilu 相关符号存在于固定 Lilu 1.7.2 导出表。[A3] 这是有价值的构建/格式/部分依赖证据，不是 Tahoe kernel ABI、Apple framebuffer 私有接口或 HP 硬件工作的证据；不能推广到所有其他 kext。
- 当前没有 Tahoe 目标 build 的运行内核、匹配 Kernel Debug Kit/kernel symbol 信息和准确 Apple 系统驱动 binary。缺这些输入时，不能完成针对目标 build 的内核/私有 KPI 符号解析、结构体与 vtable 布局兼容、具体 Apple 驱动实现/导出符号、IOKit match/attach、kernel loader 初始化、代码签名/系统策略接受或运行稳定性验证。Apple 的 bundle/依赖文档解释了由系统 kernel loader 和依赖 kext 执行加载链接；只有 Linux 交叉链接不经过该加载器。[A2]
- 若之后取得可信的目标 build 与对应 Apple 驱动/KDK，可先在隔离 macOS 虚拟机中做**该虚拟机环境**的 loader/依赖检查；这仍然是在 VM 内启动 macOS，不属于免启动方案。它仍需目标机实测才能证明物理设备匹配和硬件路径。不能以 Windows/Linux 驱动 binary 或其他 macOS build 的 Apple driver binary 代替目标 build 的 ABI 证据。[H1] [A2]

## QEMU / OVMF 与显卡边界

初始调查时 PATH 没有 `qemu-system-x86_64`，活动系统 share 路径下也未找到 OVMF firmware image，因此该次调查没有搭建虚拟机。后续已取得独立固定工具链并开展 [实际 VM/Recovery 实验](nonboot-vm-validation.md)。测试覆盖范围仍限于所选虚拟机板型、OVMF UEFI、OpenCore 与所配虚拟设备交互。OVMF 面向虚拟机平台；QEMU 设备模型是仿真或虚拟化出来的 guest device。[A4]

QEMU 的 virtio-gpu 是 VirtIO 半虚拟化 GPU/display 设备，即使使用 virgl 等后端提供 3D，也不等于 Intel Tiger Lake `8086:9a49` 的 Xe 驱动或这台机器的内屏/Metal 测试。[A5] 用 OVMF + virtio 显卡看到画面，只能说明虚拟显示路径。GPU PCI passthrough 则需要把真实 GPU 从宿主机驱动解除绑定并交给 VFIO；Linux VFIO 文档明确说明该步骤。[A6] 它会涉及本项目禁止的 host driver unbind，故不是可用实验路线，也不应在本机尝试。

## 成本 / 价值排序

| 优先级 | 路线 | 成本 | 对本机问题的价值与边界 |
|---:|---|---|---|
| 1 | 静态 AML/ASL 审阅、独立 iasl 编译/反汇编、plist/ocvalidate、已有源补丁和 Mach-O/符号核对 | 低 | 便宜且可重复，适合尽早发现语法、路径、格式和依赖错误；不声称启动或硬件可用 |
| 2 | 自有 AML 的 AcpiExec 受控 OSI/方法验证；必要时对纯资源方法提供 synthetic namespace | 低 | 可验证代码分支、返回类型和值、资源 descriptor 结构；不能补上 OEM 全表 namespace 冲突或物理硬件行为 |
| 3 | 对已采集 HID descriptor 做离线解析 | 低 | 可减少 descriptor/usage 猜测；不覆盖 I²C/IRQ、实时报文和手势验证 |
| 4 | 针对固定 kext 版本的源码、构建产物、符号与目标 OS/KDK 对照 | 中至高 | 可逐步提高 ABI 线索质量；没有准确 Apple kernel/driver binary 时，目标 ABI 仍有硬边界 |
| 5 | QEMU + OVMF 虚拟固件/虚拟设备预检 | 中 | 仅在需要验证 UEFI/OpenCore 与虚拟设备的情况下值得投入；对 G2 EC、I²C、9A49 原生驱动的收益很低 |
| 6 | macOS 虚拟机内核/kext 测试 | 高 | 可验证所用 macOS build 在该 VM 里的 loader/虚拟硬件路径；不能替代物理 G2 设备测试 |
| 7 | 目标机 macOS 功能级验证 | 高 | 对真实驱动绑定、I²C/HID、图形、音频、睡眠等最有决定性；只应作为这些 runtime 结论的证据，不是前述离线工作的入口门槛 |

## 参考与证据索引

- **本机项目记录：** [外围设备与 HID 采集索引](peripherals.md)、[ACPI 部署前审阅](acpi-preflight.md)、[本机工具与构建边界](build-environment.md)、[WhateverGreen 链接就绪度](framebuffer-build-readiness.md)、[验证记录](verification.md)、[脱敏硬件 inventory](../hardware/elite-dragonfly-g2.json)。
- **H1 / H2：** inventory 及其 `.local/hardware/20261015T174049.365004Z/` 原始/分析证据；不在本轮复采。
- **A1 — ACPICA：** [ACPICA changes.txt 固定 commit `fe061f034dcc521f980d8aa00b4139611d3a2ada`](https://github.com/acpica/acpica/blob/fe061f034dcc521f980d8aa00b4139611d3a2ada/documents/changes.txt)，记录 AML 可执行 opcode 在 table load 阶段的行为。`acpiexec -h` 则以本机 `20260930` 二进制为准。
- **A2 — Apple KEXT：** [KEXT bundle anatomy](https://developer.apple.com/library/archive/documentation/Darwin/Conceptual/KEXTConcept/KEXTConceptAnatomy/kext_anatomy.html)；[Mach-O Programming Topics](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/MachOTopics/0-Introduction/introduction.html)。用于说明格式、kernel loader 和依赖概念，不是 Tahoe build 的 ABI 说明。
- **A3 — 本地链接证据：** [链接核查 manifest](../manifests/framebuffer-link-check.json) 及 `docs/framebuffer-build-readiness.md`；只覆盖所记录的 WEG/Lilu 版本。
- **A4 — 虚拟固件：** [TianoCore OVMF](https://www.tianocore.org/tianocore-wiki.github.io/platforms-packages/platform-ports/ovmf.html)；OVMF 是供虚拟机使用的 UEFI firmware 项目。
- **A5 — QEMU 10.2 文档：** [virtio-gpu](https://qemu.readthedocs.io/en/stable-10.2/system/devices/virtio/virtio-gpu.html)、[device emulation](https://qemu.readthedocs.io/en/stable-10.2/system/device-emulation.html)。
- **A6 — Linux VFIO：** [VFIO kernel documentation](https://docs.kernel.org/driver-api/vfio.html)，含从宿主驱动 unbind 并绑定到 VFIO 的操作前提。
- **H3 — Linux HID：** [HID report descriptors](https://docs.kernel.org/7.1/hid/hidintro.html)、[HID transport drivers](https://docs.kernel.org/7.1/hid/hid-transport.html)。

[H1]: ../hardware/elite-dragonfly-g2.json "脱敏硬件 inventory"
[H2]: verification.md "采集与 ACPI 验证记录"
[A1]: https://github.com/acpica/acpica/blob/fe061f034dcc521f980d8aa00b4139611d3a2ada/documents/changes.txt "ACPICA 固定 commit"
[A2]: https://developer.apple.com/library/archive/documentation/Darwin/Conceptual/KEXTConcept/KEXTConceptAnatomy/kext_anatomy.html "Apple KEXT bundle anatomy"
[A3]: ../manifests/framebuffer-link-check.json "patched WhateverGreen 链接记录"
[A4]: https://www.tianocore.org/tianocore-wiki.github.io/platforms-packages/platform-ports/ovmf.html "TianoCore OVMF"
[A5]: https://qemu.readthedocs.io/en/stable-10.2/system/devices/virtio/virtio-gpu.html "QEMU 10.2 virtio-gpu"
[A6]: https://docs.kernel.org/driver-api/vfio.html "Linux VFIO documentation"
[H3]: https://docs.kernel.org/7.1/hid/hidintro.html "Linux HID report descriptor documentation"
