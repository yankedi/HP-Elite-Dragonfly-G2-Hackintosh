# Forcewake、Power及锁序审查

## 能确定的Linux域

v5.15 `intel_uncore.c:1219`的Gen12表，`:1253–1256`为`0xB400–0xCFFF → FORCEWAKE_GT`。TGL12.0走`:2122–2125`，不是XeHP/DG2表。v6.18`:1345,1379–1382,2440`交叉一致。CEB8/CEBC/CEC4全部在此区间。**需要GT域，不能仅假定Render窗口足够。**

`intel_uncore_forcewake_get`使用独立uncore锁、RPM assert/refcount；内部先request再等待ACK（v5.15函数 `fw_domain_wait_ack`/`fw_domains_get`），超时日志不等于已成功获得域。使用FORCEWAKE_ALL可以覆盖GT但不等于更安全：新增获取/等待/释放会影响时序和锁依赖，本轮不实现真实序列。

## 现有GA3.3

实查 `/tmp/opencode/ga33/kern_igfx.cpp:1455–1517`：

1. wrapDoHangAnalysis在调用原函数前置hangInProgress，原函数返回后清。
2. wrapSafeForceWake先调用原SafeForceWake（void），再在enable且domain==7窗口捕获。
3. 现有源码注释将7称作render；**目前未有当前25G83二进制独立证明该数字究竟代表哪些域/掩码**，不能把Apple7直接等同Linux枚举值。
4. 没有返回ACK成功状态，也没证明GT域refcount、runtime-power、reset互斥与线程/中断条件。
5. hangCapture直接volatile读已列旧寄存器；本轮不扩该数组。SafeRead映射+0x1270只是已有源码注释/实现假设，不能代替当前binary验证。

## 门禁结论

**Linux required domain已确定；Apple Hook安全接入仍BLOCKED。** 新独立核心只接受mock Reader/guard，没有真实MMIOprovider，不连原hook。必须先独立证明：当前exact-binary对应的domain映射与ACK、设备active电源引用、reset/clear互斥锁和锁序、允许上下文及稳定MMIO映射生命周期。

mock中的“GT已ACK、锁已持有”仅是调用者声明；测试通过不能建立真实驱动持锁证明。epoch前后不变可拒绝观察到的竞态，不能单独替代阻止read与reset重叠的真实锁。失败立即停止后续读取，无无限重试、无重新forcewake、无reset等待循环。
