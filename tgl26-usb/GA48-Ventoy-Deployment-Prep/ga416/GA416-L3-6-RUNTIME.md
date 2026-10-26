# GA416 L3=6 首次实机结果：已检查桌面恢复正常，R8 PIXEL_PASS

日期：2026-10-25。用户手动启动 `HP-Tahoe-GA416-L3-6.img` 后，现场反馈“成功启动，看起来确实是没有花屏了，壁纸先不管”。本报告记录的是**新驱动本次启动**，此前构建报告中的 `NOT_TESTED` 是当时状态。

## 结论

**本次已确认 L3 从 donor 的 0 修正为硬件对应的 6，并且 System Settings、Finder、Dock 中此前可见的缺字、图标残缺和黑矩形在新截图中消失。一次实际 R8 回归也保持 PIXEL_PASS。壁纸按用户要求排除。**

这是已有 GA414 NOAUX + PLANES2 基线上，只改变 L3 回退 8→6 的独立构建结果，支持错误 L3 配置是此前桌面花屏的关键原因。对照属于跨启动的真实场景观察，不把动态界面当成逐像素固定 Expected，也不将短期观察扩展成长期稳定性结论。

## 本次启动身份与运行字段

| 项目 | 实测结果 |
|---|---|
| 系统 | macOS 26.6.2 / **25G83** |
| Boot session | `REDACTED-SESSION-ID` |
| 启动时间 | 2026-10-25 15:57:16 +0800 |
| NG UUID | **`4C4C44D4-5555-3144-A13A-DFB86EFBE513`**，与 GA416 构建一致 |
| GPU | **8086:9A49**，subsystem **103C:8716** |
| 拓扑 | **1 Slice / 10 SS / 8 EU per SS / 80 EU** |
| donor L3 | **0** |
| effective L3BankCount | **6** |
| 拓扑 mirrors / dispatchers | **1/10 / 5** |
| NOAUX | HP/25G83 gate=1，preflight 1/0，postflight 0/1 verified=1 |
| NOCCS3 | 安装日志命中 |
| PLANES2 | 安装日志命中 |

本次启动原始日志摘录：

```text
[39.821372] HP-GA416: native Tiger Lake 80EU / 10SS
[39.821376] HP-GA416: hardware L3 fuse = 0x88 (measured on NixOS; prior static evidence, not a runtime fuse read)
[39.821378] HP-GA416: donor L3 = 0
[39.821379] HP-GA416: L3 override 0 -> 6
[39.821380] HP-GA416: effective L3BankCount = 6
[39.821382] HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80 L3Banks=6 nativeL3=0 mirrors=1/10 dispatchers=5
```

Fuse `0x88` 行明确是前次 NixOS 实测的静态依据；donor/effective 值来自本次 GPUInfo 对象。boot-args 与此前旧 PLANES2 对照启动相同，没有靠添加未知 `ngreen-l3` 参数冒充修复。

## 桌面真实图像

实际在图形 Terminal 中执行系统 `screencapture`，同时保存独立窗口图、全屏图和窗口元数据。

- **System Settings / About：**窗口 ID 40，723×960，位置 `(759,71)`。此前侧栏缺字/图标碎片已不再出现；Bluetooth、Network、Appearance、Desktop & Dock、Siri 等文字/图标正常，Graphics 字段也正常显示。
- **Finder：**窗口 ID 34，已检查的侧栏和主区域文字/文件图标正常，此前黑矩形、Desktop 图标残缺未见。
- **Dock：**全屏原图保留，已查看图标正常；区域裁剪来自真实原图。
- 用户现场观察与截图结论一致；没有摄像头与软件截图的同帧配对。`desktop-capture` 只用于元数据，不声称运行了 ScreenCaptureKit 图像捕获。

对照图：

- [System Settings：旧 L3=8 / 新 L3=6](images/l3-six-runtime/settings-before-after.png)
- [Finder：旧 L3=8 / 新 L3=6](images/l3-six-runtime/finder-before-after.png)
- [Dock：旧 L3=8 / 新 L3=6](images/l3-six-runtime/dock-before-after.png)

原始 PNG 与元数据：`ga416/private/l3-six-runtime/captures/desktop/`。

## 原生签名验证补齐

对**同一跨平台构建产物**在 macOS 临时目录中执行：

```text
codesign --verify --strict --deep --verbose=4  → rc=0
valid on disk
satisfies its Designated Requirement
Signature=adhoc
```

没有重新签名或安装。其 UUID 与已加载 UUID 一致，可执行文件 SHA256 仍为：

```text
e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb
```

回执：`ga416/private/commands/l3six-native-signature.json`。因此此前未运行的 Apple 原生严格验证现在已补齐为 **PASS**；此前离线 verifier 的 CMS 报错回执仍保留。

## R8：一次实际 GPU 执行，两个独立 Expected 校验通过

首次 launcher 因归档程序文件模式为 `0644`，在进入程序前被 shell 拒绝，退出 126。该次 stdout 为空、stderr 明确 `Permission denied`，没有创建 dump，也没有提交 GPU 工作。随后用户明确指示使用已提供的 root 权限继续处理。

使用已有 sudo 将**临时测试程序**模式改为 `0700`，确认二进制 SHA256 前后不变。保留原 claim、STOP 和错误回执，记录这次用户指示后，用独立 recovery claim 执行 **一次 R8**；实际只有 **一个显式 Command Buffer**，没有循环测试。

| 比较 | 错误像素 | 不同有效字节 |
|---|---:|---:|
| GPU vs 独立 Expected | **0 / 16,705** | **0** |
| CPU vs 独立 Expected | **0 / 16,705** | **0** |
| CPU vs GPU | **0 / 16,705** | **0** |

原严格 auditor 校验 schema、输入、独立 Expected、四份独立 dump、命令时间线、快照顺序及有效像素。第二 auditor 另行按坐标公式重建 Expected，没有导入主 auditor/生成器；两者一致。有效像素 SHA256 与 GA414 成功基线一致：

```text
743eb209da06b225596c6870bcb0d6ba89353e5c5b21d917005cb4caacee11d1
```

10 条 tracer 事件嵌套平衡。用户态 getBytes/lock/unlock 观察不冒充内核逐资源 NOAUX/CCS 计数证明。原始 dump、metadata、stdout/stderr/exit、两次授权阶段和权限修改前后回执均保留。

## 健康与最终状态

本轮 **10 次健康门控全部 PASS**；86 个既有相关诊断文件在本轮内的路径/hash 集合不变，未见本次启动的 GPU hang/reset、panic 或 WindowServer watchdog。WindowServer PID 197 保持不变。此前 190 项 GA416 历史证据 hash 也保持相同。

```text
NEW_DRIVER_BOOTED            = CONFIRMED
L3_6_RUNTIME_CONFIRMED       = CONFIRMED
DESKTOP_ARTIFACTS_RESOLVED   = CONFIRMED_IN_OBSERVED_SETTINGS_FINDER_DOCK
DESKTOP_ARTIFACTS_REMAIN     = NOT_OBSERVED_IN_THOSE_SCENES
R8                          = PIXEL_PASS
NATIVE_CODESIGN_STRICT_DEEP  = PASS
WALLPAPER                   = EXCLUDED_BY_USER
LONG_TERM_STABILITY         = NOT_TESTED
```

本轮没有修改驱动源码、重新构建镜像、替换系统驱动、写 KC/内部 EFI、改壁纸或自动重启。临时测试程序执行位是唯一权限修正。

结构化当前结果：[L3-6-RUNTIME-RESULT.json](reports/L3-6-RUNTIME-RESULT.json)。原始新启动 SSH 回执：`ga416/private/commands/l3six-*.json`；新启动捕获：`ga416/private/l3-six-runtime/`。本报告只覆盖此次 L3 实验，不代替历史 GA415 其他路径问题的验收。
