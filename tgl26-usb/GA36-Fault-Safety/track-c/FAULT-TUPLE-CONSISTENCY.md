# Fault Tuple 一致性：StableEpoch 不等于设备侧同代

**结论：`StableEpoch` 只表示 mock observer 在六次观察中报告 epoch/token/power/GT/ACK 未变。它不证明 CEC4、CEB8、CEBC 三次读取属于同一个设备侧 fault tuple，也不排除 mutation/ABA。因此 `FaultTupleConsistencyEstablished` 必须独立 VERIFIED；否则九条件门拒绝。**

## 1. 本文使用的 tuple 定义

在本轮 108B wire 内，可比较的原始 tuple 是：

```text
tuple = (rawFault, rawData0, rawData1)
context = (resetEpoch, exclusionToken, sequence)
```

- `rawFault` 来自 `0xCEC4`，`rawData0` 来自 `0xCEB8`，`rawData1` 来自 `0xCEBC`。
- `raw*` 是原样保留的 DWORD；即使读取失败，失败 callback 返回的字也可能被保留，但对应 validity 位必须为 0。
- `resetEpoch`/`exclusionToken` 是调用者声明，不是硬件 epoch。
- 108B wire **没有** ContextID、PML4、RingHead、allocation generation。本文不新增这些字段，也不把页地址匹配当作 hang 因果。

`derive()` 只在记录为 `Complete`、fault-valid、DATA1 MBZ 为零时给出 48-bit 页地址。两个都“可派生”的记录仍可能对应不同设备状态。

## 2. GA3.4 模型实际证明了什么

采集顺序是：

```text
observe -> read CEC4 -> observe
observe -> read CEB8 -> observe
observe -> read CEBC -> observe
```

每次 `observe` 返回同一个 `EpochObservation`，采集器比较：

- `resetting == false`
- `epoch == Request.resetEpoch`
- `exclusionToken == Request.exclusionToken`
- `knownActivePower == true`
- `forcewakeHeldDomains & DomainGT`
- `forcewakeAckDomains & DomainGT`

全部通过后，`Complete` 记录才置 `StableEpoch`。但 observer 是外部 callback；模型只能看到它**报告**的值。它不能：

- 拦截一次 MMIO 读取中的设备异常；
- 在两读之间强制重新采样设备 latch；
- 观察到 callback 没有报告的 mutation；
- 区分“设备值从 A 变 B 再变 A”与“设备值一直是 A”；
- 证明 epoch/token 来自真正的全局 reset 排他域。

所以正确的表述是：

```text
StableEpoch == observer-reported epoch/token/power/GT/ACK unchanged
StableEpoch != device-side tuple coherence
```

## 3. 跨 capture A/B/A：epoch 不是唯一 fault generation

`tests/test_evidence_gate.cpp::same_epoch_aba_is_not_tuple_coherence` 用一个 Collector 连续采集三次：

|capture|sequence|resetEpoch|token|raw tuple|validity|
|---|---|---|---|---|---|
|1|1|3|41|A|Complete + StableEpoch|
|2|2|3|41|B|Complete + StableEpoch|
|3|3|3|41|A|Complete + StableEpoch|

三次的 `hangId` 递增、`monotonicNs` 递增，`bootId`/`callerId` 相同，因此都通过 GA3.4 的 identity/timestamp 检查。三次的 observer 都返回同一 epoch，所以三次都有 `StableEpoch`；但 `rawFault` 的序列是 **A → B → A**，两个不同 tuple 的 `derive()` 还给出不同的 48-bit VA。

**这个测试证明的是：**

- epoch/token 不是唯一的 fault generation 计数器；三个不同的 Complete 样本可以共享同一 epoch；
- `Complete`/`StableEpoch` 不会自动产生 `FaultTupleConsistencyEstablished`；
- `callerClaims == RequiredClaims` 也不会；
- 若把 `FaultTupleConsistencyEstablished` 设为 `UNKNOWN`、`CONDITIONAL` 或 `FAILED`，九条件门都拒绝；只有设为 `VERIFIED` 且其余八项也 VERIFIED、`enable=true` 时才允许。测试逐一断言了这四种状态。

**这个测试本身不证明单次 capture 内的 tuple 被撕裂。** 三次 capture 是三个独立样本；它们之间的 A/B/A 只说明 epoch 不唯一，不能单独当作 torn-tuple 证据。真正的最小 torn-tuple 模型在下一节。

## 4. 单次 capture 内 mutation：确定性 torn tuple

`tests/test_evidence_gate.cpp::within_capture_mutation_tears_tuple_in_mock` 在一个 capture 内确定性地改变 mock 设备状态，并显式记录子读取事件时间线：

|事件|动作|返回值/状态|
|---|---|---|
|O1|observer #1|epoch=3, token=41|
|R0|read `CEC4`|`A.fault`|
|M0|mock 设备 mutation → B|—|
|O2|observer #2|epoch=3, token=41|
|O3|observer #3|epoch=3, token=41|
|R1|read `CEB8`|`B.data0`|
|M1|mock 设备 mutation → A|—|
|O4|observer #4|epoch=3, token=41|
|O5|observer #5|epoch=3, token=41|
|R2|read `CEBC`|`A.data1`|
|O6|observer #6|epoch=3, token=41|

断言结果：

```text
record.validity == CompleteValidity
record.validity & StableEpoch != 0
raw tuple = (A.fault, B.data0, A.data1)
raw tuple != A
raw tuple != B
derive(record).available == true   // 这组混合值恰好仍可派生
```

这证明：**一次 `Complete` + `StableEpoch` 的采样可以持有混合 raw tuple；derivable 也不等于原子一致。** 测试只断言 mock 事件时间线和 raw 值，不声称真实设备发生了该 mutation，也不把 derivable 当作 coherence。

同一场景还提供了 mock-only 的 CEC4 before/after 检查：`faultBefore == A.fault` 且 `faultAfter == A.fault`，但 `DATA0 == B.data0`、`DATA1 == A.data1`。因此“重复读 CEC4 都是 A”不能证明 tuple 未被撕裂，也不能证明 ABA 不存在。该 before/after 只是 mock 内部记录；**core 仍然只调用 read 三次，没有新增真实读取，也没有修改 108B wire。**

## 5. 独立 VERIFIED 需要什么（未实现，未授权）

本轮没有实现、也没有假装实现以下任一项：

- 设备侧 fault latch/clear 协议的完整时序证明；
- 三次读取之间不被 clear/reset 覆盖的硬件保证；
- 独立于 observer 的 tuple 重读/交叉校验；
- 真实 MMIO 映射生命周期、异常和电源副作用证据；
- 同次 hang 的 context/PML4/ring generation 关联（108B 也没有这些字段）。

这些只能作为未来实验假设，不能由当前 mock 测试升级为 `VERIFIED`。任何“再读一次 ACK/再读一次 fault 就一致”的方案都是新增真实 MMIO 探测，既未授权，也不能替代更外层的 power/reset/lifetime 契约。上面的 within-capture 测试只证明模型能表现 torn tuple，不证明真实设备行为。

## 6. 与 admission gate 的关系

`FaultTupleConsistencyEstablished` 是九条件之一，默认 `UNKNOWN`。门的准入逻辑与 tuple 证据独立：

```text
allow == enable && CorrectBinary==VERIFIED && CorrectHookABI==VERIFIED
      && CorrectGTDomain==VERIFIED && RuntimePowerHeld==VERIFIED
      && ForcewakeReferenceHeld==VERIFIED && ForcewakeACKConfirmed==VERIFIED
      && ResetExcluded==VERIFIED && MMIOReadSafe==VERIFIED
      && FaultTupleConsistencyEstablished==VERIFIED
```

当前项目裁定中该项为 `UNKNOWN`，所以整体 admission 为 DENY。`results.json` 的 `project_evidence_assessment.blocking_conditions` 明确列出它。

## 7. 证据位置

- 测试源码：`tests/test_evidence_gate.cpp`
- 门实现：`source/kern_tglfault34_gate.hpp`
- 实际运行日志：`logs/build/*-gate.run.log`
- 实际结果：`results.json`
- 历史静态审计：`../../GA35-Driver-Reversing/GT-FORCEWAKE-AUDIT.md`、`../../GA35-Driver-Reversing/FAULT-CAPTURE-SAFETY.md`（只读引用）

**FAULT_TUPLE_COHERENCE=UNPROVEN；WITHIN_CAPTURE_TORN_TUPLE=MOCK_MODELED；STABLE_EPOCH_DOES_NOT_IMPLY_COHERENCE=CONFIRMED_BY_MODEL_TEST；HARDWARE_APPROVAL=NO。**
