# 验证记录

> **状态说明（2026-10-27）：** 本文保留早期阶段的验证记录，其中“尚未启动 macOS”等表述只适用于各自记录日期。Tahoe 26.6.2 / 25G83 后续已安装；当前硬件功能和稳定性见 [README](../README.md) 与[公开续接入口](continuation.md)。原始 `.local/` 证据未随公开副本提供。

## 2026-10-16：在线采集与本机分析

原始时间：`2026-10-15T17:40:49.365004+00:00`（UTC）。私有目录：`.local/hardware/20261015T174049.365004Z/`。

| 检查 | 证据 / 结果 |
| --- | --- |
| 仓库 | `git init -b main` 成功；工作目录 `/home/USER/lib/mac-for-elitebook` |
| 远端采集 | `python3 scripts/collect_hardware.py --host <target>`，15 组文本观察退出码均 0，白名单二进制采集退出码 0 |
| 完整性 | `make verify-evidence CAPTURE=…`：62 个文件的长度和 SHA-256 一致；ACPI/EDID 校验和与 VBT 签名通过 |
| 脱敏 | `scripts/summarize_hardware.py` 从原始 DMI 的白名单字段生成库存；不输出设备序列号、UUID、Windows 密钥 |
| ACPI 首次尝试 | `iasl -da -dl` 共享 namespace 失败，记录 HP 条件重名与动态表重叠；没有修改固件表 |
| ACPI 后续分析 | `make acpi CAPTURE=…`：32 张 AML 独立反编译，全部退出码 0、输出 DSL；DSDT 和 SSDT6 的 namespace 诊断仍保留 |
| U 盘 | `scripts/inspect_usb.py` 只读元数据：Lexar `21c4:0809`，116.1GiB、MBR/Ventoy；未挂载、未读取剩余空间、未写入 |
| 本机构建空间 | 项目所在文件系统当时约 153GiB 可用；不将另一个 99% 占用的 `/srv` 当作构建目录 |

关键证据 SHA-256：

```text
DSDT: 7afb4e662e79265a1a7c42c1af7ad448c003e8dbfa735b354e77dbb82f1ab343
DMAR: 2ca3fa2c612c438a8bd5a9f2583596f7c680202a4fc2212933c20db63963aa9b
NHLT: a5778dc31aa1a8788ce91f0dd78dc112cb0135a1251fc818db3f77d11b76c096
VBT:  715772cebbc951aef00ddec4bc76fe571c5f4f5dc5c0c26b8171a53f6333241d
EDID: 229597c3c0f0577d85202c7928c8ad4718a7624558e41afde1f8b7dce15adba5
```

## 本轮（2026-10-15）当时未证明的事项

- 没有在 HP 上启动过 OpenCore、Tahoe 安装器或桌面。
- 没有证明内屏 framebuffer、Metal、音频、网络、睡眠、触屏/笔在 macOS 下可用。
- 没有完成 USB 全端口映射，也没有确认 macOS 安装目标。U 盘可用空间后续已通过只读挂载解决，见下节。
- 独立反编译成功不是 OEM DSDT 可重编译证明；没有执行 patched DSDT 注入。
- 本轮不进行任何远端重启、休眠、BIOS/EFI/NVRAM 写入或 U 盘改动。

## 同轮：VESA 原型与源码一致性

- `make prototype`：本机组装 `build/vesa-prototype`；OpenCore 1.0.8 `ocvalidate` 退出 0。验证 13 个引用文件、4 个 AMD64 PE/COFF EFI、5 个 x86_64 Mach-O kext、第三方依赖顺序、编译 SSDT 校验和及 VESA 实验隔离。
- OpenCore、Lilu、VirtualSMC、stock WEG 的发布包摘要与固定官方 GitHub 元数据一致；VoodooPS2 缺少上游摘要，记录本机 SHA-256 `d5483298736ba4b3b82c7203d9a46968c668fb7af732b8b22c2096deb0acf83f`，不伪称已独立核对上游摘要。
- 原型 `EFI/OC/config.plist` SHA-256：`04e0f170468c1aac8bd5e3460122aef1ea0f5f50565ba7f2460a9231511f2c69`；`SSDT-PLUG.aml`：`24956a41669b37fce98f09b9b6d28475a099693bb3522391d35609415e0ffed2`。身份为空/零占位，未部署。
- `scripts/check_framebuffer_sources.py`：固定 WEG `0762cecc…` 与 Latitude `1010490d…`，3/3 原始补丁依序 `git apply --check` 和应用均退出 0。详情与字节摘要见 [补丁核查记录](../manifests/framebuffer-patch-check.json)；未构建 patched kext，未执行下载源码中的安装脚本。
- 完整私有 capture 的临时副本校验通过；仅修改 EDID 一个字节后，同时被 SHA-256 与 EDID checksum 拒绝，没有依赖“缺文件”导致失败。原始证据未被修改。
- 从真实原始 DMI 提取的 3 个有效序列号均未出现在 `hardware/*.json`；Git 忽略检查确保 `.local/`、`.cache/`、`build/`、`dist/` 不进入提交。

上述源码 patch 成功不证明 HP framebuffer 可用，也不证明 macOS 内核链接或运行兼容性。下一步继续推进 Linux 上可执行的 VBT/构建前置分析。

## 同轮：无需重启的后续观察

- 本机构建环境通过 Nix 临时取得 IGT 2.3（约 8.6MiB 下载，无永久 profile 安装），以固定本地 nixpkgs path/NAR 运行 VBT 与 OpRegion decoder；工具元数据和输出均保留在私有分析目录。
- `make vbt CAPTURE=.local/hardware/<capture> DECODER=<intel_vbt_decode>` 复验通过；解析出的内屏路由从 child-device 表读取，未硬编码 DP-A。解码摘要见 [display-analysis.json](../hardware/display-analysis.json)，保留所有 stderr 诊断，未把变长表提示误称为数据截断。
- 追加只读 PCI config、kernel log 和 eDP debugfs 观察：GGC/Gen11+ BDSM/内核预留范围三者印证 512MiB；取得 Linux 面板 PPS 时序和 ASLE BCLM，见 [运行态显示补充](runtime-display-notes.md)。没有执行 MMIO 写入、forcewake、retrain、亮度/显示电源改变。
- 本机 `udisksctl mount --options ro --no-user-interaction` 成功，findmnt 确认 VFS 与 FS 都是 `ro`；exFAT 可用 `99,215,736,832` 字节（92.40GiB）。随后正常卸载；没有修改任何文件、分区或 Ventoy EFI。私有检查 JSON 哈希 `5588d641e242145fac357c797e622d8e69d8bf2fb8d0403c1f6cc04e90816e80`。
- 所有追加运行态证据的长度/哈希与清单复核通过；GMS 大小和预留区间的独立算术一致。`hardware/`、`docs/`、`manifests/` 全文本均未包含从原始 DMI 提取的 3 个有效序列号。

## 同轮：Linux framebuffer 编译阶段

- 固定资源转换器已移植为 Python，完整语义回读通过；修改一字节的 plist 被输入哈希拒绝且没有写出 C++，指向原始 hardware capture 的输出也被拒绝。
- 初次完整编译产生 23 个 Mach-O x86_64 对象，检查发现 LLVM 21 后端引入 userspace atexit 注册；已通过保留 `__mod_term_func` 的后端选项修正，再次完整编译 23/23 并逐对象确认 atexit/dso_handle 导入消失。见 [编译核查记录](../manifests/framebuffer-compile-check.json) 和 [构建就绪度](framebuffer-build-readiness.md)。
- 对象阶段没有链接成 kext，不是 macOS loader/ABI 验证。真实 ld64 链接另行记录，不能将 LLVM 21 `ld64.lld` 忽略 `-kext` 的输出当成功。
- 后续 `make prototype` 仍通过匹配 ocvalidate 及 13 文件引用检查，配置摘要未变；实验源码/对象没有混入 VESA 原型。

## 同轮：Linux 真实 kext 链接

- Luna 本机从固定 cctools-port 源码构建 ld64 956.6；主代理用它执行 `make framebuffer`，23 对象编译/真实 `-kext` 链接均退出 0。与前次独立对象构建的 23 个摘要完全一致。
- 解析 Mach-O 头确认 filetype **11**、x86_64、flags `0x85`，原生构造/析构段及模块入口存在；6 个 load commands 中无 dylib/用户态 loader。未 strip、未签名、未部署。
- 421 个内核/Lilu 导入中，抽取的 18 个 Lilu 类相关符号均在固定 Lilu 1.7.2 RELEASE 中导出；没有 userspace atexit/dso_handle。Tahoe 的 kernel 导出及 ABI 尚无法在缺实际系统环境时核实。
- 产物、私有报告和源码/工具链摘要见 [framebuffer-link-check.json](../manifests/framebuffer-link-check.json) 与 [macho-toolchain.json](../manifests/macho-toolchain.json)。本机构建前置已解决，不能再以缺 Xcode/Apple SDK 作为此 WEG 路线的阻塞。

最终审计：`make check` 通过（13 Python / 16 JSON / 13 Markdown）；链接产物/私有报告/构建脚本/ld64 的哈希、23 个跨目录对象摘要、kext plist 与 VESA 配置摘要全部复核通过。后续阶段的实际阻塞是禁止目标机重启、安装目标/保留介质的部署路径未确定，以及 Apple 官方固定 build 元数据当前无法通过网络取得；不是本地 WEG 无法构建。

## 后续：不启动 macOS 的组件验证

根据用户要求继续探究非启动验证。`make nonboot-graphics` 已在 Linux 用户态执行固定补丁的原始 C++ 方法：7 组 / 655,454 次断言通过，ASan/UBSan 无报告。错误 DP 目标地址、吞掉 PWM 零 duty 两种故障注入均在预期断言处被拒绝；源码缓存和既有 kext 未修改。

该组件测试的所有寄存器、NVRAM 和 IORegistry 操作均指向内存替身；测试过程没有启动 macOS、加载 kext、访问实机或 U 盘。测试补丁逻辑的能力独立于整机测试窗口，不能因首次启动受阻而一并停止。准确覆盖范围与替身列表见 [图形组件验证](nonboot-graphics-validation.md) 和 [证据摘要](../manifests/nonboot-graphics-check.json)。

## 无安装虚拟机与 HID 实验

- 本机 QEMU 11.1.2 / OVMF 202608 / TCG 中实际运行 OpenCore 1.0.8，探针查到 OpenRuntime revision 12，并通过 OpenHfsPlus 的 binding/loaded-image handle 调用其 ComponentName 方法。正例 exit 33；firmware-only 和移除 OpenHfsPlus 的对照均得到预期的 exit 35；3/3 实验通过。两个隔离 profile 的匹配 ocvalidate 均退出 0。
- KVM/AMD host 初次触发 guest P-state MSR `#GP`，TCG 初始 picker 的默认项和工具选择也曾导致超时；失败均被保留，未将退出 0 的 QMP quit 当成功。修正虚拟 profile 和探针识别后才获得上面的实际结果。
- 固定 hid-tools 0.12 实际解析 Synaptics 700B 与 Wacom 843B 描述符，解析检查为零错误；两份上游 CLI exit 0，截断项和保留 Main tag 的反例各 exit 1。报告、源码、依赖、capture 和日志摘要已审阅。
- 初轮 Apple recovery 路线取得签名通过的 92-chunk 清单，但 960,530,321-byte 镜像只返回 1,048,576 bytes；官方 verifier 拒绝，诊断脚本 exit 2。authenticated Range 的不完整响应和 TLS/403 失败均留存。该次没有运行 Apple kernel；下载阻塞已在下述后续实验解决。
- 本轮实验没有安装 macOS、访问目标机、写物理分区/EFI/NVRAM、接触现有 Ventoy 或解绑驱动。虚拟 VARS 写入仅发生在新建映像文件。

复现、摘要和边界见 [VM/Recovery 验证](nonboot-vm-validation.md)、[HID 验证](nonboot-hid-validation.md)、[VM manifest](../manifests/nonboot-vm-check.json)、[Recovery manifest](../manifests/nonboot-recovery-check.json)。

## 后续：解决截断并真正进入 XNU / kext loader

- fresh session + 开放结尾 Range 实际取得余下 959,481,745 bytes，拼成完整 DMG，Apple RSA 签名和 92/92 chunks 通过。公开 `fetch_recovery.py` 又从原 1 MiB 前缀独立续传复现成功；两份完整输入 SHA-256 相同。
- 镜像内 SystemVersion 与 guest `sw_vers` 均为 **26.6.2 / 25G83**，实际 Darwin **25.6.0 / xnu-12377.161.14~5**。旧候选 26.6 / 25G72 未被自动替换。
- 修复虚拟 Haswell 的 stepping=3，以及错误 standalone booter override。原始签名 DMG 实际越过 Apple booter 进入 XNU；验证后的 raw 派生介质自动选择 CoreServices **bootbase.efi**，实际进入 BaseSystem 单用户 shell。
- 6 个独立 VM 均完成 guest `uname`、`sw_vers`、`kextstat`/`kmutil showloaded`、`ioreg` 与 `sysctl` 命令。Lilu DEBUG/RELEASE、stock/patched WEG、1/2 vCPU 分别记录；三种 kext 在六次已加载列表中均存在，匹配版 ocvalidate 六次为 0，无 panic，VM 均已退出。
- 保留真实反例：`-s` 未配 `-liluforce` 时，已加载列表仍包含模块，但 Lilu 主动退出、WEG parent 7。修正后 DEBUG Lilu 可观察 WEG API 请求、PE console 初始化和部分真实加载回调；不能仅凭列表宣称插件已工作。同次 `_kernel_trap` 路由由 VirtualSMC 的通用初始化发起，不是 WEG framebuffer 路径。
- 三个后续 case 仍有 VirtualSMC parent 6 / legacy PMIO；另三个显示 Gen2 MMIO。单 vCPU 对照未解决时序问题，也排除了“只在 stock WEG 出现”的概括。没有把这些诊断隐藏成全通过。
- 有界源码诊断已确认 parent 6 为 Lilu `TooLate`：VirtualSMC 请求晚于 `finaliseRequests()`，随后故意降级 Gen1；`vsmcgen=2` 不能覆盖这个分支。六份 VirtualSMC payload 与固定官方 release 成员逐字节一致。未发现已证实的现有参数修正，具体触发条件仍保留为未解决限制。
- 当前 KC 的 204 个 fileset 符号组可读取；421 个 patched WEG undefined 名称有 419 个精确匹配，两个保留 IOService 名称未精确匹配，但实际模块已加载，静态缺名不能代替 loader 结果。当前 Recovery KC 没有 AppleIntel framebuffer 条目，虚拟机也无 HP GPU/I²C/eDP 直通。

公开执行器、审计器与结果见 [Recovery/kext 验证](recovery-kext-validation.md) 和
[新 manifest](../manifests/recovery-kext-check.json)。这轮证明了免安装的真实内核与 kext
加载路线；HP framebuffer、周边功能、Metal、多用户系统及完整 Recovery GUI 仍未验收。
