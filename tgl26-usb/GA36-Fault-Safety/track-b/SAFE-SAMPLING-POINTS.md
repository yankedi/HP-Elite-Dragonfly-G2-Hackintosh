# SAFE-SAMPLING-POINTS：安全采样点审查

## 结论

**没有证明任何 actual-hardware-safe point；结论为 BLOCKED。** 本轮只做静态有界函数和一轮 bounded-xref；无 SSH、无硬件/MMIO、无镜像/EFI/deploy、无 hook。

## 候选审查

|候选|已有静态事实|缺失的硬条件|判定|
|---|---|---|---|
|A `doHangAnalysis` 尾部 late wake|`13edcea9` `SafeForceWake(true,7)`，`13edceb9` disable；函数之后才回 `2`|active PM/lifetime、ACK success postcondition、wrapper 外锁、reset/clear exclusion、fault epoch/latch|BLOCKED|
|B early `gatherKeyRingData`|GA35 已见 RCS 早期 mask1 forcewake/read path；早于尾部 mask7|不是 GT4/7 证明；上下文/root/head/epoch 同代性、reset 并发、ACK/lifetime 均未知|BLOCKED|
|C existing GT software reference|`+0x12c0>0` 可走 no-transition；local wrapper 有 c222/c228|software ref 不等于 active power/ACK；lock 不覆盖 reset/PM，且 interrupt/forwarding 入口不同|BLOCKED|
|直接 SafeForceWake return|可见 early/forward/local/ACK/panic 全部不同出口|return 无 bool；正常返回不能证明硬件 ACK，panic 无正常 unlock续行|BLOCKED|

## 五条件门槛

任何未来候选必须同时满足：

1. **PM/lifetime**：调用者持有可证明的 active-power 和对象引用，且 stop/free/sleep 不能并发回收。
2. **request**：知道实际 selector/transition mask，不把软件 `7` 当硬件状态。
3. **ACK**：同一请求的设备 ACK 成功后置条件明确，包含 timeout/panic/early/forward 分支。
4. **lock**：采样期间有明确覆盖目标对象、PM、reset/clear 和异步入口的锁序；不能以 forcewake 自身 spinlock 代替。
5. **reset exclusion**：同一 fault epoch 内证明 clear/reset 未经并发或已清除，且不会在采样中阻塞/改变硬件状态。

A/B/C 均至少缺两项，故不生成“安全地址”。

## Hook/身份/Recovery工程比较

|评价|A 现有晚期wrapper|B 更早doHang阶段|C 既有GT引用期间|
|---|---|---|---|
|新增Hook|原则上沿用两个旧route；仍须认证live trampoline|需新入口/位置与原参数保存，不能只改回调顺序|需先确定实际local/forward目标，再谈最小接入|
|ABI|stock参数和prefix可核验；live未证|doHang入口stock可核验，任意中间指令插桩ABI未证|内部helper的shift/引用后置条件不同，不能复用旧wrapper签名|
|Fault Clear时序|晚于engine gather/check，可能较早已有clear；全局未证|局部更早不能排除另一线程clear|即使GT-held也不提供latch/clear排他|
|Context/PML4/tuple|旧108B不含context/PML4；global捕获未证明线程/engine归属|需新的同代context/root/head关联，不能从早晚推出|需真实owner/engine及generation，不从GT计数推出|
|重入与锁序|旧全局volatile状态可交叉；不得扩大原spinlock|诊断也可能在restart中，新增锁可能反转锁序|ACK轮询在spinlock内，中断与普通入口不同|
|Recovery副作用|任何附加分配/文件IO/等待均无Hook上下文授权|可能改变最早诊断时序或阻塞恢复|forcewake acquire本身会写request；持锁延长可放大恢复延迟|
|本轮离线证明上限|stock路径、source缺陷、mock协议|stock相对先后和候选入口|静态软件引用/transition/ACK分支|
|缺失的runtime契约|live字节/selector、PM与对象hold、ACK、reset/clear排他|以上加新ABI及context身份|实际receiver/reference owner、ACK与power/reset共享协议|

保持三读固定、不可把它解释为无风险瞬时原子操作；不以任意延长Apple锁持有范围弥补未知。

## 不可接受的替代论证

- `mask=7` 只表示请求值，不能证明 render/media/GT ACK。
- `SafeReadRegister32` 的 forcewake/ACK 循环会写请求、等待和释放，不是无副作用只读。
- `+0x12c0` 软件引用大于零不能生成硬件引用。
- `c228` unlock 不能证明 ref/lifetime/reset 排他；**spinrelease != ref validity**。
- `resetGraphicsEngine` 的旧 4094 clear 位于 941c request 后等待循环，不能移植为 CEC4 fault clear。
- 静态 vtable target 不等于 live receiver；本轮不 fabricated receiver。

## 交付与复核

`analysis/focused-fragments.json` 保存 24 个函数的 raw bytes/SHA、VA/fileoff/UUID/source SHA、field/lock 片段和 caller 记录；`analysis/bounded-xref.json` 记录一轮过滤计数；`analysis/branchmap.json` 记录 SafeForceWake 全出口与 reset/clear 证据；`analysis/verify_track_b.py` 只读 raw KC 做独立 slice/hash 检查。若 raw KC 不在 GA35 sealed 输入位置，脚本失败而不是降级为“通过”。
