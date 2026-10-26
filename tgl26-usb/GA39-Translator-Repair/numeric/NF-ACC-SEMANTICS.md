# NF / ACC：已查明的格式与尚不能证明的转换

## 结论

**NF 不是普通 F，也不是 ALT 模式；现有资料不足以建立完整位精确 NF 算术模型。默认拒绝实际 NF→F-GRF 转换。**

`NF_NUMERIC_MODEL=UNKNOWN`，四真实程序的数值等价性未获证明。拒绝是转换策略的决定；它不把任意一条真实候选升级为 `REFUTED_WITH_COUNTEREXAMPLE`。

## 官方证据与历史表述的收窄

固定 ICL PRM Vol9 1.20 p434–436 明确将 NF 称为 Native Float，用于 plane macro 的高精度 accumulator 中间存储。摘要表给出1符号位、10位指数（bias511）、56位significand并标67bit；另一图/类型名标66bit。**格式轮廓已有证据，精确位数存在同文档冲突**。原文及完整源SHA见 `../reference/numeric-debug/raw/icl-vol9-NF-accumulator.txt`、`EXTRACT-RECEIPT.json`。不能沿用GA38“完全没有NF格式依据”的宽泛表述，也不能改写GA38封存记录。

同卷p366–367的 F accumulator 表称32位、与GRF相同精度；VS使用普通`:f` ACC，不是NF。这个表不能独自证明跨代MAC融合、隐式ACC状态、区域和掩码行为。

ICL Vol2a p942的MAD表与LRP宏确有NF用途；Vol9 p442说明融合运算及accumulator/GRF允许有不同结果。这些足以拒绝“无条件按FP32临时值替换就等义”的准入依据，**还不足以给四个真实输入程序构造经硬件规范闭合的数值反例**。

## 明确未决

- 位精确NF算术、中间舍入、保护/粘滞位、NF→F收窄与融合规则。
- 66/67bit冲突、区域粒度（IGA按4byte索引，Mesa NF type-size为8；不据此猜物理ACC布局）。
- denormal、FTZ/DAZ、cr0/ALT与NF的相互作用，saturate及特殊值。
- SIMD8各channel group的源NF区域到scratch F区域逐lane对应。
- predicate/execution-mask下未写lane的保存与后续隐式ACC状态。
- EOT前最终可观察SEND payload的数值关系。
- Scratch的外部thread-payload ABI、间接访问及目标GRF资源配额。

“所有中间结果恰好FP32可表示”仅是可能的输入引理，当前没有证明NF自身舍入和收窄满足该引理的必要规则，因此没有注册成可接受的lowering规则。

## 真实位置与实现

PS0 NF位置4处：`0x0,0x20,0x30,0x40`，候选scratch r122；KP1共16处：`0x0,0x20,0x30,0x40,0x50,0x60,0x70,0x80,0x90,0xA0,0xB0,0xC0,0xD0,0xF0,0x100,0x110`，scratch r107；KP2共8处：`0x0,0x20,0x30,0x40,0x50,0x60,0x70,0x80`，scratch r117。

VS普通ACC链：`0x0 MUL,0x20 MAC,0x28 MAD,0xD8 ADD`。`proofs/lowering.py`对全部32个ACC相关源节点生成携带原码、目标序列、临时寄存器和未满足条件的拒绝证明，初版输出`proofs/run-013/`；每个结果仍为`UNKNOWN_REJECTED`。

`scratch-liveness/liveness.py`独立计算已知GRF byte投影的may-live集合，partial write只杀确定写入的字节，mask/predicate写不杀may-live；未知/间接访问不当成空集。已知投影无碰撞不是外部ABI安全证明。

## 数值Oracle的适用范围

`oracle/f32_rational.py`用精确有理数建立**假设的有限binary32、RNE、gradual-underflow模型**，给出融合/分步舍入不等的精确示例。它不是Gen11NF仿真器；NaN/Inf、signed-zero传播、模式差异有显式域外处理。随机测试不充当等价证明。严格接受的有限实现是无临时GRF的整数MOV位拷贝孤立片段，与NF模型无关。
