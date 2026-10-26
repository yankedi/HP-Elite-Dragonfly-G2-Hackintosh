# Fault–Command证据关联模型

实现 `correlate.py`。修复后的正负样本由 `python3 -B track-c/correlate.py` 写入 **`track-c/reports/synthetic-correlation-fixed.json`**；18 个场景全部是合成 mock，不是实机 fault 捕获。原 `track-c/synthetic-correlation.json` 与 `logs/audit-parser/` 保留为历史证据，不覆盖。

```text
Hang(sequence, context, PML4, clock, reset_epoch, timestamp)
 -> Fault(raw decode, status, pageVA, address-space, read-before/after, same sequence/epoch)
 -> Batch / Shader / Surface / PostSync allocation candidates
  -> allocation-id + mapping-generation + clock/reset domain + lifetime + verified identity receipt
  -> SAMPLE_ONLY identity / HANG_THROUGH_SAMPLE identity
```

## 输入契约

* `hang_sequence`、`context_id`、`reset_epoch`、时间戳与 `mapping_generation` 必须是非负 **int**，不接受 bool、float、字符串。0 是已知值；缺失/None 不是已知值。
* `clock_id` 必须是非空字符串；hang 与 fault 相同。`fault.valid` 与 `fault.pre_reset_epoch_verified` 必须严格为 **True**；`1`、`"true"`、`"false"` 都不是布尔证明。
* 故障页 VA 为 4-KiB 对齐的 `[0, 2^48)` 地址。`hang.timestamp <= fault.sample_before <= fault.sample_after`，两侧 reset epoch 必须已知且相同。
* PPGTT 的 hang、fault、allocation PML4 必须是同一个非零、4-KiB 对齐的 int，范围 **`0 < root < 2^48`**。输入是已归一化的物理根地址，不是带 PCID/控制位的 CR3。这个固定 48-bit 证据模型只做边界检查，不证明对应物理内存存在或该平台的实际物理地址宽度。
* GGTT 不需要 PML4，也不从缺失 PML4 编造 PPGTT 身份；hang/fault context 仍需匹配才能提升身份等级。
* allocation 的 `base,size` 为 int，`size > 0`，半开区间满足 **`0 <= base < base+size <= 2^48`**。exclusive end 可以等于 `2^48`；最后一个 VA 字节是合法候选。
* 身份证据必须同时包含 allocation/fault 一致的 `allocation_id`（非空字符串或非负 int，类型也一致）、`mapping_generation`、非空字符串 `identity_evidence`（凭据引用）和严格为 **True** 的 `identity_verified`。
* allocation 的 `clock_id`、`reset_epoch` 是身份提升的**必需证据**，必须类型正确且与 hang/fault 相同。跨时钟/跨 reset 的数值相似区间不能比较为同一生命周期。
* allocation 的 `valid_from,valid_to` 必须为有序非负 int。缺失是未证明；类型错误/倒序是结构化 `INVALID_ALLOCATION_INTERVAL`。记录不是 dict 或地址区间非法时，记录在 `rejected_candidates`，继续处理其他候选。

`identity_verified=True` 是可信采集/归一化流程传入的显式断言，不是本函数验证凭据真实性或读取硬件的结果。函数验证这些元数据是否齐全、一致、类型正确；它不会把一个 truthy 凭据字符串自动当成已验证证据。

## 候选与身份等级

```text
UNAVAILABLE
 -> TEMPORAL_UNPROVEN
 -> ADDRESS_RANGE_CANDIDATE
 -> ADDRESS_SPACE_MATCH
 -> SAMPLE_ALLOCATION_IDENTITY_MATCH
 -> ALLOCATION_IDENTITY_MATCH
```

先验证 fault 成功、valid、页 VA 与 hang/fault 时间/epoch/clock。缺少这些证据时不作地址归属。通过后，保留与 fault **整页**有重叠的 allocation 作为弱候选；缺少 allocation domain/receipt/lifetime 时仍只是范围或地址空间匹配。

* **Sample identity**：生命周期覆盖完整 `[sample_before,sample_after]`，且地址空间、allocation ID、generation、domain、已验证凭据全部一致。
* **Hang-through-sample identity**：另要求生命周期覆盖 **`[hang.timestamp,sample_after]`**。如果 hang 提供 `allocation_id` 或 `mapping_generation`，每个已提供字段必须类型正确且与 allocation 一致；显式 None 不当作未提供。hang 未提供这些可选字段时，凭完整生命周期与同代映射凭据检查连续性。
* hang 之后才创建的新 allocation，或与 hang 提供的 ID/代次冲突的 allocation，只能保留 `SAMPLE_ONLY` 身份，不能成为 hang 的同一 allocation。
* 多个符合 sample identity 的记录（即使只有其中一个跨越 hang）保留 `AMBIGUOUS_ALLOCATION_ALIAS`，顶层两种身份证明都为 false。

结果字段：

| 字段 | 含义 |
|---|---|
| `sample_allocation_proved` | 恰好一个候选满足 sample-time 身份条件 |
| `hang_allocation_proved` | 该唯一候选也满足 hang-through-sample 连续性 |
| `same_allocation_proved` | 兼容旧调用者，严格等于 `hang_allocation_proved` |
| `identity_scope` | `NONE` / `SAMPLE_ONLY` / `HANG_THROUGH_SAMPLE` |
| 候选 `sample_identity_match,hang_identity_match` | 本条记录满足相应证据条件；不代表顶层 alias 已排除 |
| `range_overlap_only` | 没有额外的 sample/hang 身份证据时为 true；false 也不证明页内精确访问偏移 |
| `exact_access_address_proved` | 始终 false；fault 寄存器只有页地址 |
| `hang_causality_proved` | 始终 false；地址/身份匹配不是 hang 因果证明 |
| `limitations` | 顶层与各候选的明确缺失/冲突/非法证据码 |
| `rejected_candidates` | 无法形成合法范围候选的输入下标与错误码 |

即使小 allocation 有身份凭据，本函数也不推导页内的确切访问字节。没有身份凭据的多个同页 post-sync/surface 范围继续保留为弱候选。

当前 THAG 没有 allocation generation 与原 PTE，且没有真实 Gen12 fault 快照；这次合成正例不改变该事实。

## 检查与回执

```sh
python3 -B -m unittest discover -s track-c/tests -v
python3 -B logs/audit-correlation-fixes/verify.py
```

`test_correlation_fixes.py` 覆盖原独立审计 C01–C05 和 Track C X01 的 **9 份精确失败输入**，并使用补齐所有其他必需证据的正/负对照逐个隔离修复条件。还检查 alias、GGTT、同页弱候选、边界、输入不变与后续有效候选不被畸形候选中止。

新日志与逐项 findings→tests/SHA-256 回执在 `logs/audit-correlation-fixes/`；交付说明在 `track-c/reports/`。验证器直接读取原审计 JSON 的 9 份输入再调用真实 `correlate()`，独立核验旧证据 hash，绝不重写原审计回执。
