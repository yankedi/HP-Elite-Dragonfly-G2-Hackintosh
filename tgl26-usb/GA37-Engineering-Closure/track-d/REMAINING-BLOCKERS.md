# 剩余阻塞与最小额外证据

以下是工程交付后的**真实XNU/GPU准入阻塞**。不能因CPU测试通过、raw字节能解析或磁盘KC已认证而删除。

|缺口|当前证据|最小额外证据|阻断对象|
|---|---|---|---|
|目标ThreadCall实现/ABI|目标12377.161.14~5，已查tag只提供121.6参考；enter1/cancel_wait/free语义已固定|匹配目标源码或有界stock指令契约核验，并证明真实回调/参数/合并引用的调用方协议|真实scheduler适配及卸载|
|live patched bytes/trampoline/HookABI|25G83 stockKC `fbab2d48…`及模块metadata已核对；不是认证Lilu/Weg改写后的内存|完整被覆盖指令、trampoline与调用约定、实际receiver/selector、代码/对象寿命的认证证据|任何新Hook/寄存器读取|
|RuntimePower与GT owner|静态请求/计数/锁路径PARTIAL，7含GT；锁释放不证明引用必有效或必无效|同一次调用持有active-power/GT生命周期owner、正确域、覆盖采样/退出所有分支的引用证明|READ_SAFE|
|same-request ACK|normal return/软件count/未panic不等于本次硬件ACK|关联本次请求的GT ACK后置条件，含earlyreturn/转发/interrupt路径及超时恢复不破坏原流程|READ_SAFE|
|MMIO地址/映射/读副作用|寄存器offset/GT域有固定参考，实际映射寿命未知|准确bar/mapping对象和lifetime、读本身安全、序列化与上下文约束|READ_SAFE|
|reset/clear/teardown共同排他|Apple24函数静态timeline不足以证明全入口排他；旧4094不等同CEC4|覆盖所有并发reset/clear/sleep/stop/free的共同owner或可证边界，确保新增读取不破坏恢复路径|READ_SAFE|
|设备tuple/latch/ABA|CEC4/CEB8/CEBC三读无设备一致性证明；同CEC4两次仍可ABA；GA36实际torn-tuple mock反例|设备latch/hold/clear代际规范及独立验证，不靠observer自报epoch|FAULT_DATA_COHERENT|
|context/PML4/engine/allocation身份|v1缺字段，v2可以表达unknown；caller claim不自认证|同boot/hang/context及allocation generation/lifetime的独立来源；GT-globalengine来源规范|有效FaultVA关联与根因|
|完整XNU捕获链|旧producer/ThreadCall/同步vnode IO与实际Hook未整合；本轮宿主Session不在内核|安全上下文中的固定容量producer、queue/active owner、入口撤销与code-unloadfence、返回式IO/消费者契约|CAPTURE_PIPELINE真实系统|
|持久性环境|本地主机POSIX文件/目录sync、进程crash注入通过；不是APFS或掉电试验|未来目标持久化消费者/文件系统/API约束及必要实测；不直接移植复杂内核vnode事务|内核/目标OS持久化认证|
|完整图形兼容|四shader编码不等义、5命令格式矛盾已证；105包UNKNOWN及资源缺|GA38消息/依赖IR起步；后续整程序等义、命令状态、资源ABI/映射/同步/用户态完整链|Metal/WindowServer加速|

**本轮不请求macOS SSH、不需要用户手工现场命令。** 没有必要为补一个UNKNOWN而运行新Hang。`READ_SAFE=BLOCKED / FAULT_DATA_COHERENT=UNKNOWN / REAL_MMIO_BACKEND=NONE / READY_FOR_HARDWARE_APPROVAL=NO`。

## 离线工程的边界

有主executor和事务writer的证明以持有Client/Ticket、正常返回callback、调用方保有稳定输入及受控目录权限为前提。同一个Ticket/Client对象被并发销毁/访问、异步强杀/longjmp、模块代码提前卸载均不在合法API契约内。超时不能free activebuffer；Cancel模式明确可放弃尚未持久化prefix，需查看watermark/error，不能把Closed当已写成功。

v2严格codec验证wire/派生字段相容，不认证观察者声明或GPU；未知身份仍未知。TrackB只承诺旧THAGv2/v3和TGF4v1持久化，本轮v2 codec独立交付，若后续选择通过该backend保存v2须新增显式parser分支/集成测试，不能偷用旧长度。

这些限制不是无限延长诊断路线的工作队列。新实机权限/必要证据不可得时停止硬件准入研究，离线研发转向TrackE唯一任务。
