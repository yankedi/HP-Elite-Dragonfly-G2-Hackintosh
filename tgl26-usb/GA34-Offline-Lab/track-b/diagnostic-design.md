# GA3.4独立诊断设计与真实接入门槛

## 交付架构

本轮组件为GA3.3本地staging的4文件只读副本旁新增独立CPU可编译fault核心；不修改base内容，不挂接原doHangAnalysis/SafeForceWake，不替换reset逻辑，没有真实MMIOprovider。Default-off开关只供新组件解释显式参数，不能因参数存在绕过power/FW/reset/context门禁。

分层：RawSnapshot → ValidatedDerivedFields → VersionedFaultRecord；MockProvider提供read/guard/clock，BoundedStore提供固定容量追加，serializer按固定小端wire布局。raw read的有效位独立保存，无法取得的context/PML4等metadata保留有效位0，不能用数值0假装已取得。

## 接入前必须满足的契约

1. Exact25G83 binary/module identity与实际符号/偏移匹配，不能套用同24.0.5的旧build偏移。
2. 确证Apple域映射包含GT，已ACK且持有运行期电源引用；不能在诊断内擅自写forcewake/request或等待未知锁。
3. 真实reset/clear排他锁与正确上下文已持有，锁序不会与原分析/恢复路径倒置；epoch只是附加观测，不能替代此锁。
4. current context/PML4/clock/sequence/capturePhase的获取点有证据；fault的GT-global engine不自动等于RCS当前context。
5. 每个read前后guard仍有效；任何read/guard/时间异常立刻停；原始值被保留但不得标成完整成功快照。
6. 多hang只有有界追加，slot满/sequence溢出拒绝，禁止覆盖首条；异步用户读取必须有稳定发布与buffer lifetime契约。

上述真实驱动契约当前未证，所以实现阶段不提供可执行的硬件接入adapter。离线可编译和mock测试只验证核心控制流，不解决这些缺口。

## 采样序列与一致性

实际实现：准备metadata → 全部门禁 → fault/DATA0/DATA1各一次（共3read，每次前后guard最多6次）→ 发布。当前没有第二次fault/raw读取，也没有从设备测得采样前后时钟；单个monotonicNs及身份由caller给出。它检测可见epoch/power/GT/ACK变化，不证明三个值原子一致、同次hang、未发生ABA或counter未重用；真实reset exclusion与latch/clear契约必须先证。未来即使两次raw相同也只能排除部分变化，不能证明context归属。

CaptureStatus应区分Disabled、Unsupported、PowerUnavailable、ForcewakeUnacked、ResetInProgress/Changed、MMIOFailed、InvalidFault、InconsistentSnapshot、BufferFull、SequenceExhausted、TimestampMismatch和Success。每种错误都停止后续read。采样器不清fault；Linux清fault的RMW/postingread仅作为时间线研究依据。

## 旧GA3.3设计须保留的待审风险

现有wrapper共享hangInProgress/hangCount/hangRec及thread_call写出，当前局部源码未展示覆盖所有入口的同步/生命周期证明；这不是凭单个wrapper就断言必有UAF或可利用race，而是不能批准新读取的具体未关闭项。现有捕获还含非RCS范围MMIO，不能将其曾运行过作为新CE寄存器访问安全证明。本轮不修改或扩大旧行为。

## 下一步资料

首要补齐exact25G83 kernel collection中图形驱动binary/符号/相关函数反汇编及导出方式；先离线确认SafeForceWake/analysis/clear/reset/CSB/context生命周期再审集成。是否采集该资料、是否运行新诊断均由用户另行授权决定；当前没有获批GA3.4b启动。
