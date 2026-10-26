# 加速主线重新评估：选择四个真实 Shader 的消息／依赖闭环

**唯一推荐GA3.8核心任务：四个真实Shader的全程序消息／依赖IR与Gen12候选调度一致性校验器。** 属于A方向的可验收前置工程；不是立即承诺四shader完整等义翻译，更不以Fault研究为启动条件。具体实现计划见`GA38-TECHNICAL-PLAN.md`。本轮没有启动GA38代码。

## 已核对的证据与当前缺口

* 四指定入口合计1096B、79条ICL指令，PS0=152B/11、KP1=440B/29、KP2=216B/15、VS=288B/24，都直线至EOT、无branch。原31隔离单位只到字段/编码往返，不能拼成程序。
* 固定上游四份Gen12输出可解码/validator通过/再编码同bytes；仍将`acc0:nf`换`r122:f`、debug ARF `{Switch}`换`mov null,0`。消息和SWSB只有编码，不是等价性证明。继续跑同样的roundtrip无新的工程价值。
* 命令166包中56只是55NOOP+END；5明确格式矛盾已有Null/Draw研究，105UNKNOWN、33heap引用和2继承缺口，完整Shadow在PIPE_CONTROL就拒绝。
* Batch/EU窗口存在；Surface/Binding/Sampler/RT/aux-CCS、vertex/constant与thread payload实内容、原始PTE和CSB序列不足。GA35的**准确25G83KC已取得并验证**，不要继续引用GA34“未取得binary”的历史状态。当前缺的是patched livebytes、receiver/owner及完整资源语义。
* 整99648B双record THAG文件SHA为`1622ecc2…`，不是record1单独的hash。历史有效采集不因源码CAS缺陷被否定。PIPE_CONTROL stall是停止位置，不是已证首因。

163项精确输入路径、sizes、SHA、schema与来源阶段见`evidence/INPUTS.json`；`evidence/CORRECTION-NOTE.md`保留历史假设A–F与本轮候选A–F混淆等纠正。以下使用用户本轮A–F定义。

## A–F × 八个维度

|候选|距离当前代码|可离线证明|额外数据|是否依赖新Fault|难度|内存安全风险|对真正加速的贡献|较小中间成果|
|---|---|---|---|---|---|---|---|---|
|A 完整四Shader语义翻译|已有31隔离单位/79原指令及4上游候选；缺整程序IR、精度/消息/依赖|原bytes framing、静态GRF/acc def-use、descriptor字段、条件化消息契约、调度hazard约束；不自动证明NF数值等义|现有原bytes/IGA/Mesa/PRM足够启动；具体payload/URB/RT ABI仍需额外证据|静态阶段不依赖；上机因果仍不能跳过安全数据|高，但可按4个实际直线程序有界|宿主parser需边界/alias保护；未来变长shader、GRF占用/缓存写回风险高|消除确定的ISA兼容障碍之一；单独不会让WindowServer/Metal工作|**本轮首选：消息/依赖IR＋候选校验器**|
|B Gen11→12命令状态转换|已有stateIR/typedreloc/Null/Draw；完整Shadow仍拒绝|5矛盾的格式与条件编码、继承UNKNOWN、可证明子集layout|33heap引用、MOCS/stepping、完整启用状态/地址归属不足|格式阶段不依赖；具体执行内存失败归因有帮助|高，跨状态族多|错reloc/未知继承/预取边界可指向任意GPU地址|是必要命令前端适配，但不能弥补Shader或resource ABI|新增一个受限状态族；5格式问题已研究，不重做它作GA38主目标|
|C Surface/Binding/Sampler/URB/RT/CCS资源ABI|有packet字段/PRM差异，缺真实heap|固定格式bit对照、抽象资源契约/布局约束；不能认证未捕获实例|启用资源raw heap、pitch/tile/view/format/aux/CCS、寿命/generation、payload|规范研究不依赖；Fault不等于自动补齐资源|很高|pitch/size/CCS/地址空间错误可越界或损坏内存|决定渲染结果与安全性，是完整加速关键障碍|选择一个已知资源对象的双代规范图；当前尚无足够真实对象闭环|
|D 修复复用上游Translator|固定1010490d…与Mesa86333827…可复用编码器；不是可信语义oracle|在新IR下逐项检测/反证NF/acc、debug替换、SEND/SWSB；有证子集再修|同A语义规范，不能靠validator替代；更广输入需修前端OOB/错误validator指针|不依赖新Fault|中高；借助后端降编码成本|原前端有8B剩余却读16B等；首4KiB cache、半写无回滚不可沿用|是A的实现工具，不应作为未经校验的整体运行时方案|先用IR校验现有4候选，输出实际offset反例，再修一条有证规则|
|E 已知简单负载原生TGL pipeline|没有完整macOS提交/资源/同步栈；Linux可作为规范参考|离线构造规范化简单pipeline与资源预算；不验证Apple队列下运行|清楚的上下文/提交ABI、分配映射、MOCS/WA、native shader/payload、fence|简单pipeline可不依赖旧hangFault；仍要独立实机准入|很高，跨越多个当前缺口|新command/resource/上下文/同步路径风险集中|未来能隔离Apple跨代翻译，但离Metal整栈仍远|只离线建一个native参考状态图；对现有四shader的直接增益低|
|F 原生TigerLake驱动/用户态编译器适配|现有主要是ICL兼容研究；macOS driver/MetalUMD不是可直接替换Linuxi915/Mesa|公开参考架构、离线shader编译、ABI差异；不证明系统二进制兼容|IOKit/IOAccel/Metal用户态ABI、scheduler/GGTT/PPGTT、资源管理、显示/电源、编译器集成|架构研究不依赖旧Fault；全栈验证需新数据/授权|极高，长期多阶段项目|内核映射/调度/同步/资源寿命风险最高|最终潜力大，当前不适合作最小GA38闭环|单个compiler前端/IR适配只能作远期子项目|

## 为什么不是“先把Fault做到可上机”

GA36/37已将最后的读取安全前提收敛为外部证据缺口，继续增加mock或无目标反汇编不会认证live owner/ACK/reset排他。四Shader静态语义任务有真实完整输入，可立即写代码并用反例推动兼容层。Fault有助于后续定位，却不是理解descriptor位布局/数据依赖的必要输入。

也不把“无Fault”当作许可提交Shader：离线IR完成不产生部署批准，当前`READ_SAFE=BLOCKED`与`READY_FOR_HARDWARE_APPROVAL=NO`保持。
