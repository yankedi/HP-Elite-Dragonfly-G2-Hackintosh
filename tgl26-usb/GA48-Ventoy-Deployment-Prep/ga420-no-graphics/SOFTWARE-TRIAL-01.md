# GA420C：基本显示桌面已实际验收，开始稳定性对照

## 本轮已结束并封存；issue草稿已准备

全量流已自然SSH255结束，没有当前采集。`reports/SOFTWARE-STREAM-END.json`已完成gzip及压缩/未压缩双SHA核验：2822835856原始收到字节、2613574完整事件、198641921压缩字节；唯一非法JSON为断连时末尾386字节半事件，原始字节未丢弃。事件范围01:20:27.497155–02:20:57.069752+0800，最后事件mach uptime3755.014秒（约62分35秒）。`reports/SOFTWARE-SHUTDOWN-EVIDENCE.json`有02:20:55 shutdown确认、ShutdownLogoutUIManager shutdown及GUI退出开始；符合主动关机序列，最终物理断电未由SSH观测。没有因SSH255新增panic。

本轮可总结为：实验GPU栈运行时近期四次252–340秒panic；该栈未加载且保留基本软件桌面时，本次持续约62分钟，无用户报告卡死，末尾进入关机序列。单次对照/负载未量化匹配仍不能定位具体组件。

用户将自行提交issue；标题和完整英文正文已写`ISSUE-DRAFT.md`，明确是HP本地移植/非纯上游HEAD，含四次panic表、运行时对照证据、准确构建身份和问题。草稿未发布。私有日志及完整身份不直接附入草稿。

## 延长观察结果：本轮初步对照已足够

用户“2点了，还没崩，这个数据量够了吧”。2026-10-27 02:11:12+0800独立SSH确认仍为同一boot，uptime3165.475秒（52分45秒）；完整kext再次确认无TGL/HookCase/NGreen，远程全量log PID799已运行50分45秒。收到gzip175847809字节只是进行中快照，不是最终文件大小/完整性结论。原件`private/macos-live/C-extended-observation-20261026T181113Z.json`，结论`reports/SOFTWARE-OBSERVATION-01.json`。

对比本轮此前GA419四次252.560–339.564秒失败，无故障窗口明显拉长，足够结束首轮用户在场观察，显著加强实验图形栈相关性的怀疑。未量化匹配工作负载、只有一次无故障试次，不能认定具体组件已定位或永不再崩。用户可以正常关机结束本轮，无需熬夜；代理不执行关机，采集保持到自然断连后完成gzip/双SHA验收。下面仍等待较长观察的段落为初始计划，当前判断以本段为准。

## 本次实际状态

用户明确“已进入mac”；SSH独立确认macOS26.6.2/25G83，boot`REDACTED-MACHINE-ID`，开机2026-10-27 01:18:27+0800，有效`ga420csw=1 -igfxvesa`。

12项完整只读观测全部exit0，完整kext、IOService/IODeviceTree、system_profiler、dmesg、ps等先原样保存开发机`private/macos-live/software-baseline-20261026T172104Z/`，再本地分析。运行时报告`reports/SOFTWARE-RUNTIME-01.json`逐原件SHA记录。

## 已证明的显示路径

- 核显仍是IOPCIDevice/VGA（class-code00000300），报告device-idffff，未关断设备。
- 可见1920×1080、32bit桌面；system_profiler标明GPU驱动未加载，7MB标签。
- 实际路径`PC00/AppleACPIPCI/IGPU/.Display_boot`是`IONDRVFramebuffer`，IOFBMemorySize=8294400字节，连接AppleDisplay及FramebufferUserClient。
- 完整加载表中没有TGL framebuffer、TGL accelerator、HookCase或NootedGreen；原WhateverGreen1.7.1加载。
- 没有实际IntelAccelerator或AppleIntelFramebufferController服务。树中有`IOKitRegistryCompatibility/display/IOAccelerator`名字，但其类是IOServiceCompatibility，只是兼容节点，不是GPU加速器。
- 因此“保留可用桌面/基本固件显示且实验GPU栈未运行”的对照条件已实际成立。未另做每个应用的renderer API查询，不把缺失的per-app信息编造为已测。

## 全量日志正在持续采集

- stem `private/macos-live/all-debug-20261026T172026Z`，最早真实事件01:20:27.497155+0800，来自kernel，handshake和事件已验。
- 开发机collector PID117775，异步shell`sh_1793a4e520011Dbbp4C9Ek5gt9`。
- 无进程/predicate筛选、无时长/大小上限、不采样丢弃，开发机无损gzip。**不要因响应结束主动停止或重复启动。** 不跨boot自动重连。
- 采集从本次boot约120秒后开始；不声称覆盖此前全部启动历史。gzip最终trailer和双SHA等流自然结束后核验；进行中不误报为损坏。

## 稳定性仍待观察

进入桌面与无加速验收成功，不等于内存panic已修复或图形已被证实是根因。用户用与之前尽量相似的日常操作；卡顿允许，记录实际工作负载，关注原pmap/链表等故障。先20–30分钟，再更长时间；不对日志采集设置对应停止时间。若再次卡死由用户控制重启，之后原样取新panic并核对boot/时间，不把断连本身算panic。

其他外围配置来源保持GA419，但本次尚未逐设备重新物理验收，不以历史反馈冒充C版实测。
