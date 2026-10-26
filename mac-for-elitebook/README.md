# HP Elite Dragonfly G2 → macOS Tahoe

这是面向长期移植工作的公开工程副本，记录 HP Elite Dragonfly G2 上的实验性 macOS 26 Tahoe 适配。**截至 2026-10-27，Tahoe 26.6.2 / 25G83 已安装并进入桌面；Xe/Metal 加速和整机稳定性仍未验收。** 当前摘要以 [`configs/install-preparation.json`](configs/install-preparation.json) 为准；继续工作前请读[公开续接入口](docs/continuation.md)。

## 当前结论

- 四次启用实验性 Tiger Lake 图形栈的启动在约 **252–340 秒**后发生 panic。
- 一次保留固件显示、避免实验性 TGL 驱动匹配并采用软件显示的对照，运行约 **62 分 35 秒**，用户未报告冻结。采集末段包含关机序列；这不是工作负载匹配的重复试验，也不能证明因果或定位具体组件。
- 运行态硬件观察为 **80 EUs / 10 subslices**。这只是硬件枚举结果，不代表 macOS Xe 加速已工作；旧文档中的五-subslice 数值不是本次运行态结论。
- 用户实测可用：Bluetooth、触控板、电池显示、相机，以及 Bluetooth 双向音频。
- 仍未解决：内建 HDA 音频、内建数字麦克风（DMIC）和亮度调节。首个内存破坏者、panic 根因、加速图形栈内的具体故障组件均未证明。

## 文档入口

- [当前状态与证据边界](docs/continuation.md)
- [分阶段适配计划（保留的历史设计）](docs/roadmap.md)
- [实机硬件基线](docs/hardware.md)
- [运行态显示记录](docs/runtime-display-notes.md) · [显示分析](docs/display-analysis.md)
- [安装与启动历史](docs/install-handoff.md) · [输入与 USB 历史](docs/input-recovery.md)
- [图形源码与移植边界](docs/graphics-research.md) · [周边设备状态](docs/peripherals.md)
- [静态 / 非启动验证](docs/verification.md) · [VESA 原型](docs/vesa-prototype.md)
- [`manifests/`](manifests/) 中保留来源、版本和可公开的验证摘要；[`manifests/experiment-history.json`](manifests/experiment-history.json) 是简要索引，不是完整运行日志。

## 开发检查

```sh
make check
make prototype
make nonboot-graphics
```

`make check` 检查 Python 语法、JSON、Markdown 本地链接、来源固定信息与仓库卫生。非启动测试及原型构建有额外本机工具/缓存前置条件，详见各文档和 `Makefile`。`.local/` 下的原始采集、机器身份和生成工件不属于公开副本；缺少这些私有材料时，不能把公开摘要当成原始证据或声称独立复现。

## 隐私与证据

公开副本不包含个人用户名、真实网络端点、设备序列号/SMBIOS 身份、凭据、私钥、原始机器日志或私有编排历史。私有原件没有复制；公开记录会明确区分用户报告、观察到的结果、静态验证和未证明事项。详见 [`PUBLICATION.md`](PUBLICATION.md)。
