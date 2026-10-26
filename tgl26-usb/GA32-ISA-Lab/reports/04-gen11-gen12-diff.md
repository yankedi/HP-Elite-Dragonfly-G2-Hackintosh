# 04 · Gen11/Gen12 逐指令差分

原始 bytes 未变，分别用 IGA `-p=11`（icl）与 `-p=12p1`（tgl）解码。可复现输出为 `analysis/{ps,vs}-{icl,tgl}.asm`；JSON 完整 operand 表为 `analysis/isa-diff.json`，逐条Markdown表为 `analysis/isa-diff.md`，stderr 在 `logs/`。不能把 IGA 的部分输出有汇编文本等同于合法性验证。

| 指标（EOT 有界） | PS0 | VS |
|---|---:|---:|
| ICL 可解码 | 11 | 24 |
| TGL 可解码（op != illegal） | 5 | 13 |
| 相同源偏移下双端可解码 | 5 | 13 |
| 双端可解码中的 opcode 差异 | 1 | 1 |
| 双端可解码中的 operand/执行控制差异 | 5 | 13 |
| ICL compact | 3 | 12 |
| ICL SEND 系列 | 2 | 2 |
| ICL 分支 | 0 | 0 |
| ICL unknown/illegal | 0 | 0 |
| TGL illegal（解码错误，非硬件 hang 证明） | 6 | 11 |
| 已证编码语义不同（双端有效解码子集） | 5 | 13 |

后续依据PS的非零KP1/KP2和三种dispatch enable补充解码：KP1 29条ICL/17条TGL未报illegal（12非法），KP2 15/9（6非法）；两者compact各3、SEND分别4/2、分支0、opcode差异各1、可解码子集的operand/执行差异分别17/9。完整字段、原字节及CFG在 `analysis/ps-variants.json` 与额外四份ASM。三个PS合计ICL55、TGL31、目标非法24；VS另计24/13/11。

“operand/执行控制差异”统计含 exec size/offset、predicate、flag、mask、dst、src、opts任一变化；opcode统计也比较subop。依赖编码变化另在逐条差异标签标注（Gen11没有TGL SWSB），不静默略掉。这里“可解码”只指IGA未将该条标illegal，**不是硬件合法性或完整validator通过**。全部数据由程序生成，非人工估数。不同指标可重叠，不能相加为总数。

## 本机明确反例

* VS `+0x00` 同一 compact 字节 `41 2b 02 20 e0 20 02 04`：ICL `mul (8|M0) acc0 ... r2 ... r4`；TGL `mul (16|M0) r2.3 ... -r32.3 ... r4 {$11.dst}`。opcode 同名，但执行宽度、dst、src、依赖完全改变。由真实字节和两端工具输出支持，**兼容性已被静态反证**。
* VS `+0x58` ICL `mov r9, 0.0`，同 bytes TGL 落入 sync opcode，却有 invalid src0 register file；PS `+0x10` 与 VS `+0xF0` ICL debug-register MOV `{Switch}`，TGL 则是可解码 `sync.nop`。后者是“合法解码但功能不同”的本机证据；不能仅以参考项目 MOV/SYNC 说法替代。
* Gen11 native MAD 的寄存器/类型/execution 控制在 TGL 被重新解释；PS0/VS 的 Gen11 SEND(S/C) 字节在 TGL 报 GED decoding error，不能靠改 MOV opcode 修复整个程序。

## 静态能证明及不能证明

可以确认：两入口是有效 ICL 指令流；相同 bits 不是等义 TGL 编码；compact/native、操作数布局、MOV/SYNC 与 SEND 均需真正转换。目标错误存在明确工具诊断与固定编码表支持。

不能确认：这些入口已经被 hang 的 draw 执行、哪个指令先导致 hang、硬件对非法编码的实际处置、SWSB/payload/SEND/URB/RT/CCS 等重建是否足以使整个 render pass 正确。Gen12 decode invalid 不自动等于 GPU 必然 hang；根因仍须保持竞争假设。
