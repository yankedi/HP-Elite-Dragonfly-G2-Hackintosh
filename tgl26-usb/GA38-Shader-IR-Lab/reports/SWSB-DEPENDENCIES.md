# SWSB、寄存器与消息完成依赖

执行模型：Xe-LP 单一 in-order ALU 流水线距离等待与显式 SEND token 事件子集。未建模的 pipeline、ACC/NF、外部副作用可见性和 EOT 消息完成规则返回 UNKNOWN。

|程序|checked|counterexample|unknown|
|---|---|---|---|
|PS0|15|0|1|
|PS-KP1|116|0|3|
|PS-KP2|34|0|1|
|VS|23|0|6|

Payload 被消费、response 写回、副作用完成、token 可重用、EOT 安全为五个不同事件。源图的 symbolic 访问不会推定与别的指令独立。distance wait 统计 in-order 指令而不把异步 SEND 当已完成。

本表为程序内有限子集约束；完整事件与每条边的状态见各程序 `*-schedule.json`。独立 mutant 删除等待/提前复用 token 的预期来源与原候选分开保存。
