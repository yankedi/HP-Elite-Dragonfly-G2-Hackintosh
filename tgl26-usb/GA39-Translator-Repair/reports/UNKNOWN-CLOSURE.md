# GA38 → GA39：同口径 UNKNOWN 对照

已运行的机器可读逐项差分：`../candidates/comparisons/diff-020/diff.json`。比较单位固定为`(shader_id, source_instruction_offset, layer)`；79条源指令×12层=948，源SHA一致、键集合完全一致，禁止用拒绝程序数量替换这个分母。

|口径|GA38基线重放003|GA39重生研究候选014|变化|
|---|---:|---:|---:|
|有明确前提的静态核对|627|627|0|
|已建模子集确定反例|0|0|0|
|UNKNOWN|321|321|0|
|总评价|948|948|0|

四研究候选bytes与历史一致，未猜测性插SYNC或重写NF算术。本轮有效改变是**转换准入/义务覆盖与诊断**，不是把未知的原候选变成证明通过。真实完整程序严格接受0/4，明确因证明不足拒绝4/4。

## 新证据收窄了什么

- 官方ICL资料明确NF=Native Float、高精度ACC用途及格式轮廓；66/67bit同文档冲突，精确算术仍缺。因此“完全没有格式依据”收窄为“位精确算术/收窄未闭合”。这不消除十二层数值等价UNKNOWN。
- VS实际是普通FACC，不是NF；仍需隐式ACC、融合及区域证明。该分类纠正不自行改变旧层判定。
- scratch独立byte投影和活跃图提供了精确可审计范围；没有ABI证明，不能关闭资源/数值层UNKNOWN。
- Debug显式数据值无人再读不排除ARF或Switch调度效果，四处继续UNKNOWN。
- 新SEND逐字段合同细分132/48/10/30等新模块统计（以最终实际回执为准），它们不是948旧评价单位。已知字段数不能与旧UNKNOWN相减。

## 工程缺陷关闭与语义未知不同

`audit/messages-initial`发现漏传/UNKNOWN长度被当0、错误缺失事件、ordinal配对、丢失目标消息及None相等伪已知等实际代码问题；`repairs-001`保留初源、diff与回放，独立最终审计另存。修复会让**新模块**更诚实地保留UNKNOWN，不能宣称证明了null-response/SBID硬件语义。

数值初审A1–A5使policy与emitter同域、补目标symbolic义务、修正自指边与执行证据、区分ISA前提/机械检查。原失败和初审永久保留。有限位拷贝接受域和整体硬件未知仍分别标注。

初始对照014/020已经在集成修复后的`candidates/delivery/fresh-A-044/comparison/diff.json`及`fresh-B-045/comparison/diff.json`重新实跑确认：各948、changed=0、unknown_closed=0。107项语义/二进制工件双目录比较见`candidates/comparisons/determinism-046/determinism.json`，不以日志文字路径或计时噪声冒充语义不确定。

消息003阶段E/F及004阶段G/H保留。当前消息005源码后最后证据为`candidates/delivery/final-I-072/comparison/diff.json`与`final-J-074/comparison/diff.json`，仍各948、627/0/321、changed=0、unknown_closed=0；`candidates/comparisons/final-determinism-075/determinism.json`在必需108项语义/二进制工件上通过。076又独立重算每程序counts对findings、直接断言候选与归档bytes相同，最新source/default绑定见state；工具DT08/目标diff策略的低风险限制没有被用于降低这次真实验收条件。
