# REPAIR7：回到已验证的 NOAUX + NOCCS3 + L3=6 组合

## 用户观察与旧修复对照

- 2026-11-03 用户对 R6 新基底候选的现场结论是“没有改善”，即桌面局部花屏仍在。
- 上一次花屏修复对应上游 issue #3：80 EU 部件使用 `ngreen-eu=80 ngreen-l3=6`；本机此前的 issue #3 评论也确认，在原生 TGL 80EU/10SS、已有 NOAUX/NOCCS3 的 GA416 分支上，把 L3 fallback 从 8 改为 6 后，观察到缺失字符、空白图标/碎片和 Finder 黑矩形消失。
- issue #7 是另一条问题线：NOCCS3 跳过真实 resolve 而调用方仍清 dirty，导致 CPU `getBytes` 全错；当时单独加 NOAUX 后 CPU 读回 0 坏像素，但桌面花屏仍在，直到 GA416 的 L3=6 组合才在已检查场景中消失。
- 因此上次并不是“只加 L3=6”单独修好，而是 **NOAUX（关闭 render compression/AUX）+ NOCCS3（resolve stub）+ L3=6** 的组合；CPU 读回和桌面花屏要分开验收。

## R6 实测结果（失败，已保留现场）

- R6 boot `399C43BA-5743-477B-ABF2-C253C4EDCCDE`，准确 UUID/250 内容/ROW5/rect/CCS6 安装门控均通过。
- 66.570207 秒只有 **一次** `HP-CCS6: real resolve command/state page committed rects=1`；随后大量 `HP-CCS6: resolve rejected; preserve dirty state and fail caller`。因此“真实 CCS resolve”并未在绝大多数调用中实际执行。
- 126.559592 秒出现 `GPURestartSignaled`，129.770893 秒进入 RCS reset；报告为 context 29，`IPEHR=0x40158001`、`ACTHD=0x40008004`、`BB_ADDR=0x40008005`。这与 R5 延迟 hang 的 `IPEHR/ACTHD` 相同，但发生得更早。
- smoke 在 R8 前因检测到 reset 中止（`smoke_reset_before_r8_no_load`）；没有新的像素结果，Terminal 截图 helper 也以 exit 93 失败。不能把“进程未跑完”当成修复或回归结论。
- R6 的 `accel+0xc78 bit1` 门控与 donor 一致：donor 在 bit1 为 0 时静默返回。我们的 wrapper 把它转成失败并反复重试，造成大量拒绝；这不是可接受的最终语义，需在后续候选中明确区分“donor 正常跳过”和“真实失败”。

## R7 候选

在 R6 源码基础上只改 `kern_gen11.cpp`，改回已验证组合：

1. 原生 TGL/Tahoe 应用 NOAUX，强制 `fillSurfaceStateAuxInfo` 为 AUX_NONE。
2. 应用 NOCCS3，`IntelAccelerator::submitCCSResolve` 立即返回；不再安装 R6 的整页 CCS6 jump/route。
3. 保留 `getGPUInfo` 的 80EU/10SS、L3 fallback 0→6，以及 R5 的 ROW5/rect/ABI/topology 修补。
4. 不改变固定上游 `6f03560ef9694f9826caae15624d4a6cb1bf9ffc`，不迁回旧基底。

本地核查：

- 实际 TGL donor 中 NOAUX 与 NOCCS3 的 find/replace 各唯一匹配；替换字节与 GA416 相同。
- `verify.py` 确认只改 `kern_gen11.cpp`、R6 的 CCS6 调用未安装、L3=6 条件仍在。
- 构建、98 EFI 仅 NG 变化、配置 SHA `7df7f1f6…`、OC 1.0.8 `ocvalidate`、FAT 只读检查通过；无新增未定义导入，warnings 类别与 R5 相同。
- IMG `HP-UPSTREAM-6F03560-REPAIR7-NOAUX-KNOWN-FIX.img` SHA256 `cbc97613858be1e35fa40eae42ec629d099ec865f238ed0ede1ee07d905e02ab`。
- NG SHA256 `0613108d9b35b954254044026a2d61c41c908353f097700373843e44473a5c4a`，UUID `4C4C44FA-5555-3144-A1F6-57711AE034CD`。
- source diff SHA256 `5a49681722f87d01c7f8ac38ed634cfa516a8baa24fe40f453d4065e69fdfb37`。

这些只是本地候选核查；尚未证明新基底上花屏/CPU/hang 已修复。

## 实测准备

- 已从当前 USB 捕获 R6 consumed env，并用 pristine 本地 R6 镜像核对 98 EFI；使用过的 USB R6 IMG 因 OpenCore 运行日志导致整文件哈希变化，确认其 NG 二进制匹配后才移除，原件和回执保留。
- R7 测试使用独立 `trial/`，先完整回收当前 NixOS 身份/USB 状态，再交付/整图回读/武装；macOS 测试脚本失败、完成或 reset 都不自动回程重启。
- 实测顺序：准确身份和 98 内容→NOAUX/NOCCS3/L3=6 安装与实际日志→真实桌面截图→一次原 R8（CPU/GPU 像素）→健康门控后 Metal→持续观察超过 R5 延迟 hang 时点。任一项失败保留现场和完整采集，不提前结论。

## 2026-11-04 GPU 压测结果：花屏/CPU 已修，但 GPU hang 与 watchdog panic 仍复现

用户要求启动之前的 Geekbench Metal 压测，测试 GPU hang 是否仍发生。使用与 `trace-repeat.py` / `no-r5-repeat.py` 相同的命令：

```text
sandbox-exec deny network
geekbench6 --gpu Metal --gpu-platform-id 0 --gpu-device-id 0
```

实际 R7 boot `27908E81-6247-4232-AB10-893E5A5172E0`：

- 00:40:33 启动；输出 `Background Blur → Face Detection（workload 303 validation failed）→ Horizon Detection`。
- 00:43:04 首次 `GPURestartSignaled`；00:43:08 `GPU hang`，context **5**，`ACTHD=0x0a000140`、`IPEHR=0x61040001`、`BB_ADDR=0x4bdaabf8 valid=0`。
- `XeNG GPUREC: reset RCS ret=1 ... replay=1 (n=1)` 后约每 5 秒重复 `GPURestartSignaled` / `GPURestartSkipped`；00:44:54 左右第二次 `GPU hang`，reset `n=2`。
- 00:44:32 和 00:45:12 的 WindowServer spin 报告分别显示 40 秒、80 秒无 successful checkin，0/1 induced crash。
- 00:47:09（uptime `1132988261049ns`）发生 panic：

```text
panic(cpu 2 caller 0xffffff80033f8fd9): userspace watchdog timeout:
no successful checkins from WindowServer (2 induced crashes) in 120 seconds
```

- 新 EFI PanicInfo 0000–0005 全部变化；7-bit 解码 3948 packed bytes 精确 roundtrip，正文完整读出上述 watchdog panic。`000K` 未变。
- `debug=0x100100` 生效，系统自动回到 NixOS boot `796a7bb1-aa30-482e-9e64-65f443417050`；已由观察器完成 EFI 和系统/所有用户 DiagnosticReports 采集。

结论：**黑屏对应 GPU/WindowServer hang，随后是 WindowServer 120 秒 watchdog 的 userspace panic，不是 RCS 页故障 panic。** R7 的花屏与 CPU 读回修复仍然成立（R8 三组 0 坏像素），但 Geekbench Metal 的 context-5 RCS hang 及由此触发的 watchdog panic **仍未修好**。证据在 `repair7-noaux-known-fix/stress-r7/panic-analysis.json` 和 `post-panic/`。
