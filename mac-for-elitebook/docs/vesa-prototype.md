# VESA 离线原型

状态：**已组装并通过静态检查；不可直接部署，尚无 HP 启动测试**。

```sh
make prototype
python3 scripts/validate_efi.py build/vesa-prototype
```

该命令只在本机 `.cache/`、`.local/`、`build/` 写文件，不操作远端、块设备、U 盘、固件或内置 EFI。首次运行需要从固定上游 URL 下载发布包与许可文本；再次运行校验缓存资产，不自动跟随 latest。

输出目录：`build/vesa-prototype/`。包含 EFI 文件树、`report.json`、`ocvalidate.log`、ACPI 编译日志和 `NOT-DEPLOYABLE.txt`。产物与任何机器身份都不提交 Git。

## 版本和来源

| 组件 | 固定版本 | 获取 / 验证 |
| --- | --- | --- |
| OpenCore / ocvalidate | 1.0.8 | 同一官方 RELEASE zip；上游 SHA-256 核对 |
| Lilu | 1.7.2 | 官方 RELEASE zip；上游 SHA-256 核对 |
| VirtualSMC | 1.3.8 | 官方 RELEASE zip；上游 SHA-256 核对 |
| WhateverGreen | 1.7.1 stock | 官方 RELEASE zip；上游 SHA-256 核对；未应用 TGL 图形补丁 |
| VoodooPS2 | 2.3.7 | 官方 RELEASE zip；API 未提供摘要，仅记录本机实测 SHA-256 |

许可文本从各仓库固定源码 commit 获取，保存到产物 `Licenses/`；发布包、源码 pin、许可 URL 和观测摘要见 `manifests/core-sources.json`、`manifests/vesa-assets.json` 与本机 `report.json`。

## 配置依据

- 从 **OpenCore 1.0.8 官方 Sample.plist** 重新生成，不以 Dell 完整 EFI 为底稿；移除示例音频、网卡、设备属性及所有二进制 patch。
- CPU spoof EAX `0x000706e5`、16-byte mask 仅覆盖 EAX，SMBIOS 候选 `MacBookPro16,2`：依据同代 Latitude 7320 固定提交的配置。其余 EC/USB/传感器和图形参数没有一起复制；该 spoof 在 HP 上仍未测。
- 本机 DSDT 证明 `Processor (PR00)` 位于 `\_SB`，因此只编译自有 `acpi/SSDT-PLUG.dsl`，在 Darwin 下提供 `plugin-type=1`。真实 EC0 暂不改名、不禁用、不替换，EC/USBX 仍待完整审阅。
- modern memory-map 组合为 `EnableWriteUnprotector=false`、`RebuildAppleMemoryMap=true`、`SyncRuntimePermissions=true`、`SetupVirtualMap=false`、`ProtectUefiServices=true`，是同代参考的实验候选，不是已确认的 HP 最优值。
- 保留 BIOS VT-d，原型使用 `DisableIoMapper=true` 绕过 macOS IOMMU 路径；待 DMAR/设备行为验证后再优化。
- CFG Lock 未测，原型将 `AppleXcpmCfgLock=true` 作为内核侧实验绕过；`AppleXcpmExtraMsrs` 与 `ProvideCurrentCpuInfo` 同样来自同代启动经验，后续按日志逐项消减。
- 原型只包含 Lilu → VirtualSMC → stock WEG → PS2 controller → PS2 keyboard，限制 Darwin `25.0.0–25.99.99`。不加载 PS2 trackpad/mouse、I2C、Wi-Fi、音频、Dell SMM、NVMeFix 或 Xe 实验插件。
- `-v keepsyms=1 debug=0x100 -igfxvesa`；没有 GPU device/platform spoof、`lilucpu`、`igfxtgl*` 或 framebuffer 二进制 patch。VESA 仍不保证 HP GOP 内屏输出正确。
- 仅 OpenRuntime 与 OpenHfsPlus 两个 UEFI driver；无 Reset NVRAM/Shell 工具和安装启动项的 launcher。配置关闭 `WriteFlash`、`PlatformInfo.UpdateNVRAM`、`AllowSetDefault`，实际启动对固件和系统的影响仍未测试。
- 保留 SIP（`csr-active-config=0`），DMG 仅允许 signed；调试阶段候选 `SecureBootModel=Disabled` 与 HP 的 UEFI Secure Boot 是两种机制，后者本轮没有更改。
- 序列号/MLB/ROM 留空或零占位，**不是可部署的机器身份**。后续需仅在 `.local/` 生成私人身份并重新校验。

## 已通过与未通过的门槛

已通过：匹配版本 ocvalidate；13 个启用引用文件存在；4 个 EFI 文件为 AMD64 PE/COFF；5 个 kext executable 包含 x86_64 Mach-O；第三方依赖加载顺序；编译 SSDT 长度/校验和；VESA 与图形实验参数隔离。

未完成：首次外部启动窗口、启动介质的保留 Ventoy 方案、安装目标、固件 Secure Boot 策略、私有身份、完整 USB 映射、EC/USBX 审阅与安装器网络/固定 build 介质。U 盘可用空间已通过后续只读挂载核实为 92.40GiB，容量不是当前阻塞。

这些未完成项在机器可读 recipe 和生成 report 中明确列出。不能把本页的“静态通过”改写成“EFI 已可启动/可安装”。

## 工具差异记录

1.0.8 的 `UEFI/Drivers` 条目新增 `HideVerbose`，已由匹配验证器发现并补齐。官方 README 写 `ocvalidate --version`，但当前发布包的 Linux binary 将该参数当作文件路径并失败；其启动 banner 明确标示兼容 1.0.8，实际使用验证 plist 的退出码与输出，不依赖这个参数。
