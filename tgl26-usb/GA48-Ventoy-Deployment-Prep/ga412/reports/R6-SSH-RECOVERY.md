# R6 重新启动后的保活与上次 SSH 超时分析

## 本次实际完成

用户手动重启并授权继续之后，SSH短命令均正常返回，核对到新启动实例：

- boot session：`REDACTED-SESSION-ID`。
- NootedGreen UUID：`4C4C44D0-5555-3144-A111-5710B37AE86F`，与R6一致。
- WindowServer PID197、状态Ss。PID在重启后复用，不能用PID判断仍属旧启动。
- 电源为AC。07:25时1分钟负载43.64；07:29降至1.91，不能将启动早期高负载直接判为hang。
- 07:29诊断目录最新文件仍是旧02:55 watchdog；没有在该目录看到本次启动新生成的GPU reset/watchdog报告。这是有限观察，不是无hang或稳定性证明。
- 07:33:52（启动约11分钟）最终检查仍能SSH响应，同一新boot session，两个caffeinate进程仍在；1分钟负载1.53，诊断目录仍无本次启动新报告。
- 直接 `stat` 确认两个文件：
  - `/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-Recovery-GA410-CSR0.img`
  - `/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-VESA-XHCI-RHUB.img`
  - 均为1,343,225,856字节。只验证存在与大小，未重新计算介质完整内容hash或实测启动。

本次未运行像素探针，也没有新GPU像素结果：`GPU_TEST_NOT_RUN`。

## 保活措施及有效期

| 临时进程 | 功能 | 启动时限 | 预期到期（目标机+0800钟表不变时） |
|---|---|---|---|
| PID991，`caffeinate -ims -t 7200` | 防空闲系统睡眠、防AC系统睡眠、防磁盘空闲 | 2小时 | 约2026-10-24 09:25:44 |
| PID1082，`caffeinate -d -t 6600` | 防显示器空闲熄屏 | 110分钟 | 约2026-10-24 09:20:24 |

在07:30:45的独立回执中，两个进程均已成为PPID1的`caffeinate`进程，`pmset -g assertions`确认四类断言均为1，并列出对应PID及剩余时限。启动后立即读取断言可能存在调度竞态，所以以这份后续回执为生效证据。

这是临时电源断言，不修改 `pmset` 持久配置。当前AC配置原本已是 `displaysleep=0`、`sleep=10`、`ttyskeepawake=1`、`tcpkeepalive=1`。防熄屏断言不能证明之前是自动熄屏引发故障，也不能强制打开已经关闭的显示器。

远端日志和PID文件位于：
`/private/tmp/ga412-r6-REDACTED-SESSION-ID/`。

这些断言不能修复GPU hang，不能保证合盖后系统保持运行，也不阻止手动睡眠/关机。到期自动释放，无自动重启或恢复动作。

若要提前结束，应先核对仍是上述boot session，且PID991/1082仍分别对应这里记录的caffeinate进程，再发送普通TERM；不要在未来的另一个启动中直接按旧PID操作。此次没有远程执行终止命令。

SSH工具原本已配置 `ServerAliveInterval=5`、`ServerAliveCountMax=2`、连接超时8秒。协议保活只能检测连接，对挂起的远端命令不提供完成保证，也不是GPU恢复机制。

## 上次究竟发生了什么

时间表使用目标机+0800；原SSH回执时间为UTC，已换算。主机存在不合理的部分进程elapsed/Time Since Fork值，因此不拿这些大值计算运行天数。

| 时间 | 原始证据 | 能确认的事实 |
|---|---|---|
| 02:40:09 | `Kernel_2026-10-24-024009_*.gpuRestart` | GPU Reset；RCS busy in batch、context33、ACTHD `0x401bd014`、IPEHR `0x84ff1111` |
| 02:49:25 | 原身份SSH回执rc0 | 旧R6 session `REDACTED-SESSION-ID`；SSH仍能返回完整命令输出 |
| 02:49:52–02:49:57 | `WindowServer_2026-10-24-025006_*.spin` | WindowServer被watchdog判为不健康；同快照含find PID2078及sshd-session PID2074/2077 |
| 02:50:02 | `WindowServer-2026-10-24-025002.ips` | 明确属于旧R6 boot session；Display not ready，Surface1和10为GPU Busy；displayState为OFF |
| 02:50:11 | 原介质检查回执 | 30秒`LOCAL_SSH_TIMEOUT`，已有卷与磁盘列表输出，无文件搜索结果，远端最终完成状态未知 |

### SSH命令超时的最直接线索

旧介质命令在 `diskutil` 后执行整个 `/Volumes` 下的 `find`。watchdog快照中：

- `find [2078]` 12个样本进入 `lifs` 文件系统路径；5.53秒采样期间累计CPU时间0.242秒。
- `UVFSService [278]` 有 `livefiles_ntfs.dylib` 调用栈。
- 两条 `sshd-session` 进程仍在快照中，不能据此断言SSH服务已经死亡。
- 其进程年龄约11秒与02:49:52附近、30秒超时在02:50:11结束的命令窗口一致，强烈支持这些是同次目录搜索相关进程；没有完整命令行，不能把关联表述为唯一身份认证。

**合理解释是目录遍历在文件系统请求中耗时，SSH会话等待远端命令结束。** 证据没有证明NTFS死锁、坏盘，也没有证明网络断开或sshd崩溃。该进程在采样期间既有CPU执行也有等待，不能仅凭样本写成永久阻塞。此次用已知路径直接stat，避免重现广域递归搜索。

### 图形故障是独立且更早存在的事实

旧报告把WindowServer内存记录为约10.22GiB，IPS的 `residentMemoryBytes=10978615296`；watchdog直接指出显示Surface仍GPU Busy。结合更早的GPU reset，之前“进程Ss所以图形健康”的判断显然不足。

但没有证据把“GPU hang→文件系统等待→SSH服务不可用”串成已证因果链。也没有这段时间的成功/失败新连接对照或网络抓包，因此无法确定用户后来观察到的完全SSH不可达，究竟是睡眠、网络、全系统资源退化还是其他后果。

`displayState=OFF` 只说明快照时显示状态。它既不等于整机睡眠，也不证明熄屏触发GPU hang。`ROOT_CAUSE_UNVERIFIED`。

本次新WindowServer的RSS在07:29:48为648436KiB（约633MiB），07:30:45为725124KiB（约708MiB），07:33:52为973376KiB（约951MiB）。约4分钟增加317MiB，当前仍在增长。`HYPOTHESIS_SUPPORTED`：存在持续资源占用增长线索；没有足够长时样本、分配栈和受控工作负载，不能确诊泄漏或证明它导致旧SSH失联。这个趋势也不支持立刻宣称新启动已经稳定。

## 对后续采集的影响

旧的INVALID记录保持有效：上次像素探针运行0次，没有新测试GPU提交，因此02:40的GPU故障不能归咎于那个尚未运行的R8采集。

这次已确认新的R6身份、恢复文件存在以及临时保活。尚未在新启动实例完成真实编译/链接、observer ABI和完整运行前健康核验；保活不是像素采集验收。

唯一后续实验仍是取得完整单次R8 legacy快照；只有这份基线有效后，才有条件比较仅改变Command Buffer边界的staged对照。新出现的超时/reset/watchdog仍应停止实验，不以自动重试或保活进程掩盖故障。

## 离线复核与产物

```sh
python3 ga412/tools/analyze-ssh-recovery.py --output ga412/reports/R6-SSH-RECOVERY.json
```

该脚本只读取本地已保存回执、gpuRestart、spin和IPS，不建立SSH或执行GPU命令。它验证新旧session、NG UUID、断言和直接文件stat，导出事件字段，并为引用的所有私有证据计算SHA256与大小。缺少或不匹配的必要证据会报错。

- [机器可读证据索引](R6-SSH-RECOVERY.json)
- 私有原件：`ga412/private/commands/`、`ga412/private/previous-failure/`
- 旧失败原件：`ga410/private/commands/ga411-r8-once-preflight-{identity,media}.json`
- 已封存结果：[旧INVALID报告](../../ga411/reports/R8-LEGACY-ONCE-RESULT.md)

这里只提交分析源码、报告和hash索引，不提交原始私有日志。
