# 剩余证明义务与最小下一份证据

下表描述语义缺口。工程审计发现的错误与这里的硬件/ABI未知分别留痕；修复UNKNOWN传播不表示取得了新的硬件规则。

|义务|真实位置/资源|当前事实|最小下一份证据/退出条件|
|---|---|---|---|
|NF精确算术/收窄|PS0 4、KP1 16、KP2 8个NF相关源节点|ICL PRM Native Float格式轮廓已知，66/67bit冲突；非普通F|明确对应Gen11的中间舍入、NF→F、融合、denormal/特殊值与模式规则；再建立独立位精确模型。更宽格式本身不构成真实输入反例|
|普通FACC隐式状态|VS `0x0/0x20/0x28/0xD8`|不是NF；同32bit精度表不能证跨代MUL/MAC数据流|逐lane/region、隐式ACC读写、精度/融合和thread FP-control合同|
|scratch外部ABI|PS0 r122、KP1 r107、KP2 r117|已知源GRF byte投影无直接碰撞；仍拒绝|真实dispatch payload、GRF配额、未知间接引用/live-in/live-out及使用范围。源文本未出现不证明可分配|
|Debug与Switch冗余|三个PS `0x10`、VS `0xF0`|写DBG与强制切换/IQ flush是不同作用；没有后继显式DBG读仍不够|外部观察/特殊ARF作用排除合同、Switch目的与目标至少等强顺序、真实环境前提|
|null-response `.dst`|KP1 `0x168→0x178`|目标RT SEND无response，其后MOV含`$0.dst`；不可据此宣称消息副作用完成|Xe-LP明确硬件规范：无response时dst等待覆盖哪些完成事件、何种执行条件|
|SBID0复用|KP1 `0x168→0x1A8`及其它复用|IGA实现模型不是硬件完整完成保证|token生命周期、implicit serialization及复用约束的确切代际规范；没有证据不插SYNC|
|EOT可见性|四程序最终SEND；RT/URB|Thread终止位迁移可核，EOT对先前消息的可见性未闭合|EOT、RT/URB写入及跨线程/引擎顺序合同；不要把结束位当全局flush|
|Sampler ABI|PS0 `0x50`、KP1 `0xE0/0x120`、KP2 `0x90`|SFID/BTI/Sampler编码与若干长度可核|绑定表、Surface/Sampler State真实身份/内容、输入coord/payload布局、格式/边界模式、缓存/可见性|
|RT ABI|PS0 `0x88`、KP1 `0x168/0x1A8`、KP2 `0xC8`|RT index、载体字段可核；descriptor相同不证效果|RT surface布局、格式/aux/compression、tile/pixel mask、线程payload与写控制、MOCS/可见性|
|URB ABI|VS `0x100/0x110`|两消息编码与长度有有限检查|URB配置、entry handle/size/offset、dispatch输出布局、分配/释放及顺序合同|
|message type/ExDesc|全部十SEND，特别RC结构|ExDesc低字段迁移可见；若干代际解释仍有条件/UNKNOWN|与实际代际匹配的消息特定格式；解决固定PRM/头文件解释冲突|
|全程序准入|全部四真实输入|当前只有孤立整数MOV的条件性GRF位传递域；没有完整Shader许可证书|逐节点语义及所有全程序控制/ABI/完成义务闭合；不能连接已接受片段跳过EOT|

## 接受/拒绝的证据等级

- `PROVEN_UNDER_EXPLICIT_ASSUMPTIONS`：仅限报告明确列出的有限域和ISA前提，机械检查项目单列；不是硬件执行证书。
- `REFUTED_WITH_COUNTEREXAMPLE`：必须保留确切输入和所反驳命题。合成scratch碰撞、mutant谓词/长度改变是负控制，不是原上游真实Shader缺陷。
- `UNKNOWN_REJECTED`：必要事实未证，策略拒绝。不能计作“UNKNOWN已消除”或“确定错误”。

NF→普通F的通用无条件接受依据已被拒绝；尚未得到针对真实四Shader的位级数值反例。浮点有理数oracle只刻画其声明的有限binary32假设模型，不能替代NF。`FIELD_DIFFERENCE_CONFIRMED`包括预期的`sends→send`形式差异，不等于消息语义反例。

## Symbolic资源合同的必须字段

资源类型/代际、来源identity+generation、分配范围/寻址空间、引用field及offset、生命周期、初始化/可见性、布局/stride/format/aux、启用/继承条件、线程输入/输出payload ABI、消息访问范围和副作用顺序。缺项继续UNKNOWN；不制造一个heap把真实捕获补绿。

GA40唯一离线路线及停止条件见`GA40-PLAN.md`。**READY_FOR_HARDWARE_APPROVAL=NO**。

## 工程接口的已披露适用范围

- Research当前四程序与归档目标bytes相同；root semantic bundle使用认证baseline，候选目录另存fresh IR生成的bundle。未来若研究候选bytes/布局改变，必须重新处理fresh bundle身份及显式witness传递，不能把当前baseline bundle的SHA当新目标定理；当前偏移漂移会fail-closed为未配对，不自动取得许可。
- 独立`run_preflight.py`/`run_lowering_proofs.py`遇到伪造IR会exit1且不发布summary/proof，但其CLI可能显示traceback；主`driver.py`提供结构化拒绝。未来接口消费者应分清两者，不能把非零退出当成功空合同。
- 工具每程序counts直接复制、target bytes变化只记录；本次最终交付额外逐程序重算counts并断言原码相同，具体回执由FINAL-REPORT引用。从其它cwd按模块导入delivery脚本有路径限制，README所示脚本入口是复现接口。
- 不能写入任何报告的存储故障只返回内存FAILED及I/O错误列表，不承诺磁盘审计；持续rename失败可能留下隐藏stage及FAILED报告。两者均不意味着候选已成功发布。
- seal核完整GA39文件集合、历史manifest列出的外部文件/链接文字，不自动核未列新成员或symlink目标；最终会话交付SHA需独立保留。
