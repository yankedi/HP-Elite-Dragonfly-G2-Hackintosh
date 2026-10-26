# GA3.9 中文工程报告：Translator 修复与严格拒绝闭环

**最终工程交付：三轨独审必修问题已闭环；四个完整Shader保持严格拒绝，硬件批准为NO。完整性封存结果以`logs/seal-verification.json`及`.txt`的实际回执为准。**

日期：2026-10-20。全部新产物位于本Lab，CPU离线。对象为固定THAG Record1中PS0、PS-KP1、PS-KP2、VS。当前正确工程结果是有限整数位传递可条件接受、四个完整真实Shader均因必要证明不足严格拒绝；Research显式生成供离线检查，完整等价仍未证明。

逐条原目标、命名工件、命令、测试、门禁和结论的对应关系见`reports/ACCEPTANCE-CHECKLIST.md`；所有未证明的语义继续明确UNKNOWN，不以报告文字替代实证。

## 1. 主要结果

1. 实际实现了默认Strict的Translator策略及有限整数MOV codegen，不是只有报告或validator。`translator/translate_unit.py`通过固定IGA生成目标bytes；`driver.py`对完整输入执行封闭策略，任何必要UNKNOWN保持拒绝。
2. 官方ICL资料补足了NF=Native Float、高精度ACC用途及格式轮廓；保留66/67bit文档冲突。NF算术、收窄、舍入、denormal/FP控制仍没有足够位精确规范。没有伪造普通FP32等于NF，也没有声称取得真实四程序数值反例。
3. 独立byte may-liveness覆盖8程序与3个scratch；已知源投影无直接占用碰撞，但未知外部payload/间接引用/资源配额阻止安全分配证明。32个真实NF/ACC节点都有携证拒绝：三个PS共28个NF，VS四普通FACC，不是NF。
4. PS-KP1 `0x168→0x178→0x1A8`的null-response `.dst`、SBID复用和EOT副作用仍UNKNOWN。没有补猜测SYNC。四处Debug/Switch消除没有许可证明。
5. 十源/十目标SEND逐字段原码、载体、offset、资源合同及完成事件可以审查；整体消息等价未宣称。220个新字段评价与旧948层评价分母不同，不能相减。
6. 同一948评价单位重新比较仍为627有明确前提静态核对、0已建模子集确定反例、321UNKNOWN，关闭UNKNOWN为0。Strict拒绝4/4不能计作减少321。

独立`numeric/oracle/f32_rational.py`仅以精确有理数/RNE核有限binary32融合与分步舍入的诊断例；NaN/Inf、signed-zero传播、溢出、denormal模式及非RNE控制均不在其定理内。真实NF和普通FACC未获该oracle准入；这些特殊情况继续形成拒绝义务。

## 2. 十四项最终验收状态

|状态项|当前判定|精确边界与证据|
|---|---|---|
|INPUT_PROVENANCE|VERIFIED|完整捕获/IGA/Mesa/Translator pin、87身份、GA38/37 seal核验；`reference/inventory/`|
|NF_NUMERIC_SEMANTICS|UNKNOWN|格式轮廓有证，准确算术/收窄未闭合；`numeric/NF-ACC-SEMANTICS.md`|
|ACC_LOWERING|REJECTED|真实32节点均有义务并拒绝；不以有限整数MOV冒充ACC证明|
|SCRATCH_LIVENESS|VERIFIED_SUBSET|独立已知byte投影/活跃/干涉；外部ABI仍UNKNOWN；`run-031`及当前bundle|
|PS_KP1_SBID_RULES|UNKNOWN|`0x168/0x178/0x1A8`完成事件、硬件规则与IGA实现分层|
|DEBUG_SWITCH_ELIMINATION|UNKNOWN|PS三处`0x10`、VS `0xF0`；没有显式后读不证副作用/顺序冗余|
|SEND_FIELD_MAPPING|PARTIAL|真实十SEND有限编码值有核对；final4闭合O6，005分类优先级由final5独立闭合15/15原失败、33行零失败；ExDesc/RC U7仍带前提|
|SEND_RESOURCE_ABI|UNKNOWN|真实heap、thread payload、sampler/RT/URB配置缺失，保留symbolic|
|TRANSLATOR_STRICT_MODE|IMPLEMENTED|默认、未知拒绝、不跳指令、全节点义务及有限真实codegen；integration-final已验证原十项修补|
|TRANSLATOR_RESEARCH_MODE|IMPLEMENTED|显式隔离、固定新native、重新映射/解码/往返；IG-NEW-01经053修补及独立integration-final2故障矩阵闭合|
|FOUR_SHADER_REVALIDATION|COMPLETE|最终I072/J074各四程序实际重生与GA38再验证，075确定性、076原码/报告核对；最终来源绑定见state，不是全程序语义证明|
|INDEPENDENT_AUDIT|CONDITIONAL|数值、消息、集成三轨必修全部独立闭合，final5无开放新MUSTFIX；工具主要项闭合；结论限于已审域，保留语义UNKNOWN与低风险/信息项|
|READY_FOR_GA40_OFFLINE_INTEGRATION|PARTIAL|可以规划严格拒绝组合器；当前没有完整可接受真实Shader构成成功Draw|
|READY_FOR_HARDWARE_APPROVAL|NO|所有产物NOT_FOR_HARDWARE；没有硬件批准|

## 3. 输入与来源

- 捕获99648B SHA-256：`1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333`，仅Record1有效。
- IGA：`c36a504a4e6c68030c3302646aa396b8b59b22cb`。
- Mesa：`863338275d915e867319c3690ffd3272b06303c3`。
- Translator：`1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`。
- GA38 manifest：`db30c52513df69b6aede0cab767861de137ed669a26d88cbfee61ceddbe326f8`。

上游只有13blob的认证归档；native重建使用必要Mesa adapter/header子集，适配/原始源码逐项区分，不冒称完整原上游树。五构建clang-debug/release/sanitize、gcc-debug/release成功；原GCC C23/once_flag失败及gnu11修复保留。

`trust.py`以固定GA38 manifest身份核验baseline source/target IR、comparison、schedule、messages；调用者不能只修改派生NF flags或findings隐藏未知。原GA32–38只读。GA38复制仅作路径/scope/test-default适配，语义核心保留；diff见两次适配/集成修补目录。

## 4. 四Shader与实际代码变化

|Shader|源→目标bytes / 条数|NF/ACC节点|scratch|Strict|Research|
|---|---|---:|---|---|---|
|PS0|152→152 / 11→11|4 NF|r122|UNKNOWN_REJECTED|新生成、mapped/decoded/roundtripped，未证等价|
|PS-KP1|440→440 / 29→29|16 NF|r107|UNKNOWN_REJECTED|同上，RT链完成义务UNKNOWN|
|PS-KP2|216→216 / 15→15|8 NF|r117|UNKNOWN_REJECTED|同上|
|VS|288→288 / 24→24|4普通FACC|无上述NF scratch|UNKNOWN_REJECTED|同上，URB/隐式ACC未证|

源与目标完整SHA见`reports/FOUR-SHADER-STATUS.md`和当前metrics。合计1096→1096B、79→79条，Research扩张率1.0，与原研究候选bytes相同，无新增wait；不是重新证明了旧候选正确。

有限codegen仅NoMask SIMD8/M0、连续DWORD同整数类型、直接且分离GRF的MOV。目标16B MOV+16B自动sync.nop=32B，对8条lane等式的条件性GRF投影核对、IGA字段及exact往返单列；`isa_semantics_machine_proved=false`。它没有EOT或完整程序许可证，不能拼接成VS/PS后宣称成功。

NF/ACC携证合同明确源指令、目标序列、数值/FP模式、输入输出、scratch、mask/predicate、隐式状态及未满足项。Debug四处保留DBG显式值与Switch线程切换/延迟/IQ flush的不同义务。十SEND位置：PS0 `0x50/0x88`；KP1 `0xE0/0x120/0x168/0x1A8`；KP2 `0x90/0xC8`；VS `0x100/0x110`。每条raw hex、字段bit载体与资源引用在当前semantic-bundle和`messages/outputs/contracts-all.json`，CURRENT绑定实际源码/输出身份。

关键KP1目标原码（按文件原始byte顺序，不是DWORD反向打印）：

|offset|机器码hex|观察与未证边界|
|---|---|---|
|`0x168`|`3290040000000000441600500000c400`|RT sendc，null response，set SBID0；副作用完成仍未知|
|`0x178`|`61202400a00a0578056c460000000000`|MOV含`$0.dst`；无response语境下该wait覆盖范围未知|
|`0x1A8`|`3290240004000000447800500000c600`|RT EOT sendc，SBID0复用；EOT不默认等于全局flush|

这三条bytes与归档研究候选一致，当前没有以猜测硬件规则改变它们。

## 5. 同948单位前后结果

|固定口径|GA38|GA39|变化|
|---|---:|---:|---:|
|有前提静态核对|627|627|0|
|子集确定反例|0|0|0|
|UNKNOWN|321|321|0|
|总计|948|948|0|

单位是`(shader_id, source_offset, layer)`。新比较器机械锚定GA38封存历史键集合与源SHA，防止两次fresh共同漂移仍混称同分母。每条新旧规则/机器码/状态均保留，changed=0、unknown_closed=0；0反例不等于全程序正确。

220个新SEND字段评价中132为有限编码字段值核对、48有条件、10形式差异、30未知；10差异全是`sends→send/sendsc→sendc`助记符，明确不是语义反例，RT U7仍开放。精确最终字段scope/计数以CURRENT和最终审计为准。

## 6. 测试、独审和失败证据

- 历史隔离回归：31独立单位、8程序、640 native调用、21旧mutant；ASan/UBSan诊断0，另有Debug断言负控制。不能把Python称作ASan覆盖。
- 新native五构建20组四程序输出与归档候选一致；ASan/UBSan两配置8次输出匹配，独审含UBSan正控制；主代理035重算5binary+20outputs SHA一致。
- GA38复制47测试：旧009路径fixture失败保留，010修路径后通过；040显式`env -u GA38_RUN`仍47通过，解决default state缺失与环境回执缺项。
- 主测试047为34项通过，发布边界修补053增加至36项；最后消息005源码后整合重放073仍36项通过，另有消息40+51专门单测及独立探针重放。主测含真实MOV、源码身份、派生IR篡改、生成器写完再失败/超时、验证失败不提交、结构化kill、未知ABI、mapping缺漏、封存篡改及确定性误差负控制。
- 独立15类mutant、6controls在final009/010两次全通过，绑定最终driver053源码；35 IGA命令/次全部exit0；54个原始工件（40 bin、13 asm、1 fixture JSON）SHA一致。原007/008与更早结果保留；合成错误不冒充上游真实缺陷。
- 最终I072/J074两套全新目录：冻结消息005源码及发布053后各重提取、Strict4拒绝、Research4实际生成/验证、28NF+4普通FACC相关节点、4Debug、10SEND合同及有限正例。075要求全部必需工件，108项语义/二进制比较通过。只忽略明确artifact/JSON路径的耗时及本次run根，JSON键序/空白规范化明示；嵌套同名语义字段不删。旧A–H保留而不作为最终源码绑定。076额外从实际工件断言各程序counts与findings相等、候选与归档bytes相同、两处report字节相同；8份真实程序核对全部PASS。最新源码/默认合同绑定见state，区分新鲜度核验与语义审计。

15类独立mutant逐项入口与预期/观察在`tests/independent-mutants/runs/final-009/results.json`和010对应文件：

|固定类别|覆盖|预期的含义|
|---|---|---|
|C01–C04|scratch/live、partial write、predicate、隐式ACC丢失|独立may-live或认证IR/比较器保守识别，合成冲突与真实未知分开|
|C05|中间舍入改变|有限binary32 fused/split诊断反例；**不是NF位级反例**|
|C06–C11|SEND length、SFID、过早SBID复用、错误wait、提前EOT、错误Debug消除|符合独立编码/合同检查或继续UNKNOWN的固定预期，不声称取得缺失硬件规则|
|C12–C15|不完整mapping、插指令offset错位、跳unsupported、资源UNKNOWN伪已知|映射/身份/Strict边界与UNKNOWN传播负控制|

PASS表示每项达到预先独立写定的精确预期，并非15类都变成语义确定反例。六个control另含有限MOV正例、四真实Strict拒绝和NF片段拒绝。

独审链：数值`numeric-initial→numeric-repair-022→numeric-final→numeric-refresh`，224+115独立探针；消息`messages-initial→repairs001→messages-final→repairs002→messages-final2→repairs003→messages-final3→repairs004→messages-final4→repairs005→messages-final5`；集成`integration-initial→integration-repair038→integration-final→publication053→integration-final2`。额外交付工具`delivery-tools→delivery-tools-repair047→delivery-tools-final`。原审计、原反例、修前源、diff、回归和复审分别留存，主代理已读最终实证；没有开放必修问题。

修补回执里的PENDING是各次作者交付当时的真实状态，保持原件；闭环以随后独立审计和最新工件核对为准。数值refresh之后的lowering/工具输入验证与异常处理变化由集成两轮复审及最终正负例覆盖，不把较早数值审的源码SHA冒称完全相同。

消息004修前源码有特殊留痕：作者编辑后才保存pre-fix，故由本次差分逆推重构003 post-fix字节，再对003既存receipt核4/4 SHA一致。ERRATA与独审须明确这是字节身份已核的重构，不冒称编辑前实时复制；003及全部更早来源/反例/默认与审计原件不改。

final4原样保留了15个N15未闭合分类例：跨字段语义已为UNKNOWN，但`VALUE_CHANGED`分支仍优先给出`FIELD_DIFFERENCE_CONFIRMED`。005仅将既有矛盾/未知的降级标记优先用于equivalence，raw编码关系和值不删，不改变有限接受域；005修前源与元数据是在编辑前实际复制，和004的事后重构方式明确区分。

`audit/messages-final5/FINDINGS-FINAL5.json`独立确认这15行全部精确为`FIELD_SEMANTICS_UNKNOWN`，33行冗余长度矛盾重放零失败；合法4=4、16=16的有限编码值核对及O6控制不变。mapper最终SHA为`7858776d955228ef422835a019a6289d98e2b66d5fc104342f5bc01aabd1a78f`，completion保持`222a55a26a4e20d0730a0b116b76f9a8bd52cd3440703e15cb4f675b291d013e`。旧14+6+4回归与final4更广输入矩阵保留，不将本次有界复审冒称重新证明整个ISA。

集成final原10项MUSTFIX已独立关闭，随后IG-NEW-01实测发布rename后根报告写失败会在quarantine留下成功报告。053将全部报告写放到最终rename之前，故障处理先标FAILED、改写隔离报告并独立fallback；持久I/O失败返回结构化内存结果，不声称失败报告已落盘。`audit/integration-final2/FINDINGS-FINAL2.json`及原始`results/publication.json`已独立关闭该项，0新MUSTFIX；一次/持续根写失败、一次/持续rename失败及全部报告不可写均无公开候选、无quarantine成功报告，成功路径`post_commit_writes=[]`，两处report字节相同。若整个存储不可写，只能保留内存结构化失败；若rename持续失败，隐藏stage留有FAILED报告/候选，不当成发布成功。

额外工具final48fixture全部通过，DT01/02/03/05/07/09闭合，DT04因误读Gen11源空字段已撤回（Gen12目标carrier实际10/28/14/23）。仍披露DT08每程序counts直接复制但顶层从rows重算、DT10从异cwd模块导入限制；比较器对目标bytes变化只记录，076已另对最终8程序逐项断言原bytes完全不变及counts=rows。历史外部闭包是8875项已列文件/链接（8847文件、28链接文字），不是历史目录新增成员的自动监视。

原失败包括：GCC once_flag，复制测试路径009，指标r0省略字段029，预期失败PASS格误计入成功二进制034，测试fixture跟随danglinglink041，及独立初审反例。没有抹掉失败或改历史seal。具体代码修复清单见`reports/TRANSLATOR-REPAIR-RESULTS.md`。

## 7. 尚未闭合的语义与GA40

最小补证列表见`reports/REMAINING-PROOF-OBLIGATIONS.md`：NF位精确舍入/收窄与FP控制、普通FACC隐式状态、scratch/payload/资源ABI、Debug/Switch可观察性、null-response `.dst`、SBID复用与EOT可见性。可以继续拒绝未知并核有证字段，不能用随机通过、descriptor相等或可汇编替代证明。

GA40唯一主线详见`reports/GA40-PLAN.md`：GA39有限严格Shader组件+GA34 Command Stream Normalizer+typed symbolic资源合同，完全离线最小Draw。当前没有完整严格接受的真实Shader，GA34命令严格语义也有限；首里程碑应是真实四程序可靠拒绝的组合闭环。未来完整受限Shader、消息/dispatch及资源合同全部闭合后才可在CPU模型中谈成功Draw。**本轮仅规划，未实施GA40。**

距离真实Metal还缺驱动/command/pipeline、dispatch资源heap、GPU VM/驻留、缓存与跨线程/引擎同步、render/aux/compression、窗口系统/显示/功耗及硬件证据。未做GPU提交、MMIO、SSH、部署、IMG/EFI/固件或门禁修改。

## 8. 封存与复现

README含双模式入口、完整重放/比较命令。原件封存后仅运行`python3 -B tools/seal.py verify`；重放需复制私有Lab及manifest所列全部外部来源到独立副本。seal核对文件集合/bytes、symlink链接文字与外部输入，manifest自哈希不替代语义证明，也不自动证明链接目标。

最终封存步骤创建`manifest.json`与`manifest.sha256`，再独立执行verify和`sha256sum -c manifest.sha256`；实际命令、退出码、成员数和manifest完整SHA保存在排除的`logs/seal-verification.json`及`.txt`。这两个回执和manifest/selfhash是仅有的四个排除路径；封存后其余文件不再改写。最终会话报告给出manifest完整SHA作为独立pin。025/049外部预核与026 fixture测试不是最终封存回执。

最终仓库检查078 PASS；079/080再次核GA38/37历史seal PASS。077因record固定Lab工作目录且未给make `-C`而失败，078用显式仓库路径修正，原失败保留。GA39所有原失败、历史审计及受限结论均随完整性清单保留；硬件批准始终NO。
