# 构建环境与来源核验

核对日期：2026-10-16。目标按本项目定义为 macOS Tahoe 26 / Darwin 25，设备为 HP Elite Dragonfly G2。版本、完整提交、发布资产及许可证见 [`manifests/core-sources.json`](../manifests/core-sources.json)。没有下载发布压缩包；发布摘要仅照录 GitHub Releases API 的官方 `digest` 字段。

## 上游版本与 Darwin 25 声明

选用每个上游当前可获取的最新稳定 Release。OpenCorePkg 的用户参考版本为 1.0.7；截至核对日期，上游最新稳定版已是 1.0.8，因此 manifest 固定为 1.0.8。

| 来源 | Darwin 25 / Tahoe 26 的上游证据 | 对 Elite Dragonfly G2 的验证 |
|---|---|---|
| OpenCorePkg 1.0.8 | 发布说明没有明确写 Darwin 25 或 Tahoe 26；本次只记录为通用引导器来源，不把 1.0.7 参考版本当作支持证明。 | 未验证 |
| Lilu 1.7.2 | tag README 说明 macOS 26 及以下默认启用，范围包含目标系统。 | 未验证 |
| VirtualSMC 1.3.8 | tag README 说明支持 macOS 10.4 及更新版本；另说明 26 及以下默认启用相关 Lilu 增强。 | 未验证 |
| VoodooPS2 2.3.7 | README/发布说明介绍 PS/2 输入功能与修复，但没有 Darwin 25/macOS 26 支持范围。 | 未验证 |
| VoodooI2C v2.9.1 | README列出控制器世代和设备类别，没有 Darwin 25/macOS 26 支持范围。 | 未验证 |
| IntelBluetoothFirmware v2.4.0 | 发布说明提示 Monterey 及更新版本需要额外配置；没有明确列出 Tahoe/Darwin 25 的测试结果或支持上限。 | 未验证 |
| NVMeFix 1.1.3 | tag README 明确写支持至 macOS 26，发布说明也提到 macOS 26 常量。 | 未验证；具体 NVMe SSD 组合亦未测试 |

“上游声明包含目标版本”只复述来源文档，不等于本设备已测试。特别是键盘/触控板、I2C 控制器、蓝牙芯片和 NVMe 型号的匹配仍需独立硬件证据。

### 许可证归类

- **BSD-3-Clause**：OpenCorePkg、Lilu、VirtualSMC、NVMeFix。NVMeFix 的 GitHub 仓库元数据返回 `NOASSERTION`，但 tag `1.1.3` 的 `LICENSE.txt` 是三条款 BSD 文本；manifest 同时保留元数据差异。
- **GPL-3.0**：VoodooI2C、IntelBluetoothFirmware。以各自 tag 中的 `LICENSE.txt` / `LICENSE` 为准。
- **其他**：VoodooPS2 是 Apple Public Source License 2.0（APSL-2.0）；其 GitHub API 许可证字段为 `NOASSERTION`，manifest 记录了源许可证文件。

这些是仓库级许可信息；打包前仍应保留各上游文件及其依赖各自的许可声明。

## 本机只读工具清点

本机是 Linux `x86_64`。已检测到：

| 工具 | 本机版本 / 状态 |
|---|---|
| clang / clang++ | 21.1.8，默认目标 `x86_64-unknown-linux-gnu` |
| GNU Make | 4.4.1 |
| CMake | 4.4.3 |
| Ninja | 1.13.2 |
| Python | 3.13.15 |
| git | 2.55.0 |
| iasl | Intel ACPICA 20260930 |
| acpiexec | Intel ACPICA 20260930 |
| Docker CLI | 存在；Docker daemon、Compose 插件和构建镜像未验证 |

当前 PATH 中未发现 `xcodebuild`、`xcrun`、`xcode-select`、`ocvalidate`、`gcc`、`nasm`、`flex`、`bison`、`zip` 或 `unzip`。没有安装或升级任何工具。

以上为首次盘点快照。后续主代理从固定官方 OpenCore 1.0.8 发布包取得静态链接的 Linux `ocvalidate`，已在本机直接运行；没有安装到 PATH，也不需要在 NixOS 修改 ELF loader。官方 Sample 与项目 VESA 原型均通过匹配版本验证，详细结果见 [VESA 原型](vesa-prototype.md) 和 [验证记录](verification.md)。标准库 `zipfile` 用于读取发布包，无需为此安装 unzip。其他 kext 源码构建环境仍须按各固定项目实际脚本核实。

## Linux 上可做的构建与校验

1. **ACPI 源表**：本机现有 `iasl` 可编译/反汇编 ASL 与 AML；`acpiexec` 可在用户态执行 AML 方法作有限模拟。可在后续从受控输入的 `.dsl` 编译 `.aml`，并用 `iasl -d` 检查反汇编结果。Intel ACPICA 官方文档确认 iASL、AcpiExec 属于 ACPICA 用户态工具，Unix/Linux 有对应构建支持。它们不能证明真实固件、设备资源、睡眠/唤醒或目标机器上的 ACPI 行为正确。
2. **ocvalidate**：使用 OpenCorePkg 1.0.8 官方包中静态链接的 Linux binary，与本工程 schema 对齐。无需为单独获取验证器启动完整 OpenCore Docker 构建；源码构建路径留作后续可选工具链研究。
3. **OpenCore 本体**：上游也有 Linux Docker 构建任务。它使用项目的构建脚本和预备的 UDK/工具链环境，不等同于在宿主机直接调用一个 clang 命令；本机的 `nasm`、归档工具缺失，Docker daemon/Compose 环境也尚未验证。

## Kext 的 macOS SDK / Xcode 区别

- **macOS SDK** 提供目标系统的头文件、框架接口和构建配置。应按各项目固定版本的构建说明选择 SDK、deployment target、架构与编译器；运行在 Tahoe 不代表每个传统 kext 都必须用 macOS 26 SDK 重编译，兼容性仍需单独验证。Xcode 的命令行工具包可带 SDK 和编译器；但 Apple 文档指出 `xcodebuild` 只随完整 Xcode 提供，不属于单独的 Command Line Tools。多个上游 Kext 项目使用 `.xcodeproj` / `.xcworkspace`，因此不能把仅有编译器等同为具备其完整构建环境。
- **MacKernelSDK** 是 acidanthera 提供的附加 XNU/kernel-extension 头文件与库，不是 Apple 的 macOS SDK，也不能替代 Xcode 工具链。VoodooI2C 的官方构建文档明确要求 macOS、Xcode 和目标 OS SDK，并说明该项目另用 MacKernelSDK、VoodooInput 等依赖。
- 本机没有 Apple SDK、Xcode 或 `xcodebuild`；clang 21.1.8 已实测能交叉产生 x86_64 Mach-O 对象。固定 Latitude 的 WEG CLI 脚本直接使用 clang，MacKernelSDK/Lilu 资源已让 19/20 C++ 单元通过语法探测，其余缺生成资源。完整 kext 构建还要处理资源生成、支持 `-kext` 的链接器及实际库依赖，不能仅以“缺 Xcode”作为阻塞。后续核实与实验见 [framebuffer 构建就绪度](framebuffer-build-readiness.md)；这些结果不能外推到其他全部 kext。

后续已解决上述 WEG 资源/链接器缺口：Python 生成器、23 对象编译及 Linux 版 ld64 956.6 链接成功，输出确为 `MH_KEXT_BUNDLE`。LLVM 21 的析构 lowering 通过保留原生析构段的后端选项适配；工具链与产物均有固定哈希，详见上链文档。尚未进行 macOS loader、内核 ABI 或 HP 显示测试。

## 官方参考

- [OpenCorePkg 1.0.8 Release](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8)、[ocvalidate README](https://github.com/acidanthera/OpenCorePkg/blob/1.0.8/Utilities/ocvalidate/README.md)、[上游 Linux CI](https://github.com/acidanthera/OpenCorePkg/blob/1.0.8/.github/workflows/build.yml)
- [Intel ACPICA 下载与 Linux 工具说明](https://www.intel.com/content/www/us/en/developer/topic-technology/open/acpica/download.html)、[ACPICA 项目](https://acpica.org/)
- [Apple：安装 Xcode Command Line Tools](https://developer.apple.com/documentation/xcode/installing-the-command-line-tools/)、[Apple：Xcode SDK 与系统要求](https://developer.apple.com/xcode/system-requirements/)
- [VoodooI2C Build Environment](https://github.com/VoodooI2C/VoodooI2C/blob/v2.9.1/Documentation/Build%20Environment.md)、[MacKernelSDK](https://github.com/acidanthera/MacKernelSDK)
