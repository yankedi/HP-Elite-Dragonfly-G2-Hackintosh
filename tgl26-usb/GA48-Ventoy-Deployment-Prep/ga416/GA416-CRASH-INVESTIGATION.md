# GA416 崩溃调查：watchdogd 失联 98 秒，底层阻塞点尚未证明

**后续范围更新（2026-10-25）：** 用户确认多次空闲等待也会崩溃；又取得两份内存管理异常 panic，并在 Debug 实时回传期间确认一次新的整机卡死。本文保留最初 watchdog 事件证据，最新汇总见 [多次崩溃、增强日志及 RTC 调查](GA416-CRASH-SERIES-AND-LOGGING.md)。隐私页面不是已证明的必要触发条件。

2026-10-25。用户在部署内部硬盘引导后报告 macOS 崩溃，并补充最后操作是**打开“隐私与安全性”设置**。本轮通过已固定主机密钥的 macOS LAN SSH 读取诊断文件、NVRAM、持久日志及重启后的短时线程采样。

**用户随后补充：“我最后是长按关机键强制关机的。”**现场过程应记录为打开设置后系统无响应，最终由用户长按电源键结束；没有“panic 自动重启”的现场证据。保存到 NVRAM 的 watchdog panic 与用户最终强制断电是两个层面的事实，不能混成同一动作，也不能仅因最后强制关机就将此前无响应归因于关机键。

## 已确认的直接原因

新 panic 文件：`/Library/Logs/DiagnosticReports/Kernel-2026-10-25-170545.panic`。

- Incident：**`REDACTED-SESSION-ID`**。
- 它不在之前 GA416 USB 验收的诊断 hash 集合中，确为新事件。
- 文件中的 panic 与读取到的 `aapl,panic-info` 独立解码文本完全一致；解码器验证了 7-bit 编码逐字节往返。

```text
panic(cpu 4 caller 0xffffff80033f8f48): watchdog timeout:
no checkins from watchdogd in 98 seconds
(69 total checkins since monitoring last enabled)
```

内核中 `AppleSMC::SMCWatchDogTimer::watchdogThread` 调用 `IOWatchdog::checkWatchdog` 后触发 panic。**操作系统看门狗守护进程 watchdogd 连续 98 秒没有正常报到，是直接触发条件。**

该回溯是**发现超时的定时器线程**，不是 watchdogd 当时阻塞的线程。回溯列出的 watchdog 和 AppleSMC 因此不能直接认定为根因；也没有 NG/TGL 驱动的异常指令或 GPU hang 回溯可供归责。

panic 时运行了 **791.509710422 秒，约 13 分 11.5 秒**。`System shutdown begun: NO`，Sleep/Wake 的 Sleep 字段为零，压缩内存/交换空间检查为 OK。现有文本不支持“正在关机或睡眠恢复”或“交换空间耗尽导致崩溃”的结论。

**文件时间 17:05:45 属于重启后报告写出时间，不能直接当成原始崩溃的精确发生时间。**

## 崩溃前的持久日志

前一启动 UUID：`636D5DFC-CBBB-4ECF-BFE4-65F72FE7093F`。`last reboot` 对应 16:44；后一个启动记录为 17:05。持久日志里的 wall clock 与单调时间都已保留。

| 记录 | 观察 |
|---|---|
| watchdogd 最后保留下来的日志 | 16:55:38，之后没有该启动更晚的 watchdogd 日志；不是精确最后一次成功 check-in 的证明 |
| System Settings | 16:55:35 最后保留的页面切换为 Displays → Trackpad；没有保留可证明隐私页异常的调用链 |
| WindowServer | 16:56:07 仍有触控输入日志；不是此前那份“WindowServer 失联 120 秒”的旧 panic |
| 后台 Metal 编译 | 16:55:12–16:56:08，共 **800 条**来自 `mediaanalysisd_632` 的 `MTLBuildLibraryFromSourceToArchive` BEGIN 记录 |
| TCC | 16:56:10 仍有访问请求与响应记录；未找到可归因为隐私数据库死锁的证据 |
| STExtractionService | 一份磁盘写入资源诊断：613 秒内 dirtied 约 2147.8 MB，`Action taken: none`；它本身不是应用崩溃，也不证明磁盘故障 |

后台 mediaanalysisd 的密集编译是值得继续追踪的**并发活动线索**。仅凭编译 BEGIN 数量或缺少某条 SUCCESS，不能证明编译死循环、GPU hang 或其饿死 watchdogd。用户报告打开隐私页面是现场触发场景，当前日志仍不足以认定隐私页/TCC 本身有错误。

## 重启后当前系统

- 当前 boot session：`REDACTED-SESSION-ID`，17:05:34 启动。
- 已加载 NG UUID：**`4C4C44D4-5555-3144-A13A-DFB86EFBE513`**，与 GA416 交付一致。
- 本次新启动日志仍明确显示 **donor 0 → effective L3=6，80EU / 10SS**。
- 初次采集看到两个 MTLCompilerService 各约 90% CPU，之后降下来了。17:19 采样时 load average 为 `0.80 / 4.44 / 4.85`，采到的编译服务已空闲；不将短暂高 CPU 判为持续死循环。
- watchdogd 的后置采样为 RunLoop 与限时信号量等待。**这是重启后的状态，不能替代崩溃时的线程栈。**

本次 panic 文本没有前一启动的已加载 NG UUID/L3 字段，不能把当前启动的 L3 运行证据直接冒充前一启动的日志；同样，单凭 UUID 也不能独立证明这次走的是内部 ESP 还是 USB 启动路径。

## 结论与未解部分

1. **确认发生了新的系统级 watchdog panic，直接原因是 watchdogd 98 秒未报到。**
2. **尚未定位让 watchdogd 停止报到的具体线程、锁或驱动。**报告的 stackshot 字段解码后明确为：`no on disk or sleep/wake failure panic stackshot found`。现有 panic 不含所需的全线程等待链。
3. **目前不能据此判定 L3 修复无效，也不能排除图形驱动仍有其他稳定性问题。**先前桌面花屏消失和单次 R8 PIXEL_PASS 仍是已观察的事实；本次新 panic 说明不能据此宣称整机长期稳定。
4. 进一步定位需要卡死时 watchdogd、WindowServer 及内核线程的完整栈，才能找到阻塞/锁持有者。本轮没有主动打开该页面复现或追加 GPU 测试。

### 为什么会超时，当前证据解释到了哪一层

watchdog 检查的是 watchdogd 有没有按期报到。98 秒无报到表明该进程或它报到所依赖的路径没有及时完成；可能涉及等待、调度或更底层阻塞，但现有栈不能在这些机制中做选择。**“watchdog 超时”解释了为什么触发 panic，不等于解释了为什么系统最初卡死。**

最后保留的 watchdogd 日志在 uptime642.668秒，距panic791.510秒约148.842秒，而panic说缺少check-in98秒。这也直接说明**最后一条已落盘日志不等于最后一次成功check-in**，不可据它反推精确卡死时刻。用户没有提供开始卡死和按住电源键的精确时间，当前不能进一步严格排列panic与按键时刻。

结构化分析：[L3-6-CRASH-INVESTIGATION.json](reports/L3-6-CRASH-INVESTIGATION.json)。私有原件：`ga416/private/crash-investigation/`；远程命令回执：`ga416/private/commands/crash-investigation-*.json`。本轮没有更改驱动、EFI、NVRAM或重启设备。
