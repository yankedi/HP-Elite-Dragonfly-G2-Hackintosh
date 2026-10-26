# GA3.5 最终结论：精确二进制已定位，真实Fault采集仍不满足安全条件

**本轮交付真实25G83驱动离线逆向证据、隔离默认关闭核心与差距报告。下一次实机Gen12 Fault采集仍为NO。** 原因已从“缺准确驱动”推进为具体的运行分支、电源引用、全局reset排他和硬件latch一致性缺口。

## 七项状态

|状态|值|严格含义|
|---|---|---|
|EXACT_25G83_BINARY|VERIFIED|磁盘KC、目标UUID/版本与前后loaded元数据匹配；**不是live指令认证**|
|APPLE_FORCEWAKE_MAPPING|PARTIAL|静态domain bit及寄存器路径可核验；当前设备实际selector/转发状态未证明|
|GT_ACK_AND_POWER|PARTIAL|可见GT ACK轮询/引用代码；运行态ACK与active-power契约UNKNOWN|
|RESET_CLEAR_ORDER|PARTIAL|两类分析语境和旧4094 reset中clear已恢复；Gen12 latch/全局clear并发UNKNOWN|
|HOOK_CONTEXT_SAFETY|BLOCKED|没有证明现有晚期Hook拥有必要排他/电源/一致性条件|
|FAULT_DIAGNOSTIC|OFFLINE_BUILT|隔离core/mock已编译与测试；真实backend为NONE，完整kext未构建|
|READY_FOR_HARDWARE_APPROVAL|NO|关键安全前提未证明，不申请实机启动|

## 四项关键推进

### 1. 拿到准确驱动，不再依赖25G72注释

普通uid501只读SSH观察26.6.2/25G83 x86_64，复制完整Boot/System/AuxKC，三个目标驱动磁盘bundle没有独立MacOS executable。SystemKC361922560B的远端前/本地/远端后SHA均为：

`fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`

AppleIntelICLGraphics UUID `B7DF3049-D3A9-3070-9843-6E5AE47673D7`、Framebuffer `7949B335-4901-3B40-9EB6-3D9A34FE65C7`、IOAccelerator `B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9`与loaded前后逐项对应。KC容器坐标加`0xffffff7f80ce5000`可对应报告的运行地址；这是包含映射origin的bias，不误称随机KASLR slide。Lilu/WhateverGreen可能改内存入口，本轮未读内核RAM。

### 2. Apple的7不是简单的Render枚举

ICL `SafeForceWake(bool,unsigned)@0x13ec39f6`有feature位门控、early return、间接转发和多线程路径。在已恢复的多线程实现中按1/2/4测试位；bit1对应render请求a278/ACK d84，bit4对应GT请求a188/ACK130044。Framebuffer另有参考计数/ACK实现。因此旧“domain7就是render”注释不能沿用。

但**请求mask7包含GT，不等于当前Hook已经成功取得GT及active power**：实际feature/转发表选择、early-return、ACK超时/无状态返回以及reset/电源引用都须分别证明。具体路径、bytes和独立复核见[APPLE-FORCEWAKE-CALLGRAPH.md](APPLE-FORCEWAKE-CALLGRAPH.md)、[GT-FORCEWAKE-AUDIT.md](GT-FORCEWAKE-AUDIT.md)。

进一步按本版`determinePowerDomain`机器码对三目标offset静态求值，CEC4/CEB8/CEBC都返回mask4（GT），不是把Linux分类直接当Apple实现。该结果仍不证明实际转发表、ACK、电源或reset排他。

### 3. 现有采集点比“hang刚发生”更晚

精确doHangAnalysis先遍历engine、`gatherKeyRingData`和`checkEngineStatus`，最后才调用mask7 enable/disable。GA3.3 wrapper在原SafeForceWake返回后采集，因此它位于既有engine数据收集之后，而其内部spinlock已经释放。

doHangAnalysis既能从`debugGraphicsEngine`在请求hardware-error前调用，也能经IOAccel channel restart中的诊断虚调用进入。后者已经在restart处理语境，不能统称“reset前安全点”。已见reset941c等待循环清旧4094；没有把这个旧路径冒充CEC4的Gen12 fault latch契约。[GPU-RESET-TIMELINE.md](GPU-RESET-TIMELINE.md)逐答全部十问。

### 4. 核心的软件边界有效，硬件前提仍未知

GA34独立复核确认408项manifest未变、20项修复均有可执行回归；104项Python、224 native组、4freestanding和4alias构建、5个108B样本通过。GA35保留相同核心的独立源码副本，没有接入真实MMIO、Hook或bootarg。108B是显式wire v1，不是struct dump；默认拒绝、固定容量、失败即停、部分记录保留、序列/身份及别名篡改反例均有证据。

它仍是外部串行化的mock模型：busy不是线程锁、observer不是设备异常屏障、StableEpoch不是硬件tuple一致性证明。核心本地域GT=1与Apple bit4不同，不可直接强制转换。[FAULT-CAPTURE-SAFETY.md](FAULT-CAPTURE-SAFETY.md)列出逐项缺口。

## 工程与审查

**额外发现旧GA3.3源码的writer门控写反：** `kern_igfx.cpp:1578`成功CAS时返回；本轮直接核对25G83 XNU `_OSCompareAndSwap`为`lock cmpxchg; sete al`，成功确实返回1。首次writer因此退出且留下flag，失败者才可能进入写路径。证据在`analysis/atomic-semantics.json`及独立安全审查SR-05。旧源码未修改，GA3.3实物kext缺失，不能把源码缺陷说成已认证的当前运行二进制缺陷。Hook内分配/物理读取、volatile共享状态和teardown亦仍有阻塞项。

五映像共11416个符号上界片段、469052条解码指令的bytes/fileoff/VA与原KC重新匹配。Direct edges和未解indirect都保留；线性解码不冒充CFG可达性。经format11链成员验证解析stock stub/有界vtable候选，保留原编码值而不直接当运行指针。

按用户偏好，DeepSeek V4.1 Flash（OpenCode Go）承担历史来源清点、离线工具边界反例/closure及CSB/时间线索引。主代理负责关键逆向和结论整合，独立高推理审查核查GA34、Forcewake及隔离安全。工具初审找到8类正确性问题，修复前文件及原失败日志保留；详见[TEST-REPORT.md](TEST-REPORT.md)与`audit/`。

最终工具回归48/48真实通过（没有把expectedFailure计入成功）；九报告/七状态、61项外部历史SHA、五份core与原件/被测试副本一致的跨工件审计通过。通用工具剩余低级预算/事务边界另列，未宣称任意输入或并发修改下零问题。完整私有文件集由`manifest.json`及`manifest.sha256`封存，实际核验回执见`logs/manifest-verification.txt`；可用`python3 -B tools/seal.py verify`只读重验。

所有新工件仅在本GA35目录；没有sudo、GPU实验、新增MMIO读取、kext部署、VM、IMG/USB/EFI/NVRAM/固件变更或Command/Shader写回。Apple专有二进制和派生分析仅本地私有，未公开上传。原始GA31/32/33、ISA-Lab、GA34历史不覆盖。

## 下一步

[NEXT-EXPERIMENT.md](NEXT-EXPERIMENT.md)给出离线优先的证据缺口，不是硬件操作指令。需要证明实际dispatch、active-power/GT ACK引用、所有reset/clear的共同排他、真正TGL latch语义及context generation关联后，才能另行设计并申请新采集。当前选择用户明确允许的**只交付隔离核心与差距报告**分支；本研究交付不等于实机批准。
