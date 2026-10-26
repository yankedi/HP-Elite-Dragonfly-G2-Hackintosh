# GA3.6 最终报告：CAS源级修复已验证；真实Fault采样仍不放行

**本轮完成可得GA33源码的CAS门控/失败终态修复、默认关闭隔离writer/core、准确25G83的有界GT/PM/reset路径分析与九条件准入。完整XNU/GPU捕获链未认证，三个Fault寄存器不能被称为一致快照。**

## 11项状态（严格作用域）

```text
CAS_WRITER_FIX = VERIFIED
CAPTURE_PIPELINE = PARTIAL
APPLE_GT_LIFETIME = PARTIAL
RUNTIME_POWER = PARTIAL
FORCEWAKE_ACK = PARTIAL
RESET_CLEAR_ORDER = PARTIAL
FAULT_TUPLE_CONSISTENCY = UNKNOWN
SAFE_SAMPLING_POINT = BLOCKED
HOOK_ABI = PARTIAL
FAULT_DIAGNOSTIC = MOCK_ONLY
READY_FOR_HARDWARE_APPROVAL = NO
```

CAS的VERIFIED指**明确缺陷的源级修复及实际函数体mock并发验证**，不是当前运行kext认证。PM/ACK/Reset的PARTIAL是“静态路径已恢复”，实际持有/成功/排他仍UNKNOWN。MOCK_ONLY包含已实际离线编译测试的实现与Mach-O对象，不包含完整可部署kext或真实MMIO backend。

## 验收15问

1. **GA3.3 CAS Writer缺陷是否完全修复？** 已确认的门控错误在GA36独立源码中修复，并将失败作为2终态，先发布error再释放owner，缺uio_free时在O_TRUNC前拒绝。不可宣称完整旧捕获链修复；其volatile producer与生命周期尚未集成，candidate强制hangDump=0。详见track-a/CAS-ROOT-CAUSE.md、CAS-FIX.patch。
2. **修复前后有确定性反例吗？** 有。直接提取原函数体：原首次CAS成功writes0/flag1，两个失败者同时写同buffer(maxConcurrent2)；修正后2/16线程仅winner写(max1)，错误保持flag2且不重试。不是手抄一个替代算法测试。
3. **诊断快照能否并发完整写出？** 隔离Pipeline在稳定输入、append-only buffer和可靠executor契约下可：release/acquire发布，唯一writer、pending握手、递增watermark、immutable snapshot；实际原v3布局经CPU核心写入本地文件并解析往返，Clang/GCC逐字节一致。真实XNU ThreadCall、GPUproducer及断电文件事务未闭环，整体PARTIAL。
4. **GT引用生命周期是否明确？** 部分。普通local分支+12C0计数及0→1/1→0 transition、+1468锁，start/stop初始化/清零已恢复；转发表、PM、reset、interrupt和活跃对象的统一owner契约未证。
5. **domain7实际取得GT吗？** 7=1|2|4且静态GT路径成立，目标CEC4/CEB8/CEBC的determinePowerDomain静态均4。实际feature/selector/forwarding、early-return、count reuse及设备请求/ACK没有执行证据，不能答“已实际取得”。
6. **Runtime Power前提可靠吗？** 尚不可靠。本轮定位setPowerState、systemWillSleep、PowerWell、start/stop字段，busy lock不等于forcewake spinlock；没有证明采样持有active-power引用且排除sleep/stop/free。
7. **选定点能确认ACK吗？** 未选出可放行点。a188/130044 GT request/ACK及shift/轮询/panic恢复不等于所有正常return均ACK成功；zero/flag12/forward/no-transition出口不同，void API没有成功返回值。
8. **Reset与Fault Clear顺序明确吗？** 局部明确、全局未明。debug诊断与Channel Restart内诊断是两类语境；旧4094 clear在941C reset请求之后的等待循环，不是清除先于reset。Gen12 latch/clear及其他reset入口的共同锁/epoch未知。
9. **更安全的点存在吗？** A晚期SafeForceWake、B更早gather/doHang、C已有GT引用路径已逐项比较。更早不等于PM或GT；持软件GT count不等于ACK/Reset排他；三者目前均BLOCKED。没有通过扩大锁范围制造“安全”。
10. **三个寄存器是一致快照吗？** 未证明。新增同一次capture中CEC4=A、DATA0=B、DATA1=A的mock反例：epoch/token保持不变，核心仍Complete+StableEpoch且derive可用，却是A/B都不是的混合tuple；前后CEC4相同也无法排除ABA。保留raw并报告一致性未知。
11. **候选Hook ABI精确验证了吗？** stock入口/寄存器/完整指令覆盖前缀可核验。最小5字节跳转实际需6字节指令；doHang最小14需16字节、SafeWake为14字节。mangled name不能证明完整类型；live patched bytes、trampoline、重定位/并发入口未认证，因此PARTIAL。
12. **FaultRecord能可靠关联Hang/context/PML4吗？** 不能。108B v1仅有caller-provided boot/hang/caller/epoch/token，不含context/PML4/ring-head/generation；格式合法不能认证这些声明或同次GPU故障。原捕获的context关联假设仍须独立证明。
13. **生成默认关闭候选了吗？** 有源级最小修正和无硬件隔离writer、原字节兼容GA34核心及九条件gate；均实际离线构建测试。没有新增真实reader或接入真实GPU backend，完整kext未构建/链接/安装。
14. **剩余安全阻塞？** live代码/ABI与receiver、GT ref/ACK和power ownership、全局reset/clear排他、设备tuple latch，以及旧全局capture重入、queued callback teardown、可靠调度、O_TRUNC损坏旧证据、永不返回IO。CSB/TraceDisk旧路径另有审查问题，未扩大本轮修复或扰动既有逻辑。
15. **值得申请下一次只读实机吗？** 当前不值得申请三寄存器采样；关键条件未证，应先完成NEXT-EXPERIMENT列出的最小离线契约/适配工作。未来提案须另行明确授权，不自动升级审批。

## 本轮新增证据

- 原GA33源码hash `6f2f73e5d404c4c5daf8294f6d8f59ae5d02fb040e24fbe99713949750ede395`；GA33实物kext本机缺失。GA31/32只有二进制与差异等间接来源，不能推广当前运行缺陷。GA32b THAG `1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333`保留有效。
- SystemKC `fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`；24个函数、72caller、197field/lock fragments与原KC逐字节核验。没有重做GA35全量11416片段扫描。newflags写入与start/stop/PM定位见track-b五报告及analysis。
- GA34 108B核心/boottext副本逐字节一致。九条件四值gate只有全部VERIFIED且enable才allow；当前3CONDITIONAL+6UNKNOWN，DENY。完整组合测试检验布尔门逻辑，**不代替任何设备安全证明**。
- 独立审查F6发现retry reasons被bzero抹掉，GA36 helper现保留先前理由；attempt1重新清空，2–8回归验证。其他实际集成风险保持明确阻塞。

## 验证、限制与持久交付

实际命令/日志/覆盖边界见track-a/TEST-REPORT.md、track-c/results.json、logs/track-b-main-verification.txt、audit/writer-review/。Clang/GCC release和ASan+UBSan、实际函数体故障注入、并发、原布局文件/codec回归通过；不是TSan或GPU测试。仓库make check通过。

上游ThreadCall契约固定在reference/thread-call，公开XNU12377.121.6不是目标12377.161.14，不能伪称匹配25G83。cancel_wait不阻止后续submit，quiescent不覆盖尚未开始的raw callback。

所有交付在本私有目录。历史源码/捕获/清单的原字节保持；一次子进程bytecode副作用已保留并纠正，详见audit/bytecode-sideeffect，不将其描述为从未发生。没有SSH、GPU实验、新增真实MMIO、kext部署、IMG/USB/EFI/系统/固件变更或公开上传。完整迁移/封存核验/回滚步骤见README、NEXT-EXPERIMENT与manifest。
