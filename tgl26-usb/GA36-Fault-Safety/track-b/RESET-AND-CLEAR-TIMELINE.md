# RESET-AND-CLEAR-TIMELINE：reset、bypass 与旧 4094 clear

## 坐标与来源

来源为 GA35 sealed accurate25G83：SystemKC SHA `fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`，ICL UUID `B7DF3049-D3A9-3070-9843-6E5AE47673D7`。以下静态路径不声称实际 receiver、实际执行线程或硬件 latch。

## reset 调用链的新有界闭环

1. `IOAccelFIFOChannel2::restart@0x145869fe`（850 B，raw SHA `08a9dae1c2c7555ebfc092df88a19354a68c9950b502f6cc415f4629580fb9bc`）在 `0x14586b02` 调 receiver vptr+`0x208`，随后 `0x14586c44` 调 `reportGPURestart@0x145bf782`，较后 `0x14586d27` 调 receiver vptr+`0x200`。因此诊断可能在 restart 前/中，不能标一个统一 reset-safe 点。
2. ICL 静态 vtable 候选：`__ZTV18IGAccelFIFOChannel` slot `0x208`→`getHardwareDiagnosisReport@0x13ee5e50`，slot `0x200`→`resetHardwareAndReplay@0x13ee5e08`；IOAccelFamily2 的对应静态 slots 是 pure virtual，live receiver 未知。
3. `getHardwareDiagnosisReport` 直接 `call doHangAnalysis@0x13edcdd2`（`0x13ee5e64`），而 `doHangAnalysis` 的两个可见 caller 是 `debugGraphicsEngine@0x13edcd92` 与 `getHardwareDiagnosisReport`。这解释了 A/B 两种 reset 语境，但不证明同一运行实例命中哪一条。
4. `doSchedulerReset@0x13edca80` 是 38 B thunk：`0x13edca99` 取 scheduler vptr+`0x190`，`0x13edcaa4: ffe1` 间接尾跳。`__ZTV12IGScheduler5` 的静态候选 slot `0x190`→`processGPUReset@0x13ed1ed6`；receiver 仍 unresolved。
5. `processGPUReset@0x13ed3c92` 调 `beginReset@0x13f13832`（`0x13ed3d21`），结束调 `endReset@0x13f1390c`（`0x13ed3dde`），中间还调用 ring reset/恢复路径；这只是静态先后，不是全局锁序。

## `resetGraphicsEngine` 的 bypass 与 4094 clear

目标 `IGHardwareRingBuffer::resetGraphicsEngine@0x13edcaa6`，748 B，raw SHA `35be8e2cc173c304ed9cb5e8a351ad740a16251c7b2a2fa0d1ba7f42d15353f1`。

|阶段|精确字节/地址|判定|
|---|---|---|
|scheduler 状态分支|`13edcacd: ff9058010000`，`13edcad3: 84c0`，`13edcad5: 744b`|vptr+0x158 状态为 false 时跳过前面的 reset-register 诊断段；不等于没有其它 reset。|
|进入 forcewake|`13edcb3f: be01000000`，`13edcb44: ba07000000`，`13edcb49: e8a86efeff`|调用 `SafeForceWake(true,7)`；其内部 local lock 在正常 return 前释放。|
|绕过实际 reset 写|`13edcc2b` 检查 `+0x78` list；空路径 `13edcc5f` 后 `13edcc6c: e8856dfeff` 调 `SafeForceWake(false,7)`，`13edcc71` 跳 `13edcd80` return|存在不写 `+0x4a08/+0x941c` 的静态返回分支；不能假设所有执行都发 actual reset。|
|发出旧 reset 请求|`13edcc7a: c780084a000004000400` 写 `[MMIO+0x4a08]=0x40004`；`13edcc87: 89881c940000` 写 `[MMIO+0x941c]=resetMask`|这是旧代码路径的 request，不是 CEC4/CEB8/CEBC 证明。|
|旧 4094 clear|`13edcc98: 8b811c940000` 读 941c；`13edcc9e: 8b9194400000` 读 4094；`13edcca4: f6c201` 检 bit0；`13edcca9/cb3: c78100410000b1b1f0f0` / `c78104410000b2b2f0f0`；`13edccc0: 899194400000` 写 `4094=old&~1`|clear 发生在已写 941c 后的等待循环内；不是“先 clear 再 reset”，也不能把 4094 解释成 TGL fault latch。|
|等待/退出|`13edccd9: e83af612ec`=`assert_wait_timeout`，`13edcce0: e881f612ec`=`thread_block`，`13edcce9: 75a9` 回读循环；末端 `13edcd79: e8786cfeff` `SafeForceWake(false,7)`|存在阻塞和 forcewake release；未证与所有 PM/interrupt/reset 入口共享排他。|

## vtable 与 unresolved-indirect 清单

- `__ZTV20IGHardwareRingBuffer` slot `0x168`→`resetGraphicsEngine@13edcaa6`：format-11 静态候选，非 live receiver 证明。
- `__ZTV12IGScheduler5` slot `0x190`→`processGPUReset@13ed1ed6`：`doSchedulerReset` 的静态候选。
- `IOAccelFIFOChannel2::restart` 的 `vptr+0x208`、`vptr+0x200`，以及 forwarding `[this+df8]+8`、`resetGraphicsEngine` 末端 vptr+0x190，均保留 unresolved receiver。
- 不将 `cache-fixups.json` 的静态 target、vtable slot 或 indirect edge 写成实际调用；不伪造 receiver。

## 目标寄存器与安全结论

本轮没有读取 CEC4、CEB8、CEBC，没有安装 clear/reset hook，也没有把旧 4094 clear 当作 Gen12 fault 清除。实际 reset 排他、fault latch 生命周期、PM/lifetime 和 live receiver 仍 UNKNOWN；因此任何真实采样点仍 BLOCKED。
