# 默认拒绝策略

`policy.py` 是封闭规则注册表：没有“未知指令原样复制”的回退。完整程序准入必须有数值、scratch、消息、资源、调度、Debug、EOT 和映射证明；当前四真实程序均有未证义务，必须拒绝。

唯一拟接受的有限转换域是**孤立、直接 GRF、同整数类型、不带 modifier/predicate/saturate/特殊 options 的 MOV 位拷贝**。它不申请临时 GRF，不调用 NF 数值模型。codegen 仍须经过固定 IGA 目标译码、字段核对、完整机器码 roundtrip 和精确 offset mapping；该域不能被宣传为完整 Shader。浮点 MOV/ADD/MUL 也不自动继承旧原型的 roundtrip 认证为严格数值证明。

`preflight` 收集所有真实节点的义务，保持 GA38 原948项状态不变。新的 Strict 拒绝统计与旧 UNKNOWN 不是同一计量单位，不得将拒绝计作“UNKNOWN 已消除”。Research 输出必须带 NOT_FOR_HARDWARE，不属于 Strict 接受结果。
