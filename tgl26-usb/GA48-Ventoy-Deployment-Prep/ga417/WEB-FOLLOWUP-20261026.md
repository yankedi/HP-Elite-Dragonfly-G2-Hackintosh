# 2026-10-26 网络追加复核：内存 Panic 与上游最新反馈

用户要求“网络上再搜搜”。本轮使用 Exa 搜索／原页提取、GitHub issue／评论／完整 commit diff，以及 Context7 官方 OpenCore 文档。研究 goal 保持已完成；这是追加检索记录，没有启动新的自主研究 goal。

## 结论

本轮没有找到已验证可修复 HP Elite Dragonfly G2、25G83 的 `pmap_recycle_page` 或 `early.kalloc.48` wrong-zone 的网络方案。找到并复核了上游最新变化，其中 **XE-ROWCHK 已有外部用户的“无改善”反馈**，不能按 changelog 中的 confirmed 标签推断对所有机器有效，更不能推断修复内核 Panic。

### 1. OpenCore 三项组合：旧线索重核，没有新增独立验证

原帖：<https://www.hackintosh-forum.de/forum/thread/60523-macos-26-tahoe-auf-den-hackintosh/?pageNo=21>，2026-02-13，hanspeteroliver，#407／#409。

对方为 B860-A／Core Ultra 7 265KF／RX5700／Tahoe26.2。报告 `pmap_recycle_page`、物理页约 `0x180009000` 附近，Linux 中也是普通可用 RAM；尝试预留区域未解决。切换以下组合后，作者的分配／释放压力复现不再触发：

| Booter.Quirks | HP 基线已封存值 | 外部报告值 |
|---|---:|---:|
| SetupVirtualMap | false | false |
| RebuildAppleMemoryMap | true | false |
| SyncRuntimePermissions | true | false |
| EnableWriteUnprotector | false | true |

作者未隔离 SetupVirtualMap，之前还改过 BIOS／kext；这是单平台报告，不是官方确认的根因。本轮精确搜索返回的帖子与作者聚合页是同一报告的重复收录，不计为第二例。

**这不是本轮新发现。** 已载于 `../ga416/GA416-PMAP-OPENCORE-CANDIDATE.md`、`../ga416/GA416-EXA-PERPLEXITY-FOLLOWUP.md`。本轮工作中曾先称“新线索”，核对历史后已向用户更正。

HP 已完成的 MmapDump 也不能忽略：三页在原始／分割／压缩图均为 Available，MAT38条重建前后相同，未覆盖问题页。见 `../ga416/GA416-OC-MEMORY-DEBUG-RESULT.md`。该工具时刻不是 macOS 最终交接或 Panic 现场，因此既不证实此组合能修 HP，也不彻底排除此路线；无需重复 MmapDump。

官方文档重核：<https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.tex>。RebuildAppleMemoryMap 应用 MAT 权限并处理图大小兼容问题，通常与 SyncRuntimePermissions 配合；有 MAT 时官方优先建议它而非 EnableWriteUnprotector。后者改变 UEFI runtime 调用期间的写保护，依赖 OpenRuntime。官方并没有给出适用于全部相似硬件的固定组合。HP 原组合并不是明显漏配。

### 2. XE-ROWCHK：新增提交与反例都已读取

完整 diff：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/875ce5db45ba107166ba13b9eca9738f232f3a6f>，2026-10-25 18:33:26 UTC。

上游在 render-engine start 路径中写 `GEN8_ROW_CHICKEN2 (0xe4f4)` bits14／15，并以自己的 forcewake requester 保护寄存器访问；目标为 Wa_1606931601／Wa_1508744258。维护者报告 SIMD32 private-array 测试从6/6次结果不同变为0/6，Lanczos GPU/CPU 差异从约300像素变为0。这是上游机器的 GPU 计算正确性结果，不是 HP 实测，也不是 PV／zone 元数据损坏的因果证据。

- 维护者分析／测试：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/9#issuecomment-6401531748>
- **2026-10-26 01:53:34 UTC，原报告者复测无改善**：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/9#issuecomment-6406479487>

复测者使用453a7b5（包含875ce5d），报告 `xe-rowchk-pre/post` 都为 `0xffffffffffffc000`、计数6，Preview／Photos缩放破块依旧。仅低16位为c000不能替代所有寄存器与 forcewake 有效性验证；该反馈至少表明不能将作者机器的成功概括为外部平台问题已解决。issue仍为OPEN。此补丁未移植、未构建、未安装到 HP；尚未审核其在 HP 固定代码中实际可达性与适配细节。

### 3. XE-PM、A7A8 与另一台 HP 的工作报告

- 最新 XE-PM 介绍：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/16#issuecomment-6407640927>，2026-10-26。针对混合 P/E 核的 HWP／XCPM／C8/C10；维护者说 XCPM patch 限25G241且有字节检查。HP本机为非混合核 i5-1135G7／25G83，没有证据将其作为当前内存 Panic 修复。
- A7A8启动故障：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/13>。读取正文及全部4条评论，当前是启动时 task init 失败与 release(NULL成员) page fault，仍需启动前序日志；不同于 HP 已能进入桌面后的 pmap／wrong-zone，不能套用它的推测。
- HP ProBook450G9／i5-1240P 工作报告：<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/16#issuecomment-6399605613>。另一代平台的80EU／L3=6成功支持拓扑配置的可用性，但没有对本机故障的修复前后证据。

### 4. Olarila 同签名：不能当作已解决案例

<https://olarila.com/topic/46465-random-system-freezes-on-macos-after-bios-update-asus-z890-arrow-lake-hackintosh-issue/>

原作者为 Z890／Core Ultra5 225F／RX580，报告 BIOS 更新后异常、Resolve／Final Cut 负载下同类 pmap Panic。后文明确说 GPU／视频负载仍冻结／重启。另一回复者 overflow 声称类似问题通过回刷旧 BIOS解决，但未给出匹配 Panic／精确 BIOS 版本／隔离结果；这不是原作者闭环，也不构成 HP BIOS 回退依据。帖子中“page仍有引用”的一般解释不能取代本机精确 binary 已确认的多分支判据。

## 后续价值排序

1. 核心缺口仍是失败时 managed属性／PV／对象与所有权历史；`MEMORY-NEXT-DIAGNOSTIC.md` 的现场捕获保持适用。
2. 如用户希望先尝试配置层对照，现有三项关联 Quirk 组仍可作为独立可回退候选，但需用户在场、以当时实际基线为准，保留完整图形栈及固定 RTC 设置，不与 Metal 或 ROWCHK 同次改变。尚未生成／部署新 IMG。
3. ROWCHK 可另列 GPU 计算正确性研究线索，目前证据不足以优先当作内存 Panic 修复。

## 检索边界

本轮已搜索精确 `pmap_recycle_page`／1511／Tiger Lake／`0x10131*`、`early.kalloc.48`／IOMachPort，以及上游近期 issues／kern_gen11.cpp提交。未取得本机 wrong-zone 的确定修复；搜索无结果不是不存在缺陷或不存在案例的证明。

Perplexity用量查询失败、线程列表403；没有取得其搜索答案，本轮结论来自上述实际读取的来源。本轮只有网络与开发机文档操作，没有执行 HP 现场修改或复现。
