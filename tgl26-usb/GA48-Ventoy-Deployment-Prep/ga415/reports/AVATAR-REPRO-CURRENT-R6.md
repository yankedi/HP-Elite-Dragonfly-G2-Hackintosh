# 当前 R6 单次头像路径复现：系统失联，panic 类型待取证

## 执行与结果

用户要求“先在这个系统触发这个崩溃”。本次保留当前 R6，进行了
一次正常系统设置导航，随后 SSH 和 ping 均不通。失联后没有继续
GUI/GPU 提交、重试触发或执行重启。

用户随后在现场明确确认“已经卡死”。当前可报告状态为
**USER_CONFIRMED_SYSTEM_FREEZE_AFTER_SINGLE_SETTINGS_NAVIGATION**。
新 panic 尚未取得，不能宣称同一 `0x72bcd / div r15d` 已复现。

## 时间线（2026-10-24，UTC+8）

| 时间 | 观测 |
| --- | --- |
| 18:23:22 | preflight：25G83，session `REDACTED-SESSION-ID`，启动时间 18:03:07 |
| 18:23:25 | preflight SSH 完成，现有 73 份相关诊断记录路径、大小、mtime、SHA256 已保存 |
| 18:26:22 | 图形 Terminal 启动 `avatar-ui-inspect.command`，launch 返回 0 |
| 18:26:46 | 读取检查结果时 SSH 建连超时（返回 255） |
| 18:26:57 | 单次 ping 无回复，邻居状态 `INCOMPLETE` |
| 后续现场确认 | 用户明确确认系统已经卡死；未提供精确确认时间 |

## 触发前身份

- NG：R6 UUID `4C4C44D0-5555-3144-A111-5710B37AE86F`。
- 启动参数包含 `-ngreennoplanesfix`，不是已准备的 PLANES2 修复镜像。
- WindowServer PID 197；本次 preflight dmesg 的 GPU hang/reset/restart/
  `PIPE_CONTROL`/panic 检查无匹配。
- 本次是 R6，不能与上一次 GA414/NOAUX 的 panic 直接等同为同一构建复现。

## 唯一启动脚本

`tools/avatar-ui-inspect.command` 经已授权图形 Terminal 执行。其预定动作：

1. 创建独占 `inspect` 目录，并保存 stdout/stderr。
2. `open x-apple.systempreferences:com.apple.Users-Groups-Settings.extension`。
3. 等待两秒，读取前窗辅助功能元素（20 秒 AppleScript timeout）。
4. 使用系统 screencapture 保存一次截图。

没有点击头像或 Memoji 的自动操作。SSH 的 launch 成功只证明请求已交给
图形会话；失联时尚未回读脚本输出，因此不能确认脚本实际执行到了哪一步，
也不能确认 `AvatarPickerMemojiPicker` 是否已启动。

## 证据和恢复后所需取证

- `private/commands/avatar-repro-preflight-v1.json`
- `private/commands/avatar-repro-inspect-launch-v1.json`
- `private/commands/avatar-repro-inspect-result-v1.json`
- `private/commands/avatar-repro-loss-network-v1.json`
- 远端待回读：`/private/tmp/ga415-avatar-repro/inspect/`。

恢复后只读取得 boot session、脚本输出、诊断目录与 NVRAM panic，
与保存的 73 份基线逐项比较。以新增/变化 panic 的 RIP、除数、进程和
uptime 判断是否为同一故障；不要仅用文件名日期判断是否新 panic。

## 恢复后确认

已在修复镜像启动后取得新增
`/Library/Logs/DiagnosticReports/Kernel-2020-01-01-080126.panic`，
SHA256 `664d73bf931d8f40cb23431914675d666ce3870add03198b4d574614f4704bb6`。
该文件不在触发前基线中，incident 为 `REDACTED-SESSION-ID`。

本次确实复现同一故障：`AvatarPickerMemojiPicker` PID 1510，
RIP `0xffffff7f96718bcd`（donor VA `0x72bcd`），`div r15d`、R15=0。
panic uptime `1406030287843 ns` 加上一轮 boot epoch，推算实际发生于
**18:26:33.030288 +0800**，与单次导航及失联时间吻合。

NVRAM 7-bit 独立解码并重新打包核验通过；除诊断文件末尾多两个换行外，
panic 内容相同。详情见 `PLANES2-PRETEST.json`。
