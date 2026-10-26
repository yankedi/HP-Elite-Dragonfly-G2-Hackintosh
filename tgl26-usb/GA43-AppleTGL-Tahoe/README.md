# GA4.3 — Apple Tiger Lake 原生 Metal 驱动适配（第一阶段）

本仓库是 GA4.0–GA4.2 之外的独立离线分析树，目标是评估在原生 Tiger Lake
`8086:9A49` + macOS Tahoe `26.6.2 / 25G83` 上复用 Apple TGL Gen12 驱动
（配合 NootedGreen、Metal ABI 修补与 Shader Compiler 桥接）的可行性。

严格边界：只做公开源码审计、离线代码开发、CPU 测试与受控编译；不安装/加载
kext，不修改 EFI/NVRAM/SIP/SSV/AMFI，不连接目标 macOS，不执行 GPU MMIO 或
batch，不自动下载 Apple 专有二进制或运行上游安装脚本。

## 目录

- `FINAL-REPORT.md`：第一阶段中文结论与方案 A/B 比较
- `reports/APPLE-TGL-STACK.md`：原生 Apple TGL 调用链
- `reports/TGL-PATCH-MATRIX.md`：逐补丁 TGL/RPL 分类
- `reports/TAHOE-25G83-COMPAT.md`：25G83 ABI/二进制兼容性
- `reports/BUILD-VALIDATION.md`：受控构建检查
- `reports/NEXT-STEPS.md`：下一阶段最小计划
- `inputs/upstream/`：锁定 commit 的公开参考源码（不纳入 Git）
- `docs/provenance.json`：URL、commit、许可证与关键文件 SHA256
- `configs/`：目标配置
- `tools/`、`tests/`：只读预检工具及测试
- `logs/`：原始构建、测试与工具日志

**当前状态：ANALYSIS_ONLY。** 本仓库没有可部署的 EFI/kext，也没有在
9A49/25G83 上运行过 Metal；25G83 目标二进制与合法签名/加载路径仍是阻塞项。
