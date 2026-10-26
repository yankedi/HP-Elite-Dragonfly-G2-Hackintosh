# GA416 第五份 panic 与当前分类

**2026-10-26 续审：** 第五份的 kernel 帧已用UUID匹配25G83 KDK私有符号区间补齐，见 [GA417 Panic证据](../ga417/PANIC-EVIDENCE.md) 和 `../ga417/reports/PANIC-KDK-SYMBOLS.json`。AppleFSCompression/APFS帧仍保留原始kext归属，不冒充全部私有符号化。下文“尚未补全”保留为取得续审结果之前的历史状态。

2026-10-25 20:43 +0800，从用户手动恢复的 boot
`F83A1346-445B-49F2-B84C-EE0169369D20` 重新清点诊断目录。

最新全量原件：`private/crash-series/panic-inventory-20261025T124307Z.json`。
当前已确认本轮 **5 个独立 incident、3 种 panic 签名**；此前四事件 JSON
`reports/L3-6-CRASH-SERIES.json` 仍为取得第五份之前的快照，不代表最新计数。

| 签名 | 本轮独立事件数 | 现场任务 |
|---|---:|---|
| `pmap_recycle_page: page ... is referenced` | 3 | TrackpadExtension、log、spindump |
| `not in the expected zone early.kalloc.48` | 1 | VTDecoderXPCService |
| `no checkins from watchdogd in 98 seconds` | 1 | kernel_task |

另有已保留的历史 WindowServer 120 秒 watchdog 事件，计入它则是当前清点
目录中的 **6 个 incident、4 种具体签名**。这不是整个项目所有历史 panic 的穷举。
不同签名不是已经证实的独立根因；共同根因及最早损坏者仍未证明。

## 新发现的第五份

- Incident：`REDACTED-SESSION-ID`。
- 文件：`Kernel-2020-01-01-080054.panic`。
- SHA256：`9d760edfe1e150c5ec6194ee00455dbc25ecaa3c96294b871f1d0724b6ec4347`。
- `pmap_recycle_page: page 0x101313000 is referenced @pmap.c:1511`。
- CPU2、任务 `spindump` PID1187；uptime `981120527292 ns`，即16分21.121秒。
- 25G83、相同 release kernel UUID、相同 bootargs，shutdown NO，sleep字段0。
- 原始栈含用户缺页 → vnode/APFS page-in → AppleFSCompression 解压／
  IOFreeData及VM页面释放检查。尚未对此栈补全KDK私有符号；原始最近导出
  符号不应全部当作精确函数链。
- 该事件是新增incident，但不是新增panic签名。任务名及栈中的文件系统组件
  不单独证明它们是最早破坏内存状态的组件。
- 与用户20:33附近卡死场景相符，尚未在本记录中做旧boot实时流的单调时钟
  精确对齐；不能以2020文件时间作为真实发生时间。
