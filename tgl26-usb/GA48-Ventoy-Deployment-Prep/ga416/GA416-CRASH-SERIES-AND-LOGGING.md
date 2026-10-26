# GA416 多次崩溃、增强日志及 RTC 调查

2026-10-25。最新结论：**现已确认四份新 panic，根因尚未证明。**用户手动恢复启动后，新取得 `6D7209BA-EF7A-4CE6-9FD8-35A33E55810D`，再次为 pmap 引用断言，最后回传距 panic uptime 仅 6.587 ms；详情见 [第四份 panic](GA416-FOURTH-PANIC.md)。下文保留此前采集过程，注明后续确认。

用户补充多次开机后只等待也会崩溃，等待时间不同；因此打开“隐私与安全性”不再是唯一或必要触发条件。用户确认本轮从 HP 内部硬盘引导；这是用户现场报告，不能用当前 NG UUID 独立证明启动介质。

## 四份 panic 的共同点和差异

以下按运行时长排列，**不是按发生顺序**。两份文件日期回到了 2020 年，不能按文件名或 mtime 排序推导时间线。

| 运行时长 | 检测到的异常 | 当前线程所属任务 | Incident |
|---|---|---|---|
| 13 分 11.510 秒 | watchdogd 98 秒未报到 | kernel_task | 2A1A0C70-8653-4835-976D-9F65B7305672 |
| 19 分 52.044 秒 | pmap_recycle_page：页面仍被引用 | TrackpadExtension | B917E5B8-0501-47BD-8520-D38B59A725E0 |
| 20 分 18.757 秒 | pmap_recycle_page：页面仍被引用 | log | 6D7209BA-EF7A-4CE6-9FD8-35A33E55810D |
| 39 分 31.089 秒 | 对象地址不属于预期 early.kalloc.48 zone | VTDecoderXPCService | 1EB6C969-8EC2-418E-A4E9-01F21BDF49BD |

共同事实：

- 全部为 25G83，Release X86_64 内核 UUID `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`，启动参数相同。
- 全部 `System shutdown begun: NO`；Sleep 字段为零；压缩内存和交换空间报告 OK。
- 全部没有保留下来的完整 panic-time stackshot；字段解码为 `no on disk or sleep/wake failure panic stackshot found`。
- 三次内核内存管理一致性检查失败（其中两次相同 pmap 断言），一次 watchdogd 超时；不能直接断定四次同根因，也不能由不同进程名断定是独立应用问题。
- panic 文本没有记录已加载 NG 的 UUID，不能用当前启动身份替代每个崩溃启动的身份。

历史 `B8572953-6114-4FC0-94E2-0693162ACF22` 是 WindowServer 120 秒超时，单独作历史比较，不计入四份新 panic。

## 实际使用匹配 KDK 补全了栈

目标机已经安装 `KDK_26.6.2_25G83.kdk`。本轮读取 Mach-O UUID，确认其 x86_64 release kernel 及对应 dSYM UUID 都与 panic 完全一致，然后按各 panic 的 kernel slide 使用 `atos` 重新符号化。

这比仅依赖 panic 中最近的导出符号更准确；原文部分 `vm_object_sleep` 等名称不是完整私有符号，不能当作真实函数链的最终解释。

得到的关键路径：

1. **Zone 异常：** `ipc_right_dealloc → ipc_notify_no_senders_kobject → IOMachPort::free → OSObject_typed_operator_delete → zfree_ext → zone_invalid_element_panic / zone_page_metadata_index_confusion_panic`。
2. **页面仍被引用：** IOSurface `get_value` 路径进入 `OSSerialize::free → kmem_free_guard → vm_map_remove_and_iunlock → vm_map_entry_free_locked → vm_object_deallocate → vm_object_terminate / vm_object_reap → vm_object_reap_pages`，随后触发页面一致性检查。

这些是**发现异常的清理／释放路径**，尚未找到较早的非法写入、错误映射或引用管理操作，也不证明是某个特定 kext。

## 日志能力核对及实际增强

20:04 的实测：

- `kern.osbuildconfig=release`；系统日志模式 `INFO STREAM_LIVE`。
- `kern.msgbuf=10485760`，内核消息缓冲为 10 MiB。
- 已验证部署的 OC 配置启用 `AppleDebug=true`、`ApplePanic=true`，并启用 DebugEnhancer；当前加载清单可与原始回执交叉检查。
- 读取进程级 kernel 日志配置失败：`log config --status --process kernel` 返回无法读取 pid 0，`--process 0` 也不接受；没有把失败查询或未执行的配置更改写成成功。
- `/cores` 为空；`kern.coredump=1` 是用户进程 core 控制，不能据此认定内核转储已启用。
- `/System/Volumes/VM/kernelcore` 为 1 MiB：256 个 4 KiB 块，每块 4095 字节零加换行，没有有效转储头。双端 SHA-256 相同：`54313a7a14895407b19c55146482d436aff74881a18d9fb83baf0b0ca960f712`。**它是占位内容，不能用于内核内存分析。**
- 匹配 KDK 包含 x86_64 `kernel.development` 和 `kernel.kasan`；用 `file` 和 Mach-O header 实际确认。它们尚未安装到启动 KC，当前仍为 release；开启 KASAN 也不等于所有未插桩的第三方 kext 都会获得相同检查覆盖。
- `ktrace info` 显示 kdebug buffer 未初始化、kernel tracing disabled；有 tailspind 后台归属，后续不能盲目重置并覆盖其配置。
- `sysdiagnose` 和 `ktrace` 工具存在；未在本轮执行重型 sysdiagnose 或开启内核 trace。

实际增强：先按 boot UUID 和完整命令核对后，只终止自建的 Info 日志采集进程 PID 903，正常封存此前 570745 字节记录。随后为同一 boot `REDACTED-MACHINE-ID` 启动最多 30 分钟的 Debug 实时采集。

新增采集包含 kernel、watchdogd、WindowServer、VTDecoderXPCService、TrackpadExtension、MTLCompilerService；不再排除原来两类无线消息。使用 NDJSON、`--level debug`、`--source`、`--backtrace`，保存已有的源位置和可用回溯，不等于每个事件的完整线程栈。没有改变持久日志配置、EFI、NVRAM、驱动或 KC。

## 本轮再次卡死，已有崩溃前回传

- Debug 回传始于 **20:07:25**，最后事件 **20:12:00.698524 +0800**。
- 本地保存 **11210218 字节、10991 个事件**，包括 6039 条 Debug、4815 条 Default、94 条 Info、33 条 Error、10 条 activity 事件。
- 完整文件 SHA-256：`655238b22e6729b7214297c19a189443def7841b17d5e24762fb281325e55e8a`。
- WindowServer 有 **8 次 `synchronize timed out`**，分别在 20:08:13–14 和 20:11:32–35。后者之后仍收到 kernel、WindowServer 和 watchdogd 消息，故它不是已定位的全机停止时刻。
- 最后收到 watchdogd 消息为 **20:11:54.827624**；这不是最后成功 check-in 的证明。
- SSH 于 **20:12:14.897 UTC+8** 超时结束（回执 UTC 为 12:12:14.897），rc 255。用户随后回答“**又卡死了**”，确认桌面、触屏、外接鼠标整体无响应。
- 本轮 clock-history 日志查询也因断连失败；未获得结果。不能把查询发出时间等同卡死起点，也不能由时间相邻认定查询导致卡死。
- 当时尚未恢复新 panic；**后续用户手动重启已取回并确认第四份新 panic**，见顶部及独立报告。最后日志不是最早损坏点；蓝牙服务断连、同步超时和无线日志均只能作为现场线索。

该段采集已因 SSH 失联结束，没有自动重连、重启或循环测试。用户恢复后的新 boot 单独启动了新一段限时采集。

## BIOS 时间丢失／RTC 线索

用户报告每次运行 macOS 后，下次开机 BIOS 报系统时间丢失。两份新 panic 的报告时间为 `2020-01-01`；当前进程列表还出现跨多年 elapsed time，与开机后墙上时间被大幅校正相符，但不能单靠这些证明谁写坏了 RTC。

进一步离线分析已经保存的 16871 条持久日志、7 个 boot，发现 **3 个 boot 内部同时有先 2020、后 2026 的消息，且单调时间递增**：`REDACTED-MACHINE-ID`、`REDACTED-MACHINE-ID` 和本次 `9B645EE2-32EA-4EB1-BCCB-668460AC4634`。这把时钟异常从“文件名线索”推进到实际跨时钟校正证据；仍不能据此确定 RTC/CMOS 的具体破坏者。本次 `--last 6h` 查询实际包含这些 2020 消息，不能反过来说它们已经被该查询排除了。

当前实测：

- 联网后时间正确，时区 `Asia/Shanghai`，`Network Time: On`；不证明 RTC/CMOS 内容正确，也不能证明 macOS 没有写入 RTC。
- `AppleRTC` registered/matched/active，RTC 节点 IO memory address 112、length 8。
- 已部署基线 OC 配置：`Kernel.Quirks.DisableRtcChecksum=false`，无 AppleRTC Kernel.Patch，无 RTCMemoryFixup。
- BIOS 提示原文／错误码／照片尚未取得。应区分固定 UTC 偏移、RTC 无效／复位、CMOS 校验不符及断电保持问题。
- `DisableRtcChecksum` 等只能按其实际覆盖范围评估，不能保证解决所有 RTC 区域写入、固件时间或电池问题；本轮没有启用任何 RTC 修复。
- 查询崩溃历史时不能只依赖墙上时间窗口：RTC 回到 2020 时，文件日期／时间筛选的含义需要实际核对。优先关联 boot UUID、单调时间及报告身份。

DS 上游研究另见 `GA416-UPSTREAM-CRASH-RTC-RESEARCH.md`（研究完成后整合；文件未生成前不得称已完成）。直连 DeepSeek 因余额不足失败，已切至 OpenCode Go DS。

## 证据与下一步

- 结构化汇总：[`reports/L3-6-CRASH-SERIES.json`](reports/L3-6-CRASH-SERIES.json)。本地重现：`python3 ga416/tools/summarize-crash-series.py`。
- 原始快照、完整流、匹配 KDK 符号化结果及占位 kernelcore：`ga416/private/crash-series/`。
- 固定 SSH 命令回执：`ga416/private/commands/logging-*`、`kdk-core-capability-*`、`panic-kdk-symbolication-*`、`rtc-clock-history-*`。
- 下一次用户手动恢复 macOS 后，优先收集新增 panic／NVRAM，并与本次 boot 和日志末尾关联；不自动重放旧采集。
- 若普通 Debug 流仍不能定位内存破坏者，再设计独立的 development／KASAN 或适配硬件的内核现场采集方案；修改 KC、EFI 或启动参数需单独明确授权。RTC 修复与崩溃诊断分别验收。
