# 无安装虚拟机与组件验证

本轮目标：在本机执行不安装 macOS 的组件实验，验证虚拟机能先加载到哪一层，并保留后续可复现入口。

**后续进展**：下文的下载截断已解决，完整签名 Recovery 已核实为 **26.6.2 / 25G83**，
并已实际运行 XNU、进入 BaseSystem 单用户 shell 和检查 kext。
详见[后续内核与 kext 实验](recovery-kext-validation.md)。本页保留第一轮 UEFI 对照与下载失败证据。

## 验证分层

| 层 | 方法 | 证据含义 |
| --- | --- | --- |
| UEFI/OpenCore | QEMU + OVMF，加载固定 OpenCore 1.0.8 和真实 UEFI drivers，再执行检查程序 | 可证明所用虚拟固件下的 EFI 路径和 driver entry/protocol 注册；不涉及 XNU kext loader |
| 图形组件原逻辑 | [原始 C++ host tests](nonboot-graphics-validation.md)，7 组、655,454 次断言及两种故障注入 | 可发现地址/位域/PWM/写序错误；不是物理 GPU、Apple driver 或 Metal 验证 |
| 自有 AML | [受控 AcpiExec](nonboot-component-survey.md)，真实 SSDT-PLUG 的 OSI 分支及 `_DSM` 返回 | 可验证指定 synthetic namespace 下的 AML；不证明 OEM 全表或 HP 电源管理 |
| HID descriptor | [固定上游 parser 实际解析](nonboot-hid-validation.md)既有 capture，两份输入通过、两个反例被拒绝 | 只覆盖声明的 report 结构；实际设备、IRQ 和 macOS 绑定另需验证 |
| macOS 内核/kext | 不安装到磁盘，启动 Apple recovery/BaseSystem，再让 OpenCore 注入 kext | 初轮下载失败；[后续](recovery-kext-validation.md)已取得准确 build 并实际运行 XNU / kext 检查 |

## 本机虚拟化环境

本机约 32GB RAM，`/dev/kvm` 可读写，CPU vendor 为 `AuthenticAMD`。使用固定 Nix store 产物：QEMU 11.1.2、OVMF 202608、GNU-EFI 4.0.2、LLD 21.1.8。Nixpkgs 取自现有内容寻址的 source NAR；不能在没有 Git revision 的情况下把它描述为上游 commit pin。二进制与 firmware 摘要、NAR pin、derivation path 单独留存。

第一轮 KVM/host CPU 实测在 OpenCore 早期触发 guest `#GP`，串口记录 `RCX=0xC0010064`（AMD P-state MSR 地址）；只有直接 firmware/probe 对照成功。仅凭该日志可以定位出错现场，不能证明所有 AMD KVM 组合都不兼容。随后改用 TCG 的 `Haswell-noTSX` Intel CPU 模型，避免更改宿主 KVM 参数或宿主驱动。

初次 TCG 运行已进入真实 OpenCore picker，但默认候选 `NO NAME` 指回自身 EFI fallback，未执行 probe，实验被判为超时失败。截图确认 picker 后，补回官方 archive 内的 `.contentVisibility=Disabled` 和 `.contentFlavour=OpenCore`，避免自身 fallback 被重新列为系统；没有通过忽略超时来“修复”测试。最终 TCG CPU 明确关闭不受该后端支持的 `pcid`、`tsc-deadline`、`invpcid` 特征。

测试 VM 的磁盘只包含新建的普通 FAT 映像，变量存储是 OVMF VARS 的独立副本。没有安装目标磁盘、网络、共享宿主目录或 PCI passthrough。虚拟 VARS 的修改只发生在 `.local/nonboot-vm/run-*/` 文件；它不是 EliteBook 的 EFI/NVRAM。

VM profile 从官方 Sample 生成，清空 ACPI、Kernel Add、设备注入和平台身份更新。它与 HP VESA 原型分开；不能把虚拟机通过当成 HP 原型通过。检查程序 `tests/uefi_component_probe.c` 是实际 PE/COFF UEFI application，调用真实 firmware Boot Services 查询：

- OpenRuntime protocol GUID `570332E4-FC50-4B21-ABE8-AE72F05B4FF7`，revision 必须等于 12；来自固定 OpenCore [协议头](https://github.com/acidanthera/OpenCorePkg/blob/6fe4d15cb66596d99d8cfedce69d8fc6dad71886/Include/Acidanthera/Protocol/OcFirmwareRuntime.h)。
- OpenHfsPlus 的 EFI driver-binding handle、对应 loaded-image handle，并实际调用 ComponentName `GetDriverName("eng")`。返回值必须等于固定源码中的 `Fsw hfsplus File System Driver`；源码 [fsw_efi.c](https://github.com/acidanthera/OpenCorePkg/blob/6fe4d15cb66596d99d8cfedce69d8fc6dad71886/Staging/OpenHfsPlus/fsw_efi.c) 和 [OpenHfsPlus.inf](https://github.com/acidanthera/OpenCorePkg/blob/6fe4d15cb66596d99d8cfedce69d8fc6dad71886/Staging/OpenHfsPlus/OpenHfsPlus.inf)。
- 虚拟 GOP 与 ACPI 2.0 table 是否存在。

probe 通过 QEMU debugcon 输出，使用 `isa-debug-exit` 给出机器可判定的结果。它没有模拟 OpenRuntime/OpenHfsPlus，也没有把 kext 改编成 EFI 程序。测试记录中的 `MACOS_KERNEL_EXECUTED=0`、`KEXT_EXECUTED=0` 表示这一实验的设计范围，并非能检测任意内核历史的通用探针。

## 虚拟机实测结果

最终 **3/3 实验通过**；两个 OpenCore VM profile 均通过匹配版本的 ocvalidate。真实返回值如下：

| 实验 | OpenRuntime rev 12 | OpenHfsPlus binding / name | 虚拟 GOP / ACPI | guest exit |
| --- | --- | --- | --- | --- |
| 直接 OVMF + probe 对照 | 无 | 无 | 有 / 有 | 35，预期缺组件 |
| OVMF → OpenCore → probe | 有 | 有，driver-name 函数调用成功 | 1024×768 / 有 | 33，成功 |
| OpenCore 中移除 OpenHfsPlus | 有 | 无 | 1024×768 / 有 | 35，正确检测缺失 |

OpenCore 默认不把工具设为自动启动默认项，因此无人值守执行器通过 QMP 保存 picker 截图后，向唯一可见的 ComponentProbe 项发送 Enter。只有 probe 输出符合预期且进程返回指定 debug-exit code，才判定成功。

这里还纠正了探针本身的一个假设：该加载路径没有保留带 `OpenHfsPlus.efi` 名字的 image device path，仅凭文件名检测会漏报。改为检查真实 binding、loaded image 并调用固定上游的 ComponentName 函数后，正例和移除 driver 的反例呈现不同结果。没有为让测试通过而伪造接口或放宽“缺少 HFS”判断。

这证明的是 **UEFI driver entry/协议注册与一次 driver 方法调用**，本轮没有创建 HFS+ 卷或测试其文件读取。结果清单见 [VM 证据摘要](../manifests/nonboot-vm-check.json)，完整报告在 `.local/nonboot-vm/run-v8rrfd3i/report.json`；SHA-256 `77f89bcd91d5221220b92d97a0bfbd299b2848952185b96373abadcd97903ef8`。

## 初轮 Recovery 下载阻塞（后续已解决）

固定 OpenCore release 内附的 `macrecovery.py` 使用其 Tahoe/latest 查询示例，Apple 返回产品 `140-93589`。这是路线调查，**不是对既有 26.6 / 25G72 基线的替换或确认**；产品编号及 CDN 日期不能替代系统 build 信息。

本轮实际结果：

- 取得 3,604-byte chunklist，穷尽原始 verifier 的生成器后，Apple RSA 签名校验通过。
- 签名清单声明 92 chunks、镜像总长 **960,530,321 bytes**。
- 下载的 `BaseSystem.dmg` 只有 **1,048,576 bytes**，首 chunk 应有 10,485,760 bytes；原始 macrecovery 和独立诊断均拒绝此输入。
- 带原始 AssetToken 的 Range 请求返回 `206` 和匹配的 Content-Range，但从 1MiB 位置开始的正文为零字节；curl 返回 **18**（响应未完整）。从 0 开始请求 10MiB 也只得到 1MiB。加查询参数没有改善。
- `https://oscdn.apple.com` 遇到 hostname mismatch；没有关闭证书验证。对同一 Apple 路径尝试 `swcdn.apple.com` 的 HTTP/HTTPS 返回 403。
- 将私有 chunklist 副本的签名改动一字节后，原始 verifier 正确拒绝。

因此没有使用这个残缺 DMG 启动，也没有声称 kext 已被 macOS 加载。签名 chunklist 通过不等于镜像完整；Boot Services/EFI driver 通过不等于 XNU kernel extension 可加载。

可复核的输入摘要、诊断退出码、Range 与 TLS 证据索引见 [Recovery 证据摘要](../manifests/nonboot-recovery-check.json)。

## 下一层如何无需安装来测

有完整可信的 BaseSystem 与匹配启动文件后，可以在本机创建**仅有 recovery 介质、没有安装目标盘**的独立 VM。启动 recovery 本身不要求把 macOS 安装到 EliteBook 或虚拟硬盘。应先从系统文件读取 `ProductVersion`/`ProductBuildVersion`，核验目标 Darwin/kernel，再将 Lilu、VirtualSMC 等加入隔离的 OpenCore profile，观察 loader 日志和已加载组件列表。

具体要区分三件事：

1. **注入**：OpenCore 能否解析 bundle、找到依赖并把 kext 纳入所启动内核的集合。
2. **加载/初始化**：目标版本的 XNU 是否接受依赖、符号、ABI 和初始化入口。
3. **设备匹配/功能**：驱动是否匹配并操作真实硬件。

前两层可在具备准确版本输入的 VM/recovery 环境取得部分证据；第三层仍取决于 VM 是否具有相应设备。没有 9A49 的 VM 中，WhateverGreen 可能加载而 Intel framebuffer 根本不 attach；这不能证明 HP 内屏或 Metal。QEMU 虚拟 PS/2、虚拟网络及 GOP 同样不是 HP 的 I²C 触控板、Wi-Fi 或 eDP。

本机为 AMD，直接 KVM/host 已出现一个具体 MSR 异常，未来不能直接照搬 Intel 机器的 VM recipe；本轮选用 TCG 的 UEFI 结果也不代表 Tahoe 的完整指令、性能和内核行为已验证。

## 复现入口

```sh
python3 scripts/check_nonboot_vm.py \
  --qemu <qemu-system-x86_64> \
  --ovmf-code <OVMF_CODE.fd> --ovmf-vars <OVMF_VARS.fd> \
  --efi-include <gnu-efi/include/efi> --lld <lld-link>

python3 scripts/check_recovery_probe.py
```

VM 默认 TCG/Haswell-noTSX，三个实验分别为 firmware-only、OpenCore + 两个 driver、OpenCore 缺少 OpenHfsPlus 的反例。probe 的正常成功退出码是 33；缺组件退出码为 35。反例得到 35 且准确指出缺失组件时，实验判为通过。45 秒超时或 QMP quit 返回 0 均不会被当成成功。

Recovery 诊断默认不联网，验证已有 `.local/nonboot-vm/recovery/` 文件；不完整时退出 **2**。显式 `--download` 可再次执行有 75 秒上限的官方 latest 路线调查。它不自动修改既有 Tahoe 基线，也不自动启动或安装系统。
