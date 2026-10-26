# CAS根因及最小源级修正

25G83 XNU `_OSCompareAndSwap`实际机器码为lock cmpxchg/sete al，成功返回1。GA35冻结GA33源码1578恰在成功时return，使Idle→Claimed但无人写；下一次失败者反而进入写路径。两个失败者可同时使用hangWriteBuf，旧flag释放后hangWriteError才发布也留有失败重试窗口。

原状态：Idle(0) → CAS成功后错误退出且Writing(1)永久留下；CAS失败者→copy/write→flag0→error。它不是可靠的单writer状态机，ThreadCall coalescing不能修复反向所有权。

candidate/kern_igfx.cpp做源级最小纠正：只有CAS成功线程写；首错误先release发布，writing进入Failed(2)不可重置；成功回Idle；缺uio_free时在任何open/O_TRUNC前拒绝。独立Pipeline使用同一语义实现完整发布消费，而不是以修正if替代快照与生命周期协议。

**范围限制：原完整kext的全局volatile capture状态没有认证并发正确，候选强制hangDump=0，不安装旧capture routes。** 新Pipeline是可离线构建的替代协议，并未冒充已集成的真实XNU/GPU链路。不能把CAS_WRITER_FIX软件验证扩大为运行kext或CAPTURE_PIPELINE硬件验证。原始GA33 kext缺失；GA31/32只有实物与历史差异，不能因本源码错误否定GA32b的有效THAG。

修复前后确定性反例、提取实际callback函数的编译和vnode故障路径测试保存在tests与logs；专有KC来源仍在私有历史目录，不发布。
