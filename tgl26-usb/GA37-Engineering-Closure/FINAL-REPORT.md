# GA3.7 最终报告：离线诊断工程收口，恢复加速语义研发主线

**GA37已实现并验证可离线完成的有主调度、事务记录和版本化协议工程；真实MMIO读取继续阻塞。GA38唯一推荐是“四个真实Shader的全程序消息／依赖IR与Gen12候选调度一致性校验器”。本轮没有实现或验证Metal加速。**

本报告的最终结论应与`state.json`、`track-d/FINAL-SAFETY-AUDIT.md`、独立`FINAL-CLOSURE.md`及交付audit/seal回执共同阅读；初期checkpoint和失败日志均保留，不重写历史结论。

## 一、最终十二项状态及作用域

```text
CAS_WRITER = VERIFIED
EXECUTOR_LIFECYCLE = VERIFIED
TRANSACTIONAL_WRITER = VERIFIED
CAPTURE_PIPELINE = PARTIAL
FAULTRECORD_V2 = VERIFIED

READ_SAFE = BLOCKED
FAULT_DATA_COHERENT = UNKNOWN
REAL_MMIO_BACKEND = NONE

DIAGNOSTIC_ENGINEERING = CLOSED
READY_FOR_HARDWARE_APPROVAL = NO

GA38_DIRECTION = FOUR_SHADER_MESSAGE_DEPENDENCY_IR_AND_GEN12_CANDIDATE_VALIDATOR
GA38_OFFLINE_ENTRY = READY
```

|状态|证据|严格限制|
|---|---|---|
|CAS_WRITER VERIFIED|实际GA36 candidate函数原样提取8组合、baseline确定性反例、candidate独占/终态/缺uioFree前置拒绝|源级软件修复，不认证当前运行kext；GA33实物binary不可得|
|EXECUTOR_LIFECYCLE VERIFIED|原GA36core＋有主Session/Client/Ticket；1/2/16/64、queued/active关闭、重入/timeout/sequence/ASanUBSan/TSan；独立复审|**宿主所有权协议**，要求独占Ticket/活Client、callback正常返回、阻塞wait不重入；真实XNU适配和code-unload仍BLOCKED|
|TRANSACTIONAL_WRITER VERIFIED|用户态POSIX全量snapshot事务、旧revision保留、短写/crash/recovery/权限测试，实际Pipeline集成|本地主机FS/API契约；不是APFS断电、XNU vnode或不可取消同步IO认证|
|CAPTURE_PIPELINE PARTIAL|实际THAG2原bytes→GA36core→ownedSession→准确ABIbridge→文件→hash完整回归|宿主链已接通；真实Hook/producer/ThreadCall/驱动全链未接，不能叫内核完成|
|FAULTRECORD_V2 VERIFIED|384B LE codec、108Bv1原样、严格dispatch/负例/可选字段/派生一致性、跨8buildexactbytes、独立修复复审|wire内部一致性；caller身份/epoch/provenance不自认证，不证明raw来自同事件|
|READ_SAFE BLOCKED|12条件模型与有界目标证据|livepatchedABI、receiver、PM/GT owner、same-requestACK、mapping/读副作用、reset/clear/teardown仍有UNKNOWN|
|FAULT_DATA_COHERENT UNKNOWN|10独立维度、GA36torn-tuple/ABA反例及v2unknown表达|没有设备latch/原子tuple证明；raw不可升有效FaultVA或确定首因|
|REAL_MMIO_BACKEND NONE|新增实现只有CPU/用户态文件和codec；旧源码只读freeze|没有真实reader/Hook路由/部署|
|DIAGNOSTIC_ENGINEERING CLOSED|本轮明确的离线工程、实际集成、独立审查和持久证据交付|只表示**授权离线收口范围**；不宣称所有未来诊断功能或XNU/GPU链已完成|
|READY_FOR_HARDWARE_APPROVAL NO|安全审计与最小证据缺口|本轮不能自动申请为“已安全可部署”，更没有部署/实机批准|
|GA38_DIRECTION 唯一方向|TrackE六路线八维对照与八项技术计划|消息/依赖IR＋候选checker，不是同时启动六方向或重开Fault主线|
|GA38_OFFLINE_ENTRY READY|163精确输入锚、四完整直线shader及已固定工具/规范|只表示该**离线工程可启动**，不是shader可执行、MetalREADY或硬件READY|

## 二、工程收口的实际增量

### 1. CAS没有被新示意算法替代

保留GA36真实candidate `kern_igfx.cpp` SHA `62e3abf2a303a5c27910c35c363d5b286ede88353da38b91773de218855d4ab9`。原`hangThread/hangWriteRecords`函数体逐字节提取，mock只替换OS/VFS环境。baseline首次成功CAS不写且flag1、两个loser同时写；candidate只有成功owner写、失败先error再终态2、不重试，缺uioFree在O_TRUNC前拒绝。8组合和历史parser22检查通过。

旧Hook没有接入新scheduler或文件事务；hangDump仍强制0。这样保留真实缺陷修复证据，同时不把原volatileproducer/裸回调卸载风险掩盖。

### 2. 排队回调也有所有权，不再只看quiescent

实际GA36 `kern_capture36.hpp` SHA `7771dfb4bbc229fbec746976559a4ffeba9ac7c348c0e1ec1322f7898ef1afae`不改。Control拥有slots/snapshot/backend；每个Client持强引用，Accepted在同一gate事务交付move-onlyTicket。Ticket从queued转active时引用不中断，cancel/run/destructor结清计数。Shutdown先关新准入；Drain保留queued，Cancel显式放弃通知；activeIO自然返回后才能close。超时不free，不支持强杀/longjmp或卸载live代码。

独立审查发现非递归mutex自try_lock和publish中关闭问题，修复为recursivegate＋publishing计数。原core 32CAS lease预算可暂时返回Stopped，源码和原stress失败保留；submit在确认Running时映射Busy，drain暂时拒绝保留**同一Ticket**返回Retry，调度器必须再排队或显式取消。`Closed`只说明任务结清，另查watermark/error才能知道是否写完。

ASan实际重现“原core quiescent后释放对象，queuedrawcallback进入”的UAF负例；有主适配层通过正例。Clang/GCC TSan确实可用并exit0，但仅覆盖CPU模型。精确目标ThreadCall代码不可得，不能从reference源码假装内核卸载已认证。

### 3. 全量snapshot事务与真实Pipeline集成

输入不是增量，而是0..watermark的完整immutable prefix。相同prefix/bytes幂等，后续更长prefix需先前bytes完全一致；旧record可能出现在多个全量revision中，不能当新增事件重复计数。

后端使用受控父目录、dirfd/no-follow/权限校验与lock、独立临时目录/文件、短写循环/有限EINTR、文件sync/close核验、新revision原子发布、回读SHA/parse、revision目录与父目录分别sync。旧revision不截断。NotCommitted、VisibleButDurabilityUncertain、DurableVerified明确区分；不确定不向core确认成功，不能因进程还能读到文件就宣称掉电耐久。

独立审查又发现父路径中间symlink可被跟随、rename后bad_alloc误报NotCommitted两个HIGH，以及暂存资源无界和文件名非canonical问题。修复逐component no-follow/拒绝`..`、发布前转移完整buffer所有权并预留校验buffer、发布后异常标不确定＋terminal且无分配保留bytes；清理仅限可验证的自有临时资源，无法安全清理者保留并由64目录上限拒绝新事务；digest名强制小写。原66案例checkpoint留档，新增至73案例/8profile。

独立最终复审已重放原symlink反例并确认拒绝、post-publish OOM不确定终态及bytes保留、未知/wrong-mode/hardlink残留不删除、64目录拒绝、canonical names与真实GA36名义ABI；Clang strict/ASan/UBSan及GCC自定义重放均exit0。`track-d/writer-review/FINAL-CLOSURE.md`对当前源码SHA `865b609ffda438d0a5d776ffcb9f5dfbf812e4faa371f6f3ab3d8979816df820`给出受控目录、单实例序列化Linux契约内CLOSED PASS。

集成真实历史THAG2双record：先record0再record1，准确名义返回类型`callback_adapter<Capture36::WriteResult>`；最终snapshot SHA与原99648B文件`1622ecc2…`完全相同。重复通知/恢复不新增revision；注入新写失败后published2/written1/Failed且旧证据bytes不变。6个Clang/GCC Debug/Release/ASanUBSan build通过。

### 4. 双层gate与新版本记录

READ_SAFE安全门和FAULT_DATA_COHERENT可信域分开，各自保留全部前提；coherenceUNKNOWN不能取代硬件读取审查，READ_SAFEPASS也不代表可声明有效VA。保留raw的例外只针对数据可信度，不是允许危险读。

v1原108B不动，v2独立version2、384B、LE显式编码/保留零、精确长度、presence/unknown、context/PML4/ringhead/engine/allocationgeneration、三个采样时点/resetphase/provenance、raw/derived分开。无来源身份不伪造；外部旧报告关联不补写旧wire。

独立审查发现初版伪VA可往返、数值/MBZ/关联flag不严等真实问题；初版完整checkpoint封存后修复，canonical raw→derived、数值和双向关联一致性均由独立旧反例重放关闭。MBZ raw仍可保留为不可信，derived必须拒绝。修复后样本SHA `ca2e1f32a0de781728c725ab5a5cc1087e9a55cb3947f8090b03f33198c250f0`，不是此前checkpoint的`a2a4f041…`。

TrackB明确兼容THAG2/3与Faultv1；v2 codec独立交付，本轮没有偷用108B parser保存384B数据。未来若选择此backend持久化v2，需显式新parser和集成测试，不将未实现功能列为本轮PASS。

## 三、有界补证与最后硬件缺口

五问题均限定最多两来源，未进行新的全量指令扫描。AppleGitHub匹配tag集合未找到`xnu-12377.161.14`，可得参考`12377.121.6`固定commit；这不是所有公开渠道均不存在源码的证明。enter1 true表示此前pending，cancel_wait不能阻止未来submit，free可因pending拒绝；真实桥接还需外部入口/代码生命周期fence。

24函数既有证据仍未证明共同PM/GT/ACK/reset/clearowner。SafeForceWake正常返回不构成本次ACK后置条件；锁释放不表示GT引用必失效或必有效；磁盘KC与loadedmetadata不认证livepatchedbytes。官方已查文档未提供足够tuplelatch/ABA规范，不能靠更多mock放行。

最小缺口及阻断对象逐条见`track-d/REMAINING-BLOCKERS.md`。**不需要macOS SSH，没有待用户现场执行的步骤。**

## 四、GA38如何推动真正GPU加速

六路线完整八维表在`track-e/ACCELERATION-OPTIONS.md`。选择A方向中可有界验收的全程序消息/依赖IR＋Gen12候选checker：四真实程序共79条、无branch，输入完整；相对继续5个已知命令格式矛盾或依赖缺失heap的全pipeline，能直接推进已确认的ISA兼容障碍。D的编码后端只作被审查候选；E/F当前跨越提交/资源/用户态整栈，不适合作最小任务。

具体代码计划包括corpus、语义IR、消息descriptor/payloadsymboliccontract、lane/GRF/acc/flag def-use图、RAW/WAR/WAW与SEND完成依赖、SWSB/SBID校验、四候选差分和独立mutantoracle。验收不只是再次decode：需要在**完整程序**定位具体缺边/消息字段/offset，拒绝NF→GRF与debug改写等不等义候选；缺精度或payload证据保持UNKNOWN。四实际无branch，generalCFG/branchreloc不在最小任务内。

输入、代码模块、离线验收、范围、六组Metal障碍和未来硬件门槛见`track-e/GA38-TECHNICAL-PLAN.md`八节。此任务不依赖新Fault，却也不因静态IR完成就准许shader提交。

## 五、测试、失败与完整性

|证据|真实执行|
|---|---|
|实际CAS函数8组合|Clang/GCC Release/ASanUBSan，baseline132/candidate158mock检查；parser22|
|实际core＋executor12组合|Clang/GCC Debug/Release/ASanUBSan；1/2/16/64及关闭/重入/失败/寿命/饱和/中断拒绝/mockgeneration|
|TSan|Clang/GCC各1profile实际exit0；独立review另重放，非XNU覆盖|
|事务writer|8profile各73案例，真实文件、crash/shortwrite/stagefault/recovery/路径权限/post-publish OOM/资源边界；命令以TrackB最终结果为准|
|codec/gates/CLI|8profile，修复后codec140、gate71断言；strictv1/v2负例与crossbytes|
|实际集成|6build原THAGbytes逐record发布、事务/恢复/失败保护，最终原SHA一致|
|历史与仓库|1713历史manifest文件＋GA36外部53来源全部重算，makecheckexit0（46Python/42JSON/27Markdown）|

每项命令/exit/stdout/stderr与sourceSHA在各`results.json`所指logs及独立复审中，不把上述计数相加当硬件安全证明。原GA36stress拒绝assert、早期GCC格式警告、外层120秒harnesstimeout、集成未启faultmacro的两次assert、初版codec审计失败均保留并说明纠正。writer最初写到错误local子目录，已确认自有工件后按SHA原样迁回唯一交付root，保留receipt，没有覆盖用户/历史文件。

最终manifest/selfhash和验证回执见README；AppleKC/捕获/派生分析仅私有本地保存，未公开上传、提交或推送。全部新最终工件在GA37目录；source/resultIMG均无，无新GPU实验、SSH改机、部署、重启或系统/固件/物理门禁变更。

## 六、两个问题的明确答案

**诊断还能仅靠离线推进吗？** 软件所有权、文件事务和数据协议能，并已在本轮用真实代码和文件实现。剩余真实设备访问证明依赖当前不可得的目标/运行态/设备规范；只增加mock或无目标反汇编不能消除。离线收口完成后应停止把Fault当唯一研发主线。

**GA38怎样真正推动TigerLake macOS加速？** 用已有四真实Shader建立全程序消息合同与调度依赖校验，把“31单位编码正确”推进到能审查实际候选和定位可修反例的工程工具。完整shader等义、Command状态、resourceABI、映射/同步/调度、PM/恢复及Metal用户态整栈仍有独立障碍。本轮没有提前开启GA38工程；最终交付封存后停止GA37。
