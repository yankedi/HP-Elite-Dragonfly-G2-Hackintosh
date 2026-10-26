# GA3.8 唯一工程任务：四Shader全程序消息／依赖IR与候选一致性校验器

`GA38_DIRECTION = FOUR_SHADER_MESSAGE_DEPENDENCY_IR_AND_GEN12_CANDIDATE_VALIDATOR`

`GA38_OFFLINE_ENTRY = READY`只表示下面的离线工程可启动，完整翻译/执行/Metal不在READY含义内。**GA37只交付本计划，无GA38新实现、无新Shader或Batch输出。**

## 1. 选择依据与本轮要跨过的实质边界

现有31独立单位不含跨指令读写、acc隐含状态或SEND完成依赖。现有四上游候选只检查再编码。GA38要首次产出**覆盖四个真实全程序的寄存器/消息依赖图与可执行的兼容性判定**，能指出哪个真实offset、哪条寄存器lane/消息契约、哪项调度约束未保持。不能只重画既有反汇编或把UNKNOWN列表重新包装成成功。

首要工程不是修Fault Hook，也不是立即发射完整shader。A方向先闭合实际程序的全局语义表示和候选拒绝理由，再为D方向提供逐条可修的约束。四程序无branch，故可先做有界直线依赖；输入出现branch必须拒绝，未来再扩CFG。

## 2. 具体输入（固定，不重采）

|输入|精确入口|用途|
|---|---|---|
|原始THAG双record|`GA32/capture/tgl-hang-GA32b-crash-20261018.bin`，99648B，SHA `1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333`|来源不变；仅使用已证record1窗口，不改源文件|
|4入口边界/原bytes|`GA32-ISA-Lab/analysis/ps-variants.json`、`isa-diff.json`、`reports/03-shader-boundaries.md`；共享EU窗口PS0+0x40/152B、KP1+0x200/440B、KP2+0x100/216B、VS+0x3C0/288B|79条源指令framing、完整EOT边界、实际offset|
|既有独立IGA输出|`analysis/{ps,ps-kp1,ps-kp2,vs}-icl.asm`及其JSON/目标输出，详见本轮`evidence/INPUTS.json`路径/SHA|源IR对照；不能以ASM文本代替原bytes|
|4上游候选|`analysis/upstream-{ps,ps-kp1,ps-kp2,vs}-gen12.bin`与`upstream-semantic-review.json`|只读对照候选，不执行；如PS0 SHA `146d58968884e2b4f89bc2c89b7665156953ae491165288b8e4cf816aa3cb71f`，其余用清单逐项验证|
|31严格单位|`analysis/translated-{ps,vs,ps-kp1,ps-kp2}/report.json`及unit*.bin|回归既有字段检查，不假定unit之间的调度可拼接|
|固定工具/规范|IGA commit `c36a504a…`、Mesa `863338275d915e867319c3690ffd3272b06303c3`、上游translator `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`与GA32/34固定IntelPRM及来源清单|先验证完整pin/hash再调用；可使用已有binary，不覆盖历史build|
|启用状态|`ps-variants.json`、GA34 `state-ir.json`/stencil/draw证明|绑定三个PS入口均启用；RT/URB/heap/payload内容仍UNKNOWN|

所有工具来源的完整SHA以163项输入清单及历史manifest为权威，不根据短hash猜源码。Apple25G83KC不作为此任务必须反汇编的输入，避免再次偏向诊断。

## 3. 要编写的代码（未来新独立GA38目录）

1. `corpus.py`：只读抽取4入口、精确hash/长度/offset、源到候选mapping；长度不符/多余padding/解码错误原子拒绝。
2. `semantic_ir.py`：有版本schema，保存原bits/compact长度、opcode/type/region/predicate/execmask、显式与隐式GRF/ARF/acc/flag访问、读写byte+lane集合；unsupported不是默认空集合。NF/acc精度与debug Switch作为一等语义项，不能删。
3. `message_ir.py`：独立解析Gen11 split SEND及Gen12 SEND的descriptor/exdescriptor/SFID、payload0/1长度、response长度、header、URB/RT消息参数、EOT。字段规则必须引用固定规范章节。动态descriptor、缺payload/heap内容以带来源的symbolic参数表示，禁止推导假BTI/RT身份。
4. `dependency_graph.py`：构建四直线程序的RAW/WAR/WAW、partial write/predicate/lane overlap、acc/flag隐含依赖和消息payload/response/terminal边；区分发送提交与消息完成，不用单一“上一条指令”近似。
5. `gen12_schedule_check.py`：从候选实际编码解析SWSB regDist/SBID set/wait、pipeline分类和sync，检查所需边被覆盖、SBID复用前完成、EOT不提前；不把IGA auto-deps当证明。用保守unknown拒绝未建模pipeline行为。
6. `compare_program.py`：按实际offset mapping比较4组规范化IR/依赖；结果分`STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS / COUNTEREXAMPLE / UNKNOWN`，每项给rule/source/target/前提，不设置`hardware_validated=true`。
7. `tests/`与`emit_report.py`：独立小oracle/限定属性模型、损坏/突变负例、稳定JSON/SHA和中文真实逐程序报告。测试oracle不得复用被测同一个字段解析函数计算期望。

这是一项完整工程任务的模块分解，不是同时启动A–F六个项目。可复用旧decoder/encoder，只在新目录适配，既有历史产物不变。

## 4. 可离线测试的验收标准（区分工程完成与语义放行）

* 4程序79条源指令**全部有IR节点和sourcebytes锚**，每条SEND/EOT均有消息节点和payload读写范围；无法语义解析的字段保留UNKNOWN并阻止对应候选放行，不允许跳过该节点。
* 两套独立字段依据（IGA与固定PRM/Mesa对应规则）对每个实际消息的已知descriptor字段对照；长度/执行宽度/消息种类/EOT变化在准确offset拒绝。符号payload契约清楚列前提，不宣称缺失资源实内容已验证。
* 四完整依赖图均能确定性重建；31旧单位回归字段保持；**新增跨指令**partial-lane RAW/WAR/WAW、acc、predicate、SEND response→consumer、SBID reuse/EOT事件的正负oracle，对mutant能指出具体缺边。
* 用真实上游4候选输出作为输入：NF→GRF与debug Switch改写必须产生明确反例或有根据UNKNOWN，不能继续报告整shader等义。SEND有证字段保留可单独通过，不以一个未知吞掉其余分析。
* 精度不明的NF等**不以随机float测试宣告等义**；若要关闭它，需固定官方精度/舍入/融合语义和独立数值模型，否则继续UNKNOWN。此项不阻止IR/validator工程交付，但阻止完整shader通过。
* 删除必要wait、提前复用SBID、缩短payload、改变RT/URB消息类/寄存器region/EOT、截断compact/native、别名/partial-write突变，均结构化拒绝。branch输入拒绝；四真实无branch不要求本轮实现generalCFG/branchreloc。
* 四source/candidate exactbytes保持原hash；Clang/GCC涉及native组件时Debug/Release/ASanUBSan；Python逻辑以独立oracle/属性负例验证，稳定输出跨两次干净目录相同。保存命令、exit与所有失败。
* 对每个程序给“能静态保证什么／仍缺什么”的机器可读合同。工程验收可完成而四程序全部仍不准执行；这比原31独立unit增加全程序消息与调度判定，不冒充完整加速。

## 5. 明确范围

本任务不改真实GPU Batch/Shader、不部署translator、不开GPU实验、不新增MMIO/Hook、不继续大规模Apple逆向。无需重做已完成的NullStencil/Draw格式规范化。资源实内容与submission ABI不足时只给symbolic契约，不造heap、PML4、allocation身份。完整通用编译器、任意branch CFG及新nativeTGL pipeline不在GA38最小任务内。

## 6. 与完整 Metal 加速仍隔着哪些关键障碍

至少六组独立障碍，不是完成本任务即可“一步开Metal”：①NF/acc/debug/完整SEND与依赖的可执行等义翻译；②CommandStream跨代状态、PIPE_CONTROL、relocation和未知继承；③Surface/Binding/Sampler/URB/RT/MOCS/CCS及payload资源ABI；④分配/映射/context-generation/缓存失效与内存安全；⑤Apple调度/提交/CSB/fence/恢复、PM/GT安全生命周期；⑥macOS IOAccel/Metal用户态与WindowServer真实功能、长期稳定性/恢复验证。Fault可帮助缩小④⑤，但不能代替①②③。

## 7. 后续硬件准入（本计划不批准）

需新明确授权；先定义一个有界、可回退的具体实验和单变量目标。真实访问先满足独立READ_SAFE所有关键条件与exactpatchedbytes/ABI/receiver/owner；写入/提交shader比只读MMIO还需更强的整程序语义、资源映射/寿命/隔离、命令与同步契约，完整shadow原子构造/验证、失败回滚、恢复/超时及卸载fence。不可取消IO不返回、reset排他/ACK不明或资源UNKNOWN时拒绝。不得将GA38_OFFLINE_ENTRY READY解释为hardwareREADY。

## 8. 最小实施顺序与停止规则

先corpus+IR→实际SEND合同→完整依赖图→Gen12候选checker→四真实差分及mutant验收。每步只前进到下一有证边界；公开NF/消息规范不足就记录具体字段/章节/所需证据，不无限查资料、不转回Fault循环。需要的新硬件数据作为未来独立事项，继续完成可离线的validator。最终唯一方向保持上述IR+checker，不因某条规范UNKNOWN又扩成完整native驱动项目。
