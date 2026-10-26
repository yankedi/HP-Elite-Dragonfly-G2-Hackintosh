# Apple Forcewake：精确25G83静态调用图

**APPLE_FORCEWAKE_MAPPING=PARTIAL。** 已证明本版实现的mask与MMIO路径；当前设备所走feature/转发分支和对象生命周期尚未知。全部地址为KC坐标，非可调用runtime地址。

## 来源及实际工件

- SystemKC SHA `fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`；ICL UUID `B7DF3049-D3A9-3070-9843-6E5AE47673D7`。
- `analysis/disassembly/com.apple.driver.AppleIntelICLGraphics.{json,txt}`：函数原始bytes、fileoff/VA、symbol extent、逐指令。
- `analysis/expanded/*`：五映像全符号上界语料；`analysis/safety-callgraph.{json,dot}`：精确callsites与未解indirect。
- `analysis/cache-fixups.json`：format11链成员验证后的static stub/vtable候选；layout固定Apple dyld commit `e9da5ae571b4191dcdbcfd827363f19847c84561`，本地头SHA `90bd2b316ada7fc5fe47c2872ea679f0c6cc6d249ed5965dbbdc5bea5afdd21a`。
- 独立复核及可执行byte检查：`audit/forcewake-binary/`。初审中的bit11分支极性文字错误由主代理对照`bt/jb`指出，初稿保留，最终以机器码和修订报告为准。

## 分派图

```
SafeReadRegister32(offset) @13ec7c58
  determinePowerDomain(offset) @13ec7b20 → selector
  SafeForceWake(true,selector) @13ec39f6
  load32 [this.MMIO+offset]
  SafeForceWake(false,selector)
  return sampled DWORD

SafeForceWake(bool) @13ec81e2 → SafeForceWake(bool,mask7)

SafeForceWake(bool,mask) @13ec39f6
  if mask==0 or object flag bit12 set → early return
  bt [this+11c0],11; jb local
    bit11 CLEAR → handler = [ [this+df8] +8 ]; tailcall handler(bool,mask)
    bit11 SET   → local spinlock, refcount transitions
                   → SafeForceWakeMultithreaded(bool,transitionMask,1)
                   → ordinary unlock tailcall → wrapper resumes

SafeForceWakeInterrupt(bool,mask) @13ec8198
  distinct forwarding/local branch
  local → SafeForceWakeMultithreaded(bool,mask,2)
```

**极性明确：** `0x13ec3a34: 0fbae00b (bt eax,0xb)`；`0x13ec3a38: 7222 (jb 0x13ec3a5c)`；目标装载`this+0x1468`锁，fallthrough才装载`this+0xdf8`转发表。不能把bit11 clear说成local路径。

转发时参数只有bool/mask（EDI/ESI），不是把accelerator this继续传给另一个同签名成员函数。表项的装配来源/动态内容未证明，不猜函数指针。ICL里另有`_SafeForceWake(bool,unsigned)@0x13ec7aaf`六字节空体`55 48 89 e5 5d c3`，Framebuffer有真正全局实现`SafeForceWake(bool,unsigned)@0x1401616e`；这些符号的存在不能证明当前表项必然指向其中某一个。

## mask与硬件寄存器

|Apple mask位|精确二进制行为|命名依据|
|---|---|---|
|1|请求a278、ACK d84|固定Linux/Intel寄存器名称Render|
|2|依active engine mask、0x79-byte stride表，request字段+71、ACK字段+75|字节直接证明engine-table；Media命名为交叉依据支持的分类，不假定单一media寄存器|
|4|请求a188、ACK130044|固定寄存器名称GT|

因此**7=1|2|4，包含GT**，不是单一Render枚举。GA32捕获wakeDomain=7只证明wrapper记录了这个请求值（原THAG `GA32/capture/tgl-hang-GA32b-crash-20261018.bin`，SHA1622ecc2…；完整来源见`reference/inventory/`），不是运行态ACK/电源采样。

`SafeForceWakeMultithreaded@0x13ec7d7a`按第三参数shift构造固定render/GT请求及比较位：普通调用`ECX=1@13ec3c01`，`request=(0x10000+enable)<<1`，ACK mask为2；Interrupt变体`ECX=2@13ec81d6`为另一个位。表驱动media仍检查bit0，不能把三臂的ACK位写成完全相同。Framebuffer全局实现的render/media/GT路径则检查bit0，也不能把其协议与本地shift1实现混同。

## 引用与锁

local分支在`13ec3a67`调用stub c222，BootKC解析为`_IOSimpleLockLock/_lck_spin_lock`，不是IOLock mutex。临界区更新三个域的软件引用，只有相应获取/释放转变才把过滤后的mask传入multithreaded helper；因此每次mask7调用不一定新写所有请求。

普通local返回经c228的`_IOSimpleLockUnlock/_lck_spin_unlock`尾调用。spinlock覆盖内部ACK轮询，但在GA3.3 post-original wrapper采样前已释放；它的引用计数语义不能单独替代reset排他或active power。early-return/forwarding分支不走这个local锁。中断变体/引用更新辅助函数的契约也不能直接套用到普通API。

Framebuffer实现使用独立try-spin机制（ca56 `_IOTrySpinLock`、ca5c `_IOSpinUnlock`）及静态计数，render a278、media a540、GT a188，对应d84/d50/130044轮询，还可等待13805c状态。实际转发是否进入它未证明；不能因它也叫SafeForceWake就合并两种对象/计数/锁。

## ACK失败与阻塞边界

固定render/GT臂有inner `0xbb8`、outer `0x12c`计数及`_IOPause(0x64)`，即有界轮询与再发request，而不是返回一个bool成功值。timeout分别从`13ec8176/13ec8184`调用cold2/cold4；表驱动media从`13ec8193`调用cold3，均到`_panic`。cold1则是table请求/IOPause辅助，不是panic handler。

这里的100只是函数实参，不能自行换算成毫秒；300外层预算也不是实测耗时。local spinlock仍覆盖轮询；panic路径没有正常unlock续行。Framebuffer全局实现另有`pause`循环，不把前者预算推广成后者timeout保证。

`SafeReadRegister32`在EAX返回采样DWORD，无本地ACK成功返回或错误分支。selector为0时原forcewake可以early-return而它仍执行读；这进一步说明API名字“Safe”不等于可给任意硬件offset调用。`determinePowerDomain`中的table/边界是本版代码，不直接移植Linux寄存器域表。

对三个目标常量按该stock helper逐条unsigned比较求值，CEC4/CEB8/CEBC都走尾部default产生mask4（`analysis/target-selector-derivation.json`）。这是Apple自身静态分类，增强了域映射证据；无runtime实际调用或MMIO发生，也不填补dispatch/ACK/power/reset缺口。

结论：**静态三域映射成立；具体当前硬件上下文安全仍未知。** 见[GT-FORCEWAKE-AUDIT.md](GT-FORCEWAKE-AUDIT.md)。
