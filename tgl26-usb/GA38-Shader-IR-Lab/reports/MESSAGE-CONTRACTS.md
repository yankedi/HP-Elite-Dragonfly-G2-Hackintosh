# 全部实际 SEND 合同

四源与四候选各 10 条 SEND。消息族只有 SAMPLER、RENDER_TARGET、URB；原 bytes、descriptor、carrier 与资源/完成未知各自独立保存。

|程序/平台|偏移|族/SFID|Descriptor|ExDescriptor|payload0+1 / response (GRF)|Header|EOT|
|---|---|---|---|---|---|---|---|
|PS0 / 11|+0x50|SAMPLER / 2|0x2420001|0x42|1+1 / 4|0|False|
|PS0 / 11|+0x88|RENDER_TARGET / 5|0x8031400|0x25|4+0 / 0|0|True|
|PS0 / 12p1|+0x50|SAMPLER / 2|0x2420001|0x40|1+1 / 4|0|False|
|PS0 / 12p1|+0x88|RENDER_TARGET / 5|0x8031400|0x0|4+0 / 0|0|True|
|PS-KP1 / 11|+0xE0|SAMPLER / 2|0x4840001|0x82|2+2 / 8|0|False|
|PS-KP1 / 11|+0x120|SAMPLER / 2|0x4840001|0x82|2+2 / 8|0|False|
|PS-KP1 / 11|+0x168|RENDER_TARGET / 5|0x10031000|0x5|8+0 / 0|0|False|
|PS-KP1 / 11|+0x1A8|RENDER_TARGET / 5|0x10031800|0x25|8+0 / 0|0|True|
|PS-KP1 / 12p1|+0xE0|SAMPLER / 2|0x4840001|0x80|2+2 / 8|0|False|
|PS-KP1 / 12p1|+0x120|SAMPLER / 2|0x4840001|0x80|2+2 / 8|0|False|
|PS-KP1 / 12p1|+0x168|RENDER_TARGET / 5|0x10031000|0x0|8+0 / 0|0|False|
|PS-KP1 / 12p1|+0x1A8|RENDER_TARGET / 5|0x10031800|0x0|8+0 / 0|0|True|
|PS-KP2 / 11|+0x90|SAMPLER / 2|0x4840001|0x82|2+2 / 8|0|False|
|PS-KP2 / 11|+0xC8|RENDER_TARGET / 5|0x10031000|0x25|8+0 / 0|0|True|
|PS-KP2 / 12p1|+0x90|SAMPLER / 2|0x4840001|0x80|2+2 / 8|0|False|
|PS-KP2 / 12p1|+0xC8|RENDER_TARGET / 5|0x10031000|0x0|8+0 / 0|0|True|
|VS / 11|+0x100|URB / 6|0x2080007|0x206|1+8 / 0|1|False|
|VS / 11|+0x110|URB / 6|0x2080027|0x226|1+8 / 0|1|True|
|VS / 12p1|+0x100|URB / 6|0x2080007|0x200|1+8 / 0|1|False|
|VS / 12p1|+0x110|URB / 6|0x2080027|0x200|1+8 / 0|1|True|

BTI/Sampler 数字是 descriptor 中的编码值，不能由它推断真实 Surface/RT 的身份或有效性。相同 descriptor DWORD 仅能说明编码位值相同；完整消息语义需按代际逐字段证明。

规则与证据索引见 `reference/rules/`；机器合同逐字段有 bit 范围、rule、known/unknown 与资源依赖。
