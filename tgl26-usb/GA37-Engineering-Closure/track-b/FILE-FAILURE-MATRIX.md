# 文件失败矩阵（Track B）

以下是 writer 的实际阶段和回调可见结果。所有“发布后”情况都保留旧
revision 与已可见的新 revision；不执行覆盖或清理旧证据。测试使用真实临时
目录、`fork`/`_exit` 和 fault injection；不是 mock-only 结论。

| 阶段/故障 | 是否可能已 rename | `CommitStatus` | writer 后续 | 上层动作 |
| --- | ---: | --- | --- | --- |
| parent open、lock open/acquire | 否 | `NotCommitted` | 可重试 | 不确认，保留内存快照 |
| revision 目录创建/恢复扫描 | 否 | `NotCommitted` | 可重试 | 修复目录/恢复输入后重试 |
| 临时文件 open (`O_EXCL|O_NOFOLLOW`) | 否 | `NotCommitted` | 可重试 | 不确认 |
| short write、EINTR 超预算、write error | 否 | `NotCommitted` | 可重试 | 不确认；临时文件不是 evidence |
| 临时 file `fsync` | 否 | `NotCommitted` | 可重试 | 不确认 |
| 临时 file close error | 否 | `NotCommitted` | 可重试 | 不确认 |
| rename/发布前目标冲突或 symlink | 否 | `NotCommitted` | 可重试 | 拒绝不安全路径 |
| rename 成功后 process `_exit` | 是 | 下次启动恢复 | 新进程扫描 | 不把本次 callback 当成功 |
| 发布后 verify open/read/close 或 `bad_alloc` | 是 | `VisibleButDurabilityUncertain` | **terminal** | 保留已转移的 immutable bytes；新进程验证 |
| 发布后 revision directory `fsync` | 是 | `VisibleButDurabilityUncertain` | **terminal** | 不确认；旧证据仍在 |
| 发布后 parent directory `fsync` | 是 | `VisibleButDurabilityUncertain` | **terminal** | 不确认；新进程重试 digest |
| 两个目录 sync 后完整 readback 成功 | 是 | `DurableVerified` | 可接收后续 callback | 只有此行可以 ack |
| 重复相同 digest | 已存在 | `DurableVerified`（重新验证/同步后） | 可继续 | 不新增 sequence，不提前 ack |
| 新快照改变已有 prefix | 否 | `NotCommitted` + `SnapshotNotPrefix` | 可重试别的输入 | 拒绝业务数据，不覆盖旧 evidence |
| 恶意 lock/revisions/temp symlink、异常 filename、硬链接、坏 digest | 否/未知 | `NotCommitted` | 可重试但应人工检查 | fail closed，不信任 recovery |

## 边界说明

发布前会预先取得输入 vector 的所有权并准备发布后 readback buffer。因而
发布后的异常（包括测试 fault 注入的 `bad_alloc`）不会回到
`NotCommitted`：writer 进入 terminal 并无分配地保留已拥有字节。发布前的
异常可以清除 scratch 临时状态。run directory 清理由单一 `flock` 保护，
只删除已验证的已知 `snapshot.tmp`；未知 entry 或无法证明 ownership 时拒绝
清理，并以 64 个残留 run directory 的 bounded admission 作为资源上限。

“发布后”不等于“已证明耐断电”。它只表示相对 pinned directory fd 的 rename
已经成功；因此在任何随后错误时都不能把新文件删除来制造一个看似干净的
结果。恢复会验证 filename digest、完整文件 bytes、wire parser 和 sequence，
然后在 fresh process 中再做 file/directory sync。

当前矩阵没有加入 APFS/XNU 特殊 ioctl、vnode hook、SSH、EFI/NVRAM 或硬件操作。
APFS、XNU、真实电源故障和 power-loss durability 在本矩阵中均**未认证**。
