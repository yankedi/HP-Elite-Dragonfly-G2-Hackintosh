# Track C correlation fixes — tested delivery receipt

**Delivered all six assigned findings: C01–C05 and Track C X01.** CPU verification passed: **40 unittest methods**, **9/9 original archived failing inputs**, **18 updated synthetic scenarios**. Original audit evidence and the historical synthetic output retain their original hashes.

## Findings → exact regressions

Test methods below are in `track-c/tests/test_correlation_fixes.py`, class `CorrelationFixes`. Their calls use the actual `correlate()` function, without replacing its validators. Paired isolated tests add all otherwise-required evidence, so a newly mandatory field cannot mask an unfixed condition.

| Finding | Original audit case(s), replayed unchanged | Exact regression method | Isolated positive/negative checks |
|---|---|---|---|
| C01 | `reset-epoch-both-missing`; `verification-string-false` | `test_c01_exact_missing_epochs_and_false_string` | `test_c01_gate_isolated_with_all_other_evidence_present`; `test_c01_zero_epoch_is_known_and_missing_one_side_is_unknown` |
| C02 | `pml4-negative`; `pml4-unaligned` | `test_c02_exact_invalid_matching_pml4` | `test_c02_root_bounds_and_types_isolated`; `test_c02_allocation_root_must_also_match` |
| C03 | `allocation-different-clock`; `allocation-different-reset-epoch` | `test_c03_exact_foreign_allocation_clock_or_epoch` | `test_c03_allocation_domain_is_mandatory_isolated`; complete-evidence positive fixture |
| C04 | `allocation-replaced-after-hang` | `test_c04_exact_replacement_after_hang` | `test_c04_replacement_has_only_sample_identity_with_complete_evidence`; `test_c04_lifetime_must_cover_hang_even_without_hang_identity_fields`; `test_c04_supplied_hang_identity_and_generation_each_bind` |
| C05 | `allocation-malformed-time` | `test_c05_exact_string_interval_is_structured` | `test_c05_malformed_candidate_does_not_abort_next_valid_identity`; `test_c05_reversed_missing_or_sample_expired_intervals` |
| X01 / Track C | `last-va-byte-allocation` | `test_x01_exact_last_va_byte_is_a_candidate` | `test_x01_valid_half_open_ends_and_adjacent_nonoverlap` |

Original-input count: **2 + 2 + 2 + 1 + 1 + 1 = 9**. The verification receipt stores the exact archived input dictionaries, original observations and new observations for every row. Source: preserved `logs/audit-parser/results.json`.

## Implemented behavior

* Known epochs/counters exclude bool, floats, strings, negative and missing values. Epoch **0** remains valid. Fault pre-reset verification and allocation identity verification require literal **True**.
* Normalized PML4 root addresses require nonzero int, 4-KiB alignment and the explicit **`root < 2^48`** input-model bound. Both hang/fault roots and the candidate root must match. GGTT does not require a PML4.
* Candidate `clock_id` and `reset_epoch` are mandatory for identity, correctly typed and equal to hang/fault domains. Identity additionally requires a typed matching allocation ID/generation, nonempty receipt label and **`identity_verified=True`**.
* Sample identity covers the complete fault sampling interval. Hang identity additionally covers **hang timestamp through sample-after**, and binds each hang allocation ID/generation field when supplied. An explicit None is not an omitted field.
* A post-hang allocation can produce **SAMPLE_ONLY** identity with complete independent evidence; `same_allocation_proved` and `hang_allocation_proved` remain false. Full continuity uses **HANG_THROUGH_SAMPLE**.
* Malformed intervals remain weak candidates with structured limitations. Non-record/invalid-range candidates have indexed `rejected_candidates` entries. Neither case aborts a subsequent valid candidate.
* Half-open ranges may end at **`2^48`**. A one-byte allocation at **`2^48-1`** is valid; overflow by one byte is rejected.
* Page overlap alone stays weak. Multiple same-page small allocations without verified identity remain candidates. Matching multiple verified identity records remains ambiguous. `exact_access_address_proved` and `hang_causality_proved` always remain false.

Input/output contracts and proof-flag semantics are documented in `track-c/correlation-model.md`. The 48-bit PML4 bound is a parser evidence-model bound, not verification that physical memory exists or that the target CPU implements that width.

## Verification evidence

Executed:

```sh
python3 -B logs/audit-correlation-fixes/verify.py
```

The verifier ran:

```sh
python3 -B -m unittest discover -s track-c/tests -v
python3 -B track-c/correlate.py
```

Results:

| Check | Actual result |
|---|---|
| Original 15 test methods, updated identity-positive fixtures | 15 passed |
| Added regression test methods | 25 passed |
| Total unittest methods | **40 passed**, exit 0 |
| Original archived Track C inputs replayed unchanged | **9/9 passed** |
| New generated scenarios | **18**, including full identity, sample-only identity and genuine negative controls |
| Protected historical files | **6/6 hashes unchanged** |
| Tested source hashes before/after verification | unchanged |

Full machine receipt: **`logs/audit-correlation-fixes/verification-run-1.json`**.

```text
8c291939a7b616ccb881dff576a60f40d02728a2a90ead3912965f021e4963bc  logs/audit-correlation-fixes/verification-run-1.json
abc1eaa59e2e0b400969ff0d89014d0e6f349b0b2daa230afc37c88966df976d  logs/audit-correlation-fixes/tests-run-1.txt
38c8bd5094c34a0fcaa936caf0fa5e0b2be54d567ca593fca80a60dd621f3251  logs/audit-correlation-fixes/samples-run-1.txt
f2f641815755d0db98dca9ab1c449ff312a1266af7225c7df17af4625a43575c  track-c/reports/synthetic-correlation-fixed.json
```

## Source hashes

Tested final files:

```text
f2c631a8e6b8aba3046d51968f50dd829f050f213a2fc844cf5dfa42d43a0da0  track-c/correlate.py
e08f479d631a9ba98dcbf985344de7930f50a3e800c1c1eb4e4c1f4ea9d8f692  track-c/tests/test_correlation.py
9933071ee57a6f3df101fcfb2d5c31f98b91c33fb339202cb11bd470c160a1bb  track-c/tests/test_correlation_fixes.py
ddf60a81d015241ae4710ce9a55602c0f3fcfc03144fba7c8a78851a97bbe009  track-c/correlation-model.md
504ac93920bdacaf27351ddb3cb3205d1c35d75965504876af3893de6d82acdc  logs/audit-correlation-fixes/verify.py
```

Pre-change hashes of the three edited existing files:

```text
c442cad43fc1a0deee8fee2b012cfbf48d1e718ccd8eaa4c11f2a389e1b109ee  track-c/correlate.py
6c334c8b836af571f03e95aa73dcaf1aecd6592737d09f0314d7f109499036e7  track-c/tests/test_correlation.py
f96e082a7769012b4f49cd83b846c3f0a13f45bf22b26e7e1c739b5145b83745  track-c/correlation-model.md
```

Preserved evidence includes:

```text
b10b8464a96a9772c9ff20af0e0afe00a8ad1325974b6745dfaa7d82783d6c17  track-a/reports/independent-parser-audit.md
06e3a0e1aad4c0a9f5829e07ab4eec74f2cbe3713a206e55572aedd103308c33  logs/audit-parser/results.json
465e41e0625e99a0f7cfc4f37cae49901a74ad1a53d2125aa15b19679f37f525  track-c/synthetic-correlation.json
```

The machine receipt records all six protected hashes, including the original reproducer and both original baseline logs. Historical failing observations remain historical failures; fixes and outcomes are separate new evidence.
