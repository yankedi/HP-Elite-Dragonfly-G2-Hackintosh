# Hook ABI与原始指令审计

本轮**未实现、安装或路由任何新增Hook**。审计对象是GA3.3源码声明与25G83 stock KC的对应关系。源码副本`inputs/kern_igfx.cpp`，SHA `6f2f73e5…`（全值见manifest），实际路由1015–1016行、两个wrapper分别1455/1490行。历史报告Mac树行号不同，不据其推断机器码地址。

|符号|KC VA / fileoff|相对ICL header|可见ABI|
|---|---|---|---|
|`__ZN20IGHardwareRingBuffer14doHangAnalysisEv`|`0x13edcdd2`|`0x3ddd2`|this在RDI；可见最终`mov eax,2; ret`|
|`__ZN16IntelAccelerator13SafeForceWakeEbj`|`0x13ec39f6`|`0x249f6`|this RDI、bool ESI/SIL、unsigned mask EDX；wrapper声明void，调用者不获取ACK返回|

证据：`analysis/hook-abi.json`逐条保留原字节、fileoff、函数入口、来源SystemKC SHA、UUID、5/14字节跳转所需的完整指令前缀。该前缀检查**不是**Lilu实际trampoline重定位验证。返回类型通常不在C++ mangled名中；不因看到临时EAX值就把SafeForceWake改成bool，也不虚构ACK返回值。

源码实际时序：

```
wrapDoHangAnalysis: global hangInProgress=1 → original(that) → flag=0
  original doHangAnalysis:
    gatherKeyRingData + checkEngineStatus (each active engine)
    SafeForceWake(true,7) → SafeForceWake(false,7) → return 2
wrapSafeForceWake: original(accel,enable,mask) → if accepted enable/mask7 → hangCapture
```

**新发现的精确阶段：**7窗口在doHangAnalysis采完既有engine数据之后、函数最终7释放之前。它不等于hang检测的第一瞬间。`gatherKeyRingData`的RCS窗口使用mask1；旧wrapper会拒绝该窗口而等到最后mask7。

## ABI以外的未关闭项

- SafeForceWake原函数在某些路径直接early return，或者间接转发；原函数返回不自动提供“GT ACK成功”的可观察证明。
- 多线程路径内部spinlock在返回wrapper前已经释放。即使forcewake引用仍有语义，wrapper也没有由此持有reset排他锁。
- GA3.3共享`hangInProgress/attempts/count/captured/wakeDomain`不是按线程/调用实例拥有的上下文；源码未展示足以证明跨线程、跨engine、嵌套分析不混淆的同步。全局窗口只能提供弱关联。
- live entry bytes未读，Lilu/WhateverGreen会修改内存；stock字节与UUID对应不证明当前路由/原函数trampoline有效。
- MMIO映射`this+0x1270`已在精确`SafeReadRegister32`的`0x13ec7c7f–0x13ec7c91`被确认；映射生命周期、设备active电源引用和reset互斥仍不能由该偏移推导。
- ring this与accelerator this属于不同对象，不可把ring字段偏移、spinlock、IOAccel mutex或busy锁混同。

## 默认关闭行为

交付的GA35源码只是GA34独立核心的逐字节副本；没有route request、bootarg接入、真实reader或调用原函数的wrapper。诊断关闭时没有新Hook执行或额外硬件行为。独立测试证明`Request{}`不调用mock callback；它不是“已部署Hook的关闭分支实测”。

结论：可核对现有声明的参数寄存器与stock入口，但完整live ABI/生命周期/锁契约未闭环，**HOOK_CONTEXT_SAFETY=BLOCKED**。

## 独立安全审查补充：旧writer门控反向

`audit/safety-review/SAFETY-REVIEW.md`的SR-05指出`inputs/kern_igfx.cpp:1578`：`if (OSCompareAndSwap(0,1,&hangWriting)) return;`。主代理另从同一25G83 BootKC核对`_OSCompareAndSwap@0xffffff8000a18d30`：`mov eax,edi; lock cmpxchg [rdx],esi; sete al; ret`，确认**成功返回1**（`analysis/atomic-semantics.json`保留原始bytes/fileoff/UUID/SHA）。因此该源码首次成功抢到writer时反而退出并留下flag1，失败者才可能进入写路径，确与注释相反。

这是已有GA3.3源码的可复核缺陷；GA3.3对应kext二进制本机缺失，不能宣称已证明运行实例存在同一机器码。未修改旧源码、部署或硬件。GA34/GA35隔离Fault核心没有该writer。另有SR-03/04/06关于Hook内descriptor分配/读取、全局volatile状态、uio释放及teardown的未闭环项，均不因core测试通过而消失。
