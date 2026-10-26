# Hook ABI 复核：复用 GA35 精确前缀证据，区分 stock 与 runtime

**结论：现有 GA35 证据只能核对精确 stock KC 的函数入口、参数寄存器和前缀字节；它不证明当前加载镜像中的 live bytes、Lilu trampoline、路由或调用者锁/生命周期契约。Track C 没有新增 Hook、route request 或真实 reader。`CorrectHookABI` 仍为 CONDITIONAL，`HOOK_CONTEXT_SAFETY=BLOCKED`。**

## 1. 证据来源与身份

|项|值|
|---|---|
|stock KC|`SystemKernelExtensions.kc`|
|KC SHA-256|`fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`|
|image UUID|`B7DF3049-D3A9-3070-9843-6E5AE47673D7`|
|GA35 逐字节证据|`../../GA35-Driver-Reversing/analysis/hook-abi.json`|
|GA33 源码副本 SHA-256|`6f2f73e5d404c4c5daf8294f6d8f59ae5d02fb040e24fbe99713949750ede395`|
|GA33 路由行|`inputs/kern_igfx.cpp:1015-1016`|
|GA33 wrappers|`1455-1488`（doHangAnalysis）、`1490-1517`（SafeForceWake）|

以下 VA/fileoff 是**静态容器坐标**，不是运行指针。前缀是 stock 文件字节，不是 live patched 字节。

## 2. 精确入口与有限 ABI

|符号|KC VA / fileoff|相对 image header|可见 ABI（有限）|
|---|---|---|---|
|`__ZN20IGHardwareRingBuffer14doHangAnalysisEv`|`0x13edcdd2` / 334351826|`0x3ddd2` (253394)|`rdi = ring this`；静态观察到 `EAX=2`；完整 C++ 返回类型不由 mangled name 证明|
|`__ZN16IntelAccelerator13SafeForceWakeEbj`|`0x13ec39f6` / 334248438|`0x249f6` (150006)|`rdi = accelerator this`；`esi/sil = bool enable`；`edx = unsigned domain mask`；源码 wrapper 声明 `void`；调用者不获取 ACK 返回值|

前缀长度必须区分“请求的最小跳转覆盖”和“实际 whole-instruction prefix 字节数”：

|符号|requested patch length（最小覆盖）|whole-instruction prefix 实际长度|prefix bytes|
|---|---|---|---|
|`doHangAnalysis`|5 B|**6 B**|`554889e54157`|
|`doHangAnalysis`|14 B|**16 B**|`554889e54157415653504889fb488b4710`|
|`SafeForceWake`|5 B|**6 B**|`554889e54157`|
|`SafeForceWake`|14 B|**14 B**|`554889e541574156415541545350`|

解读：

- `554889e54157` 是 12 个十六进制字符，即 **6 个实际字节**，不是 5 字节；它覆盖最小 5 字节跳转边界。`554889e54157415653504889fb488b4710` 是 32 个字符，即 **16 个实际字节**，覆盖最小 14 字节边界。`SafeForceWake` 的 14 字节前缀字符串正好是 28 个字符、14 个实际字节。
- 这些 prefix 是 **stock 文件字节**，不是 live patched 字节。whole-instruction prefix 覆盖 minimum jump 只表示离线边界足够，不代表 Lilu trampoline 重定位、跳转目标、CPU 指令缓存同步或 live 路由正确。
- mangled name 与寄存器使用只支持有限的参数观察；**不证明完整 C++ 类型/ABI、sret、异常、调用约定、所有路径返回或对象生命周期**。
- `doHangAnalysis` 的 `EAX=2` 是静态观察，不等于完整返回类型或所有路径的统一后置条件。
- `SafeForceWake` 的 `void` 来自源码 wrapper 声明；没有把 ACK 成功作为返回值。不能因为寄存器里出现临时值就虚构 bool 返回。

## 3. stock 与 runtime 的区别

|层面|已核对|未证明|
|---|---|---|
|磁盘 KC 身份|三方 SHA、UUID、函数入口和前缀|—|
|live 入口字节|—|现有 Lilu/WhateverGreen 可能已 patch；未读取 live bytes|
|trampoline|—|重定位、跳转编码、目标地址、指令边界|
|调用者上下文|源码 wrapper 的可见参数|所有调用者是否持锁、是否允许等待/分配、生命周期|
|forcewake|静态 mask/ACK 路径|当前设备实际 selector 分支、ACK 成功、引用所有权|
|reset|旧 4094 clear 分支|Gen12 CEC4/Data 全局 clear、reset 排他、并发入口|
|电源|`SafeReadRegister32` 会请求 forcewake|active power 引用、sleep/wake/teardown 互斥|
|映射|`this+0x1270` 基址字段|extent、空指针/teardown、异常行为|

因此，`CorrectBinary` 和 `CorrectHookABI` 只能保持 CONDITIONAL。它们不是“已部署 Hook 的关闭分支实测”，也不是“live 原函数可安全调用”的证明。

## 4. Forcewake/reset 的未闭环项（复用 GA35）

- `SafeForceWake` 有 mask0/flag12 early return、flag11 clear 的间接转发、flag11 set 的 spinlock/refcount 路径。
- 普通返回前 spinlock 已释放；它不是 reset/clear 排他锁，也不自动等于设备 active power 引用。
- ACK 超时可能走 cold panic 路径；没有覆盖所有分支的“GT ACK 成功”后置条件。
- `determinePowerDomain` 对 `0xcec4/0xceb8/0xcebc` 的静态求值均为 mask4，但这只是 stock helper 的分类，不是 live selector/引用证据。
- `doHangAnalysis` 的 mask7 窗口在 engine gather/check 之后、最终释放之前；外层可能已处于 restart 路径。不能把该窗口标成统一的“reset 前安全点”。
- 旧 `0x4094` clear 发生在 `0x941c` reset 请求后的等待循环中；不能照抄成 Gen12 fault 的 clear 序列。CEC4 的真实 clear/并发时序仍 UNKNOWN。

## 5. 旧 writer 反向门控（Track C 不修改；Track A 独立 candidate 已修复）

GA35 安全审查指出 `inputs/kern_igfx.cpp:1578`：

```cpp
if (OSCompareAndSwap(0, 1, &hangWriting)) return;
```

GA35 从 exact BootKernelExtensions.kc 核对 `_OSCompareAndSwap` 原始字节：

```text
554889e589f8f00fb1320f94c05dc390
```

即 `mov eax,edi; lock cmpxchg [rdx],esi; sete al; ret`，成功时返回 1。因此该历史源码在首次成功抢到 writer 时反而返回并留下 flag 1。这是已有 GA3.3 源码的可复核缺陷；不能宣称本机运行实例存在同一机器码。

**Track C 不修改该历史源码，历史文件保持只读。** 按 GA36 集成说明，Track A 已在独立 candidate 中修复 CAS 语义和失败终态，并将 legacy capture 强制关闭；本文不重新审计 Track A candidate，也不把该修复当作 Track C 离线 gate 的证据。Track C 的 gate 不包含该 writer。

## 6. 对九条件门的输入

|条件|本轮裁定|原因|
|---|---|---|
|`CorrectBinary`|CONDITIONAL|stock KC 身份已核对；live bytes 未认证|
|`CorrectHookABI`|CONDITIONAL|入口前缀/参数可核对；live 路由、trampoline、锁/生命周期未闭环|
|`CorrectGTDomain`|CONDITIONAL|静态 mask4 分类；live 分支未执行|
|`RuntimePowerHeld`|UNKNOWN|无 PM 引用证据|
|`ForcewakeReferenceHeld`|UNKNOWN|请求/计数不等于采样持有引用|
|`ForcewakeACKConfirmed`|UNKNOWN|无跨分支 ACK 后置条件|
|`ResetExcluded`|UNKNOWN|无全局排他契约|
|`MMIOReadSafe`|UNKNOWN|无真实映射/异常/副作用证据|
|`FaultTupleConsistencyEstablished`|UNKNOWN|见 `FAULT-TUPLE-CONSISTENCY.md`|

九项全部非 VERIFIED，所以门在项目当前证据下为 DENY。测试中的“全 VERIFIED 允许”只是验证门逻辑的合成用例，不是对上述条件的升级。

## 7. 证据边界

- 本轮没有 SSH、实机读取、MMIO 写、reset、ACK 探测、Hook 安装、kext/EFI/IMG 变更或启动项修改。
- 没有重新跑 GA34 全矩阵或全二进制扫描；只复用 GA35 已固定的精确前缀/ABI 证据。
- 静态前缀检查不能替代 live 验证；`HOOK_CONTEXT_SAFETY=BLOCKED` 仍成立。

**HOOK_ABI=STATIC_STOCK_CONDITIONAL；FULL_CPP_ABI_TYPE=UNPROVEN；LIVE_ROUTING=UNPROVEN；HARDWARE_APPROVAL=NO。**
