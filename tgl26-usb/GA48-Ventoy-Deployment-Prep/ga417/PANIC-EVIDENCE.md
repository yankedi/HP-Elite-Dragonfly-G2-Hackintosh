# GA417：现有 Panic / 25G83 KDK 限定审计

2026-10-26。本轮保留的五个近期 incident 为 pmap×3、wrong-zone×1、watchdogd98s×1；另列历史 WindowServer120s。签名不同不证明根因独立；POSH 用户态泄漏与这些内核异常之间尚无因果证据。

## 本轮新增的可核验结果

- 从已有 KDK 的本地 `kdk.cpio` 提取 release kernel / private-symbol dSYM。两者 UUID 均为 `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`，kernel SHA256 `1542ae9efea6d3a212248446d610b677d66fec02da5a5bfacf2b1a67f544b47e`，与原安装 KDK 回执一致。
- `reports/PANIC-KDK-SYMBOLS.json` 对六个 incident 的所有内核回溯地址减各自 slide，再在 kernel 可执行 section 内查询匹配 dSYM 私有 nlist 区间；保留原地址、符号起点、偏移、下个符号边界及原始文本。不是 DWARF 行号/内联展开，也不是现场内存逐字节验证。kext 地址不错误套用 kernel 最近符号。
- 第五份 spindump 的**内核部分**已补齐；AppleFSCompression/APFS 帧仍明确保留原始 kext 归属，未冒充完整私有符号化。
- wrong-zone 的原始近邻导出名 `_thread_corpse_continue`、`_workload_config_available` 不是真实函数；现已定位到 zone 检测函数及 `_zfree_ext`。
- 25G83 KDK `IOSurface` x86_64 UUID `8E1FFEDA-8C53-336F-B59B-776024E3B66D`，与 TrackpadExtension panic 中 IOSurface UUID 一致。其 `IOSurface::getPlaneCount()` 在未滑动 `0xa774` 执行 **`mov 0x98(%rdi),%eax`**。这补齐了“25G83 IOSurface planeCount 位于 +0x98”的静态 ABI 证据；不代表所有 IOSurface/IOAF2 私有布局已审计完，也不代替原 patch 应用位置的运行验收。

## 检测现场与最早操作候选

下表从外层操作向断言排列；省略通用 trap/debugger 尾部。完整地址见 JSON。任务名只是上下文。

| Incident / 检测现场 | 匹配 KDK 后的相关路径 | 最早值得追溯的操作与仍缺的证据 |
|---|---|---|
| `B917E5B8…` / TrackpadExtension / page `0x10131c000` | IOSurface `get_value` → `OSSerialize::free+0x59` → `kmem_free_guard` → `vm_map_remove_and_iunlock` → `vm_map_entry_free_locked` → `vm_object_deallocate/terminate/reap` → `vm_object_reap_pages` → `vm_page_free_list+0x2cb` → pmap断言 | 序列化临时 VM 对象销毁是发现问题的操作；需更早的该页分配/映射/撤销记录和 pmap 元数据，不能认定 IOSurface 查询先写坏它。 |
| `6D7209BA…` / log / page `0x101311000` | 用户缺页 → `vm_fault_internal` → `vm_fault_page` → `vm_page_free_unlocked+0x18e` → pmap断言 | 缺页处理回收页时发现；缺具体 fault VA、PTE、managed属性和 PV 项，不能把 log 视为原始损坏者。 |
| `5AA77673…` / spindump / page `0x101313000` | 用户缺页 → `vm_fault_internal/page` → `vnode_pager_cluster_read` → `vnode_pagein` → APFS page-in → `decmpfs_pagein_compressed` → `decmpfs_fetch_uncompressed_data` → AppleFSCompression → `IOFreeData` → `kfree_ext` → `kmem_free_guard` → VM object回收 → `vm_page_free_list+0x2cb` → pmap断言 | 解压缓冲释放触发检查。需缓冲分配及物理页生命周期、解压对象边界和 PV 元数据；不能由栈中 APFS/解压直接推导文件系统根因。 |
| `1EB6C969…` / VTDecoderXPCService / `early.kalloc.48[87]`，found `[0]` | `ipc_right_dealloc+0x412` → `ipc_notify_no_senders_kobject+0x2a` → `IOMachPort::free+0x45` → `OSObject_typed_operator_delete+0xa1` → `zfree_ext+0x158` → `zone_invalid_element_panic+0x123` → `zone_page_metadata_index_confusion_panic+0xe3` | 检测到释放目标 `0xffffff9024954b50` 的 zone 页元数据与预期不符。需实际对象/vtable/typed kalloc描述符、zone页metadata、分配释放历史，才能区分过期/错误指针、重复释放、metadata损坏或ABI/allocator不匹配。`found[0]` 不是已知“zone0对象”的身份证明。 |
| `2A1A0C70…` / kernel_task / watchdogd98s | AppleSMC `SMCWatchDogTimer::watchdogThread` → watchdog `checkWatchdog` → panic | 这是发现98秒未报到的定时线程。需**同次卡死时** watchdogd/WindowServer/内核全线程等待链、锁持有者和调度状态；后续启动采样不能替代。 |
| 历史 `B8572953…` / WindowServer120s | watchdog UserClient `externalMethod` / userspacePanic → panic | 独立历史对照，不能与watchdogd98秒合并为同一次事件。缺WS实际阻塞链，无法从检测栈判断GPU/CPU/锁等待。 |

### wrong-zone 的调用点进一步约束

完整 `IOMachPort::free` 反汇编已保存：返回地址减 slide 为 `0xffffff8000a15895`，正好紧随 `call *0x50(%rax)`；该调用的 receiver 来自 **`this+0x20` 成员**，并设置第二参数 tag。它不是函数末尾的 `this` 自身虚析构跳转。因此不能把 `early.kalloc.48` 直接称为 IOMachPort 本体，也不能仅凭 VTDecoder 任务名判定它是视频缓冲。`IOMachPort` 本身 new/delete 已另存，尚无现场分配栈把失败指针绑定到任何具体对象类或第三方分配器。

## pmap 断言仍不能区分的分支

已有匹配 KDK 机器码：`pmap_verify_free=0xffffff80003c6690`、`pmap_recycle_page=0xffffff80003c6700`。失败可来自页号上界检查、页属性位未置位、或相应反向映射项非空；recycle 内联检查汇合到同一 panic。三个现场不是在独立 recycle 函数入口留下唯一可判定分支的栈。

Linux/MmapDump 中三页为普通可用 RAM，MAT 正常，未发现固定保留区冲突；这不提供 panic 时 managed 属性、PV 项、PTE/VA。原 `kernelcore` 是约1MiB占位，不是 RAM。缺寄存器/全RAM/页历史使这些分支及最早修改者仍不可判定。MmapDump 已完成，无需重复。

## 第三方 kext：分配 / 释放 / ABI 核对

限定审查固定 GA416 NG 源码 `f93dc2447631553d2dcc2f6d5a8a495acf57990c` 中与当前问题直接相关的路径。迁移后两源码与该 commit blob 字节相同，见 `THIRD-PARTY-SOURCE-IDENTITY.json`。NG 实装/镜像身份 `e44ef327…` / UUID `4C4C44D4-5555-3144-A13A-DFB86EFBE513` 由原回执和本轮 IMG 回读关联；这是构建来源链，不是每条源语句的现场反汇编证明。

| 路径 / 源码位置 | 核实与边界 |
|---|---|
| PLANES2，`kern_gen11.cpp:2245–2262` | 将旧 IOSurface +0xb0 读取改成 +0x98；本轮匹配25G83 IOSurface getter证明+0x98确实是32位planeCount。没有更改NG或启用xor。此局部ABI已获静态支持，不能把其余私有offset一并宣布正确。 |
| XE-RESFREE，`kern_gen11.cpp:6967–6990` | hook检查资源表+0x250、size+0x258以及40-byte entries；对未映射指针置零后仍调用原free。`xeMapeado`检查映射，不证明指针属于预期zone、仍存活或可合法释放；因此不能当成allocator正确性证明。当前wrong-zone栈没有出现该hook，但缺它并不能排除更早破坏。 |
| Blit scratch 临时分配，`kern_gen11.cpp:7011–7015,7139–7148` | 源码的临时 `IOMallocZero(0xe000)` 与 `IOFree(tmp,0xe000)` 大小配对，复制仅0xd000；**真实TGL在7011–7015先调用原initializer并返回**，不会进入该RPL临时分配路径。不能将该临时块的全局重定向直接认作本机正在触发的竞争。 |
| lock/unlock重定向与NOORPHAN，`kern_green.cpp:453–477,598–615` | 重定向只在receiver匹配全局对象时返回临时CPU指针；NOORPHAN让getMemory返回NULL，避免复用，但不证明所有资源终止/引用计数正确。源注释里的其他机器旧panic不是HP本轮动态证据。 |
| OSObject/typed allocator 与其他第三方组件 | 失败检查实际来自Apple kernel的typed delete/zone路径。未找到把失败指针绑定到NG/Lilu/任一第三方分配释放栈的现场证据；当前清单不是对全部第三方kext作“无缺陷”认证。进一步判断需要失败对象的真实类型、分配/释放历史及相关ABI，不能靠已加载名单归责。 |

**结论：** wrong-zone 检测上下文和第五份内核帧已收窄，PLANES2 的 +0x98 已获匹配25G83静态证据；内核最早损坏者、pmap具体分支、RTC写入者与各故障间关联仍未证明。

## 无人值守续查：精确 DWARF / 分配配对（2026-10-26）

`tools/audit-memory-lifecycle.py` 从固定本地 binary 重新提取36个完整函数、外部重定位和3份相关vtable。TGL UUID`BA3AA1C0-FE6B-33B3-9D85-73F848394E3D`、IOAF2 UUID`B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9`均与本轮macOS `kmutil`采样一致。没有把未链接kext的`e8 00 00 00 00`误当作运行时调用下一条指令。

- **返回地址必须与调用位置区分。** 精确RA`0xffffff8000a15895`的DWARF可标到随后的内联`OSObject::free`，但RA−1落在`IOMachPort::free / IOUserClient.cpp:409`；机器码确认实际正在执行的是成员`object`的`taggedRelease`。匹配DWARF证明`IOMachPort`大小0x28、`object:OSObject*`在+0x20。旧的“成员调用”结论获类型证据支持，仍无失败对象具体类。
- **typed-delete的内联链已展开。** RA−1为`kfree_type_impl_external / kalloc.c:3034 → kern_os_typed_free / kalloc.c:3632 → OSObject_typed_operator_delete / OSObject.cpp:378`；直接查RA则会落到较后面的382行。`vm_page_free_unlocked`调用点展开到内联`pmap_recycle_page / pmap.c:1511`和`vm_page_free_prepare_object / vm_resident.c:6186`。`vm_page_free_list`该点没有可用源码行；保留机器码依据。
- **没有发现所选allocator配对的直接不一致。** TGL `IGAccelResource`类new/delete是成对的legacy `OSObject::operator new/delete`；IOAF2基类自己的new/delete用同一ktv。TGL资源声明0x260、IOAF2基类0x180；+0x250/+0x258在子类界内。不是全私有ABI认证，也不能推断失败对象走过这些函数。
- **已追到实际table申请。** fresh initialize分支检查faces≤6、baseLOD+levels≤15，再申请`faces*(baseLOD+levels)*40`；元素数组申请`count*8`与free配对。最后使用的entry为`faces*levels+baseLOD-1`，与申请数差为`(faces−1)*baseLOD+1`，所以正baseLOD本身不是table越界证明。count为0而来源指针非空的失败分支会清空目的指针。
- **发现现有pageon保护覆盖不完整，但未证明因果。** NG `xePageon`按从0开始的`faces*levels`项做保护，原函数却从baseLOD开始取项；baseLOD>0时会遗漏尾部使用项。原始申请可仍足够，这不是已证实HP的pmap/wrong-zone修复点。RESFREE仅“VA有映射”同样不足以证明zone/所有权正确。保留基线，未新增补丁试验。
- **映射释放链已落到实际IOAF2。** resource `unmap`从map资源表移除自身、release resource+0x40并清空+0x40/+0x70/+0x20；`complete`递减+0x28计数，在类型1且归零时走同类清理；map `free`释放backing+0x18并typed-free资源指针表。缺相关对象/descriptor/GPU完成事件的现场历史，不能据此说发生过“未unmap就free”。
- **pmap现在有可直接读取的判据。** 精确指令和DWARF对应`pmap_initialized`、`last_managed_page`、`pmap_phys_attributes[ppn]&1`以及32-byte `pv_rooted_entry`的`pmap`(+0x18)；`va_and_flags`在+0x10。所缺是失败当时这些字节，不是再采一份普通RAM用途表。
- **release kernel的两项zone-log RPC均直接返回5。** 不把`zlog`+用户态读取当作本机已验证可用的分配历史工具；这也不等于内核完全没有内部btlog机制。

新增报告`reports/MEMORY-LIFECYCLE-AUDIT.json`、`MEMORY-DIAGNOSTIC-LAYOUT.json`。下一步最小证据、精确失败调用点、只读LLDB辅助及验证边界见`MEMORY-NEXT-DIAGNOSTIC.md`。本轮未找到足以直接修复所保存Panic的因果证据。

## 工件

- `reports/PANIC-KDK-SYMBOLS.json`：6 incident完整地址/符号区间/原件hash。
- `reports/PANIC-ABI-DISASSEMBLY.json`：完整所选函数区间、文件偏移、UUID和反汇编hash。
- `private/panic-kdk/`：本地KDK kernel/dSYM/IOSurface及选定函数原始机器码和完整反汇编，私下保留。
- 原始panic、pmap机器码与909MB Debug流保持于 `ga416/private/crash-series/`；本轮未再采大量日志、未主动复现GPU故障。
