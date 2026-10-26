# 四真实 Shader 状态

来源为同一99648B捕获的有效Record1。当前完整集成回放为`candidates/delivery/final-I-072`及`final-J-074`，强比较`final-determinism-075`，已在冻结消息005源码和发布053后重生。各次含baseline、Strict、Research、semantic bundle、同单位diff及metrics，076额外逐项核报告/原码/计数，最终来源绑定见state。所有旧次保留为中间观察。完整源/目标字段和raw bytes在对应IR及合同中。

|Shader|源/目标bytes|源/目标条数|NF / 普通ACC相关节点|scratch|Strict|Research|
|---|---:|---:|---:|---|---|---|
|PS0|152 / 152|11 / 11|4 NF|r122|UNKNOWN_REJECTED|已重生+IGA解码+exact roundtrip+GA38再验证|
|PS-KP1|440 / 440|29 / 29|16 NF|r107|UNKNOWN_REJECTED|同上；关键链完成语义未证|
|PS-KP2|216 / 216|15 / 15|8 NF|r117|UNKNOWN_REJECTED|同上|
|VS|288 / 288|24 / 24|4普通FACC，非NF|无上述NF scratch|UNKNOWN_REJECTED|同上；URB/隐式ACC未证|

总1096B→1096B、79→79条，研究候选扩张率1.0；与原归档候选逐字节一致，不新增wait。三scratch已知源投影无直接占用碰撞，但外部ABI/目标GRF配额未证。最大显式GRF分别127/126/126/127未变，不等于运行时可分配资源已证明。

## 全部程序身份（SHA-256）

|Shader|Gen11源|Gen12研究目标|
|---|---|---|
|PS0|`15e332f4f3fba0c2f20b781d78f36f29ebd4e65de02d5873de2b36aa1145e370`|`146d58968884e2b4f89bc2c89b7665156953ae491165288b8e4cf816aa3cb71f`|
|PS-KP1|`d6b32c1deba1538772a0a9fdb84408223760197813554cb96810ed634b42dbc1`|`4cced77c4538b3243a4493a9d921b9c16fa534ccffd4c363bb0b686608ceabbb`|
|PS-KP2|`64ba5d35a91ff7c47aad2c44d3bc3e1888b304e061f0e6c523c9bcb0a97af2a7`|`9f8b2f8e944a8fa372c79f5acfe5a1458cd8dcc91978d91625c0caa864f34996`|
|VS|`b02abaacf5a9f5fead7f0abb47a1d372bb0cafb5c5ed64b52a5912d18485d182`|`5ff3799ba005d337511f2b117572862d89f7d4d0088a4774f07aa82cfc5c6f91`|

## 拒绝原因与覆盖

- 所有79源节点均有准入义务，无静默跳unsupported；全程序EOT/ABI定理尚未实现，完整Strict接受0/4。
- PS的28个NF和VS的4个普通ACC源节点均有携证拒绝；scratch活跃区间/byte干涉图、执行掩码/隐式状态及原码逐节点保留。
- Debug/Switch：三个PS `0x10`、VS `0xF0`；显式DBG值无人后读，仍不证明其它ARF或Switch效果不可观察。
- 十条SEND：PS0 `0x50/0x88`；KP1 `0xE0/0x120/0x168/0x1A8`；KP2 `0x90/0xC8`；VS `0x100/0x110`。字段/资源/完成事件是独立义务。
- KP1 `0x168→0x178→0x1A8`始终保留null-response `.dst`、token复用和EOT副作用UNKNOWN，没有猜测性SYNC。

每条SEND的源/目标机器码、desc/exDesc、SFID、payload及offset在`../messages/outputs/contracts-all.json`，最终CURRENT绑定消息005；I/J bundle已按该源码重新生成。相同offset布局仍是显式假设，不是语义证明；位移映射需明确hash-bound witness。

## 测量边界

最终072集成CPU生成+验证观察耗时：PS0约0.163s、KP1 0.510s、KP2 0.219s、VS 0.231s；含携证合同、生成、接口校验和往返，不是GPU性能或跨环境稳定基准。074独立记录另一份耗时；确定性比较仅排除指定路径的耗时键，不排除数值/字段/状态差异。历史044/054/066等测量保留于原receipt，不充当最终版本数值。

`metrics-029`曾因IGA省略r0索引在指标脚本触发TypeError；初失败保留。脚本按IGA省略字段的r0约定修正，`metrics-030`成功。没有改Shader或预期结果。

**所有完整目标均是NOT_FOR_HARDWARE研究候选；没有全程序等价或Metal成功结论。**
