# VS：真实源与 Gen12 候选逐程序审查

源：288B／24 条，EU 窗口 `+0x3C0`。
源 SHA256 `b02abaacf5a9f5fead7f0abb47a1d372bb0cafb5c5ed64b52a5912d18485d182`；候选 SHA256 `5ff3799ba005d337511f2b117572862d89f7d4d0088a4774f07aa82cfc5c6f91`。

## 结论和边界

十二层逐项结果：`{'COUNTEREXAMPLE': 0, 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS': 215, 'UNKNOWN': 73}`。目标调度约束：`{'COUNTEREXAMPLE': 0, 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS': 23, 'UNKNOWN': 6}`。
STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS 仅限该字段/约束及所列假设，不代表完整指令等价。UNKNOWN 保留来源与影响。硬件认证始终为 false。

## 指令对应与十二层状态

映射来自被冻结候选及历史布局见证，并用真实 framing 验证全覆盖。它是对应假设，等价性由各层独立检查。额外 SYNC/一对多范围可表达；多 ALU 组合缺证明时返回 UNKNOWN。

|源偏移|EU窗口|源编码|候选范围|opcode|结果 C / X / U|
|---|---|---|---|---|---|
|+0x0|+0x3C0|`412b0220e0200204`|+0x0|mul|7 / 0 / 5|
|+0x8|+0x3C8|`414b1620e0760204`|+0x8|mul|9 / 0 / 3|
|+0x10|+0x3D0|`414b1a20e0080204`|+0x10|mul|9 / 0 / 3|
|+0x18|+0x3D8|`414b1e20e0750204`|+0x18|mul|9 / 0 / 3|
|+0x20|+0x3E0|`484b2220e0000205`|+0x20|mac|7 / 0 / 5|
|+0x28|+0x3E8|`5b006000184000203960274005844001`|+0x28|mad|7 / 0 / 5|
|+0x38|+0x3F8|`5b006000084000083980208005844001`|+0x38|mad|10 / 0 / 2|
|+0x48|+0x408|`5b00600008400075395027c005844001`|+0x48|mad|10 / 0 / 2|
|+0x58|+0x418|`01006000284f20210000000000000000`|+0x58|mov|10 / 0 / 2|
|+0x68|+0x428|`01006000284f40210000000000000000`|+0x68|mov|10 / 0 / 2|
|+0x78|+0x438|`01006000284f60210000000000000000`|+0x78|mov|10 / 0 / 2|
|+0x88|+0x448|`01006000284f80210000000000000000`|+0x88|mov|10 / 0 / 2|
|+0x98|+0x458|`010b012007770600`|+0x98|mov|10 / 0 / 2|
|+0xA0|+0x460|`010b012007780700`|+0xA0|mov|10 / 0 / 2|
|+0xA8|+0x468|`01006000284f202f0000000000000000`|+0xA8|mov|10 / 0 / 2|
|+0xB8|+0x478|`01006000284f402f000000000000803f`|+0xB8|mov|10 / 0 / 2|
|+0xC8|+0x488|`010d0120077f0100`|+0xC8|mov|10 / 0 / 2|
|+0xD0|+0x490|`404b6e20070d0003`|+0xD0|add|10 / 0 / 2|
|+0xD8|+0x498|`400b7220070e2003`|+0xD8|add|7 / 0 / 5|
|+0xE0|+0x4A0|`404b7620070f0803`|+0xE0|add|10 / 0 / 2|
|+0xE8|+0x4A8|`404b7a2007107503`|+0xE8|add|10 / 0 / 2|
|+0xF0|+0x4B0|`01800000041e003e0000000000000000`|+0xF0|mov|5 / 0 / 7|
|+0x100|+0x4C0|`33006006109000002800000007000802`|+0x100|sends|8 / 0 / 4|
|+0x110|+0x4D0|`3300600610700700e80f000027000882`|+0x110|sends|7 / 0 / 5|

## 逐层状态与最小修复入口

|源偏移|层|状态|规则|结论/约束|
|---|---|---|---|---|
|+0x0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x0|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x0|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x0|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x0|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x8|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x8|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x8|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x8|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x8|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x8|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x8|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x8|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x8|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x8|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x8|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x8|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x10|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x10|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x10|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x10|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x10|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x10|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x10|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x10|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x10|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x10|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x10|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x10|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x18|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x18|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x18|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x18|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x18|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x18|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x18|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x18|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x18|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x18|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x18|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x18|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x20|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x20|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x20|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x20|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x20|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x20|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x20|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x20|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x20|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x20|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x20|swsb_sbid|UNKNOWN|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x20|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x28|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x28|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x28|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x28|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x28|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x28|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0x28|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x28|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x28|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x28|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0x28|swsb_sbid|UNKNOWN|GEN12-SWSB|3 local schedule constraints, with independent status per edge|
|+0x28|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x38|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x38|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x38|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x38|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x38|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x38|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x38|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x38|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x38|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x38|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x38|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0x38|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x48|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x48|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x48|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x48|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x48|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x48|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x48|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x48|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x48|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x48|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x48|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0x48|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x58|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x58|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x58|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x58|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x58|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x58|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x58|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x58|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x58|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x58|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x58|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x58|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x68|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x68|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x68|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x68|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x68|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x68|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x68|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x68|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x68|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x68|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x68|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x68|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x78|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x78|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x78|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x78|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x78|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x78|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x78|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x78|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x78|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x78|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x78|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x78|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x88|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x88|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x88|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x88|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x88|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x88|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x88|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x88|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x88|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x88|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x88|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x88|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x98|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x98|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x98|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x98|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x98|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x98|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x98|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x98|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x98|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x98|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x98|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0x98|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xA0|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0xA0|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xA0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xA0|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xA0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xA0|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xA0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xA0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xA0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xA0|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xA0|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0xA0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xA8|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0xA8|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xA8|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xA8|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xA8|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xA8|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xA8|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xA8|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xA8|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xA8|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xA8|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0xA8|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xB8|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0xB8|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xB8|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xB8|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xB8|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xB8|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xB8|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xB8|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xB8|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xB8|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xB8|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0xB8|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xC8|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0xC8|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xC8|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xC8|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xC8|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xC8|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xC8|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xC8|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xC8|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xC8|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xC8|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0xC8|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xD0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xD0|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xD0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xD0|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xD0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xD0|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xD0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xD0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xD0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xD0|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xD0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0xD0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xD8|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xD8|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xD8|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xD8|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xD8|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xD8|accumulator_nf|UNKNOWN|EU-ACC-NF|NF/acc internal format, rounding and fusion equivalence not established|
|+0xD8|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xD8|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xD8|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xD8|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0xD8|swsb_sbid|UNKNOWN|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0xD8|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xE0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xE0|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xE0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xE0|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xE0|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xE0|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xE0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xE0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xE0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xE0|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xE0|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0xE0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xE8|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xE8|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0xE8|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0xE8|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0xE8|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0xE8|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xE8|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xE8|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xE8|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xE8|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0xE8|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0xE8|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0xF0|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0xF0|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0xF0|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=1, target=1|
|+0xF0|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0xF0|predicate_mask|UNKNOWN|MASK-PREDICATE|Mask/predicate equal but other execution-control options differ; observability unresolved|
|+0xF0|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0xF0|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xF0|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0xF0|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0xF0|register_dependency|UNKNOWN|GRAPH-CORRESPONDENCE|Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged|
|+0xF0|swsb_sbid|UNKNOWN|GEN12-SWSB|No local schedule constraint was exercised at this offset; no positive schedule-validation claim|
|+0xF0|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x100|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x100|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x100|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x100|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x100|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x100|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x100|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0x100|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0x100|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x100|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x100|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|8 local schedule constraints, with independent status per edge|
|+0x100|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x110|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x110|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x110|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x110|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x110|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x110|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x110|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0x110|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0x110|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x110|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x110|swsb_sbid|UNKNOWN|GEN12-SWSB|6 local schedule constraints, with independent status per edge|
|+0x110|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|

## 可复核机器工件

- `runs/verification-final-026/clean-a/ir/outputs/VS-source.json` 与 candidate：原 bytes、访问集合、未知、工具身份。
- `runs/verification-final-026/clean-a/ir/messages/VS-{source,candidate}.json`：所有 SEND 合同。
- `runs/verification-final-026/clean-a/dependency/graphs/VS-{source,candidate}.json`：完整保守 hazard 图。
- `runs/verification-final-026/clean-a/validator/outputs/VS-comparison.json`：每层源/目标原码、偏移、规则、必要前提、修复与来源。
- `runs/verification-final-026/clean-a/validator/outputs/VS-schedule.json`：每条等待约束及状态。
