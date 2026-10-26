# GA416 第四份新 panic：再次出现 pmap 页面引用断言

2026-10-25。用户确认 20:12 附近再次整机卡死后，手动重启 macOS；本轮立即读取诊断文件和 NVRAM，并用匹配 KDK 对新栈符号化。

## 新事件身份

- Incident：`REDACTED-SESSION-ID`。
- 文件：`Kernel-2020-01-01-080053.panic`，SHA-256 `e73518ff1f559f548d0f0545d219f6aabd5c79cda65f2716709452128bf613e5`。
- 此 incident/hash 不在之前三份新 panic 中，**现在共四份新 panic**；旧 WindowServer 120 秒事件仍单独保留。
- 新 panic 正文与解码 NVRAM 一致，**仅末尾多两个换行**；不是原始字符串逐字节完全相同。
- panic uptime：`1218756643342 ns`，即 **20 分 18.756643342 秒**。

```text
panic(cpu 2 caller 0xffffff80004621ee):
pmap_recycle_page: page 0x101311000 is referenced @pmap.c:1511
Panicked task ... pid 1086: log
```

仍为 `25G83`、Release x86_64、相同 kernel UUID、相同启动参数，shutdown NO、Sleep 字段为零、compressor/swap OK；没有保留下来的完整 panic-time stackshot。

## 与上一段实时回传的关联

上一段流固定到 boot `REDACTED-MACHINE-ID`，最后收到 WindowServer 消息：

- 墙上时间：`20:12:00.698524 +0800`。
- `machTimestamp=1218750056525`。

本轮实测同硬件 `mach_timebase_info`：numer=1、denom=1，因此时间基准单位为 ns。新 panic uptime 与最后收到事件差 **6586817 ns = 6.586817 ms**。

结合用户确认同一现场卡死以及 NVRAM 新 panic，时间高度吻合，支持将其关联到这段回传。**panic 文本本身没有 boot-session UUID**，不能将外部关联说成 panic 内嵌了 boot UUID。日志接近到毫秒级，也不意味着已经记录每个线程或较早破坏内存的操作。

## 匹配 KDK 后能看到的更具体路径

再次核对 `kernel.dSYM` UUID 为 `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`，与新 panic 相同；按 slide `0xe8000` 使用 `atos`。

关键调用链从用户态陷入开始：

```text
log 进程中的用户态访问
  → user_trap                  trap.c:1344
  → vm_fault_internal          vm_fault.c:6786
  → vm_fault_page              vm_fault.c:2048
  → 页面释放／pmap 引用一致性检查
  → panic                     pmap.c:1511
```

panic 原始最近符号给出 `_vm_page_free_unlocked + 0x18e`；KDK `atos` 对该 cold panic 地址没有给出更精确源码位置，所以不虚构比已有断言更细的行号。

此前 `B917E5B8` 的相同 `pmap_recycle_page ... is referenced` 来自 TrackpadExtension 的 IOSurface/OSSerialize 资源清理。本次则通过 `log` 的缺页处理遇到同一类断言。**重复的内核页面／映射一致性异常比应用名字更值得追踪**。

两次被报的页面分别为 `0x10131c000` 和 `0x101311000`，不是同一页；地址接近不证明同一写坏者、硬件 RAM 故障或某个固定驱动。

## 日志采集与触发的归因边界

上一启动中同时有实时 `log stream` 和一条只读历史 `log show` 查询；历史查询回执为 SSH 失联，无完整结果。panic 的任务名仅为 `log`，PID 1086；崩溃前没有保存能把该 PID 精确对应到某一条命令的完整进程树。

因此：

- 确认异常是在 `log` 进程的内核缺页路径被发现。
- 日志操作可能触及／暴露有问题的页面处理路径；也可能是在更早损坏后成为受害者。
- 尚不能证明日志工具本身制造了内存破坏，也不能证明是实时流而非历史查询。
- 本轮采用独立限时实时回传继续观察，记录采集子进程 PID；历史分析使用开发机已有副本。

## 当前新启动及进一步获取能力

- 新 boot：`REDACTED-MACHINE-ID`；校时后的 boottime 为 20:16:49。
- 已加载 NG UUID 仍为 GA416；当前启动 `dmesg` 再次确认 L3 override 0→6、80EU/10SS。
- 新报告写出时间又是 2020 年，不能用它作为崩溃时间；当前联网后时间为 2026 年。该文件日期与此前 RTC 线索相符，不单独证明本次开机校时的具体机制。
- `kernelcore` 仍为原 1 MiB 占位内容，SHA 不变；没有新增可用内核内存转储。
- 已为新 boot 启动最多 30 分钟 Debug 回传，新增 timed 进程；20:22:27 握手、子进程 **PID 890** 及首批真实 Debug/kernel 事件已验证。文件 `private/crash-series/passive-stream-20261025T122227Z.stdout`；这是重新确认 boot 后的单次采集，不是自动跨启动重试。

**仍可进一步获取的是未来现场**：完整内核线程栈／可用转储，或经过单独部署的 development/KASAN 与相关驱动诊断。已经重启且未转储的上一启动 RAM 不能事后读回。当前没有改 KC、EFI、NVRAM或任何驱动。

## 原件与复现

- `private/crash-series/post-hang-reboot-20261025T122002Z.json`：新启动与全部报告快照。
- `private/crash-series/post-hang-nvram-decoded-20261025T122002Z.txt`：NVRAM 解码文本。
- `private/crash-series/fourth-panic-symbolication-20261025T122055Z.json`：dSYM UUID 与原地址/符号化结果。
- `private/crash-series/post-hang-timebase-20261025T122207Z.json`：1:1 时间基准实测。
- [`reports/L3-6-CRASH-SERIES.json`](reports/L3-6-CRASH-SERIES.json)：更新后的四事件统计；`python3 ga416/tools/summarize-crash-series.py` 可在开发机离线重现。
