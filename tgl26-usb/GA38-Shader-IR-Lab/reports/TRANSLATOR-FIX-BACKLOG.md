# GA3.9：Translator 修复与证明任务列表

本表区分实际候选反例、离线可验证的字段/调度修复与当前缺失的证明。变异负例只验证校验器，不被计作原候选错误。所有偏移均为各程序内字节偏移，EU 窗口绝对范围另列。

## P0：实际候选确定反例

当前已建模字段没有原候选的确定 COUNTEREXAMPLE。现有候选的不可信点是下面可精确定位、尚未完成的语义/ABI/调度证明；不得把测试 mutant 或 UNKNOWN 改写成已证实候选错误。

## P1：CPU 离线可推进的精确证明/修复

|程序|实际源偏移|任务|独立验收|
|---|---|---|---|
|PS0|+0x0, +0x20, +0x30, +0x40|NF→GRF 替换：补精度、舍入、掩码与临时 GRF 活跃区间证明；必要时拒绝该转换|固定规范规则＋独立数值等义 oracle；随机 float 仅辅助|
|PS0|+0x10|Debug/Switch→null MOV：明确删改 ARF 写入/线程切换提示的可观察性前提|按准确代际规范作消除许可或保持 UNKNOWN；无证据不称语义等价|
|PS-KP1|+0x0, +0x20, +0x30, +0x40, +0x50, +0x60, +0x70, +0x80, +0x90, +0xA0, +0xB0, +0xC0, +0xD0, +0xF0, +0x100, +0x110|NF→GRF 替换：补精度、舍入、掩码与临时 GRF 活跃区间证明；必要时拒绝该转换|固定规范规则＋独立数值等义 oracle；随机 float 仅辅助|
|PS-KP1|+0x10|Debug/Switch→null MOV：明确删改 ARF 写入/线程切换提示的可观察性前提|按准确代际规范作消除许可或保持 UNKNOWN；无证据不称语义等价|
|PS-KP2|+0x0, +0x20, +0x30, +0x40, +0x50, +0x60, +0x70, +0x80|NF→GRF 替换：补精度、舍入、掩码与临时 GRF 活跃区间证明；必要时拒绝该转换|固定规范规则＋独立数值等义 oracle；随机 float 仅辅助|
|PS-KP2|+0x10|Debug/Switch→null MOV：明确删改 ARF 写入/线程切换提示的可观察性前提|按准确代际规范作消除许可或保持 UNKNOWN；无证据不称语义等价|
|VS|+0x0, +0x20, +0x28, +0xD8|ACC 显式/隐式读写：定义内部区域与 MUL/MAC 融合/精度合同|独立 ACC 依赖 oracle 与精度规则；不能按 GRF 物理大小猜测|
|VS|+0xF0|Debug/Switch→null MOV：明确删改 ARF 写入/线程切换提示的可观察性前提|按准确代际规范作消除许可或保持 UNKNOWN；无证据不称语义等价|

## P2：SEND Descriptor 与 payload ABI

|程序|源/目标偏移|消息|最小后续任务|
|---|---|---|---|
|PS0|+0x50|SAMPLER|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|PS0|+0x88|RENDER_TARGET|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|PS-KP1|+0xE0|SAMPLER|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|PS-KP1|+0x120|SAMPLER|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|PS-KP1|+0x168|RENDER_TARGET|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|PS-KP1|+0x1A8|RENDER_TARGET|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|PS-KP2|+0x90|SAMPLER|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|PS-KP2|+0xC8|RENDER_TARGET|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|VS|+0x100|URB|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|
|VS|+0x110|URB|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|

## P3：调度、EOT 与未来独立证据

对每份 `*-schedule.json` 中 UNKNOWN_SCHEDULING_SEMANTICS 的实际 producer/consumer offset，先补精确单流水线、token source/destination wait、无 response SEND 与 EOT 规则，再决定是否需要插入等待。保守 hazard 图含传递边，不能把每条旧写覆盖边都当真实 reaching-value 依赖。

真实 Surface/Binding Table/Sampler/URB/RT/dispatch payload 身份和运行态资源有效性属于后续独立证据缺口。本轮不会通过假设 heap 一定有效消除 UNKNOWN。

下一阶段优先 CPU 离线可校验修复与可拒绝证明缺口；不提前改上游真实运行路径或部署。Metal 加速仍需要完整命令状态、资源/映射同步、调度及用户态驱动集成。

### 实际未决调度位置（逐规则去重）

|程序|producer→consumer（目标偏移）|规则|最小后续任务|
|---|---|---|---|
|PS0|? → +0x88|EOT-MESSAGE-SPECIFIC-COMPLETION|EOT does not by itself prove global side-effect visibility; exact message termination rules unresolved|
|PS-KP1|+0x168 → +0x178|NULL-RESPONSE-DST-WAIT|No-response SEND destination-wait completion is not established by the pinned specification|
|PS-KP1|+0x168 → +0x1A8|SBID-REUSE-SYNC-UNPROVEN|Explicit completion missing; IGA implements implicit synchronization on SBID reuse, but exact hardware rule is not independently established|
|PS-KP1|? → +0x1A8|EOT-MESSAGE-SPECIFIC-COMPLETION|EOT does not by itself prove global side-effect visibility; exact message termination rules unresolved|
|PS-KP2|? → +0xC8|EOT-MESSAGE-SPECIFIC-COMPLETION|EOT does not by itself prove global side-effect visibility; exact message termination rules unresolved|
|VS|? → +0x110|EOT-MESSAGE-SPECIFIC-COMPLETION|EOT does not by itself prove global side-effect visibility; exact message termination rules unresolved|
|VS|+0x0 → +0x20|SYMBOLIC-DEPENDENCY|Symbolic register footprint/effect has no exact schedule proof|
|VS|+0x0 → +0x28|SYMBOLIC-DEPENDENCY|Symbolic register footprint/effect has no exact schedule proof|
|VS|+0x20 → +0x28|SYMBOLIC-DEPENDENCY|Symbolic register footprint/effect has no exact schedule proof|
|VS|+0x0 → +0xD8|SYMBOLIC-DEPENDENCY|Symbolic register footprint/effect has no exact schedule proof|
|VS|+0x28 → +0xD8|SYMBOLIC-DEPENDENCY|Symbolic register footprint/effect has no exact schedule proof|
