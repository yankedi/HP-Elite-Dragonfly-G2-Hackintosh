# GA416 OpenCore内存诊断实测结果

2026-10-25，用户手动启动独立`HP-Tahoe-GA416-OCDBG-BASELINE.img`，运行一次`GA416 Memory Map Diagnostic`，返回菜单后手动重启到NixOS。本轮只读取回该镜像日志及SysReport，并在开发机分析。

## 结果概览

**诊断采集成功；未发现三个问题物理页被标成固件运行时或设备保留区的证据；panic根因仍未证明。**

| 项目 | 实测结果 |
|---|---|
| 新Linux boot ID | `REDACTED-MACHINE-ID` |
| 新OC日志 | `opencore-2026-10-25-131626.txt` |
| 日志SHA256 | `b1bb3258f496037e4fdae60f1018bfb0dc184360a5cd3a3f0778c5df13d76d41` |
| 固定日志文件/有效非零尾内容 | 262144 / 250439字节 |
| 新文件 | 54份：1份OC日志与53份SysReport文件 |
| 全部取回文件 | 64份，包含10份继承的旧日志；原始字节与SHA均核验 |
| 封存基线文件变化 | 0；包括全部OC/kext/config文件 |
| 运行后USB镜像SHA256 | `a28cee1d5e155d6fc40672ec467efc4892611988d960319dcedaf00145695284` |

镜像新增日志后的SHA不同是运行后状态，不替代发布前SHA。原始文件留在`private/oc-memory-debug/post-mmap-extracted/`；含私有ACPI/SMBIOS/MSDM输入，不公开或提交它们。

## 1. 三个问题物理页

`0x101311000`、`0x101313000`、`0x10131c000`在三组图中都落于同一个descriptor：

```text
Available 0x0000000100000000–0x00000004AF7FFFFF
无RUN、RO、XP标志；具有WB/WT/WC/UC缓存能力标志
```

与上一轮Linux E820/`/proc/iomem`一致：System RAM；当前PCI资源、EFI runtime-map均不重叠。缓存能力标志同时列出不等于CPU同时以四种缓存模式访问。

这是**OC及OpenRuntime已加载后的诊断工具时刻**，不是纯固件图，更不是上次panic或macOS最终交接图。仅凭该结果不能判断XNU对页的managed属性、反向映射或最早内存损坏者。

## 2. MAT与内存图检查

| 输出阶段 | descriptor数 |
|---|---:|
| 初始MAT | 38 |
| 工具原始内存图 | 445 |
| 重建后MAT | 38 |
| 按MAT分割的内存图 | 479 |
| 工具压缩图 | 60 |

验证所有输出计数、descriptor size48字节、图大小、4KiB边界、区间无重叠。38条MAT均完整包含在原始图的runtime descriptor内，具有RUN且各有RO或XP之一；没有覆盖问题页。MAT描述字段在重建前后**逐条相同**。

原始MAT中一部分`RT Code + XP`描述数据子区，工具分割后转为`RT Data`；不能仅凭这个名字组合判定固件错。压缩图会合并/转换可回收区，是工具处理结果；不是已经证实macOS会收到的最终图，也不代表应把479条一概视作内核故障。

工具没有打印`Cannot patch memory map`；输出三组完整图并成功返回菜单，末尾仍有未用日志空间，内存图没有被256KiB文件截断。

## 3. 为什么到菜单很慢

日志第一列单位是**秒:毫秒**，`129:046`表示129.046秒。

| 阶段 | 自OC日志起点的时间 |
|---|---:|
| 首次显示菜单 | 129.046秒 |
| 诊断工具开始输出 | 218.678秒 |
| 输出原始图开始 | 218.994秒 |
| 输出重建MAT开始 | 316.029秒 |
| 输出分割图开始 | 325.433秒 |
| 输出压缩图开始 | 431.544秒 |
| 工具返回 | 448.799秒 |
| 再次显示菜单 | 522.755秒 |

- 工具本身约230.121秒，其中绝大部分是大量descriptor逐条输出；含官方代码固定3秒等待。
- 到首次菜单的记录中，最大相邻日志间隔0.880秒，没有一个几十秒的无输出停顿。进入菜单后的88.115秒空档是等待用户选择区间，不计入启动扫描耗时。
- 当前`DisplayDelay=0`，不是人为配置了逐行休眠。
- OC1.0.8源码`Library/OcLogAggregatorLib/OcLog.c:425–435`表明：这份`Target=0x43`启用的普通安全文件日志路径，会反复覆写完整固定日志缓冲区；另一条unsafe路径才是增量写入并Flush。不能混称当前使用unsafe增量Flush。
- DEBUG/INFO、SysReport、控制台输出及经Ventoy虚拟磁盘反复写文件，均能贡献诊断开销；这里观察到广泛逐条延迟，**没有隔离测量控制台、USB、Ventoy与扫描各自的占比**，不能声称已经精确归因某一个设备。

这份引导用于采集证据，不应把它的129秒直接当作原Release引导或macOS运行时卡死的耗时。无需再次运行MmapDump重复同样采集。

## 4. RTC的新对照

在同一台机器上，前后两次Linux最早`rtc_cmos`日志：

| 启动序列 | 最早读到的RTC |
|---|---|
| 用户报告macOS后，进入Linux | `2020-01-01T00:00:47 UTC` |
| Linux → 本次OC内存诊断 → Linux | `2026-10-25T13:26:58 UTC` |

这次时间在Linux联网校时前已正确，不能用后来的校时解释该条早期日志。**这一次OC诊断启动没有复现Linux开机读到2020年**；不等于已经独立确认POST未显示005，更不证明macOS中某个具体组件写坏。

本轮额外离线反编译SysReport原始DSDT，看到PNP0B00 RTC设备，I/O资源0x70长度8、IRQ8，RTC与AWAC的`_STA`由STAS互斥选择；AWAC有SystemCMOS字段与读写时间方法。单独DSDT反编译出现缺少外部SSDT符号警告，因此只把这些直接可见定义作为静态线索，不把警告当作实际macOS ACPI错误或写入调用现场。未修改ACPI/RTC配置。

按用户明确指示不再走“电池坏了”的处置路线；继续软件/固件状态与macOS路径调查，不能把005当作502 checksum错误。

## 5. 后续决策

本轮完成了准备、实际启动、原始取回和离线核对。**当前证据不支持直接宣称RebuildAppleMemoryMap/SyncRuntimePermissions就是根因，或论坛三项组合能修HP。**

后续如果做内存策略对照，需要单独授权的独立可回退引导，保持全部图形栈相同，区分关联Quirks组与单项因果；不覆盖现用内部EFI。同时仍需取得实际macOS交接/现场的页管理和映射证据。RTC修复应单独设计，不与内存策略/GPU变量混为一次实验。

结构化结果：[OC-MEMORY-DEBUG-RESULT.json](reports/OC-MEMORY-DEBUG-RESULT.json)。
解析器：[analyze-oc-memory-debug.py](tools/analyze-oc-memory-debug.py)。
官方固定版本源码副本/hash在`private/oc-memory-debug/upstream-source/`。
