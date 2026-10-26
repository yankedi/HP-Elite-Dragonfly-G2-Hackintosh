# PS0：真实源与 Gen12 候选逐程序审查

源：152B／11 条，EU 窗口 `+0x40`。
源 SHA256 `15e332f4f3fba0c2f20b781d78f36f29ebd4e65de02d5873de2b36aa1145e370`；候选 SHA256 `146d58968884e2b4f89bc2c89b7665156953ae491165288b8e4cf816aa3cb71f`。

## 结论和边界

十二层逐项结果：`{'COUNTEREXAMPLE': 0, 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS': 86, 'UNKNOWN': 46}`。目标调度约束：`{'COUNTEREXAMPLE': 0, 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS': 15, 'UNKNOWN': 1}`。
STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS 仅限该字段/约束及所列假设，不代表完整指令等价。UNKNOWN 保留来源与影响。硬件认证始终为 false。

## 指令对应与十二层状态

映射来自被冻结候选及历史布局见证，并用真实 framing 验证全覆盖。它是对应假设，等价性由各层独立检查。额外 SYNC/一对多范围可表达；多 ALU 组合缺证明时返回 UNKNOWN。

|源偏移|EU窗口|源编码|候选范围|opcode|结果 C / X / U|
|---|---|---|---|---|---|
|+0x0|+0x40|`5b0060001cc000200146200704040001`|+0x0|mad|5 / 0 / 7|
|+0x10|+0x50|`01800000041e003e0000000000000000`|+0x10|mov|5 / 0 / 7|
|+0x20|+0x60|`5b0060000c4800003300220706040801`|+0x20|mad|6 / 0 / 6|
|+0x30|+0x70|`5b0060001cc00020014e200704042001`|+0x30|mad|6 / 0 / 6|
|+0x40|+0x80|`5b0060000c48007b3300220706042801`|+0x40|mad|6 / 0 / 6|
|+0x50|+0x90|`3300600238b1a7000100000001004202`|+0x50|sends|8 / 0 / 4|
|+0x60|+0xA0|`40006080284be02f00018d4e0000803f`|+0x60|add|10 / 0 / 2|
|+0x70|+0xB0|`010b0120077c0500`|+0x70|mov|11 / 0 / 1|
|+0x78|+0xB8|`010b0120077d0600`|+0x78|mov|11 / 0 / 1|
|+0x80|+0xC0|`010b0120077e0700`|+0x80|mov|11 / 0 / 1|
|+0x88|+0xC8|`3400600500000000800f000000140388`|+0x88|sendsc|7 / 0 / 5|

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
|+0x50|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x50|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x50|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x50|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x50|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x50|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x50|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0x50|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0x50|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x50|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x50|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|2 local schedule constraints, with independent status per edge|
|+0x50|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x60|opcode_math|UNKNOWN|OPCODE-CORRESPONDENCE|Opcode projection preserved; numeric/FP-mode equivalence unresolved|
|+0x60|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x60|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x60|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x60|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x60|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x60|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x60|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x60|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x60|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x60|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x60|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x70|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x70|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x70|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x70|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x70|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x70|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x70|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x70|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x70|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x70|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x70|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x70|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
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
|+0x78|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x78|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x80|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x80|operands_registers|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPERAND-EFFECTS|Decoded register/type/modifier/value projection equal|
|+0x80|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x80|region_lane|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-REGION|Region/channel projections equal|
|+0x80|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x80|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x80|send_message|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x80|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|NO-SEND-EFFECT|Neither instruction is a SEND|
|+0x80|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x80|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x80|swsb_sbid|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GEN12-SWSB|1 local schedule constraints, with independent status per edge|
|+0x80|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|
|+0x88|opcode_math|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|OPCODE-CORRESPONDENCE|Opcode projection preserved within decoded move/carrier subset|
|+0x88|operands_registers|UNKNOWN|OPERAND-EFFECTS|Special/debug effect or message carrier needs a separate contract|
|+0x88|execution_size|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EXECUTION-SIZE|source=8, target=8|
|+0x88|region_lane|UNKNOWN|EU-REGION|Message/special effect region requires its own contract|
|+0x88|predicate_mask|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|MASK-PREDICATE|Decoded mask/predicate/flag-control projections equal|
|+0x88|accumulator_nf|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EU-ACC-NF|No accumulator/NF effect in the modeled instruction|
|+0x88|send_message|UNKNOWN|SEND-GENERATION-CONTRACT|Carrier and decoded fields compared; complete per-generation message/resource semantics not proved|
|+0x88|payload_response|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|SEND-CARRIER|Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown|
|+0x88|eot|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|EOT-FRAMING|EOT flag/position preserved; completion semantics reviewed independently|
|+0x88|register_dependency|STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS|GRAPH-CORRESPONDENCE|Local access projection preserved; graph-level schedule coverage is reported separately|
|+0x88|swsb_sbid|UNKNOWN|GEN12-SWSB|5 local schedule constraints, with independent status per edge|
|+0x88|resource_thread_payload_abi|UNKNOWN|MISSING-LIVE-RESOURCE-STATE|Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness|

## 可复核机器工件

- `runs/verification-final-026/clean-a/ir/outputs/PS0-source.json` 与 candidate：原 bytes、访问集合、未知、工具身份。
- `runs/verification-final-026/clean-a/ir/messages/PS0-{source,candidate}.json`：所有 SEND 合同。
- `runs/verification-final-026/clean-a/dependency/graphs/PS0-{source,candidate}.json`：完整保守 hazard 图。
- `runs/verification-final-026/clean-a/validator/outputs/PS0-comparison.json`：每层源/目标原码、偏移、规则、必要前提、修复与来源。
- `runs/verification-final-026/clean-a/validator/outputs/PS0-schedule.json`：每条等待约束及状态。
