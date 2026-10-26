# 独立审计、修复与证据范围

本轮独立来源、规则、oracle、native回归与对抗代码审查均使用用户指定 `opencode-go/deepseek-v4.1-flash`，未使用 Luna。主代理负责核心实现和整合；独立任务没有直接改主分析器。

## 初审：冻结版本与真实反例

`checkpoints/pre-independent-repairs-006/SOURCE-CHECKPOINT.json` 保存修前代码/state精确字节；`review/initial/` 保存初审报告、9项发现（7 mustfix）、直接规则核验与独立可运行反例。以下是初版缺陷，不是原四候选硬件故障证据。

|初审项|问题|当前修复/回归入口|
|---|---|---|
|GA38-IR-001|同SBID复用仅因无显式wait就报CE，忽略IGA隐式同步实现|保留 UNKNOWN/SBID-REUSE-SYNC-UNPROVEN；独立oracle ERRATA、M12/S01|
|GA38-IR-002|null-response SEND `.dst` 被无证判已完成|NULL-RESPONSE-DST-WAIT UNKNOWN；不释放已证明完成状态|
|GA38-IR-003|整数DW MUL未恢复implicit ACC write而误checked|补 symbolic ACC WRITE；`test_review_regressions` R3|
|GA38-IR-004|仅看source Switch/debug，target-only选项被漏掉|双方options/DBG独立比较；target-onlySwitch UNKNOWN；R4|
|GA38-IR-005|零local约束 vacuous checked|零约束UNKNOWN并明确没有正向调度验证；R6|
|GA38-IR-006|`@0`造成IndexError、坏SBID形状潜在崩溃|先校验subset；不执行非法distance/token状态更新；R5|
|GA38-IR-007|通用一对多路径缺CLI可达性、构建映射潜在裸KeyError|严格schema/hash/framing，缺证据UNKNOWN，通用candidate CLI；真实expansion015 11→12|
|GA38-IR-008|部分byte/lane“oracle”仅有公式/自洽覆盖|补literal坐标/精确edge集合、独立原机器码mutant和双代消息literal表；property/selfconsistency仍单列|
|GA38-IR-009|原子性/部分新输出问题（非阻断）|失败运行留在专有新目录，不将不完整输出当交付；发布前完整审计且旧root派生输出先存档，未宣称通用事务原子writer|

`runs/verification-016` 曾实际验证34方法、42工件；后续补消息和图独立oracle，`runs/verification-021` 两新目录各43方法、51含报告规范化工件一致。native回归按原640次调用和另两独立Debug build分开，不把同一sanitizer Debug冒称所有构建。

## 额外实际发现与原失败保存

- M05：region层漏typed subregister，被真实mutant检出；已将类型宽度/sr纳入region/lane投影。M05b直接改真实Gen11 NF指令已知GRF字段，防止全条NF UNKNOWN掩盖已知错误。
- VS源 +0xD8：symbolic ACC表达式含Python dict repr，sorted JSON重读改变顺序；原失败 `runs/m12-investigation-011/serialized-ir-original-failure.json` 保留，改canonical JSON，8IR回读逐字段重建校验。
- 独立规则初稿混淆编码SubRegNum字节与JSON sr元素，ADDENDUM-SR直接核BinaryOffsetToSubReg后纠正；主代理原GRF width*sr没有错误改掉。
- 独立oracle最初把SBID复用设CE，作者实读IGA和缺失硬件规则后更正UNKNOWN；原oracles/generator在`tests/oracles/checkpoint/`，完整依据在ERRATA，未删除原错误预期。

## 复审结果

独立最终结论为 **CONDITIONAL_PASS**：7/7 初始 mustfix 全部 CLOSED，无新开放 mustfix。`review/final/closure.json`、`FINAL-CLOSURE.md` 与完整源SHA/命令/日志保留原样。独立审查再次运行自己的真实11→12 CLI、21mutant、8IR回读，以及正向“缺真实response wait→CE”和“改已知GRF→CE”控制，确认校验器没有通过全部改UNKNOWN来掩盖问题。

复审另有4个低严重度非阻断观察，主代理随后处理如下；以下是**审计后主代理补充**，没有追改独立原结论：

|新项|收口|
|---|---|
|N1 其余派生语义字段未全部重建比较|扩展 numeric/message/unresolved/evidence 完整性；原独立`probe_integrity_gap.py`不改而重新执行，6项篡改全部拒绝，`coverage_gap=False`；新增6-case回归|
|N2 bare unittest默认指旧run|所有依赖actual run的测试改用`common.analysis_run()`，优先GA38_RUN、否则读取state最新run；无环境覆盖的完整47方法通过|
|N3 admission014包含旧analyze SHA|这是原运行时代码身份，按证据规范保留不改；不把014当当前全套验证。新026逐命令记录当前完整code_identity|
|N4 mapping负例被identity提前挡住|补真实源/目标hash并明确断言MAPPING_OVERLAP与MAPPING_INCOMPLETE；两条路径在最新全套中实际通过|

`runs/review-followup-025/` 保留上述原独立7项脚本再次重放、原tamper probe和bare discovery日志。`runs/verification-final-026`是补修/冻结后的两全新目录：各47方法、8schema、51规范化工件全同。`runs/mutants-final-027`21/21。026同时覆盖复审指出其后有变化的runner/report/seal工具，另含seal内容/集合/selfhash/symlink负例。

独立审查的source SHA证明其审查时版本；补修仅`integrity.py`新增重建字段比较、`common.py`新增测试run选择和相应测试，主SWSB/compare/message/semantic/mapping算法未再改。该小范围补修由原独立反例重放与当前全套实证支持，未虚称审查员再次签署新版本。最终状态仍保守为 INDEPENDENT_AUDIT=CONDITIONAL。

## 域内已知限制

NF/ACC内部精度、真实resource/thread payload ABI、外部可见完成、无response token和SBID复用硬件规则不是“等审核员同意就能消失”的问题，已在每层结果和backlog保持UNKNOWN。独立审计评价的是离线分析工程与结论边界，不认证GPU执行或Metal。`READY_FOR_HARDWARE_APPROVAL=NO`。
