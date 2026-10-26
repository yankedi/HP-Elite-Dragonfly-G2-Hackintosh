# GPU Hang、Fault Clear与Reset：25G83证据时间线

**RESET_CLEAR_ORDER=PARTIAL。** 已从精确二进制恢复两种doHangAnalysis调用语境和一条旧fault清除分支；未证明TGL三寄存器的全局clear/reset/锁排他时序。

## 坐标与证据入口

本页VA均为SystemKC低地址容器坐标，fileoff对下列ICL/IOAccel代码恰同值；不能当作运行指针。来源SHA/UUID和完整每条bytes在`analysis/expanded/*.all.json.gz`、`.selected.txt`，原KC身份见[25G83-BINARY-IDENTITY.md](25G83-BINARY-IDENTITY.md)。`analysis/cache-fixups.json`仅在format11链成员及cacheLevel均已验证时解析静态stub/vtable；动态receiver种类仍需额外证据。

## 两条不同的可见调用语境

### A：直接诊断并请求后续硬件错误处理

`IGHardwareRingBuffer::debugGraphicsEngine`（`0x13edcd92`）：

1. `0x13edcd9b`直接调用`doHangAnalysis@0x13edcdd2`。
2. `0x13edcda3`直接调用`dumpHangAnalysis@0x13edcece`。
3. `0x13edcdcc`尾跳`IOAccelEventMachine2::signalHardwareError@0x1459511e`，可见ESI=1、EDX取channel字段。

这里只能证明该函数内的先后；不凭参数1猜完整restart枚举，不认定其他线程尚未reset。

### B：IOAccel restart处理中的诊断

`IOAccelFIFOChannel2::restart@0x145869fe`的一条常规分支：

1. `0x14586b02`调用receiver vptr+`0x208`。
2. 对静态`IGAccelFIFOChannel`主vtable，该slot指向`getHardwareDiagnosisReport@0x13ee5e50`；该函数`0x13ee5e64`直接调用doHangAnalysis，然后尾跳dumpHangAnalysis。
3. `0x14586c44`调用`IOGraphicsAccelerator2::reportGPURestart@0x145bf782`。
4. 较后`0x14586d27`调用vptr+`0x200`；同一静态类slot指向`resetHardwareAndReplay@0x13ee5e08`。
5. 该函数`0x13ee5e27`调用ring vptr+`0x168`；静态`IGHardwareRingBuffer`slot指向`resetGraphicsEngine@0x13edcaa6`。scheduler的后续resume等仍有动态分派条件。

所以**同一Hook既可能在请求restart之前被调用，也可能已经位于restart处理路径内部**。不能给所有入口贴一个未经区分的“reset前安全点”标签。静态vtable闭环不是该次实机receiver/分支被执行的证明。

## doHangAnalysis内部

精确函数`0x13edcdd2–0x13edcece`：

- 查询scheduler的`vptr+0x158`，随后遍历`accelerator+0x1340`的active-engine位。
- `0x13edce5f`调用`gatherKeyRingData(engine)`；成功才在`0x13edce73`调用`checkEngineStatus`。
- `0x13edce9f–0x13edcea9`设置enable=1、mask=7并调用SafeForceWake。
- `0x13edceae–0x13edceb9`马上调用disable、mask=7，最终EAX=2返回。

`gatherKeyRingData@0x13ec8326`的RCS分支先以mask1获取原驱动Forcewake，然后读取head/tail、batch、PDP等既有寄存器；尾部`0x13ec8bf5`读取旧`0x4094`，再释放对应mask。`checkEngineStatus@0x13edd204`又在`0x13edd22a`读取旧4094。**GA3.3只接受mask7，因此实际捕获插在上述既有engine数据收集之后。** 是否同一context/root持续有效不能由此保证。

## 已证明的旧clear分支及其界限

`resetGraphicsEngine@0x13edcaa6`常规分支：

```
SafeForceWake(true,7)                 @13edcb49
保存表驱动reset寄存器
write [MMIO+4a08] = 40004            @13edcc7a
write [MMIO+941c] = resetMask         @13edcc87
loop:
  read [MMIO+941c]                   @13edcc98
  read [MMIO+4094]                   @13edcc9e
  if old-valid-bit:
    write4100=f0f0b1b1; write4104=f0f0b2b2
    write4094 = old & ~1             @13edccc0
  assert_wait_timeout → thread_block @13edccd9/13edcce0
  until requested941c bits clear
恢复reset寄存器/调用scheduler processGPUReset
SafeForceWake(false,7)               @13edcd79
```

这里的旧4094 clear在**发出941c reset请求之后、等待完成的循环中**，不是可以照抄的“Gen12 fault先clear再reset”序列。其他状态分支还可提前退出或采用不同恢复逻辑。

在五映像的实际线性解码语料中，未发现`0xCEC4/0xCEB8/0xCEBC`这三个**字面操作数**；这不排除通过表、算术或未解码路径生成地址。`analysis/expanded/register-literal-occurrences.json`保留全部匹配与“literal不是自动MMIO/可达”的分类。TGL的4094与GLOBAL_MOCS重叠，因此上述旧valid/clear语义不能直接解释成真正Gen12 fault。

## 锁、异步及Context/CSB

可见IOAccel `hardwareErrorEvent@0x145943e6`先拿event对象的两个mutex，释放状态mutex后尝试accelerator mutex，再调用`lock_busy`、restart_channel，最后配对释放；具体取决于分支。SafeForceWake自己的多线程路径用**spinlock**保护引用计数并在返回前释放；它不是IOAccel mutex，也不自动排除所有reset入口。

`signalHardwareError`、progress timer、CSB/Execlist、scheduler reset、context begin/endReset的实际片段另见`reference/timeline-index/`。CSB处理、GPU上下文修改和IOAccel报告不是同一个原子快照协议。未证明所有interrupt/workloop/reset/power调用都共享同一reset排他锁，未建立全局锁序偏序，不能把已见一条持锁路径推广到所有入口。

历史WindowServer watchdog/spin与IOAccelerator等待关系在GA33保留。本轮静态`reportGPURestart`路径只证明报告构造调用，不证明同一次WindowServer被watchdog终止的唯一因果、同一个fault epoch或线程归属。

## 用户要求的十问

1. **当前Hook在哪个阶段？** mask7采集在doHangAnalysis的engine gather/check之后；外层存在A/B两种语境，B已进入restart处理。见上面精确callsites。
2. **fault可能已经清除了？** 不能排除。已见旧4094 reset中clear；真正CEC4在其他线程/硬件阶段的clear及latch持续性未知。不能由“本函数之后才reset”证明全局fault仍在。
3. **是否与Reset并发？** 尚未排除。虚调用、interrupt、scheduler和其他诊断入口未闭合成全局排他证明；GA33全局flags不等于锁。
4. **是否持必要锁？** 某IOAccel路径可见mutex/busy锁；SafeForceWake返回时其spinlock已释放。缺少覆盖目标MMIO与所有reset/power路径的同一排他契约，答案不能为是。
5. **哪些可能阻塞？** IOAccel mutex/busy锁、reset循环的`assert_wait_timeout/thread_block`、分支中的IOSleep；Forcewake有IOPause轮询和严重超时路径。禁止在未知上下文中新增获取/等待。
6. **Hook允许哪些操作？** 本轮不批准任何新增硬件操作。独立核心可离线有界mock/codec。未来真实Hook若获证，仍需预分配、无文件IO/内核分配/等待、不改reset/clear、不跨生命周期持借用指针等契约；这些是条件，不是现有Hook已满足证明。
7. **哪些读影响电源？** `SafeReadRegister32`实际先determinePowerDomain→SafeForceWake(true)→读→release，故“只读API”会间接进行forcewake写/轮询。直接volatile读本身无该序列但其电源可访问性不自动成立；未穷举所有硬件读副作用。
8. **能否关联同次Hang的Context/PML4/Head？** 还不能严格证明。gather和晚期mask7是分离时点，缺boot/hang/reset epoch、allocation/context generation和完整排他/latch协议；108B本身没有Context/PML4/Head字段。
9. **最小只读诊断适合哪里？** 研究候选为原驱动已持GT/active power、并处在与clear/reset共用排他区域内、第一次破坏fault之前的预分配snapshot点。尚未找到满足全部条件的精确点，不给可部署地址。
10. **有更安全位置吗？** 当前晚期SafeForceWake返回点未证合格；更早的gatherKeyRingData RCS只持mask1，不是GT4证明，不能直接换Hook。仍需继续离线核清动态selector、全局reset锁及TGL latch语义后再选点。
