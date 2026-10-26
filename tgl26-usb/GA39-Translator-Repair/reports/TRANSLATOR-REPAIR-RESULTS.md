# 实际 Translator 修复清单

工程位置为本Lab独立`translator/`树。原Gen11→Gen12 C生成器有13blob固定来源和五新构建；本轮默认严格准入与有限实际codegen由Python封闭策略实现。不是只写validator或报告，也未将受限源码副本称为完整上游树。

## 一、已实现的转换路径

|路径|代码|实际行为|证据|
|---|---|---|---|
|有限整数MOV|`translate_unit.py`、`strict-policy/policy.py`|NoMask SIMD8连续DWORD、同整数type、disjoint直接GRF；真实IGA生成Gen12片段，核字段、可选自动sync形状及exact往返后才发布片段|正例033；独立15类mutant P1；numeric-final A1/A4|
|真实全程序Strict|`driver.py`、`policy.preflight`|默认启用；逐节点列必要义务，不跳unsupported；NF/ACC、Debug、SEND/ABI或全程序定理未证则拒绝|strict032所有79节点；driver测试；四程序控制|
|显式Research|`driver.py --mode research`|固定新native binary生成完整候选，隔离NOT_FOR_HARDWARE、重新走GA38接口、解码及exact roundtrip；没有verified executable标志|research014四条实际执行回执；最终修复后的回执另记|
|NF/ACC携证拒绝|`numeric/proofs/lowering.py`|32个实际相关节点保留source/target序列、输入/输出/模式/隐式状态/临时寄存器与未证义务；无外部JSON可升级为PROVEN|proofs013及semantic023|
|scratch独立投影|`numeric/scratch-liveness/liveness.py`|逐byte may-live/精确部分写/conditional不kill；source/target未知访问均阻断；read-before-write干涉图|8程序新run031；21主测中的相关项；独立数值闭环|
|Debug/Switch许可|`debug/switch-elimination/guard.py`|四真实源位置单列DBG显式读取与Switch顺序/副作用义务；没有后继DBG读取仍UNKNOWN|proof-contracts021；numeric-final guard探针|
|SEND字段/完成检查|`messages/field_mapping.py`、`scheduling/completion.py`|字段原码与代际载体锚定、符号资源ABI、五类完成事件；保留目标未配对消息和所有UNKNOWN|初审14反例、repairs001、messages-final及第二轮修补|

有限MOV的8条逐lane方程是**列明ISA前提的条件性值传递论证**。实际机械检查项目与ISA前提分开，`isa_semantics_machine_proved=false`。它的目标为32B（16B MOV+16B自动SYNC），不是完整Shader，未证明一般SEND完成或外部程序上下文行为。

### 归档生成器的实际原码锚点

固定`translator/source/native/adapter/tgl_xlate.c`中：

- `199–215`：检测NF目的/源0并改为普通F及`nf_scratch`；这是本轮必须前置拒绝的实际路径，不是仅根据反汇编名字猜测。
- `124–126`及随后分支：注释把Apple ARF `>=0xF0` MOV的Switch称为hint并生成替代。官方强制切换/延迟/IQ flush证据使这个注释不能作为消除证明；仍不把每个真实候选升级为已证错误。
- `726–735`：以kernel未显式命名寄存器选择NF scratch；它没有证明外部thread payload/live ABI。
- `529–574`：本地token冲突集合、`$N.dst`及复用模型；compiler实现事实与硬件完成规范分开。
- `567`：单条翻译失败时内部暂记NOP并累加bad；`577`在布局发布前对bad返回失败，`752`对错误长度/原因继续传播失败。因此不能只引用临时NOP行就宣称生成器静默提交。正式Strict没有使用该生成器作未知指令fallback，Research只处理固定四源且完整再验证，异常输出先隔离。

原四个translator C/H文件与13blob归档身份一致，适配Mesa emitter/stub来源在native/PROVENANCE逐项区分；这里只引用实现事实，不用改过的adapter证明上游硬件语义。

## 二、数值初审的真实修复

原初审/原源hash永久保存在`audit/numeric-initial/`和`translator/patches/numeric-repair-022/before/`；diff与回归回执同目录。

|发现|修复|独立实际复核|
|---|---|---|
|A1 policy域大于emitter|把wren、SIMD8/M0、region、DWORD、同type/无modifier/分离GRF限制纳入同一资格域|22单字段变体一致；无(W)实际编码拒绝|
|A2 target-only symbolic漏义务|源/目标symbolic均追加`SYMBOLIC_OR_INDIRECT_GRF_ACCESS`|ANY和GRF UNKNOWN两种均拒绝|
|A3 RMW自指reaching edge|先记录同节点READ，再登记WRITE|0自指；所有链式边向前|
|A4字符串forall看似机械定理|改`conditional_claim`、`machine_checked`及明确ISA前提|无forall；8方程不变；实际32B保留|
|A5 kill靠自由文本|从结构化`iga_fields.wren/pred/es`决定；无证不kill|8真实程序核心records与旧源一致；新增文字伪装负例不kill|
|A6–A8范围/覆盖|auto-sync前提单列，nf-only也有义务，所有非GRF访问显式记out-of-projection|独立反向探针通过；A9溢出边界仍域外|

数值终审`audit/numeric-final/closure.json`224/224探针PASS；原12测试与终审相关18测试均有实际日志。旧工件004/007/019保留，最新031/032/033重新生成，终审提出的工件新鲜度N1由独立刷新复核单独留痕。测试在本Lab的隔离work目录写临时文件，未写历史树。

## 三、消息初审14项修复与第二轮发现

初版19+12单测虽通过，独立审计仍找到14个可复现问题；因此不能将自测绿灯当完成。原探针/失败、修前源、修补回放全部保留。

- 缺失、漂移或UNKNOWN RLEN不再默认0；UNKNOWN payload不丢source-consumption事件。
- 来源按shader+platform+program SHA绑定，重复相容身份拒绝；不把source/candidate覆盖成同一个对象。
- SBID复用依IGA实现的K2/K3均保留硬件UNKNOWN，不以编译器行为代硬件规范。
- UNKNOWN编码/None不会因相等成为KNOWN；缺execution/family/form/nullresponse等字段不伪已知。
- EML与payload1长度共用未闭合的字段解释，语义级状态一致保守。
- 移除ORDINAL回退，保留所有target-only消息；位移映射需hash-bound显式布局witness。
- 每字段有required enum、源目标raw/programSHA、载体位置；descriptor相同不证消息语义。

`audit/messages-final`独立证实这14项闭环，但另发现跨shader witness错误绑定、重复last-wins、KNOWNnull异常及默认输出/来源过期。第二轮`repairs-002`处理这些新反例，`messages-final2`已独立证实其六项和原14项通过；同时又找到长度字段特定上界、歧义target漏source、null-response与非零RLEN矛盾的四个MUSTFIX，随后在第三轮修补，不能以冻结四程序未触发来忽略。

第三轮`repairs-003`经`messages-final3`独立关闭上述四项，并保留旧14+6；又出现N15：descriptor中的RLEN与decoded `response_grf_length`相互矛盾仍被mapper标PROVEN。第四轮004已实现RLEN/MLEN/EML三组冗余长度一致性，以及已观测的畸形destination O6；40+51作者单测及11探针重放通过，最终结论以随后独立final4为准，不能由作者回执提前关闭。前轮来源与输出保持原字节，CURRENT只指向最新代。004 pre-fix是编辑后重构并对既存003 post-fix核4/4 SHA，不冒称编辑前实时捕获，ERRATA原文保留。

final4实际已闭合O6，另保留N15的15个具体反例：semantic/cross/raw正确，但VALUE_CHANGED仍先于UNKNOWN给出DIFFERENCE_CONFIRMED。主代理005在真实编辑前复制原源与元数据后，只修分类优先级，不改变codegen或准入域；最终独立final5只复核这些具体剩余例与必要控制，避免无界扩审计。

final5实际闭合15/15原失败，33行完整冗余矛盾重放零失败，equivalence精确UNKNOWN且raw/值/关系保留；合法4=4/16=16与O6回归不变、无开放新MUSTFIX。完整源SHA与原始探针见`audit/messages-final5/`。三轨必修闭环不等于未知数值、完成事件或资源ABI被证明。

新模块的220条字段评价不是旧948评价。其10条`FIELD_DIFFERENCE_CONFIRMED`全为`sends→send/sendsc→sendc`形式助记符，bits=null；不是硬件数值或消息反例。

## 四、回归与原失败保留

- baseline003重新从原捕获提取，79+79指令、20消息、948同口径。
- 旧31独立单位、8程序、640 native调用、21旧mutant实际隔离重放PASS，ASan/UBSan诊断0；另有debug assertion负控制。
- GA38复制47测试首次009因搬迁scopefixture失败，原失败保留；仅改引用真实历史路径，010全PASS。语义算法未改，path/scope适配diff可读。
- 新独立15类mutant与6controls在005/006双重放PASS；所有原literal预期不变，只新增结构化执行证据及一个文字伪装负例。合成输入不冒称上游bug。
- 五native构建跨四程序bytes一致；GCC首个once_flag失败与gnu11适配保留。
- 历史检查点`make check`024 PASS，GA38/37完整seal027/028 PASS；新封存器3个篡改/追加/链接测试026 PASS。025只是在当时时点做外部closure预核，不是最终seal；最终检查078/079/080及实际封存回执见FINAL-REPORT。

## 五、没有被修成“全绿”的语义

NF位精确舍入/收窄、普通FACC跨代隐式状态、外部scratch/payload/heap ABI、Debug/Switch可观察性、null-response `.dst`、SBID复用硬件完成及EOT可见性仍UNKNOWN。四真实完整程序均Strict拒绝。

同单位差分020及集成C048/D050仍为627有前提核对/0子集确定反例/321UNKNOWN。driver已连双模式合同，107项A/B比较之后又强化为必需108项C/D比较051。原常量PASS、未固定历史键集和工件缺漏问题由额外工具审计发现，修前源/diff047及独立复审另存。消息005针对性独审结论由FINAL-REPORT汇总；本修复记录不是硬件许可证书。

发布053前后源与diff、36测试及`integration-final2`独立矩阵保留；原10项及IG-NEW-01均关闭、0新集成MUSTFIX。E/F验证该driver与消息003，G/H验证004，原件均保留。最后005源码后I072/J074/075/076完整重生、108工件比较、实际原码/报告/计数均PASS，主073仍36通过；最终来源绑定见state。最终独审结论及完整封存由FINAL-REPORT汇总，不覆盖已有各代工件。
