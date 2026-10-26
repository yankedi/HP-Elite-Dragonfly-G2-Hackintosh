# GA4.16 实机验收结果：当前仍为 PLANES2，桌面花屏保留

日期：2026-10-25（HP 本地时间 UTC+8）

## 结论

**尚未证实“正确的 L3 Bank 数量真正解决了这台 HP Tiger Lake 的桌面花屏”。本次实际桌面仍然花屏。**

关键区别是：本次实际加载的是原有 **GA415-PLANES2 / GA414 NOAUX 二进制**，运行日志显示 **L3 从 donor 的 0 回退为硬编码 8**，没有证据证明 Fuse 对应的新 L3 配置已经生效。因此：

- `DESKTOP_ARTIFACTS_REMAIN`：当前桌面缺字、图标/控件残缺仍可见。
- `R8_PIXEL_PASS`：一次 R8 的 CPU、GPU 与独立 Expected 均为 0 错误像素。
- `L3_FIX_AB_NOT_ESTABLISHED`：未形成新旧 L3 单因素 A/B，不能宣布 L3 修复成功，也不能声称正确 Fuse 值已经实测失败。
- `ROOT_CAUSE_UNVERIFIED`、`STABILITY_UNVERIFIED` 保留。

本轮执行的是运行验收和取证；没有修改驱动源码、构建镜像、重启系统、覆盖回退镜像或循环测试。R8 **只执行一次**。

## 1. 实际启动身份

| 项目 | 实机证据 |
|---|---|
| 机器 | HP Elite Dragonfly G2 / i5-1135G7 |
| macOS | 26.6.2，Build **25G83** |
| Boot session | `REDACTED-SESSION-ID` |
| Boot time | 2026-10-25 **14:21:50 +0800** |
| NootedGreen UUID | `4C4C44E9-5555-3144-A1E4-CB51FF5A72E6` |
| GPU PCI | **8086:9A49**；ioreg 原始小端数据 `<86800000>` / `<499a0000>` |
| 实际修补特征 | NOAUX、NOCCS3、PLANES2 的本次启动成功日志均在 |
| `-ngreen415obs` / `-ngreenxefix` | 本次实际 boot-args 中均不存在 |

身份原件：`private/commands/boot-health-20261025T062703Z.json`，包含完整 build、sysctl、kmutil、ioreg、dmesg、NVRAM 和诊断内容。三个已安装的 GPU 驱动文件 SHA256 在前后读取中相同，与既有封存值一致：

```text
AppleIntelTGLGraphics  14e21de55f2923c3c46a33731ab2f7a71e1baf472f88d1fd8c702e821c171393
MTLDriver             e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d
libxedrv              b274aa7293acc9ba4c00acaefa564b4c9367ed29042659371ce42b62dd651259
```

本次 UUID、boot-args 与 PLANES2 日志，与此前 U 盘只读回读的 PLANES2 镜像身份相符。UUID 本身不能区分共享同一 NG 可执行文件的 GA414/PLANES2 配置；这里同时使用实际 PLANES2 安装日志和未带 `-ngreennoplanesfix` 的启动参数判定。

## 2. 拓扑与真实 L3 证据

本次 dmesg 原文：

```text
HWCAPS - NumSlices:1      SliceCountFuse:0x1
HWCAPS - NumSubSlices:10   DualSubSliceCountFuse:0x1f
HWCAPS - MaxEUPerSubSlice:8   EUDisableFuses:0x0  ExecutionUnitCount:80
HWCAPS - L3BankCount: 0
HP-R5: TGL 80EU donor L3 fallback 0 -> 8 (retained R4 value)
HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80 L3Banks=8 nativeL3=0 mirrors=1/10 dispatchers=5
```

**80EU、10SS 已有本次实际 fuse/运行字段证据；L3=8 已有本次软件拓扑字段证据，但没有“8 是硬件 Fuse 正确值”的证据。**

精确本地源码 `../GA414-Native-NOAUX-Source/src/NootedGreen/kern_gen11.cpp:6371–6414`：原函数返回后，在 real-TGL 路径读取拓扑；满足 Tahoe/GT2/1×10×8/80EU/nativeL3=0 时，把对象 `+0x1164` 写为 8，然后记录并返回。源码明确说明是兼容回退，**不是 Fuse 测量**。本轮只读核对该源码，未改动。

按用户指定实际执行了：

```sh
ioreg -rc IntelAccelerator -d1 | grep -E 'xe-topo|xe-blitfix|xe-rec'
```

结果为空、管线返回 1；完整 ioreg 采集成功。该构建没有给出所查属性，**不将属性缺失作为通过或失败**。替代证据为上述本次 HWCAPS/HP-R5 日志、加载 UUID、既有源码和交付身份。它们证明旧回退生效，不能补出不存在的 L3 Fuse 测量。

详细结构化证据：[`reports/RUNTIME-TOPOLOGY.json`](reports/RUNTIME-TOPOLOGY.json)。

## 3. NOAUX / NOCCS3 / PLANES2

本次启动实际记录了：

```text
XeNG PLANES2: calculateIOSurfaceDeviceCacheVRAMBytes planos de IOSurface+0x98: aplicado
XE-NOCCS3: IntelAccelerator::submitCCSResolve -> retorno imediato: aplicado
GA414 NOAUX: gate=1 cpu=0x8c pci=8086:9a49 subsystem=103c:8716 build=25G83
GA414 NOAUX: preflight first=1 original=1 patched=0 expected=1/0
GA414 NOAUX: postflight original=0 patched=1 verified=1 expected=0/1
XeNG NOAUX: fillSurfaceStateAuxInfo sempre AUX_NONE: aplicado
```

这不是只检查配置文件：已取得当前启动的实际修补/前后验证日志。R8 随后也验证 CPU getBytes 保持正确。

边界：没有内核逐资源 AUX/CCS 状态或 NOCCS3 调用计数。R8 的用户态 tracer 实际观察 `getBytes` 1 次、lock/unlock 各 2 次，`resolveCCS` 0 次；不能据此伪造“此资源命中了内核 submitCCSResolve”的证据。既有 NOAUX/PLANES2 已验证修复状态没有被本轮桌面问题推翻。

## 4. 真实桌面、窗口及前后对照

重启清除了 `/private/tmp` 中的旧工具。本轮从本地封存件重新上传**原有二进制**，校验 SHA256；没有重新构建。元数据使用 GA415 `desktop-capture --metadata-only`；实际图像由已获权限的图形 Terminal 内系统 `screencapture` 保存，包含全屏及独立窗口。

**本轮不声称自编 ScreenCaptureKit 图像捕获已验收。** 全屏和独立窗口为顺序拍摄，不是同帧；也没有物理屏幕照片与截图同帧配对。

### System Settings / About

- 本次窗口 ID 30，位置 `(759,71)`，尺寸 **723×960**。
- 全屏图中侧栏 `Accessibility`、`Displays`、`Siri` 等文字/图标出现截断或缺失；独立窗口截图中也保留不同位置的残缺，例如部分图标、`Desktop & Dock` / `Login Password` 标签区域。
- 同一窗口两个捕获路径的具体残缺不同，不能把顺序截图差异全部当成 GPU 错误像素数；但不能验收为“缺字已消失”。

![About 原始桌面对照：左为 GA414 启动期旧采集，右为本次](images/about-desktop-comparison.png)

上图左侧 `ga415/private/desktop-native-v1.png` 是 GA415 工具在 **GA414 启动期**取得的旧真实 About + Dock 图像；该采集发生在 2026-10-24 PLANES2 重启前。其身份记录见旧 `initial-health.json`、`terminal-native-screenshot-launch.json`。

另保存上一 PLANES2 About 独立窗口与本次同尺寸窗口对照：[`images/about-window-comparison.png`](images/about-window-comparison.png)。

**对照限制**：旧 GA414 图窗口位置/遮挡/焦点不同；上一 PLANES2 窗口是深色，本次为浅色，滚动位置和动态内容也存在差异。它们只能用于真实同类场景的症状对照，不能算新 L3 单因素 A/B 或逐像素正确参考。

### Finder

- 首次 Apple Events `open home` 返回 `-1712` 超时，原始 stderr、退出码和部分截图都保留。
- 随后的只读 Finder 采样显示主线程在事件循环正常等待，没有在该样本里发现 GPU 阻塞栈；当时健康门控仍通过。
- 改用 LaunchServices 打开 Home 后，成功取得 Finder ID 84 的全屏和独立窗口图像；不是重跑 R8 或 GPU 压测。
- 全屏图保留 Finder 侧栏标签上的黑矩形；独立窗口保留 Desktop 文件夹图标缺失和文字残缺。**未宣告 Finder 花屏消失。** 没有同状态旧 Finder 图作为精确 A/B，不能量化相同位置的修复比例。

![Finder 两条顺序捕获路径](images/finder-capture-paths.png)

### Dock 与色条

完整 Dock 区域在上述原始全屏中保留，另有无损裁剪：[`images/dock-GA414.png`](images/dock-GA414.png)、[`images/dock-current.png`](images/dock-current.png)。当前仍有可疑条带/图标形状，但 Dock 透射背景、壁纸以及应用布局发生变化。**没有干净参考时，不将所有彩色竖带当成损坏，也不能认证原色条已全部消失。**

完整元数据、限制与场景判定：[`reports/DESKTOP-COMPARISON.json`](reports/DESKTOP-COMPARISON.json)。

## 5. 一次 GA414 R8 Managed RT 回归

时间：2026-10-25 **14:31:07 +0800**；执行前后健康均通过。

复用原有 `managed-rt-probe` 和 `trace-managed-cpu.dylib`，SHA256 与 GA414/GA412 封存件完全一致。为当前 boot 建立新的本地授权记录和远端一次性 claim；旧 GA414/GA415 claim 没有修改或绕过。实际 **1 次执行、1 个显式 Command Buffer**。

| 有效像素比较 | 错误像素 / 总像素 |
|---|---:|
| GPU vs 独立 Expected | **0 / 16,705** |
| CPU vs 独立 Expected | **0 / 16,705** |
| CPU vs GPU | **0 / 16,705** |

尺寸 **257×65**，输出 BPR **1280**，只比较每行有效 1028 字节，排除 padding。

- 原有 `ga412/tools/verify-pixel-dump.py` 严格核验元数据、资源、独立快照时序、tracer、独立输入及 Expected，返回 `PIXEL_PASS`。
- 本轮 CPU-only 第二 auditor 用独立线性索引构造 Expected，再核验有效像素，三个错误数均一致为 0。
- Expected、CPU、GPU 的有效像素 SHA256 均为 `743eb209da06b225596c6870bcb0d6ba89353e5c5b21d917005cb4caacee11d1`，也与 GA414 成功回归一致。
- 保留了原始 `input.bin`、`expected.bin`、`gpu.bin`、`cpu.bin`、result/command JSON、stdout/stderr/exit 与远端 claim。

结果：[`reports/R8-RESULT.json`](reports/R8-RESULT.json)；原件：`private/captures/r8-capture/`、`private/R8-PIXEL-AUDIT.json`、`private/commands/r8-execute-ONCE.json`。

**R8 PASS 证明该 Managed RT 回归保持正确，不等于桌面修复、IOSurface B/C 路径修复或 L3 根因认证。**

## 6. 本次健康与上一次卡死

本次保存 6 份健康门控，包括截图前后、R8 紧前/后、最终检查。均为 `HEALTH_GATE_PASS`：

- 当前 boot 未见新的 GPU hang/reset/PIPE_CONTROL/panic 记录。
- 本次统一日志查询返回空数组；不是仅依据进程存在判断。
- 86 份相关诊断原件已压缩导出、逐文件 SHA256 验证；这些文件在本轮各健康检查之间路径与完整 hash 集合相同。
- WindowServer 始终 PID 197；没有本轮新增 watchdog、gpuRestart 或 Kernel Panic 证据。
- 最后检查：**14:35:52 +0800**，距离本次启动约 **14 分钟**，从首次本轮采集到最后检查约 9 分钟。仅是有界观察，不是长期稳定性验收。

### 重启前的真实失败证据

新取出的 `Kernel-2020-01-01-081848.panic` 不是按文件名可忽略的“2020 旧故障”：

```text
Incident: REDACTED-SESSION-ID
panic(cpu 2 ...): userspace watchdog timeout:
no successful checkins from WindowServer (2 induced crashes) in 120 seconds
System uptime in nanoseconds: 69977257959646
```

NVRAM packed panic 经已有 decoder 解码并通过精确重新打包校验；解码正文与该 panic 正文一致，仅末尾少两个换行。

2026-10-25 **13:49、13:54** 的三份 WindowServer IPS 明确给出旧 boot UUID **`REDACTED-SESSION-ID`**。panic 本体没有 boot UUID，但 69,977 秒 uptime 加旧 boot epoch 推算为 **13:55:40 +0800**，与这些 watchdog 相邻，强烈支持属于重启前旧启动期；这项归属是联合推断，不能伪称 panic 自带 UUID。

本次启动早期就已经保存了该 panic；它不是本轮 R8 触发。此前也保留多份 gpuRestart，例如 13:26 的 GPU Reset。只凭先前 reset 和后续 watchdog 的时间关系，不能判定二者同一根因，更不能认定由 L3 引起。

与更早那次 74 文件的历史快照相比，日志目录还有轮转和内容重写，所以不能将 `86−74=12` 当作新增故障数。本轮“未新增”的判断使用**当前 boot 内**6 次相同集合及 hash、时间、正文 boot UUID、dmesg 和统一日志联合证据。

详情：[`reports/HEALTH-AND-PREVIOUS-FAILURE.json`](reports/HEALTH-AND-PREVIOUS-FAILURE.json)；原始文件：`private/diagnostics/`、`private/diagnostics.tar.gz`、`private/nvram.xml`、`private/nvram-panic-decoded.txt`。

## 7. 对 GA4.15 错误路径的重新评估

1. 本次真实 80EU/10SS 和 R8 零错再次说明：不能继续把所有桌面问题归结为“仍在 96EU 拓扑运行”或原 CPU getBytes 问题。
2. 当前 **L3=8 仍只是旧回退**。L3 作为潜在贡献因素尚未被单因素实验排除或证实；应先取得正确 Fuse 对应值和新值实际生效证据，才能做 L3 因果判定。
3. GA415 既有 B direct Copy 保留 `0xEE`、C 多路径有效像素全零的证据仍成立；本轮没有重跑 B/C，不能宣称它们已有新结果。它们与桌面同根仍未证明。
4. 错误边界仍包含 IOSurface device-cache/pageon、额外 Copy proxy 及后续合成/捕获操作；R8 不覆盖所有这些路径。
5. 此 boot 没有 BLITOBS hook。实际 submitBlit pitch、矩形、最终 COPY2D/FAST2D/COPY3D helper、XE-BLITFIX 触发仍未观察，不能拿 IOSurface BPR 或入口 routeSel 代替最终路径。
6. System Settings/Finder 残缺进入存储 PNG，使“只在物理扫描输出才发生”不足以解释全部现象；但顺序截图的差异、黑块和条纹本身不能给出内核根因。

本轮没有叠加任何下一批补丁。**当前可交付的是旧 PLANES2 的真实回归、花屏保留和失败证据；新 Fuse-L3 修复镜像的首次启动与单因素 A/B 仍未成立。**

## 8. 复核入口

```sh
# 只进行本地 CPU 分析，不连接 HP 或提交 GPU 工作
python3 ga412/tools/verify-pixel-dump.py ga416/private/captures/r8-capture
python3 ga416/tools/summarize-evidence.py
```

完整文件大小/SHA256 索引：[`reports/EVIDENCE-MANIFEST.json`](reports/EVIDENCE-MANIFEST.json)。所有新 SSH 命令、上传、下载与退出回执均保存在 `ga416/private/commands/`。

**最终答复：目前不能回答“正确 L3 已解决”；实测花屏仍在，而正确 Fuse-L3 配置尚未被证明加载和测试。**
