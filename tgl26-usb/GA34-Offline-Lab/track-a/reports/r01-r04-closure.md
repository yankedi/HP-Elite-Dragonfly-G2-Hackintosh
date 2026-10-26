# R01–R04 independent closure confirmation

**Disposition: R01, R02, R03 and R04 are closed for the reviewed implementation
and bounded counterexamples. All 13 exact prior defect probes now produce the
required corrected result or structured refusal. All 35 confirmation checks
and all 64 existing Track A tests pass. No regression was reproduced.**

This is a new CPU-only confirmation record. The earlier review, snapshots,
results and manifests remain historical evidence and were not overwritten.
No implementation/test, frozen input, candidate binary, production receipt,
Track B/C, hardware, VM, driver or GPU operation was performed by this reviewer.

## Reviewed identity and evidence

Reviewed SHA-256:

```text
8502fc96beebbf04b44a5d0099a97c28d9e08ef7a8d19e5436a19919ae76f11b  track-a/command_stream.py
f53c487236f9c1ecbb089020b33b9a0246ff5ed8b229462585b1c193bd77b9f6  track-a/normalizer.py
b0477cb8d3a53b853bd6e5d61c3778a34f105baa9664fc6b358d97d42a77b369  track-a/tests/test_normalizer.py
```

New confirmation runner:

```sh
python3 -B logs/command-review-closure/confirm.py
```

Each invocation creates a **new timestamped directory**; it does not rerun the
old reproducer or replace old run evidence. The executed run is:

`logs/command-review-closure/run-20261018T060428.205547Z/`

It returned exit **0**, with:

```json
{
  "tests": {"run": 64, "failures": 0, "errors": 0},
  "exact_prior_probe_count": 13,
  "confirmation_count": 35,
  "all_confirmation_checks_pass": true,
  "implementation_tests_inputs_unchanged": true,
  "all_prior_evidence_preserved": true
}
```

Evidence files in that directory:

* `results.json`: every exact old input / new guard, actual outcome, assertion,
  watched-file hashes, and hashes of all 14 prior evidence files.
* `summary.json`: compact executed-run summary and implementation hashes.
* `track-a-tests.txt`: independent execution of all 64 existing methods.
* `command_stream.snapshot.txt`, `normalizer.snapshot.txt`: exact code executed
  in memory, with original `__file__` paths retained for fixture resolution.
* `candidate-A-summary.json`, `candidate-B-summary.json`: fresh in-memory
  reconstruction summaries; production candidates/receipts were not replaced.

`logs/command-review-closure/manifest.sha256` seals this report, the runner and
the run evidence. The recorded primary-agent test log
`logs/track-a-r01-r04-fixes.txt` was also preserved unchanged; confirmation did
not rely on its reported outcome.

## Finding-by-finding closure

| Finding | Exact prior probes | Current independent result | Disposition |
|---|---:|---|---|
| R01 — conditional XP extent | 2 | Ordinary seven-DWORD draw is format-checked, remains semantic UNKNOWN, and has three `ABSENT_CONDITIONAL_DEFAULT_ZERO` fields with value 0 / raw null. All four actual Candidate B draws now format-check without the false truncation. | Closed |
| R02 — weak draw checker | 5 | Both LRI substitutions reject `INVALID_DRAW_OPCODE_OR_MODE`; unsupported mode rejects `UNKNOWN_DRAW_CANDIDATE`; A/B trailing unknown DWORDs reject `INVALID_DRAW_ENVELOPE`. | Closed |
| R03 — invalid study target VAs | 4 | `-1`, `2^48`, and `2^80` reject `INVALID_STUDY_BASE`; `2^48−4` rejects `TARGET_ALIGNMENT`. | Closed |
| R04 — forged/contradictory study inputs | 2 | The exact 167-packet forged-name BBS construction and the exact genuinely reparsed stencil-enabled mutation both reject `STUDY_INPUT_PROVENANCE_MISMATCH`. | Closed |

These are the **same 13 cases** selected by `category=new_defect` from
`logs/repaired-command-review/results.json`; the new runner asserts that count.
The altered WM_DEPTH_STENCIL bytes additionally reproduce the prior recorded
altered-input SHA-256 before refusal. Prior snapshots were not imported or
executed in place of current code.

### R01 guard: the exception does not hide missing extended XP

Three independent negative checks remain effective:

* `0x7b000808` plus only six payload DWORDs: `TRUNCATED_PACKET`.
* Extended bit set with a seven-DWORD length encoding (`0x7b000805`):
  `INVALID_PACKET_LENGTH`.
* Direct validator input claiming extended form with only seven DWORDs:
  `EXPLICITLY_NONCONFORMING`, `format_checked=false`, including
  `TRUNCATED_TARGET_FIELD`.

A full extended draw with explicit XP values `[1,2,3]` retains all three
`PRESENT` values. The ordinary conditional-default representation is therefore
not being applied indiscriminately to extended data.

### R02 guard: mode, opcode, envelope and padding remain bound

Valid exact 40-byte A/B envelopes pass and decode to the expected 40-byte /
28-byte draw respectively. Swapping the extension-bit form between modes
rejects `INVALID_DRAW_OPCODE_OR_MODE`. Nonzero B padding rejects
`NON_NOOP_PADDING`.

Code review confirms that after these gates the checker rejects
`validate_target(...).classification == EXPLICITLY_NONCONFORMING` as
`DRAW_TARGET_FORMAT_INVALID`, rather than filtering only length issues. This
is a review of the actual branch plus concrete real-decoder guards above,
not a claim that every possible definite validator issue was independently
injected or that any unsupported hardware semantics were proven.

### R03 guard: typed base and final extent are both checked

`True`, `None`, a string base and an integer-valued float each reject
`INVALID_STUDY_BASE`. The page-aligned base `2^48−4096` rejects
`INTEGER_OVERFLOW` because the 4368-byte output would exceed the domain.
The last fitting page-aligned base, `2^48−8192`, succeeds within range.
The shared half-open helper separately accepts an exact exclusive end of
`2^48`.

The study admits a fixed 166-packet canonical input, reconstructs its fixed
extent, and applies an output limit. No unbounded-resource stress test or new
broad parser audit was performed for this closure.

### R04 guard: canonical identity enforced; caller fields not trusted

Same-length 166-packet mutations to command name, source VA and packet order
each reject provenance mismatch. This supplements the original extra-BBS
counterexample, whose length alone now causes refusal.

Conversely, when exact canonical names, bytes, order and source VAs are kept,
clearing every supplied `fields/groups/schema` dictionary and corrupting
supplied `length/source_offset` does **not** alter the output. Fresh real
decoding restores the canonical resource inventory, layout and target
validation, all equal to the independently reconstructed canonical result.
This verifies rederivation rather than trusting forged field claims.

The provenance boundary remains the repository's local frozen fixture.
Its full-file SHA-256, unchanged during this confirmation, is
`0d76254ae590bd03a4d17a5ac67043680ef635725e7fcdb1d92581909be47970`.
Caller-supplied flags, synthetic modes and capture-specific conditional
assumptions are not promoted to runtime evidence by this closure.

## Positive candidate evidence and unchanged scope

Fresh in-memory outputs match the prior review's output hashes exactly:

| Candidate | Bytes | Contiguously decoded packets | SHA-256 |
|---|---:|---:|---|
| A | 4368 | 166 | `a6ab33b6d92a3e203a2ec041bde7370691d46bf38c9c3aaeddc9e80a594e5f62` |
| B | 4368 | 178 | `529565eaa7406d5283beef35753a4a6e62666135415a196ef0550ac0dad9e504` |

All four repaired draw forms in each candidate format-check. Both retain
`PARTIAL_FORMAT_STUDY`, `strict_shadow=false`,
`gpu_executable_proven=false`, and `deployment_eligible=false`.
The existing present-surface test also passes: defined surface syntax remains
`UNKNOWN` with `RESOURCE_DATA_MISSING`, and present legacy stencil is refused
by the null reconstruction helper.

**Handoff:** no remaining R01–R04 blocker was reproduced in this bounded
confirmation. Primary may regenerate final candidate receipts and determinism
evidence against these reviewed hashes. This closure proves neither GPU-time
mode/state/resource facts nor full command/shader execution equivalence, and
does not expand deployment or hardware authorization. No IMG was created or
changed.
