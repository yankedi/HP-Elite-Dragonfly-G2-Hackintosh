# GA4.0 唯一主线：完全离线最小 Draw 合同管线

**本文件仅规划，本轮未实施GA4.0。** 主线为组合GA3.9严格Shader子集、GA3.4 Command Stream Normalizer与显式资源合同。第一验收里程碑是可靠的跨组件拒绝闭环；只有每个必要合同闭合后，才允许在CPU模型内形成最小Draw的语义结果。

GA39本轮的最终独审与seal状态以其`state.json`、`FINAL-REPORT.md`及实际manifest回执为准；本规划不提前假定GA39已封存。

## 1. 哪些Shader能进入

|输入|当前准入|原因|
|---|---|---|
|真实PS0 / KP1 / KP2|拒绝|NF→F scratch、Debug/Switch、SEND资源/payload/完成规则尚未证明|
|真实VS|拒绝|普通FACC的跨代隐式状态/区域、Debug/Switch、URB与EOT合同未闭合|
|GA39有限整数MOV孤立片段|只可作为寄存器传递组件|没有EOT、dispatch/payload和消息合同，不能冒充完整VS/PS|
|未来完整有限Shader|待新的离线规范/证明工件|需要独立证明整个程序及受限输出消息，不能拼接当前31单位或MOV片段作默认成功|

因此当前**没有已严格接受的完整真实Shader可做一个成功Draw**。这一事实必须进入GA40默认门禁，不能通过Research产物绕过。

## 2. 命令状态从哪里来

GA34 `FINAL-REPORT.md`和`track-a/state-ir.json`固定原166包。56个已验证包仅55纯零NOOP与canonicalEND；5个明确格式问题、105UNKNOWN仍在。真实流StrictShadow在未证明PIPE_CONTROL处拒绝。Draw A/B格式研究候选不能当作语义已证的批。

GA40可读取GA34状态IR和Normalizer的严格接口，保留每field的KNOWN/UNKNOWN、ModifyEnable及继承来源。任何需要但未捕获的继承状态都保留symbolic。不能把SBA中0值当原始heap基址，不能将格式合法替代命令语义证明。

## 3. 缺失Heap与Thread Payload的表达

使用Typed Symbolic Resource Contract：资源类型、代际、被引用字段、allocation身份/generation/lifetime、允许的byte范围、布局/格式/stride/aux/compression、寻址空间、启用条件、初始化与可见性、消息payload ABI。缺值为UNKNOWN，不分配一个假heap来满足真实捕获的缺口。

必须补齐Surface State、Binding Table、Sampler State、URB配置/条目与handle、Render Target、VS/PS dispatch及thread payload、vertex/constant数据与命令状态的一致性；一个descriptor DWORD或离线VA不是实际资源身份。

若将来使用**单独标注的CPU合成样本**验证合同求解器，必须与真实捕获分开：只证明模型和失败路径，不证明真实heap存在，更不替代真实数据源。

## 4. CPU可以先验证什么

1. 命令framing/原extent、field masks及已建模限制，不重新解释畸形源执行语义。
2. Shader raw framing、允许的有限逐lane位传递、显式边界映射和寄存器may-live投影。
3. 显式资源区间、symbolic约束相容性及UNKNOWN传播；缺输入立即拒绝。
4. 已有证据范围内的SEND载体字段和有限SWSB约束；硬件未定规则仍UNKNOWN。
5. 组合前后的身份、引用闭包、EOT和全程序证明义务完整性；无法闭合则无可执行交付。

数值NF模型、真实副作用时序和有效资源执行不能由CPU自洽测试补成硬件事实。

## 5. 跨组件 Source→Target 关联

关联键使用捕获完整SHA + Record1身份 + 命令源byte range/occurrence + kernel窗口入口 + Shader源SHA/offset + 目标SHA/范围 + 消息offset + 资源字段路径。分支/重定位与一源多目标映射分别核验；传递地址只有符号重定位，不映射到真实GPU。

每条组合边必须说明它来自原始bytes、固定规范、明确假设或仍未知。输出附全部输入与实现身份，不能由近似文件名或同一VA推断同一allocation。

## 6. 实施顺序与停止条件

唯一顺序：

1. 固定GA34/GA39只读接口、输入manifest和同口径证明义务schema。
2. 建立命令→Shader→消息→资源的符号引用闭包及fail-closed组合器；以真实四程序**预期拒绝**为首个里程碑。
3. 补证一个完整受限Shader及消息/dispatch ABI，再选能由严格Normalizer表示的最小命令状态；规范仍不足的项继续拒绝。
4. 所有资源前提能由新离线证据满足后，运行独立CPU语义模型和正负例，完成跨组件独立审计及确定性封存。

新真实heap/payload/运行态身份资料、NF narrowing、null-response/SBID硬件完成与EOT规则未获得前，不能承诺第3/4步成功，也不能申请上机。获取新实机数据需要用户另行明确授权，本计划不批准采集或部署。

## 7. 失败不输出可部署残缺工件

组合器应先完成全部验证和引用闭包，再事务发布**离线模型结果**。拒绝只发布原始输入身份、精确缺口和诊断，禁止success标志、部署包或已验证可执行bytes。Research另需独立显式开关、NOT_FOR_HARDWARE与完整未证列表，不能成为Strict fallback。故障注入必须覆盖每个组件失败、mapping遗漏、资源伪已知、断写、异常和超时。

## 8. 距离真实Metal的独立组件

仍缺适配当前25G83的用户/内核驱动集成、完整command/pipeline语义、dispatch/资源heap与缓存一致性、GPU虚拟内存/驻留/生命周期同步、render/aux/compression布局、编译器完整ISA与消息协议、跨线程/engine同步与复位恢复、窗口系统/显示/功耗路径和实际硬件证据。离线最小Draw模型不等于这些系统已工作，也不证明Metal加速。

**GA40离线集成当前可规划为PARTIAL；READY_FOR_HARDWARE_APPROVAL=NO。**
