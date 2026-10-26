# 目标 XNU ThreadCall 与适配边界

目标25G83内核为`xnu-12377.161.14~5`。本轮有界查询Apple GitHub的`tags/xnu-12377`集合未找到对应tag，最新匹配参考为`12377.121.6`，pin `ac9718fb1af618d5ce8678d0dc6e8a58f252216f`。这是检索集合中的未找到，不能证明所有公开渠道都没有源码；没有认证目标实现或其live bytes。完整查询快照/最小缺口见`../reference/bounded-research/`。

参考契约已固定在GA36 `reference/thread-call/CONTRACT.md`及实际头/源码SHA：

1. enter1 true是“此前pending”，不是失败；不能因为true就丢一个queue引用。
2. ONCE在active期间重提交可延后rearm，合并次数不等于通知次数；不能按enter次数直接推导callback引用。
3. cancel_wait不能阻止未来submit；不能在本callback内等自己，要求合适的可睡眠/中断开启上下文。取消失败不等于可free。
4. free在pending时可拒绝；必须确认结果，不能无视false。参数指针与call对象不是同一所有权。

## 真实适配前仍需的事务

先撤销所有外部入口/路由并建立不能再进入的证明，再在统一submission gate关闭准入；为每个真实排队callback建立独立于raw self的owner，包含coalesced/rearm/取消路径；active callback持引用到最终返回；在安全线程执行cancel/wait，证明没有尚未进入的回调；仅当所有任务、backend IO和外部入口都已fence时才free call、buffers、trampoline/模块。超时或free/cancel失败则保留owner并拒绝卸载。

CPU Ticket不是ThreadCall参数引用计数的直接实现，不能把`shared_ptr`塞进内核thread_call_param_t就声称集成完成。`EXECUTOR_LIFECYCLE=VERIFIED`如用于本轮，仅指有主宿主协议；真实XNU backend=未实现，exactThreadCall条件BLOCKED。

`quiescent()`只证明原core active lease/producer/writer内部退出；未运行的rawcallback不在其中。本轮ASan反例对此有实际失败/修复对照。用户不需要连接macOS SSH；本轮不采运行态数据。
