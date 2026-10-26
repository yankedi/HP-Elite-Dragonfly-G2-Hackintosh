# 下一实验的信息价值（未授权执行）

|方案|可关闭未知|当前成熟度|是否改GPU命令|恢复路径与风险|失败后的证据|额外前提|
|---|---|---|---|---|---|---|
|GA3.3b仅首拒页|record0具体门禁/物理页/翻译阶段|历史已构建未部署；不能替代新fault采样|否|既有捕获仍有MMIO/物理读，历史门禁不变；不代表零风险|首失败归因，未必得到Gen12fault|用户审批、匹配历史构建及现场恢复；不能无授权重跑|
|GA3.4 Fault-only|真实valid/type/engine/source/VA及clear/reset时间关联|离线核心可测试；**真实接入当前阻塞**|否|新增只读访问也需GT FW/ACK/电源/锁序；不应改reset行为|若有明确captureStatus可区分未取得/无fault/有效fault；未知时序仍不能排除fault|exact25G83 binary、真实采样点与互斥安全审计；独立授权|
|未来Command Normalization|明确命令格式差异是否影响首个故障|有状态IR与局部候选；资源/继承/部分规范未证|是|改变命令长度/布局/状态，可能使后续故障改变；风险高于只读|需前后fault/state/严格单变量关联，否则只看到不同hang|完整资源引用/relocation、语义证明、可回退介质、用户独立许可|
|未来Shader Translation|EU ISA不等义是否为有效执行路径故障|历史31隔离单位，不是whole-shader；NF/acc/SEND/SWSB未证|是（shader）|消息/调度/资源访问可能失控，且前序command问题未解决|若只看GUI或hang变化，因果仍不足|先完成命令兼容、所有启用入口/消息/调度证明与同次fault基线；独立授权|

## 推荐顺序

**信息方向优先Fault-only，只读优先；当前尚不具备实机审批条件。** 先补exact25G83离线binary与锁/域/时序证明，之后才有资格提交一份只读采样实验申请。不能因为GA3.3b更容易启动，就把“首拒页”当本轮真实fault未知的替代答案。

命令候选A/B仅作离线研究，不从中指定一个实机版；两候选的shader可见XP行为必须单独核验。若未来实际fault指向batch页/command处理，先收敛command；若指向shader/surface，也仍需allocation generation与state/payload证据，不凭地址近似归因。
