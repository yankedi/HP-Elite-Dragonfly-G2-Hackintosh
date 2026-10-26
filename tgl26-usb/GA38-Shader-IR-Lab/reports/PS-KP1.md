# PS-KP1：真实源与 Gen12 候选逐程序审查

源：440B／29 条，EU 窗口 `+0x200`。
源 SHA256 `d6b32c1deba1538772a0a9fdb84408223760197813554cb96810ed634b42dbc1`；候选 SHA256 `4cced77c4538b3243a4493a9d921b9c16fa534ccffd4c363bb0b686608ceabbb`。

## 结论和边界

十二层逐项结果：`{'COUNTEREXAMPLE': 0, 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS': 216, 'UNKNOWN': 132}`。目标调度约束：`{'COUNTEREXAMPLE': 0, 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS': 116, 'UNKNOWN': 3}`。
STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS 仅限该字段/约束及所列假设，不代表完整指令等价。UNKNOWN 保留来源与影响。硬件认证始终为 false。

## 指令对应与十二层状态

映射来自被冻结候选及历史布局见证，并用真实 framing 验证全覆盖。它是对应假设，等价性由各层独立检查。额外 SYNC/一对多范围可表达；多 ALU 组合缺证明时返回 UNKNOWN。

|源偏移|EU窗口|源编码|候选范围|opcode|结果 C / X / U|
|---|---|---|---|---|---|
|+0x0|+0x200|`5b0060001cc0002001b620070604c002`|+0x0|mad|5 / 0 / 7|
|+0x10|+0x210|`01800000041e003e0000000000000000`|+0x10|mov|5 / 0 / 7|
|+0x20|+0x220|`5b0060000c480000330022070804c802`|+0x20|mad|6 / 0 / 6|
|+0x30|+0x230|`5b1060001cc0002001b620070a04c002`|+0x30|mad|6 / 0 / 6|
|+0x40|+0x240|`5b1060000c480001330022070c04c802`|+0x40|mad|6 / 0 / 6|
|+0x50|+0x250|`5b2060001cc0002001b620070e04c002`|+0x50|mad|6 / 0 / 6|
|+0x60|+0x260|`5b2060000c480076330022071004c802`|+0x60|mad|6 / 0 / 6|
|+0x70|+0x270|`5b3060001cc0002001b620071204c002`|+0x70|mad|6 / 0 / 6|
|+0x80|+0x280|`5b3060000c480077330022071404c802`|+0x80|mad|6 / 0 / 6|
|+0x90|+0x290|`5b0060001cc0002001be20070604e002`|+0x90|mad|6 / 0 / 6|
|+0xA0|+0x2A0|`5b0060000c48000c330022070804e802`|+0xA0|mad|6 / 0 / 6|
|+0xB0|+0x2B0|`5b1060001cc0002001be20070a04e002`|+0xB0|mad|6 / 0 / 6|
|+0xC0|+0x2C0|`5b1060000c48000d330022070c04e802`|+0xC0|mad|6 / 0 / 6|
|+0xD0|+0x2D0|`5b2060001cc0002001be20070e04e002`|+0xD0|mad|6 / 0 / 6|
|+0xE0|+0x2E0|`3300800278c0c0010200000001008404`|+0xE0|sends|8 / 0 / 4|
|+0xF0|+0x2F0|`5b2060000c480074330022071004e802`|+0xF0|mad|6 / 0 / 6|
|+0x100|+0x300|`5b3060001cc0002001be20071204e002`|+0x100|mad|6 / 0 / 6|
|+0x110|+0x310|`5b3060000c480075330022071404e802`|+0x110|mad|6 / 0 / 6|
|+0x120|+0x320|`332080027840870dc20e000001008404`|+0x120|sends|8 / 0 / 4|
|+0x130|+0x330|`40008080284b802380028d4e0000803f`|+0x130|add|10 / 0 / 2|
|+0x140|+0x340|`0116012007160e00`|+0x140|mov|11 / 0 / 1|
|+0x148|+0x348|`0116012007181000`|+0x148|mov|11 / 0 / 1|
|+0x150|+0x350|`01160120071a1200`|+0x150|mov|11 / 0 / 1|
|+0x158|+0x358|`40208080284bc02f400e8d4e0000803f`|+0x158|add|10 / 0 / 2|
|+0x168|+0x368|`3400800560000000c002000000100310`|+0x168|sendsc|8 / 0 / 4|
|+0x178|+0x378|`01208000284b002f800d8d0000000000`|+0x178|mov|10 / 0 / 2|
|+0x188|+0x388|`01208000284b402fc00d8d0000000000`|+0x188|mov|11 / 0 / 1|
|+0x198|+0x398|`01208000284b802f000e8d0000000000`|+0x198|mov|11 / 0 / 1|
|+0x1A8|+0x3A8|`3420800560000000000f000000180390`|+0x1A8|sendsc|7 / 0 / 5|

## 逐层状态与最小修复入口

|源偏移|层|状态|规则|结论/约束|
|---|---|---|---|---|
|+0x0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x0|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x0|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x0|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x10|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x10|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x10|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=1, target=1|
|+0x10|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x10|predicate_mask|UNKNOWN|MASK-PREDICATE|Mask/predicate equal but other execution-control options differ; observability unresolved|
|+0x10|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x10|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x10|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x10|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x10|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x10|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x10|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x20|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x20|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x20|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x20|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x20|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x20|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x20|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x20|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x20|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x20|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x20|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x20|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x30|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x30|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x30|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x30|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x30|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x30|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x30|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x30|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x30|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x30|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x30|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0x30|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x40|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x40|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x40|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x40|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x40|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x40|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x40|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x40|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x40|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x40|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x40|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0x40|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x50|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x50|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x50|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x50|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x50|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x50|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x50|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x50|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x50|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x50|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x50|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|4 local schedule constraints, with independent status per edge|
|+0x50|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x60|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x60|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x60|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x60|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x60|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x60|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x60|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x60|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x60|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x60|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x60|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|3 local schedule constraints, with independent status per edge|
|+0x60|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x70|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x70|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x70|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x70|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x70|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x70|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x70|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x70|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x70|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x70|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x70|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|6 local schedule constraints, with independent status per edge|
|+0x70|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x80|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x80|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x80|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x80|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x80|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x80|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x80|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x80|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x80|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x80|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x80|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|4 local schedule constraints, with independent status per edge|
|+0x80|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x90|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x90|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x90|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x90|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x90|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x90|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x90|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x90|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x90|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x90|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x90|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|8 local schedule constraints, with independent status per edge|
|+0x90|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xA0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xA0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0xA0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xA0|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0xA0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xA0|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0xA0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xA0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xA0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xA0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0xA0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|5 local schedule constraints, with independent status per edge|
|+0xA0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xB0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xB0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0xB0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xB0|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0xB0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xB0|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0xB0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xB0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xB0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xB0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0xB0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|10 local schedule constraints, with independent status per edge|
|+0xB0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xC0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xC0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0xC0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xC0|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0xC0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xC0|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0xC0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xC0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xC0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xC0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0xC0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|6 local schedule constraints, with independent status per edge|
|+0xC0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xD0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xD0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0xD0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xD0|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0xD0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xD0|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0xD0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xD0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xD0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xD0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0xD0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|12 local schedule constraints, with independent status per edge|
|+0xD0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xE0|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0xE0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0xE0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0xE0|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0xE0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xE0|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xE0|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0xE0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0xE0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xE0|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xE0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|4 local schedule constraints, with independent status per edge|
|+0xE0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xF0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xF0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0xF0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xF0|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0xF0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xF0|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0xF0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xF0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xF0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xF0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0xF0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|7 local schedule constraints, with independent status per edge|
|+0xF0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x100|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x100|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x100|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x100|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x100|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x100|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x100|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x100|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x100|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x100|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x100|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|14 local schedule constraints, with independent status per edge|
|+0x100|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x110|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x110|operands_registers|UNKNOWN|OPERAND-EFFECTS|Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved|
|+0x110|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x110|region_lane|UNKNOWN|EU-REGION|Non-NF region/channel projections equal; NF operand region mapping unresolved|
|+0x110|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x110|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x110|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x110|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x110|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x110|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x110|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|8 local schedule constraints, with independent status per edge|
|+0x110|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x120|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x120|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x120|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x120|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x120|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x120|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x120|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0x120|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0x120|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x120|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x120|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|4 local schedule constraints, with independent status per edge|
|+0x120|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x130|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x130|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x130|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x130|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x130|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x130|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x130|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x130|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x130|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x130|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x130|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x130|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x140|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x140|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x140|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x140|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x140|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x140|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x140|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x140|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x140|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x140|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x140|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x140|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x148|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x148|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x148|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x148|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x148|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x148|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x148|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x148|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x148|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x148|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x148|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x148|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x150|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x150|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x150|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x150|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x150|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x150|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x150|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x150|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x150|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x150|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x150|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x150|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x158|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x158|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x158|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x158|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x158|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x158|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x158|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x158|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x158|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x158|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x158|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x158|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x168|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x168|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x168|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x168|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x168|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x168|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x168|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0x168|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0x168|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x168|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x168|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|4 local schedule constraints, with independent status per edge|
|+0x168|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x178|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x178|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x178|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x178|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x178|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x178|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x178|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x178|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x178|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x178|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x178|swsb_sbid|UNKNOWN|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0x178|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x188|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x188|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x188|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x188|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x188|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x188|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x188|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x188|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x188|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x188|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x188|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x188|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x198|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x198|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x198|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x198|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x198|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x198|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x198|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x198|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x198|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x198|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x198|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x198|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x1A8|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x1A8|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x1A8|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=16, target=16|
|+0x1A8|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x1A8|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x1A8|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x1A8|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0x1A8|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0x1A8|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x1A8|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x1A8|swsb_sbid|UNKNOWN|GEN12-SWSB|6 local schedule constraints, with independent status per edge|
|+0x1A8|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|

## 可复核机器工件

- `runs/verification-final-026/clean-a/ir/outputs/PS-KP1-source.json` 与 candidate：原 bytes、访问集合、未知、工具身份。
- `runs/verification-final-026/clean-a/ir/messages/PS-KP1-{source,candidate}.json`：所有 SEND 合同。
- `runs/verification-final-026/clean-a/dependency/graphs/PS-KP1-{source,candidate}.json`：完整保守 hazard 图。
- `runs/verification-final-026/clean-a/validator/outputs/PS-KP1-comparison.json`：每层源/目标原码、偏移、规则、必要前提、修复与来源。
- `runs/verification-final-026/clean-a/validator/outputs/PS-KP1-schedule.json`：每条等待约束及状态。
