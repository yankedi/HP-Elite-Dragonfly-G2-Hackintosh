# Executor 所有权：实际 GA36 core 的宿主调度适配

实现 `source/owned_executor.hpp`，直接包含逐字节 GA36 `kern_capture36.hpp`（SHA `7771dfb4bbc229fbec746976559a4ffeba9ac7c348c0e1ec1322f7898ef1afae`）。未另写一套Writer。内部 `slots/snapshot` 固定容量随Control分配，backend为持有型`shared_ptr<void>`，不可传悬空的context。调用方Record在submit返回前必须稳定。

## 三种对象及不变量

* Session：顶层owner，销毁只请求CancelQueued，不阻塞，不直接释放live任务。
* Client：每个使用线程持有自己的值；稳定持有Control才能调用submit/notify/stop/info/wait。不能在另线程销毁同一个Client/Session对象的同时调用它；应复制Client值。不能用raw Session绕过这一前提。
* Ticket：成功publish同时在gate内建立一个queued计数与强引用，并move给外部CPU调度器。move-only；同一个Ticket不能并发run/cancel/move。调度器可以保留、运行或析构Ticket，但不能只留下裸Control地址。

`submit`门控与shutdown互斥，publish复制/发布及ticket交付在同一个准入事务内；shutdown不能落在“已判Running但尚未取得queue所有权”之间。`run`在gate内完成queued→active交接，Control强引用不间断；writer执行不持gate，以允许publish新prefix和关闭请求。完成后active减一，最后一个任务推动close。Ticket取消只移除通知，不撤销已发布immutable slot。

独立审查后gate改为`recursive_mutex`，避免Policy同线程重入时对自己持有的非递归mutex执行try_lock的未定义行为。递归准入仍由原core Producer CAS拒绝为Busy；`publishing`计数防止Policy内部请求关闭时把未退出的publish误认为idle。关闭条件实际为queued=active=publishing=0。Policy和Writer内不允许调用阻塞waitClosed；可以非阻塞requestShutdown，由外部线程等待。

## 状态机

| 状态 | 新submit/notify | queued ticket run | active callback | 释放 |
|---|---|---|---|---|
| Running | try-admit，竞争Busy | 执行实际drain | 正常返回 | 引用持有 |
| ClosingDrain | 拒绝 | 允许drain | 等自然返回 | queued=active=0后close |
| ClosingCancel | 拒绝 | 消费ticket并标Cancelled | 不强杀 | 同上 |
| Closed | 拒绝 | 无合法未消费ticket | 无active | 最后Client/owner释放后free |

ClosingDrain可升级Cancel，不能重新Running。`waitClosed`只等待任务结清，不等价“数据全写成功”；需另查published/written/error。Cancel可留下未持久化records，因此用户必须选择Drain或在关闭前导出；这不是crash-safe内存存储。

超时返回false时对象、buffer、backend、task code均不可强制回收。这里没有`detach-and-free`、pthread取消、longjmp支持。Writer是noexcept且必须正常返回；普通后端错误/超时返回值进入原core Failed终态。同步IO不返回就保持Closing，真实卸载必须拒绝。即使Control最终释放，kernel代码/trampoline的卸载仍需外部路由/中断/ThreadCall栅栏，本实现只验证用户态所有权。

## 通知、去重与边界

每个Accepted伴一个Ticket，重复run返回Consumed。多个ticket可以合并到同一prefix：实际core唯一writer，后续drain Idle/Busy并不重复写同watermark。故意取消通知后bytes仍在，Running期间可用notify建立新有主通知；没有承诺自动线程池或被遗弃ticket的必达性。Drain shutdown不能把“所有通知被用户取消”描述成已持久化。

实际core drain也可能因32CAS lease预算暂时返回Stopped；适配层在非ClosingCancel状态下恢复同一个Ticket的queued所有权，返回`Executed::Retry`，调度器必须重新排队/再run，或显式取消。不能把Retry当作已消费或已写。ClosingDrain允许继续run；ClosingCancel允许丢通知但状态显示written落后。该协议没有裸指针或无所有权的“以后再通知”。

nextTicket用64位单调号，UINT64_MAX时拒绝，不回绕复用。published用有界容量，不reset。新的reset/boot generation必须新Session；没有伪装真实GPU reset语义。Context::Interrupt在访问mutex前拒绝，这个宿主适配层不能直接放入真实Hook/中断上下文。

GA36 lease有32次CAS预算；Stopped可能代表暂时耗尽而非close。门控确定Running时submit将该结果映射Busy，实际回归stress由宿主有限重试。历史原样断言失败保留，见tests/GA36-REGRESSION-NOTE.md。

## 验证边界

`tests/executor.cpp`实际使用这个适配层及原core：1/2/16/64线程、48轮submit/close竞态、queued owner销毁、active关闭与超时、buffer内容、writer失败终态、重入、重复hang、取消恢复、序号饱和、interrupt拒绝、新generation。`tests/raw_callback_counterexample.cpp`使用实际原core构造quiescent后rawcallback的ASan UAF，负例必须检测到heap-use-after-free；有主适配层正例无该错误。

真实命令/exit/版本及TSan结果以`results.json`和指向的不可变时间目录为准。Clang/GCC Debug/Release/ASan+UBSan及两种TSan为CPU宿主测试，不认证XNU mutex/内存模型以外的内核上下文、scheduler、真实Hook或GPU。
