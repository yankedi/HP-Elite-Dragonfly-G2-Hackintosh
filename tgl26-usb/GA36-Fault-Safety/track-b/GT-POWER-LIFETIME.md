# GT-POWER-LIFETIME：GT 引用、电源与对象生命周期

## 证据边界

本轮只对 24 个已有符号做有界提取。所有 VA/fileoff 为未滑动 KC 坐标；source SHA `fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`，ICL UUID `B7DF3049-D3A9-3070-9843-6E5AE47673D7`。静态字节不等于 live receiver、ACK 或硬件 active power。

## 三个关键字段

|字段|新静态事实|仍不能推出|
|---|---|---|
|`this+0x11c0` flags|`start@13ebf171` 清零；`populateAccelConfig@13ec2477–248b` 写 bit11；`populateAccelConfig@13ec2f12–2f1e` 清/置包含 bit12 的掩码；SafeForceWake@13ec3a13/3a34 读 bit12/11|bit11=local、bit12=power/sleep 的语义未经认证；配置调用和运行时值未知。|
|`this+0xdf8` forwarding|`initLocalCallbackSupport@13ec538f` 写入；`setPowerState@13ec5555/55f5` 读并调用 slot `+0x30`；`cleanLocalCallbackSupport@13ec21b6` 和 `stop@13f214e0` 清零；SafeForceWake 取 `[df8]+8`|handler 的实际对象、签名后置条件、引用/并发/lifetime 未闭合。|
|`this+0x1468` lock/reference owner|`start@13ebf12d` 建立；SafeForceWake@13ec3a5c 取 `[1468]` 后 c222 lock；stop@13f21567 清零；local 正常末尾 c228 unlock|这是一个软件锁字段，不是 active-power token；清零与异步 receiver 的顺序/排他未知。|

引用计数区的静态访问：`+0x12b8`、`+0x12bc`、`+0x12c0` 分别参与 mask1/2/4 更新。GT 旧值大于 0 时，普通 wrapper 可只更新 software refcount 而不调用 multithreaded；0→1 才形成 transition bit4。**software refcount > 0 不是 hardware ACK。**

## PM 与停止/释放

- `IntelAccelerator::setPowerState` entry `0x13ec5524`, 408 B, raw SHA `cb1a235739e60b3059044fb49e8747505cf97e74ea79d71ea12265e253db3726`：两条 state 分支都读 `[this+df8]` 并调用 `handler+0x30`，同时使用 `lock_busy@145c3cf6` / `unlock_busy@145c3d08` 的直接调用；它没有证明与 SafeForceWake 的 `+1468` 自旋锁相同。
- `IntelAccelerator::systemWillSleep` entry `0x13ec36de`, 100 B, raw SHA `10b6afbf74a7fb2e85cd4f038678ed5c4565d21ce7fb4d3674cfa361285d07c`：调用 telemetry disable、scheduler vtable `+0x118`、`0x13ea92a6`、`IGInterruptBridge::systemWillSleep@13ee3e84`，没有可见 `+1468` lock 或 flags ACK。
- `stop` entry `0x13f211b6`, 966 B, raw SHA `726be59d8179d3f4a62c18c2dd7e6d5980fa42fe0fffe6abcf940146fc7ffe0`：先有多组虚调用和 IOLock/busy 片段；`13f214e0` 清 `df8`，`13f21567` 清 `1468`。清除顺序不能解释为所有异步调用已停止。
- `free` entry `0x13ebee74`, 36 B, raw SHA `431726549b508f0e7978530fdf66e527f36095710fd85682c04c40aa3973acf8`：仅为父类/虚析构尾链，未作为生命周期安全证明。
- `IOGraphicsAccelerator2::systemWillSleep@145c2e06` 和 `system_will_sleep@145c3098` 含多个 vptr 调用、IOLock/睡眠相关间接链；没有向 ICL `+1468`/`+df8` 提供共享 token。

## 五条件比较表

条件依用户要求固定为：PM/lifetime、request、ACK、lock、reset-exclusion。`UNKNOWN` 不改写成安全。

|候选|PM / lifetime|request|ACK|lock|reset-exclusion|结论|
|---|---|---|---|---|---|---|
|A existing-latewake：`doHangAnalysis@13edcdd2` 尾部 `SafeForceWake(true,7)@13edcea9`|UNKNOWN：函数本身无 PM acquire；stop/PM 清字段的并发关系未闭合|PARTIAL：静态调用 `true,7`；7 是软件请求 mask|UNKNOWN：后续 disable 也只走同一 wrapper；无成功返回值，ACK loop 可能 panic|PARTIAL：local 分支有 c222/c228，但 forwarding/early/interrupt 分支不同|UNKNOWN：`doHangAnalysis` 有 debug/restart 两个可见调用语境，未证明共同 reset 锁|**BLOCKED**，不能作为实际采样点|
|B earlier-doHang：`gatherKeyRingData@13ec8326` 的既有早期 helper|UNKNOWN：更早不等于持 active power；上下文/epoch 未提供|PARTIAL：GA35 已有静态证据显示早期 RCS 使用 mask1；不是 GT bit4/7 证明|UNKNOWN：mask1 helper 的 ACK/lifetime 后置条件未闭合|UNKNOWN/PARTIAL：不应借用普通 wrapper 的 lock 结论|UNKNOWN：早期路径仍可能与 reset/interrupt 并发|**BLOCKED**；只能作为较早研究候选，不能安装 hook|
|C existing-GT-reference：普通 local，`+0x12c0 old>0`|UNKNOWN：软件 count 不等于 active-power hold|PARTIAL：old>0 时可无新 request；0→1 静态会发 GT transition|UNKNOWN：无新 request 更不能推出 ACK；历史 ACK 也没有跨生命周期证明|PARTIAL：local c222/c228 覆盖计数更新，但不覆盖 PM/reset|UNKNOWN：没有共同 reset exclusion|**BLOCKED**；只能说明 no-transition 分支|

表中的“lock”不把 `spinrelease` 当 ref validity；表中的“ACK”不把“未 panic”当 ACK；表中的“PM”不把 flags bit12 当电源状态。

## PowerWell 交叉检查

`AppleIntelPowerWell::init@0x140274ba`（78 B，SHA `a72d8c31479a12ee63e3e58ab6d39174aeb026879a14b39ab1c1ebdef8c16673`）把 controller 写入 `+0x10`、从 controller `+0x920` 取状态并跳 enable/override 路径。`enablePowerWellPG@0x14028cbe`（128 B，SHA `32aa2805840e966a001c7a7215c1f84bd4af715a5c3ae43a3e5fdcbd1f8bf509`）和 `disablePowerWellPG@0x1402861e`（190 B，SHA `87a923aafd3c2aef53bafa7dfc31362e74aecca5b2003dda99a9810df03f726`）只展示计数/状态到 PG state 的静态转换；它们没有证明 ICL `+1468`、GT `+0x12c0` 与 display power well 共用排他协议。
