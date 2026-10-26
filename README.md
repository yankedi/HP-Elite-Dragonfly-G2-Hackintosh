# HP Elite Dragonfly G2 Hackintosh

**macOS on HP Elite Dragonfly G2 — OpenCore configuration, driver adaptations, build tools, and hardware compatibility notes.**

这是 HP Elite Dragonfly G2 的长期 macOS 移植与研究项目，整合了安装/外围适配工程 `mac-for-elitebook` 和 Tiger Lake 图形研究工程 `tgl26-usb`。

**当前状态（2026-10-27）：macOS Tahoe 26.6.2 / 25G83 已安装并进入桌面；实验 GPU 加速存在严重稳定性问题。** 软件显示对照可进入可用桌面并完成约 62 分钟观察，尚不能据此宣称长期稳定。

## 项目入口

| 内容 | 入口 |
| --- | --- |
| 当前硬件支持情况 | [硬件与功能状态](docs/STATUS.md) |
| OpenCore 配置与 ACPI | [EFI 配置示例](EFI/README.md) |
| 实测图形源码、本地补丁与构建来源 | [graphics](graphics/README.md) |
| 加速 panic 与软件显示对照 | [实验报告](docs/GRAPHICS-STABILITY.md) |
| 四次 panic 文本和公开证据索引 | [evidence](evidence/README.md) |
| 安装、ACPI、外围、诊断脚本 | [mac-for-elitebook](mac-for-elitebook/README.md) |
| 历代图形实验与自研工具 | [tgl26-usb](tgl26-usb/README.md) |
| 构建与验证说明 | [BUILDING](docs/BUILDING.md) |
| 目录与发布范围 | [REPOSITORY](docs/REPOSITORY.md) |
| 新的上游求助 issue 草稿 | [ISSUE-DRAFT](docs/ISSUE-DRAFT.md) |
| 首次上传版本与检查记录 | [PUBLICATION](docs/PUBLICATION.md) |

## 实测机器

- **机型：** HP Elite Dragonfly G2，主板 8716，BIOS T90 01.25.00
- **CPU：** Intel Core i5-1135G7（Tiger Lake，4 核 8 线程，6 MiB L3）
- **GPU：** Intel Iris Xe `8086:9a49`，80 EUs / 10 个 Gen12 subslices
- **内存：** 16 GiB LPDDR4X-4266
- **内屏：** 1920×1080 eDP
- **系统：** macOS Tahoe 26.6.2 / `25G83`，OpenCore 1.0.8

## 当前最重要的结果

启用实验 TGL 图形组合时，近期四次启动分别在 **334.543、339.564、273.073、252.560 秒**出现内核 panic。取消该组合的加载、保留固件基本显示后，用户在本次约 **62 分钟**观察中未报告卡死。

运行时对照确认：1920×1080 桌面使用 `IONDRVFramebuffer`；TGL framebuffer、TGL accelerator、HookCase、NootedGreen 均未加载。这个结果显著加强了加速图形配置与故障的关联，但还没有定位最初破坏内存的组件或代码。

蓝牙、触控板、电池显示、相机和蓝牙双向音频已有用户实测；内置扬声器/麦克风及真实背光亮度控制仍未解决。完整状态及证据边界见[功能矩阵](docs/STATUS.md)。

## 快速查看与检查

```sh
git clone git@github.com:yankedi/HP-Elite-Dragonfly-G2-Hackintosh.git
cd HP-Elite-Dragonfly-G2-Hackintosh
python3 scripts/check-publication.py
make -C mac-for-elitebook check
```

`EFI/` 提供脱敏配置示例和 ACPI 源码；组装步骤及第三方依赖见其说明。`tgl26-usb/` 中的历史实验记录保留当时结论，当前状态以本首页及 `docs/STATUS.md` 为准。

## 来源与许可

本项目基于多个上游项目及本地 HP 适配。各源文件、子项目的许可证和版权声明保持有效；没有以一个总许可证重新授权所有第三方代码。参见 [LICENSING](LICENSING.md) 及图形源码的来源记录。

完整的私有硬件采集、机器身份、安装介质和原始全量日志继续保存在开发机原工作目录中。公开仓库收录源码、补丁、配置示例与适合共享的证据。
