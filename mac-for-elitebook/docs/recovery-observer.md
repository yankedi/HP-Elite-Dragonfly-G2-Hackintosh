# Recovery 自动观察脚本

[`collect_macos_handoff.sh`](../scripts/collect_macos_handoff.sh) 在 Recovery Terminal
运行一次即可收集现有输入、USB、磁盘与其他硬件路径，并生成一份自动摘要。
不依赖 Python，也不要求 Recovery 联网。

已在实际 26.6.2/25G83 Recovery 中从内置 NTFS 执行，经 SSH/SFTP 保存首份完整归档：
141 个文件、67 个命令、10 项缺工具/不可用、无超时，见
[`hp-recovery-runtime-check.json`](../manifests/hp-recovery-runtime-check.json)。
这次实际缺少 shasum、hidutil、system_profiler；用 SFTP 下载与独立 SSH cat 字节比较核对归档。
自动摘要的旧 `IO80211Interface` 查询为空，但本次 AirportItlwm 使用 `AirportItlwmEthernetInterface`，
Wi-Fi/SSH 实际可用；不要把单个类的 `not_observed` 当成网络失败。

## 运行

建议使用已挂载 USB 上的脚本，同时自动保存归档：

```sh
sh "/Volumes/<volume-name>/ISO/linux/collect_macos_handoff.sh" --save-usb
```

将 `<volume-name>` 替换为实际挂载的可移动卷名。脚本会自己扫描已挂载的 `/Volumes/*`，不依赖卷名选取保存位置。
默认不加参数时，只向私有 `/tmp/hp-macos-observation.*` 及相邻 `.tar.gz` 写输出。

`--save-usb` 会核对原交付目录中的启动 IMG、离线 HFS 数据文件和 checksum 标记，
并读取 `diskutil info -plist`，只接受**恰好一个已挂载、可写、外置、物理 exFAT 卷**。
它在 USB `ISO/linux/` 新建唯一的 `HP-Diagnostics.*` 目录，复制归档后逐字节比较并同步。
已有归档不会被覆盖。找不到卷、候选不唯一、工具不全或复制失败时，归档仍留在 `/tmp`，
终端会显示原因并返回非零状态；不会自动挂载任何卷。

一般查询每条默认限时 20 秒，卡住后发送 TERM，2 秒后仍不退出则 KILL **本脚本启动的查询进程**，
然后继续后面的观察。可以指定 `--timeout 10` 等 1–120 秒的整数。
这不是整个脚本的总限时；观察项目多时需要等候数分钟。

## 自动观察项目

| 范围 | 实际读取 |
| --- | --- |
| 系统/CPU | 时间、OS/build、kernel、boot-args、CPU features、内存与核数 |
| 输入 | PS/2 controller/keyboard、I2C controller/nub/HID、GPIO、precision touchpad、HID device/event service、`hidutil list` |
| USB/PCI | USB plane、XHCI/Host controller、USB device/interface、PCI、完整 IOService 与 ACPI registry 树 |
| 存储 | diskutil list/plist、APFS、最多 64 个磁盘/分区的独立 info plist、偏移/大小/挂载点、NVMe/storage、附加映像 |
| 图形 | IGPU、framebuffer、accelerator、显示摘要 |
| 其他 | SMC、电池、电源设置/断言、音频、Wi-Fi/以太网/蓝牙类、网卡状态/路由、Thunderbolt 摘要 |
| 驱动/诊断 | kmutil loaded 列表，失败时尝试 kextstat；内核消息；各命令 stderr/状态 |
| 离线资源 | 自动寻找已挂载卷上的已交付 IMG/HFS，读取大小并记录是否与交付长度一致 |

脚本不执行网络连通性探测，不注入输入事件，不测试 sleep，不改变驱动或电源状态。
磁盘偏移只用于观察，不会自行挑选安装目标，也不会格式化、修复或启动安装器。
没有执行固件/NVRAM 操作或访问原始 ACPI/MSDM 表。

## 输出怎么读

- **`SUMMARY.tsv`**：每个 registry 查询区分 `registry_present`、`not_observed`、
  `query_failed`、`tool_unavailable`、`timed_out`。驱动列表按完整 bundle ID 匹配，
  不把仅有 VoodooI2CHID 错认成 VoodooI2C core 已加载。registry 计数包含查询返回的子类，
  避免把 Intel framebuffer 或 XHCI 子类误报为缺失。
- **`command-status.tsv`**：命令的退出码、用时、是否超时和 stdout 字节数。
  127 表示工具不存在，124 表示超时；原 stdout/stderr 均保留。
- **`disk-inventory.tsv`**：磁盘标识、父盘、物理/虚拟、文件系统、偏移、大小和挂载点。
  无法查询的字段为 `unknown`，不填猜测值。
- **`resources.tsv`**：离线资源长度核对。长度一致不是 SHA-256、签名或安装可用性证明；
  默认不会再次通读 19.9GB 安装数据。
- **`export-plan.tsv`**：是否请求 USB 保存，以及核对通过的候选卷数。

`registry_present` 仅证明该类在 registry 中可见；`listed` 仅证明驱动出现在 loaded 列表中。
它们不证明触控板、USB 鼠标、Wi-Fi、音频或电池功能正常。空查询也不自动等同于硬件损坏。
Metal、实际安装和完整键盘/指针功能仍需实机验证。

这些原始观察包含私有设备标识、磁盘 UUID、网络地址或机器身份。
输出留在忽略的私有目录/用户 USB，不提交到 Git。

## 本地验证范围

```sh
sh -n scripts/collect_macos_handoff.sh
python3 -m unittest discover -s tests -p test_macos_handoff.py -v
make check
```

隔离的 Linux 原生 fixture 测试模拟 macOS 命令输出，覆盖查询失败/缺失、
TERM 无效后的超时终止、精确驱动匹配、磁盘枚举、带空格卷名、USB 保存及回读、
内置卷/多候选/链接目录的拒绝与复制失败保留原归档。没有运行 VM。
这验证脚本控制流，不等于脚本已经在 HP Recovery 实际运行。

## 交付

扩展版脚本已写回 USB `ISO/linux/collect_macos_handoff.sh`，也更新到当前启动 IMG 根目录，
同时更新交接文字与 checksum 清单。只更新 IMG 内观察脚本，35 个 EFI 文件、配置与
Recovery 均保持；匹配版本 OpenCore 1.0.8 `ocvalidate` 退出 0。
该次观察脚本刷新交付的 IMG SHA-256：`12cd17fc42333762a2363f02adbea34a278b2c52f82713eee0a438885a8290ca`。
后续 USB 所有权对照继续保留此脚本，当前 IMG 以[交接文档](install-handoff.md)为准。

USB 完整回读通过；基线 IMG 与离线数据完整摘要保持，Ventoy 配置和分区保持，
213 个其他文件大小/mtime 保持，USB 已安全卸载。证据索引：
[`hp-observer-check.json`](../manifests/hp-observer-check.json)。
