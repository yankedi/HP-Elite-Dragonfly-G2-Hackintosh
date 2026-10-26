# GA420 首次启动：用户报告停在verbose画面

## 回NixOS后的实际证据

用户已手动回NixOS，独立SSH核验新boot`86d88ffa-2411-48d1-ba45-a74e807c67c9`。完整366项固件变量、Linux dmesg/journal、内部OC全部文件清单及完整OC日志已先取回开发机；U盘镜像独立只读挂载，全文件逐SHA核对，所有原文件与交付完全相同，仅新增`opencore-2026-10-26-162349.txt`。内置GA419 OC也未改变。原始采集`private/post-failure/20261026T163203Z/`，分析`reports/FIRST-TRIAL-ANALYSIS.json`。

**已定位对照没有成立的直接原因：三个图形排除操作全部失败。** 原始日志06.285/06.295/06.302秒分别为TGLGraphics/TGLFramebuffer/HookCase的`Prelinked blocker (Exclude) ... Unsupported`。`boot.efi`明确收到`ga420nogfx=1`，因此不是用户误选内部GA419；但不能把标记生效当作驱动停用成功。此处Unsupported是这三个目标上的实测结果，不泛化声称所有KC的Exclude均不支持。

当前没有数字`AAPL,PanicInfo0000–0006`，只有`000K`，其SHA`8547ccfb…`与前次完全相同；没有新完整panic可恢复。日志早期“automatically rebooted after panic”在本次内核启动前输出，不能当作本次GA420新panic。显示停滞的具体原因仍未知。

**修订候选GA420B已放U盘，未启动。** 三项策略改为`Disable`，源码确认其处理KC的kmod入口并使启动返回失败；其他设置/EFI文件与GA420保持，标记改`ga420bnogfx=1`。新IMG`HP-Tahoe-GA420B-NO-GRAPHICS-DISABLE.img` SHA`cb1e20f8225d69dabf8fc86b8f4d17aa13c324395df1eb7baacbf846a662fe85`，见`GA420B-DISABLE.md`与`reports/USB-DELIVERY-DISABLE.json`。实际停用与可用桌面仍需下一次现场验收。

用户重申对照目的：显示驱动修复前没有这些panic，即使显示卡顿；本轮接受卡顿，重点观察原类panic是否重现。这是用户历史体验与因果检验线索，不把相关性提前宣布为已证根因。

## 当前事实

- 用户在GA420交付后发送屏幕照片并说“卡住了”。照片仅在会话附件，没有宣称已在本地归档。
- 屏幕已出现用户态进程contextstored/audiomxd、APFS和Wi-Fi APPLE80211初始化消息；可见区域没有明确panic字符串或panic回溯。
- 可见AppleKeyStore/MACF、AMFI non-fatal、code-signature page-shift消息。这些不是目前已证明的卡点；最后一行也不等于第一故障点。
- 两次使用既有严格主机身份的macOS SSH连接均返回255，`No route to host`。原始回执在`private/macos-live/reachability-20261026T162606Z.json`与`reachability-20261026T162642Z.json`。
- 因网络不可达，尚未取得本次boot UUID、有效boot-args、kext/IORegistry、panic或完整日志，无法证实缓存中的TGL/HookCase实际已排除，也无法区分整机hang与显示切换/用户态图形启动失败。

## 结论边界与下一操作

本次记录为**未到桌面的启动故障，无法进行有效稳定性对照**。不能计作新的已确认内核panic，也不能据此排除图形栈对先前内存损坏的影响。

用户手动回NixOS后先原样取固件PanicInfo（如果存在）和本次OpenCore日志，再核验IMG内配置/文件。旧panic变量可能仍是GA419残留，必须按原始内容/哈希比对，不把旧内容当新panic。需要确认本次缓存阻止路径和固件基本显示交接后再做修订候选，不让用户原样反复启动同一失败镜像。

当前无全量macOS采集流；代理未执行重启或系统端文件修改。构建/USB静态验证通过属于交付时事实，不等于本次启动验收通过。上面回NixOS后的证据优先于本节故障发生时的待取状态。
