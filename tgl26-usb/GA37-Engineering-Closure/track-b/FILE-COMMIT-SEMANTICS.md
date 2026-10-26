# 文件提交语义（Track B）

本文档只描述主机用户态 writer 的可验证边界。它不是 APFS、XNU 或断电
恢复的保证书；这些事项在本文末明确列为未认证。

## 输入与记录

一次 `write(ctx, data, len)` 的 `data[0..len)` 是**完整快照**。writer 先
把调用者的不可变输入复制到私有内存，再通过 `recordwire` 的字节读取器
验证实际的固定 wire：`THAG` v2/v3 是 `0xc2a0/0xc2f8` 字节记录，
`108BFault` v1 是 `TGF4` 的 108 字节记录。不能把历史记录转换成 C 结构，也
不能按字段重新编码。解析器拒绝截断、尾随字节、版本/extent 不支持、乱序/重复
索引、非法 legacy record 和混合 record kind。

历史最新快照必须是新快照的精确 record-index/byte 前缀，且 kind/version
相同。相同索引但任意字节不同、索引改变或回退，均为
`SnapshotNotPrefix`；旧快照文件绝不被覆盖。增加记录是完整新文件的提交，
不是 append 到旧文件。

## 文件布局与锁

调用者显式给出已存在且归调用者所有的 parent。writer 从 `/`（绝对路径）或
`.`（相对路径）开始，对每个 component 单独使用 `openat(...|O_NOFOLLOW)`；
拒绝 symlink、`.`、`..`、重复 slash 和 trailing slash，再检查最终目录并 pin
其 fd。parent 下每次操作有唯一的 0700
`.snapshot-run-<pid>-<counter>`，其中临时文件为 0600、`O_EXCL|O_NOFOLLOW`。
所有 writer 共享一个 0600 `.snapshot.lock`，用一个 `flock(LOCK_EX)` 串行化
扫描、sequence 分配、发布和目录同步。没有 SSH、硬件、vnode hook 或内核写入。

`revisions/` 里的文件名为：

```text
00000000000000000001-<小写sha256>.snap
```

文件内容就是输入的完整原字节。旧 revision 是 immutable evidence；没有
`truncate`，也不依赖可被覆盖的 `current` 指针。最高经验证 sequence 作为
下一序号；重复 digest 会重新验证和同步原文件，而不是产生重复 revision。

## 提交阶段

1. 复制输入、解析并计算 SHA-256；
2. 锁住 parent，安全扫描并验证全部已有 revision；
3. 在 run directory 创建临时文件，循环处理 short write 和有上限的 EINTR；
4. `fsync(temp)`，再 `close(temp)`；
5. 用相对 pinned dirfd 的 `renameat` 原子发布（Linux 优先
   `renameat2(RENAME_NOREPLACE)`）；
6. 重新打开发布文件，使用 rename 前准备好的 buffer 读回、hash、逐字节比较；
7. **分别** `fsync(revisions fd)` 和 `fsync(parent fd)`。

发布后任何失败都不能删除新 revision，也不能删除旧 revision。这样即使
rename 后 verification 或 directory sync 失败，旧证据和新可见证据都保留，
新进程可扫描并重试相同 digest。

rename 之前会把完整输入 vector 的所有权移动到 writer，并预留发布后读回
所需的 byte buffer。这样即使发布后发生 `std::bad_alloc`，也不再尝试复制
输入：异常边界直接给出 `VisibleButDurabilityUncertain`，设置 terminal，并保留
已经拥有的 immutable bytes。发布前异常则清除这份 scratch ownership，不伪造
可见提交。

每次 callback 在同一 `flock` 保护下清理自己的 run directory：只允许删除自己
且已验证为 owner/0600 的 `snapshot.tmp` regular file，然后删除空的 0700 run
directory。未知 entry、symlink、错误 owner/mode 或无法安全验证时拒绝清理，
绝不删除用户内容；为防止无法清理的 residue 无限增长，已存在的
`.snapshot-run-*` 数量达到 64 时拒绝新的事务。

## `WriteResult` 与回调确认

| 状态 | 含义 | 回调是否成功 |
| --- | --- | --- |
| `NotCommitted` | 没有已知发布 revision | 否 |
| `VisibleButDurabilityUncertain` | rename 已使 revision 可见，但 verification、close 或目录同步未能认证 | 否 |
| `DurableVerified` | 读回的完整字节、digest、parser 均正确，两个目录 fsync 均成功 | 是 |

`CommitResult::success()` 只对最后一行返回 true。GA36 形状的 callback
`WriteResult` 仍只有 `{error, transferred}`，只有同时观察到
`CommitResult::success()` 才能确认。第二行会把 writer 置为 terminal，并尽力
保留输入副本；同一 writer 的后续 callback 不得被当作成功。
上层 A executor 必须保留自己的完整内存快照，直到收到第一种明确的
`DurableVerified`，遇到 ambiguous 则进入终态并让新进程做恢复。重复 callback
在已有 revision 完整验证、file sync 和两个 directory sync 都成功后才可确认，
因此没有 premature ack。

## 不能从本交付推出的结论

本 Track B 仅在本地主机普通 POSIX 文件接口上做实际文件测试。它**不认证**：

* APFS 的 copy-on-write、容器/卷组语义或 macOS 特定目录 fsync 语义；
* XNU 的 vnode、挂载、电源故障或崩溃路径；
* 物理断电、控制器缓存、UPS、电池或任意 power-loss recovery；
* GA36/A executor 的业务语义、GPU/硬件采集成功或完整安装流程。

这些边界不能因一个 Linux `fsync` 返回 0、一个有效 plist 或一次测试通过而
被扩大。
