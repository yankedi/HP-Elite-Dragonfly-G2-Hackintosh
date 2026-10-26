# GT Forcewake、ACK与Runtime Power审计

**GT_ACK_AND_POWER=PARTIAL；真实读取CEC4/CEB8/CEBC仍BLOCKED。** 本文区分请求值、软件引用、硬件ACK和设备active power四个不同条件。

## 证据链

1. 固定Linux v5.15/v6.18的目标范围把CEC4/CEB8/CEBC归入GT；GA34独立审核复查过来源SHA。这是硬件域依据，不是Apple锁/电源实现证明。
2. 精确25G83本地Apple实现的mask4臂确实写a188、读130044；mask7包含mask4。[调用图](APPLE-FORCEWAKE-CALLGRAPH.md)给出路径/参数/原bytes定位。
3. 普通local helper用shift1，固定域ACK比较bit1；Framebuffer实现检查bit0。实际selector决定使用哪条协议，不能任取一个ACK位补真。
4. 原API不向当前wrapper提供可恢复的ACK成功状态。local超时路径会panic；early-return和转发仍可能绕开本地helper。仅看到原函数返回不足以建立所有分支统一的“GT已ACK”后置条件。
5. 多线程引用的spinlock在普通返回前释放；它不是reset/clear排他，也未证明是设备active power引用。
6. 精确`determinePowerDomain@13ec7b20`对CEC4/CEB8/CEBC三常量静态求值均返回mask4。它们不命中前面range，尾部unsigned减法下溢经`setae`得到1，`lea ecx,[rcx+rcx+2]`产生4，且都不等于特例1082c0，`cmovne`选择4。逐步说明在`analysis/target-selector-derivation.json`。这进一步支持Apple本版自身将三地址归GT，但仍未调用该helper或证明live分支契约。

## 请求/ACK状态机（静态局部，不是实机观测）

```
API entry
 ├─ mask0/flag12 → return (本地未作请求)
 ├─ flag11 clear → indirect handler(bool,mask) (契约未知)
 └─ flag11 set → spinlock → per-domain refcount transition
      ├─ no hardware transition → trace/unlock → return
      └─ transition → request write → IOPause → ACK loop
          ├─ compare matches → remaining domains → trace/unlock → return
          ├─ countdown expires, budget remains → reissue
          └─ terminal timeout → cold panic (非正常返回)
```

不把“内部count为正”视为硬件ACK实读，也不把“没走panic”视为电源/全局排他证明。flag11/12的真实设备状态含义、写入者与生命周期尚未完整追溯，不能给它们取一个未经证据支持的power状态名。

## 各关键条件的最终判定

|条件|判定|理由|
|---|---|---|
|精确磁盘代码/映像身份|VERIFIED|KC三方SHA、UUID/loaded前后元数据一致；live bytes未认证|
|Apple local mask4→GT请求/ACK寄存器|CONFIRMED（静态路径范围）|a188/130044字节，固定源名称交叉|
|当前设备实际branch/handler|UNKNOWN|未读取内存feature/table指针；普通ioreg查询为空|
|采样瞬间GT持有和ACK成功|UNKNOWN|wrapper只记请求mask；无已证明跨所有分支的后置条件|
|active-power所有权|UNKNOWN|局部函数没有直接证明更外层PM引用，未知不等于认定没有|
|reset/clear共用排他|UNKNOWN|内部spin仅覆盖计数/ACK，返回即释放；全局入口未闭合|
|MMIO映射生命周期/范围|PARTIAL|+1270基址字段由精确代码验证，但非空不证明extent或teardown安全|
|CEC4/Data device侧一致性|UNKNOWN|软件epoch测试不证明硬件latch、ABA或多fault覆盖|

## 明确不能使用的推论

- “Linux属GT且Apple7含GT，所以当前Hook安全”：跳过了dispatch、ACK、active power和reset排他。
- “SafeReadRegister32只读”：它先写Forcewake请求/等待ACK，最后释放；这些行为会改变真实GPU状态，本轮未调用。
- “内部spinlock保护了采样”：post-original wrapper恢复时该锁已释放。
- “赋值knownActivePower=true就能让mock通过”：只能伪造调用者声明，不能产生真实引用。
- “再次读ACK验证就行”：这本身是新增真实MMIO探测，既未授权也不能替代更外层power/lifetime契约。

## 对三个目标寄存器的决定

CEC4、CEB8、CEBC分别及整体tuple都保持**BLOCKED**。本轮没有读取任一真实目标寄存器，没有为它们安装reader或把现有旧4094映射成Gen12 fault。下一步只见[NEXT-EXPERIMENT.md](NEXT-EXPERIMENT.md)的离线前提。
