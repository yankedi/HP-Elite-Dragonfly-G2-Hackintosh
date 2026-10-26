# FORCEWAKE-BRANCHES：有界分支表

## 范围与身份

本页只复核 GA35 已封存的 25G83 SystemKC 静态片段，不 SSH、不读 MMIO、不部署 hook。来源 SHA：`fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`；ICL UUID：`B7DF3049-D3A9-3070-9843-6E5AE47673D7`。VA 与 KC fileoff 是同一未滑动坐标，不是 live 指针。函数范围是 symbol 上界，线性反汇编不是 CFG 可达性证明。

新证据是 `populateAccelConfig` 对 flags 的写入链，以及 start/stop 对 `+0x1468`、`+0xdf8` 的生命周期处理；完整原始字节、SHA、指令和 basic-block 起点见 `analysis/focused-fragments.json`，独立 raw-KC 校验见 `analysis/verify_track_b.py`。

## 普通 SafeForceWake

目标：`IntelAccelerator::SafeForceWake(bool,unsigned int)`，entry/fileoff `0x13ec39f6`，end `0x13ec3c72`，636 B，raw SHA `70310acad78445a189b55c238ae22ea475eab4ac899f8f199a1be80db768d2cc`。

|出口/阶段|精确静态证据（VA: bytes）|结论|
|---|---|---|
|zero 或 flag12|`13ec3a07: 488b87c0110000`; `13ec3a13: 83e101`; `13ec3a16: 85d2`; `13ec3a1d: 740f`; `13ec3a2d: c3`|`mask==0` 或 `flags[bit12]==1` 直接正常返回；没有本地锁、转发、ACK。|
|bit11 清，转发|`13ec3a34: 0fbae00b`；`13ec3a38: 7222`；`13ec3a3a: 488b83f80d0000`；`13ec3a41: 488b4008`；`13ec3a5a: ffe0`|尾跳 `[this+0xdf8]+8`。receiver/契约未知，不能把它称为 local helper。|
|bit11 置，本地锁|`13ec3a5c: 4c8bab68140000`；`13ec3a67: e8b68714ec`|读取 `[this+0x1468]`，经已验证 stub `0xc222` 调 `_IOSimpleLockLock/_lck_spin_lock`。|
|无软件 transition|`13ec3bf1: 09c2`；`13ec3bf3: 85d2`；`13ec3bf5: 7414`|不调用 multithreaded；这不是 ACK 成功，只是引用更新没有产生请求 transition。|
|产生 transition|`13ec3bf7: 4421fa`；`13ec3c06: e86f410000`|把过滤后的 mask 传给 `SafeForceWakeMultithreaded`；正常返回才到 release。|
|ACK normal|render 比较 `13ec7e37–13ec7e3b`，GT 比较 `13ec7f19–13ec7f21`，正常 return `13ec7fd5–13ec7fe3`|只证明软件 ACK compare 分支命中；wrapper 没有 success bool，不证明 PM、对象 lifetime 或 reset 排他。|
|超时/panic|render `13ec7e9f→13ec816d→13ec8176`；GT `13ec7f86→13ec817b→13ec8184`；table/其它 `13ec8189`|cold.2/cold.4/cold.3 均到已验证 stub `0xc342=_panic`；非正常返回，不能假设 unlock 会执行。|
|release|`13ec3c59: 488b3b`；`13ec3c6a: e9b98514ec`|`0xc228` 是 `_IOSimpleLockUnlock/_lck_spin_unlock`。**spinrelease != ref validity**，不等于对象/lifetime/reset 排他。|

极性以机器码为准：`bt eax,0xb` 后 `jb` 命中 bit11 置位的 local 分支；bit11 清才走 forwarding。不要把反向文字描述带入实现。

## 中断变体

`IntelAccelerator::SafeForceWakeInterrupt`：entry/fileoff `0x13ec8198`，74 B，raw SHA `f4cad0fe1c0b1e54ab8bbab6ccb92c8fdeefd2a30a34fd3b39fd6fc729c2584c`。

- `13ec819c: 488b87c0110000` 取 flags；`13ec81a5–13ec81b4` 复用 mask==0/bit12 early return。
- `13ec81b8: 0fbae00b`、`13ec81bc: 7214`：bit11 清转发 `[this+df8]+8`，`13ec81d0: ffe0` 尾跳。
- bit11 置时 `13ec81d2` 装 `ecx=2`，`13ec81dc: e999fbffff` 直接跳 multithreaded；该入口自身没有 `c222/c228`。

## 0→1、existing-reference 与释放

普通 wrapper 的计数区：`+0x12b8`（mask1）、`+0x12bc`（mask2）、`+0x12c0`（mask4/GT）。GT enable 路径在 `13ec3bc3–13ec3bd8`：旧值为 0 时设置 transition bit4（`13ec3bec: b804000000`），旧值大于 0 时 `edx` 可保持 0，走 no-transition。disable 的 1→0 在 `13ec3be2–13ec3bea`。

因此“持有软件 GT 引用”只能解释是否再次发 request，不能填成 hardware ACK、active power 或 reset exclusion。中断入口直接进入 multithreaded，也不能把普通 wrapper 的 spinlock 契约推广过去。

### 请求/ACK及出口条件矩阵（严格区分软件与设备）

|分支|GT请求|GT ACK检查|引用有效性|结论|
|---|---|---|---|---|
|mask0 / bit12置位|无local请求|无|没有新增local引用证据|不可采样|
|bit11清 / indirect forwarding|目标未知|目标未知|handler契约未知|不可采样|
|local enable，GT旧count>0|本次通常无新transition|本次不重新poll|本地计数增加；硬件/PM/reset生命周期未证|不可把复用当ACK确认|
|local enable，GT 0→1 且transition bit4保留|helper写a188|helper比较130044|正常返回保留软件引用，spinlock释放不等于引用失效|有条件的stock静态路径，不是实际设备准入|
|local disable，GT count仍>0|无release transition|本次无poll|本次引用递减，其他owner的实际状态未知|不构成新采样许可|
|local disable，GT 1→0|helper发release|helper对disable状态poll|软件最后引用释放；设备reset/PM仍独立|禁止推断采样窗口仍存续|
|GT ACK超时|有重发请求|有界循环未满足|panic无正常后置条件|失败路径，不能新增读|

已归档机器码证明render request/ACK是a278/d84，GT是a188/130044；engine-table臂依active mask和0x79 stride取request+71/ACK+75。普通shift=1构造`(0x10000+enable)<<1`并比较render/GT ACK bit1；interrupt shift=2；table臂为bit0，Framebuffer另一实现也不能混同。inner0xbb8/outer0x12c与IOPause(0x64)是调用预算实参，不擅自换算为实测毫秒。完整各指令bytes及VA/fileoff见focused-fragments中的Multithreaded与GA35既有索引。

## flags 写入者新证据

`IntelAccelerator::populateAccelConfig(IOAccelConfig*)`：entry/fileoff `0x13ec23bc`，end `0x13ec3102`，3398 B，raw SHA `e2fb4ac2934537bbb1753a5a477ec28fab26eecf86e8e3e8369b607415a9f918`。

- bit11：`13ec2474: 83e001`、`13ec2477: c1e00b`、`13ec2481: 49238ec0110000`、`13ec2488: 4809c1`、`13ec248b: 49898ec0110000`。这是 `flags+0x11c0` 清 `0x800` 后按 config bit 写入。
- bit12：`13ec2f07: 498b86c0110000`；`13ec2f12: 4825ff27fedf` 清 `0x2001d800`；`13ec2f18: 480d00900000` OR `0x9000`；`13ec2f1e: 498986c0110000`。静态上该路径将 bit12 与 bit15 置 1，但 config/调用上下文和 live receiver 未认证。
- start 在 `13ebf160: 4531ff` 后以 `13ebf171: 4c89bbc0110000` 清零 flags；同函数 `13ebf12d: 48898368140000` 建立 `+0x1468`。

这些是 flags 的可见软件赋值/读取，不给 bit11/12 取未经证据支持的 power 名称。
