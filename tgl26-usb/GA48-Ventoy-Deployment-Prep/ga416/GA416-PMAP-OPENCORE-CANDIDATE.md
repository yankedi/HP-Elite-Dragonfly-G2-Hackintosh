# GA416 pmap 深层检查与 OpenCore 内存图候选

**后续实测：** 已完成Linux对照及独立OC DEBUG/MmapDump启动，目标三页在原始/分割/压缩图都为Available，MAT38条重建前后相同。未发现固定保留区重叠证据；仍非macOS最终交接或panic现场图。见[诊断结果](GA416-OC-MEMORY-DEBUG-RESULT.md)。下面的“缺口/计划”是取得本轮证据之前的历史状态；论坛组合尚未部署。

2026-10-25。只读核对当前证据、已部署配置、公开源码和网络案例；没有修改 EFI、NVRAM、KC 或驱动，没有运行压力测试。

## 1. 目前可以确定到哪一层

最新清点为五份本轮独立 panic，其中三份相同 pmap 签名、一份错误 zone、一份 watchdogd98秒。第三次 pmap 来自 spindump 的缺页/APFS压缩页读入及释放路径，前两次来自 IOSurface属性清理和log缺页；不能用任务名判定原始写坏者。

三次报出的物理页为 `0x10131c000`、`0x101311000`、`0x101313000`，集中在4GiB以上约19MiB附近，起始地址跨度44KiB。这使“该物理范围的启动内存归类/映射”成为值得核对的线索；不能单凭聚集判定保留区冲突、坏RAM或固定驱动。

### 核实断言的真实语义

公开 XNU `xnu-12377.121.6` 的 `osfmk/x86_64/pmap.c`：

- `pmap_verify_free` 对非 managed 页返回false，也在反向映射项的pmap非空时返回false。
- `pmap_recycle_page` 将false统一报为 `page ... is referenced`，打印值为 `ptoa(pn)`，即物理字节地址。
- 所以错误文本**不单独证明一定存在某个未释放的正常用户映射**；页面管理属性不符也能进入同一panic。

公开源码版本不是目标完整构建版本。为避免只靠邻近版本推断，本轮额外读取目标机UUID匹配的25G83 KDK release kernel与dSYM，提取 `_pmap_verify_free` 和 `_pmap_recycle_page` 的实际机器码，在开发机反汇编：

- kernel/dSYM UUID均为 `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`。
- verify_free未滑动地址 `0xffffff80003c6690`；recycle_page地址 `0xffffff80003c6700`。
- 实际代码先检查页号上界，再检查页属性位，再检查反向映射项；recycle_page中这些检查被内联，各失败分支汇合到panic。
- 这验证了目标KDK二进制也有不止一种失败条件。**没有读取上次panic时的页属性/反向映射RAM，所以仍不能确定本机命中了哪个条件。**这也不是现场加载内核全部补丁的内存逐字节审计。

证据：`private/crash-series/pmap-kdk-code-audit-20261025T124841Z.json` 及 `25G83-_pmap_*.disassembly.txt`。

源码：<https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/x86_64/pmap.c#L1405-L1512>。

## 2. 找到的网络同签名修复报告

来源：Hackintosh-Forum，2026-02-13，hanspeteroliver，帖子#407/#409：

<https://www.hackintosh-forum.de/forum/thread/60523-macos-26-tahoe-auf-den-hackintosh/?pageNo=21>

对方是ASUS B860-A / Core Ultra7 265KF / RX5700 / Tahoe26.2（Arrow Lake台式机），引用同类 `pmap_recycle_page ... is referenced`。报告以下组合后内存分配释放压力测试不再复现：

| Booter.Quirks | HP已部署配置 | 对方报告组合 |
|---|---:|---:|
| SetupVirtualMap | false | false |
| RebuildAppleMemoryMap | true | false |
| SyncRuntimePermissions | true | false |
| EnableWriteUnprotector | false | true |

作者明确承认SetupVirtualMap没有单独隔离测试，此前还修改过多个BIOS/kext设置，长期影响仍需继续测试。因此这是**单个外部平台的成功报告**，不是OpenCore官方确认缺陷、不是HP/TGL实测修复，也不是可直接套用的固定配方。

另一个独立Arrow Lake/Z890案例也有同签名，但未提供已经验证的修复：
<https://olarila.com/topic/46465-random-system-freezes-on-macos-after-bios-update-asus-z890-arrow-lake-hackintosh-issue/>。

尚未检索到与本机25G83/TGL `early.kalloc.48` 错误zone完全对应的确定修复。旧Catalina的kalloc.48耗尽/泄漏案例不是同一种错误，不能混用其结论。

## 3. 官方文档与本机配置

已部署并回读的config SHA256：`80edfc3652fe7738e7c9586e6690fcf0da2ebc5fca63724b443ddf367260fbec`。
本地证据：`private/l3-six/image-readback/EFI/OC/config.plist`；部署对应关系见`reports/L3-6-INTERNAL-EFI.json`。

除表中四项之外，本机已有 `AvoidRuntimeDefrag=true`、`DevirtualiseMmio=true`、`ProtectUefiServices=true`、`DisableIoMapper=true`、OpenRuntime.efi启用；并不是没有配置启动兼容功能。

OpenCore1.0.8官方手册：
<https://github.com/acidanthera/OpenCorePkg/blob/1.0.8/Docs/Configuration.tex>

- RebuildAppleMemoryMap生成macOS兼容内存图，应用MAT权限等处理；有MAT固件通常用它替代EnableWriteUnprotector，并常与SyncRuntimePermissions配对。
- EnableWriteUnprotector改变UEFI运行时服务执行时的写保护行为，依赖OpenRuntime。
- SetupVirtualMap处理固件虚拟地址切换；不是“内核虚拟内存总开关”。
- 官方明确说明这些Quirks即使在相似机器上也没有固定组合，应按固件情况判断；不是全开越好。
- 当前组合是有文档依据的组合，不能因论坛另一组合有效就称本机“漏开功能”。也不能因已经成功启动就证明运行时内存图一定正确。

当前缺口：未取得本机对应启动的完整UEFI原始/修正后内存图及MAT诊断，没有对问题物理页做descriptor归属核验，也没有单变量/关联变量组A/B启动证据。

## 4. OpenCore承担的兼容边界

| 层 | 实际负责者 |
|---|---|
| 启动UEFI环境、内存图、运行时权限、ACPI/CPU标识、注入kext | OpenCore/OpenRuntime及配置 |
| GPU加速/Framebuffer/图形ABI | NootedGreen/Lilu、移植驱动及相关用户态组件；OC负责注入/传参，非完整GPU实现 |
| pmap/VM/kalloc、APFS/压缩文件、watchdog | macOS/XNU原生运行时代码；启动环境和第三方驱动可影响其状态，但没有OC通用兼容开关保证正确 |
| RTC/CMOS | AppleRTC、固件及可选专门修复；当前DisableRtcChecksum与AppleRtcRam均false、无RTCMemoryFixup，尚未部署RTC修复 |
| unified log、sysdiagnose、stackshot、ktrace | macOS诊断设施；OC日志不能替代现场 |

GPU桌面恢复和一次R8通过只覆盖已测试图形路径，不证明长期VM、文件系统、RTC与所有驱动兼容。

## 5. 修复就绪状态与后续优先项

当前是 **根因未证明、发现具体OC候选、具备设计隔离实验依据**，不是PATCH_READY/修复完成。

最有价值的下一步是保留当前图形栈，通过独立可回退引导核对固件内存图/MAT及物理页范围，再比较有文档依据的内存权限组合；关联设置需要作为一组检查启动依赖，不能随意只翻一个开关。需要用户允许引导配置变更，当前没有执行部署。

若内存图路线无支持证据，再继续定位驱动对象/映射生命周期及25G83 ABI（包括此前未闭环IOSurface+0x98）；必要时部署development诊断以取得更具体页属性、pmap/VA/PTE或可用内存转储。当前Release panic缺这些字段。DMA/硬件问题仍未被实测排除，DisableIoMapper=true不等于设备DMA一定无误。

NootedGreen上游未找到同签名修复的先前结论仍成立，详见`GA416-UPSTREAM-CRASH-RTC-RESEARCH.md`；本轮网络发现提供的是**OpenCore配置层候选**，不是新增NG修复commit。
