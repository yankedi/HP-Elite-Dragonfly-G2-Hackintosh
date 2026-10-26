# GA416 Exa追加调查与Perplexity访问结果

2026-10-25。用户要求使用Exa，随后追加Perplexity。完成6组Exa搜索并读取原始页面、GitHub issue/commit和RTCMemoryFixup源码。另一组Exa请求触及免费MCP限额。Perplexity验证码认证成功，但MCP与独立CLI搜索仍403；**没有取得Perplexity搜索答案**。

原始搜索、源码、issue/评论、commit及回执存于`private/exa-followup-20261025/`，SHA-256清单为`source-manifest.json`。本轮仅网络调查及开发机离线比对。

## 1. 进一步核实Metal每个command buffer约96KB的泄漏修复

原始报告：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/12>

修复：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/06986480e4d9c1383e57ad4e8e89213b5f124bc9>

- 报告平台：Dell Latitude7430、i7-1265U、macOS26.7.1/25G241，16.0.32移植Metal驱动。
- WindowServer从6.5GB增长到10GB约20分钟，主要在用户态MALLOC_MEDIUM。
- 最小复现：1500个已提交command buffer留下1500个约96KB的POSH块，command buffer对象本身已经释放。
- 上游分析指向`-[MTLIGAccelCommandBuffer dealloc]`：仅活跃command buffer跳过其私有POSH块的delete，而queue共享指针在该构建中始终为NULL。
- 修复在该二进制文件偏移`0x7ed87`将`75 0d`改为`90 90`；维护者报告3000个command buffer后0个残留块。
- 原报告者2026-10-25复测：1500个command buffer残留0块；WindowServer在30分钟普通使用含视频期间约166–219MB，末尾179MB，无增长趋势。

这是已有上游研究报告§2.3提及的缺陷，本轮重新取得issue、评论和commit核实。它有最小复现与原报告者复测，但**本机是否包含相同故障分支仍未核验**。这是用户态泄漏，不是已确认的内核wrong-zone或pmap修复；本机panic没有提供对应OOM证据。NOP安全性依赖该构建queue指针始终NULL，不能未经版本和代码核对照抄偏移。

## 2. RTC005：HP上的具体软件修复记录

### HP EliteDesk800G3

原始项目：<https://github.com/RomLecat/efi-hackintosh>

作者明确报告macOS后BIOS005，采用RTCMemoryFixup并设置：

```text
rtcfx_exclude=58-59,B0-B3,D0-DF
```

随后报告错误消失。这是KabyLake/i5-7500T/Mojave等旧平台，**不是DragonflyG2/25G83验证**。

### HP Elite x2 1012G2

原始项目：<https://github.com/whatnameisit/HP-Elite-X2-1012-G2-Hackintosh#sleep-wake-and-hibernation>

作者列出冲突偏移至少`58,59,7F-83,B0-B3,B7,DE,DF`，普通睡眠/唤醒可改善，但休眠恢复及安装/更新仍可能005。这说明各平台和不同操作的有效偏移范围不同，不能直接套一组范围。

### 上游RTCMemoryFixup机制与25G83待核验点

<https://github.com/acidanthera/RTCMemoryFixup>

核对源码提交`4f1db4e1ca1f4115346a2792bcb55ca29b758b0c`：

- 在PNP0B00的IOACPIPlatformDevice provider上hook `ioRead8`/`ioWrite8`，对指定CMOS偏移在RAM中模拟读写，避免相应硬件写入。
- 必须成功加载并hook对应kext，单加boot-arg不会生效；源码没有内建HP通用排除范围。
- `-rtcfxdbg`输出初始化、范围解析、hook等状态；逐次端口访问详细日志在源码中被注释，不能声称该参数能提供完整RTC写入追踪。
- 官方说明0x80–0xAB用于休眠资料，排除此区会影响休眠；不能无差别全范围屏蔽。
- provider虚表槽固定为`ioRead8=0x978/8`、`ioWrite8=0x960/8`；本轮未核验与25G83实际provider ABI匹配，不能称Tahoe兼容已验证。
- 它不按普通Lilu插件方式注册，但Info.plist仍声明Lilu库依赖，不能说完全不依赖Lilu。

## 3. RTC I/O资源长度8→2候选，与本机AML匹配

页面：<https://imacos.top/2022/03/10/02143/>

文章称HP Z240SFF的005可通过ACPI替换改善：

```text
Find:    47 01 70 00 70 00 01 08
Replace: 47 01 70 00 70 00 01 02
```

对已经取回的本机DSDT做只读二进制匹配：Find恰好1处，文件偏移`0x201f4`，与反编译RTC `_CRS`的I/O起点0x70、长度8一致。

**这里改的是I/O端口资源长度，不是把RTC存储从8字节改成2字节。**两个I/O端口可通过索引访问许多CMOS单元。字节匹配只证明目标存在，不证明该方案在本机有效。这是外部平台方案，本机尚无对照结果；本轮未应用补丁。

如后续验证，应与RTCMemoryFixup排除范围分开实验，以免无法归因。

## 4. pmap论坛候选：相似点及更多混杂变量

原文：<https://www.hackintosh-forum.de/forum/thread/60523-macos-26-tahoe-auf-den-hackintosh/?pageNo=21>

作者报告页`0x180009000`附近±64KB、Linux无保留区。尝试在OC中预留周围区域未解决；禁用RebuildAppleMemoryMap、SyncRuntimePermissions并启用EnableWriteUnprotector后压力分配/释放不再复现，SetupVirtualMap=false未单独隔离。

与本机页集中且Linux视为普通RAM的特征相似，支持保留内存策略对照的实验价值；作者未找到实际失败分支，不能因此认定本机根因。

本轮取得#409附件diff，UTF-16解码后确认是**BIOS设置差异，不是OC配置diff**：E核0→All、VT-d禁用→启用、Runtime Variables保护等同时变化。作者还提及CpuTopologyRebuild/NVMeFix等因素。它不是严格的仅3项Quirks差分实验，单项因果证据较弱。

## 5. 结论与访问边界

1. RTC005有具体HP软件修复记录；先核验本机适配，再独立对照，不能由其他型号结果直接推定有效。
2. Metal POSH泄漏有明确上游修复和复测，但不是当前pmap/wrong-zone根因证据。
3. OC内存策略组仍是探索性候选；本机MmapDump结构正常不能替代macOS最终交接图或panic时页状态。
4. 本轮完成的搜索未取得本机25G83/TigerLake `early.kalloc.48` wrong-zone确定修复，也未找到三个具体0x10131*页的匹配原始案例。旧Catalina zone耗尽、BSD pmap及AMD NootedRed早期启动panic不属于同一问题。

上述否定结论仅限已检索材料。Exa另一个查询组被限额拒绝；Perplexity邮箱验证后账户检查显示Pro active，但usage仍取不到额度，线程列表、MCP搜索、独立新CLI搜索均403。没有取得Perplexity答案，未继续重复验证码或搜索请求。

原始回执不保存用户验证码。后续若部署，RTC、Metal、OC策略分别验证，保持既定图形栈，由用户手动重启。
