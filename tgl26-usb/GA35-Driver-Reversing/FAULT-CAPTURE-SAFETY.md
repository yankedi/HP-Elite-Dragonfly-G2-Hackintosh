# Gen12 Fault 采样安全审查

**结论：只交付隔离mock核心；真实三寄存器读取保持BLOCKED。** 无真实reader、observer、route或kext接入。下列协议/状态机通过CPU测试，不代表已经证明设备侧一致性。

## 位域与来源

基线`diagnostic-src/kern_tglfault34.hpp`保持GA34原字节。依据GA34固定Linux v5.15/v6.18、Intel703046 TGL寄存器文档；独立复核见`audit/ga34-review/GA34-INDEPENDENT-REVIEW.md`。Linux只作寄存器/原型依据，不作Apple内部实现证明。

|值|提取/含义|
|---|---|
|FAULT `0xCEC4`|Valid bit0；Type bits2:1；Source bits10:3；Engine明确保留v5.15三bit及v6.18五bit两种解码，不伪装成同一版本枚举|
|DATA0 `0xCEB8`|VA页号低32bit|
|DATA1 `0xCEBC`|VA页号高4bit；bit4=1 GGTT、0 PPGTT；bit5 entry-valid、bit6 present、bits8:7 page-size编码；其余MBZ|
|VA|`((DATA1 & 0xf) << 44) | (uint64_t(DATA0) << 12)`，输出48bit字节VA；输入范围不合法时拒绝，不截断|

`derive`仅对合法Complete记录、fault-valid、DATA1 MBZ=0产出available。原始DWORD始终保留，unknown/部分失败不产出一个貌似有效的VA。48bit位图未擅自canonical符号扩展为host/kernel指针，绝不按fault VA读取物理内存。

## 108B wire v1

`TGF4` magic、version1、length108，逐字段little-endian编码，**不是C++ struct dump**。偏移：0/4/6为magic/version/size；8 validity、12 callerClaims、16 status、20 attempts、24 engineLayout；28/32 held/ack本地域；36 sequence、44 monotonicNs、52 bootId、60 hangId、68 callerId、76 resetEpoch、84 exclusionToken；92/96/100原始fault/data0/data1；104–107保留零。codec校验后才提交；坏版本/长度/保留位/状态组合不改变输出。

boot/hang/caller、epoch/token是**调用者提供的声明**；wire合法不验证这些声明确实来自Apple硬件同步。108B不包含ContextID/PML4/RingHead及其generation；不能单独完成同次hang上下文关联。

## 隔离状态机

```
Ready → preconditions拒绝(不调用callback)
      → Capturing
        observe → read CEC4 → observe
        observe → read CEB8 → observe
        observe → read CEBC → observe
        首次失败即停止 → 追加部分记录/明确status → Ready
        全成 → StableEpoch标志 → 追加记录 → Ready/Full
```

容量8，不覆盖记录0；sequence不回卷、counter饱和、满/耗尽拒绝；复制Request和callback tuple防同线程别名回调篡改检查目标。失败read即停，无后续observer/read。仅入场后消耗sequence并追加部分失败记录。默认`enabled=false`，无callback和硬件访问。

这是**单线程、外部串行化前提下的离线模型**：busy布尔不是锁/atomic，不提供并行调用安全；observer不能拦截一次MMIO指令中的设备异常，也不能撤销已做的读取。外部true布尔不能填补reset排他、引用和latch契约。

## 读取顺序与一致性缺口

CEC4→CEB8→CEBC是与固定Linux处理习惯一致的mock顺序。模型每读前后核epoch/power/GT held/ACK，但这**只检测callback报告的变化**。即使两次epoch相同，也没有证明GPU未在三读之间更新latch；ABA、设备侧clear、新fault覆盖、ACK丢失后恢复也不一定被软件counter观察。因此`StableEpoch`不等于“硬件coherent fault tuple”。不新增真实读、双读、重试或ACK探测来补猜。

## 安全前提判定

|前提|已有事实|仍缺证据/决定|
|---|---|---|
|身份/映射|精确25G83 stock KC、UUID/loaded元数据匹配；+1270为MMIO基址字段|live patch字节及映射对象生命周期未认证|
|GT域|已见Apple多线程bit4 a188/130044路径；7含1/2/4|当前设备实际selector分支与持有引用不可由数字7证明|
|ACK|静态可见ACK轮询和超时/其他分支|wrapper无成功状态；early-return/转发及运行态ACK未证|
|active power|SafeReadRegister会管理forcewake|active power引用、sleep/wake/teardown互斥未闭环|
|reset/clear|已见旧4094在reset941c等待循环中清|真正CEC4/Data latch的全局清除和并发排他未知|
|锁序/上下文|部分IOAccel mutex/busy、Forcewake spin路径可见|没有覆盖所有入口的共同排他，spin已在wrapper前释放|
|记录关联|mock显式boot/hang/caller/epoch/token|真实分配、重置epoch及context/root/head同代性无提供者|
|生命周期/异常|固定内存、无分配、失败回调即停|真实backend不在本轮；无法借mock bool处理MMIO异常|

“只读”不等于无副作用：调用SafeReadRegister会触发forcewake请求写、ACK等待和释放；直接volatile读不自行满足电源域。任何关键前提未知时不能把held/ack/power/exclusion强填true。

## 独立审查与可复现证据

`audit/ga34-review/`证明408历史项未变、20项修复的47个回归引用、104Python/224native组、4freestanding/4alias构建及5个108B样本通过。新工具缺陷及修复的初始失败/最终closure分别保留`audit/tool-review/`和其`closure/`。完整GA35独立安全审查见`audit/safety-review/`；最终结论以根报告和manifest审计为准。

**FAULT_DIAGNOSTIC=OFFLINE_BUILT；真实采样=BLOCKED；READY_FOR_HARDWARE_APPROVAL=NO。**
