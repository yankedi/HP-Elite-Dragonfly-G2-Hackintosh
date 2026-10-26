# GA3.4 离线工程报告

本轮交付**有状态命令分析/严格Shadow子集、两个完整格式研究候选、独立Fault mock核心与离线证据关联**。尚未取得完整命令/资源执行语义、实际Gen12 fault或当前Apple采样点安全证明；Tiger Lake Tahoe加速未被修复或验证。

所有新产物在本Lab。THAG/旧GA源码/镜像/SSD EFI/固件未改；无HP连接、部署、GPU写回或新实机试验。原ISA-Lab的ISA确认、Batch/Hang部分、READY NO结论保持原样。

## 1. 已有Batch多少条符合TGL？

冻结THAG记录1 Batch窗口`0x426F7000`，ring关联入口`+0x6000`，END`+0x7100`。166包与历史raw逐字节一致：**56 VALID_TGL_PACKET_SUBSET、5 EXPLICITLY_NONCONFORMING、105 UNKNOWN**。56仅55个纯零MI_NOOP与1个canonicalEND。161包通过当前格式层检查；静态可转56，33包有显式资源/heap引用，2包含继承未知事件。以上不是161条完整合法TGL命令或一个可执行批。

五个明确格式问题为旧stencil5DWORD与四个extended=0却10DWORD的draw。新增MOCS0等XMLnonzero提示保留UNKNOWN：未modify/NULL/disabled状态下不能从pack assertion直接推硬件违规。

证据：`track-a/packet-audit.json`、`state-ir.json`、`inputs/provenance.json`。78定义包含74实际种命令+4辅助模型及5传递struct；逐bit XML与未声明bit范围完整保留。官方段落索引定位ICL80/80、TGL77/80，含2194/2328个literal限制上下文；仅12条明确规则单独建模，其余语义约束保持UNKNOWN。自动提取文字不是形式化验证完成。

## 2. Null Stencil能否严格转换？

**可构造有明确前提的离线Null编码；当前捕获不能批准无条件runtime转换。** 源为`78060003 0 0 0 0`，目标必须8DWORD且SurfaceType7；只补三个零会编码reserved类型0。官方PRM+固定Mesa ISL独立核验的本地MOCS4示例：

```text
78060006 e0000000 00000000 00000000
00000000 00000004 00000000 00000000
```

Depth字段保守拷贝已解析depth状态，当前为0；不对所有null情况硬编码0。捕获的Depth为NULL、HiZ关闭、WM stencil/depth test/write关闭、HZ操作关闭，且后续四draw前没有相应状态改写。但真实resource absence inventory、Apple MOCS编程与stepping/workaround未证；MOCS4仅Mesa环境条件示例。helper对未知/存在资源、活跃/缺失state、未知MOCS或stepping严格拒绝，不能据此转换启用surface。

证据：`track-a/stencil-proof.json`、`track-a/reports/stencil-and-draw-semantics.md`、`reference/track-a/pack-proof.c`及8个native pack构建。

## 3. Draw两方式有什么语义区别？

四处原header`7B000008`在ICL/TGL都矛盾，没有已证明的原流执行语义。A改`7B000808`，10DWORD，inline XP0/1/2全0；B改`7B000005`，7DWORD，后三零成为三个独立MI_NOOP。四draw的6 vertices、1 instance、其余真实参数均保留，两者总extent同为40B。

对当前direct draw，A的XP零与B的absent-XP默认零在已定义字段上相等。XP0/XP1不是无条件BaseVertex/BaseInstance；其用途取决于VF_SGVS_2 source/enable/element/component和shader契约。捕获三XP insertion均关闭。Indirect模式下A可能从XP MMIO取值，不能套用零等价；nonzero XP、非NOOP尾值、未知shader映射均不得推广。**A/B不是与畸形源流执行等价，也未证明时序或硬件等价。**

证据：`track-a/draw-proof.json`、上游生成pack、`track-a/tests/test_normalizer.py`。

## 4. 完整Shadow可否生成？

**完整语义已验证Shadow：不能。** `strict_shadow`在真实流首个未证明PIPE_CONTROL处拒绝，无部分成功输出。严格子集支持纯零NOOP、精确END和受限typed BBS，变长/跨页、source/target映射与执行occurrence逐一核对；未知资源引用拒绝。

另交付两份**PARTIAL_FORMAT_STUDY**，含条件Null示例与四draw A/B，opaque其余命令及资源引用原样保留。每份4368B（源4356B，stencil扩12B），A连续decode166包，B178包。所有原packet起点映射与next边界检查；源流无BBS，不猜测重定位其它地址。资源/base-relative refs逐字段列入receipt，**没有把这些离线VA映射到GPU，也没有prefetch页面**；样本不能提交。

* A SHA256 `a6ab33b6d92a3e203a2ec041bde7370691d46bf38c9c3aaeddc9e80a594e5f62`
* B SHA256 `529565eaa7406d5283beef35753a4a6e62666135415a196ef0550ac0dad9e504`

见`track-a/shadow-batches/format-candidate-{A,B}.{bin,json}`；严格跨页NOOP样本另列，未混称同一验证等级。

## 5. 哪些未知heap/继承阻塞？

Surface/Binding Table/Sampler/Dynamic heap内容、RT布局/view/aux/compression、vertex/constant数据、shader payload与全部消息/调度语义没有完整捕获。SBA ModifyEnable0继承UNKNOWN，不以包中0作历史值。pipeline每field mask单独合并，非法一bit selector mask不变成已知状态。PS/VS pointer的packet值不证明完整kernel/heap可用或硬件已执行。

入口仅支持显式first-level契约；Gen11第二级内部BBS是chain，非任意软件stack。Gen12 nesting mode未知即拒绝BBS；nested最多3层，其余未证控制/条件结束/间接/alias/中途entry/资源缺失都拒绝。现有IR为静态重建而非原子GPU执行轨迹。

## 6. 更多捕获才能回答什么？

需同boot/hang的valid fault、sampling phase/前后时间与epoch、实际context/PML4有效位、submission/allocation ID+generation+lifetime、完整heap及启用shader入口/payload，才能缩小命令页/执行代码/Surface/PostSync候选。页范围相似不能认同一allocation；fault只有4KiB页地址，不是精确faulting byte，更不直接证明hang因果。

当前离线模型已有Batch/Shader/Surface/PostSync/Unknown/valid0/时序不明等18合成场景，区分sample identity与hang-through-sample continuity。真实THAG没有这些新证据，不用合成值补成实测。

## 7. Fault确认了哪些信息？

固定Linux v5.15 `8bb7eca972ad531c9b149c0a51ab43a417385813`适用9A49/TGL12.0，交叉v6.18 `7d0a66e4bb9081d75c82ec4957c50034cb0ea449`：CEC4 fault、CEB8 DATA0、CEBC DATA1，为GT-global all-engine，不是RCS基址相对寄存器。valid0、type2:1、source10:3；engine历史14:12、新通用16:12分别标记。

VA=`((DATA1&0xf)<<44)|(uint64_t(DATA0)<<12)`；DATA1 bit4=1 GGTT，0 PPGTT。官方TGL2c p906另证bits5 valid、6 present、8:7 page-size合法，31:9 MBZ。不能误拒5–8位。`GLOBAL_MOCS(37)=0x4094`数值重叠已复核，旧Apple0x4094不能排除Gen12fault。

Linux显式RMW清valid并posting read；可在物理reset前软件clear。没有定位公开CEC4/CEB8完整官方表及全部type/source枚举，故审计PARTIAL；未推断清除副作用或Apple reset时机。见`track-b/{register-spec.json,fault-registers.md,source-audit.json}`。

## 8. Forcewake domain是什么？

两固定版本的TGL12.0表`0xB400–0xCFFF → FORCEWAKE_GT`，覆盖三fault寄存器。**不是仅Render域。** 必须有GT ownership+GT ACK+active-power及reset exclusion。mock DomainGT等是本组件局部标签，不能把数值7直接等同Apple API或Linux ABI。

## 9. 当前Hook插MMIO时机安全吗？

**未证明，真实接入BLOCKED。** GA3.3 wrapper先调原SafeForceWake(void)，再在enable/domain7下捕获；这不能证明GT、ACK成功、正确运行期电源引用、锁序、thread/interrupt上下文或映射生命周期。现有共享hang flags/buffer/thread_call的完整同步契约也未独立证明，不扩大旧行为。

本地限定检索未找到25G83 exact AppleIntelICLGraphics Mach-O/完整反汇编；旧24.0.5/25G72偏移不等同当前build。无SSH取新资料或远程构建。见`track-b/forcewake-audit.md`。

## 10. reset前能捕获有效fault吗？

**设计了可拒绝失败的离线协议，但当前不能承诺真实取得。** Linux已证明capture→clear→reset的路径，Apple current clear/reset/CSB/context destroy/Watchdog完整先后未知。先于reset不必先于clear。

实际核心3 raw reads，每次前后guard共最多6次；没有再次读取fault或设备前后时钟。epoch/token和caller monotonic时间是声明，不是真实锁或原子同次快照证明。epoch复用/ABA、并发clear及GT-global多engine归属必须在真实接入前解决。固定8条append保留首条，满/sequence将回绕时拒绝，无无限重试或clear/reset动作。

## 11. 可编译独立补丁实现了吗？

**独立核心OFFLINE_PASS，whole-kext NOT_BUILT。** `kern_tglfault34.hpp`是405行freestanding C++17 header，含raw/derived分层、108B版本化LE wire codec、有界mock Collector；header-only patch只新增此文件，未include到GA3.3任何hook。四baseline文件hash相同，`git apply --check`及patch payload复原通过。capture入口冻结Request与Callbacks descriptor值，callback不能改当前epoch基准或重定向dispatch；context对象生命周期与serialized调用仍是caller义务。

`Request.enabled`默认false。独立`-igfxtglfault34`离线bounded boot-text scanner另有24正负样本，不访问OS全局参数；没有真实bootarg routing或MMIO backend。五个108B实际sample完成Collector→encode→落盘回读→decode→encode一致→derive，分别PPGTT、GGTT、valid0、DATA1MBZ、failedread，context/PML4明确unknown。

本地无已验证完整Xcode project/SDK/macOS kext构建环境，不能把standalone编译冒称kext可加载。

## 12. Mock及安全审计完成情况？

Clang21.1.8/GCC16.2.0各Debug/Release、plain/ASan+UBSan，共8个core executable×28组=224组调用通过，另4个freestanding object通过；8个上游pack executable亦通过，匹配独立pack输出。sample scanner+wire在initial和post-alias-fix两个Clang ASan+UBSan运行通过，五wire/JSON逐byte相同。Python命令64+关联40=104项通过，最终checks见`logs/lab-check.txt`。Python并未被声称由C++ sanitizer覆盖。

独立初审真实发现14问题/22反例，原失败证据保留；A13原反例独立确认关闭，第二轮R01–R04又经35项confirmation/13原输入与64suite独立确认关闭。C40项、原9输入修复验证通过。B独立审查另发现2项borrowed-input alias问题，已值拷贝修复并补5组、完整重构建；独立closure在Debug/Release ASan+UBSan重放原反例，另核63 descriptor+3 request变体、三路sample bytes一致，191受保护文件未改，见`track-b/reports/fault-alias-closure.md`。独立审查累计20distinct发现均有修复/关闭证据，不能用旧绿灯推断安全。模型防止地址范围冒identity、typedflag/epoch/PML4/clock/lifetime不明冒同次；实际硬件安全仍有前述缺口。

13个分析工件两次再生成逐byte一致；16个core/pack executable及tested source hashes核对、2个跨8build stdout组一致。历史559文件+2外部输入及源码pins最终保留审计单列。无真实MMIO、panic或machine-check试验。

## 13. 改了现有驱动行为吗？

没有。GA3.3四文件副本不变，新core/boottext/sample相邻但unattached；未改原hook/forcewake/reset/物理门禁。未部署kext、创建/修改Ventoy IMG、写GPU命令/Shader或修改SSD EFI/BIOS/SIP/SSV。SOURCE_IMG与RESULT_IMG均为无。

## 14. 首推哪个实验？

信息价值方向是**先Fault-only只读诊断**；眼下先补exact25G83离线binary及GT/ACK/power/reset-lock/clear时序证明。GA3.3b首拒页能解释安全拒绝页，却不能替代真实fault。Command Normalization再后，Shader Translation更后；后两者改变GPU输入，当前都不成熟。四方案具体比较见`track-c/next-experiment-ranking.md`。没有由本报告批准任何实机动作。

## 15. 已有可供审批实机的条件吗？

**NO。** 缺精确Apple current binary/反汇编、域/ACK/电源/锁/clear顺序、可验证同次metadata与完整集成审查。MOCS/资源/语义缺口也阻止命令候选上机。此轮离线成果可以继续离线审阅，不能申请“已经安全可部署”的试验；结束后停止，等待用户决定后续资料与授权。

## 十项最终状态及证据范围

|状态|值|范围|
|---|---|---|
|COMMAND_SPEC_DIFF|PARTIAL|XML/逐bit/struct与官方限制索引完成；全部PRM条件与资源语义未形式化|
|STENCIL_TRANSLATION|PARTIAL|显式无资源/disabled/MOCS/stepping条件下Null pack验证；Apple runtime条件未知|
|DRAW_NORMALIZATION|VALIDATED|仅四direct/XP0的A/B定义字段及离线包边界，不是畸形源执行等价|
|SHADOW_BATCH|VALIDATED_SUBSET|纯NOOP/END/typedBBS严格layout/控制流子集；完整真实批拒绝|
|FAULT_REGISTER_AUDIT|PARTIAL|历史i915/v6.18/官方DATA1确定，完整公开CEC4/CEB8表及枚举缺|
|FORCEWAKE_AUDIT|PARTIAL|LinuxGT域确定；Apple域/ACK/power/reset locks未证|
|FAULT_CAPTURE_DESIGN|PARTIAL|mock fail-stop协议完成；真实同次采样/互斥/latch未知|
|FAULT_DIAGNOSTIC_BUILD|OFFLINE_PASS|8core+8pack、freestanding/sample实际通过；unattached，wholekext未构建|
|SAFETY_REVIEW|CONDITIONAL|仅离线边界内；初审缺陷修复及独立复审另列，真实MMIO阻塞|
|READY_FOR_HARDWARE_APPROVAL|NO|真实接入门禁与exactbinary缺口未关闭|

## 再现与完整性

入口`README.md`；`make check`执行Python suites和source/JSON/frozen-input hygiene；native构建命令、精确版本与输出hash在logs。官方PDF/固定Linux/Mesa出处见`reference/**/provenance*.json`及`core-provenance.json`。所有原失败日志、失败构建和阶段结果保留；新结果追加，不改写历史成功与否。私有`manifest.json`与`manifest.sha256`封存实际文件，manifest本身hash由封存回执给出。
