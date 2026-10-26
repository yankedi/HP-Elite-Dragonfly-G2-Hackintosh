# GA36 writer / capture safety audit

## Verdict

**Independent result: do not promote this to a full integrated capture pipeline.**

- The freestanding CPU `Capture36::Pipeline` has a sound single-owner/append-only
  protocol under its stated contracts. I verified the four recorded native runs:
  Clang release, Clang ASan/UBSan, GCC release, and GCC ASan/UBSan; all exited 0
  with the same PASS line. This supports **`CAS_VERIFIED`** (more precisely,
  CPU protocol verified by the supplied tests), not hardware or XNU integration.
- The actual kext source is fail-closed: `processKernel()` parses
  `igfxtglhang` and then unconditionally sets `hangDump = 0`
  (`track-a/candidate/kern_igfx.cpp:1596-1605`). Therefore its hang writer,
  hook routes, and `hangCall` are not an integrated runtime pipeline in this
  candidate. The truthful aggregate status is
  **`CAS_VERIFIED / FULL_PIPELINE_PARTIAL (NOT INTEGRATED, NO HARDWARE)`**.
- Re-enabling the legacy route would not be safe based on this audit. It still
  has a non-atomic volatile producer/publication protocol, no scheduler
  cancellation/lifetime fence, an `O_TRUNC` non-transactional backend, and an
  unbounded synchronous write path. Do not infer that the corrected CAS alone
  fixes those properties.

This review did not use SSH, hardware, MMIO, deployment, IMG, EFI, or firmware.
It did not modify candidate, tests, track history, or source history.

## Evidence reviewed

| Item | SHA-256 / result |
|---|---|
| `track-a/candidate/kern_capture36.hpp` | `4316725f61afe3f32374582d126bec97e496aac52319e4c5d83c9cee0a00eb8a` |
| `track-a/tests/pipeline.cpp` | `c5fa96e873b3ea45a6a52a33a36282355269497151766c7ea4be822a8d294181` |
| `track-a/candidate/kern_igfx.cpp` | `a05a0f176e59a35d29c7890404a31ed9089898a98e120d38a1dc41933cd496eb` |
| `track-a/logs/pipeline/results.json` | `6bf7fdc64068fe7608424fee79c2b321f4f305e51c9fcdcbb0e1119bb1e12e52` |
| Pipeline result | 4/4 build+run pairs exit 0; no stderr |
| Track C result | 8/8 build+run pairs exit 0; project gate still DENY |

The four actual pipeline logs are:

```text
logs/pipeline/clangpp-release-run.txt       PASS ownership, immutable publication, 2/16 contenders, failure terminal, pending handoff, cancellation fence, reentry, 120x16 stress
logs/pipeline/clangpp-asan-ubsan-run.txt    PASS ownership, immutable publication, 2/16 contenders, failure terminal, pending handoff, cancellation fence, reentry, 120x16 stress
logs/pipeline/gpp-release-run.txt           PASS ownership, immutable publication, 2/16 contenders, failure terminal, pending handoff, cancellation fence, reentry, 120x16 stress
logs/pipeline/gpp-asan-ubsan-run.txt        PASS ownership, immutable publication, 2/16 contenders, failure terminal, pending handoff, cancellation fence, reentry, 120x16 stress
```

The tests use ASan/UBSan, not ThreadSanitizer. Their stress has one publisher
and up to 16 drain contenders (`pipeline.cpp:109-120`); it does not establish
the external scheduler/callback contract or a concurrent multi-publisher
scenario.

## Findings

### F1 — HIGH: `quiescent()` is not an external callback lifetime fence

**Evidence.** The core explicitly says that its buffers must survive close,
callback fencing, and quiescence (`kern_capture36.hpp:74-75`), and explicitly
says that `quiescent()` does not fence an external queued callback
(`:157-161`). `life_` counts only calls that have entered `publish()` or
`drain()`; it cannot count a scheduler item that has not started yet.

**Deterministic counterexample.**

```cpp
Fixture *p = new Fixture;
auto r = record(0);
assert(p->pipe.publish(r, true) == Submit::Accepted);
queue.push([raw = &p->pipe] { raw->drain(Sink::write, nullptr); });
p->pipe.close();
assert(p->pipe.quiescent());       // queued callback has not entered life_
delete p;                          // caller wrongly treats this as safe
queue.run();                       // raw->drain dereferences freed storage
```

The callback may be rejected by `Closed`, but it must first dereference the
freed `Pipeline` object to call `enter()`. A callback already inside `drain()`
is the same issue if the caller ignores `quiescent()==false`. This is a real
UAF window, not an atomicity failure in the core. **Action:** the integration
owner must cancel/wait all queued callbacks, prevent new enqueue/entry, and
only then free the object and its buffers. A plain cancel followed by a
quiescent check is not evidence of this fence.

### F2 — HIGH: the legacy kext writer has no release/acquire publication of records

**Evidence.** `hangCapture()` fills `hangRec[hangCount]` and the hook increments
the `volatile uint32_t hangCount` (`kern_igfx.cpp:1369-1429`, especially
`:1372-1378`). `hangThread()` separately reads `hangCount` and copies the
records (`:1574-1588`). The fields are volatile, not C++ atomics, and there is
no release publication of the completed record followed by an acquire load by
the writer. The CAS on the unrelated `hangWriting` flag only claims the writer;
it does not publish the record contents.

The source does have the correct CAS polarity for this candidate:

```cpp
if (!OSCompareAndSwap(0, 1, &self->hangWriting)) return;
```

but that proves only writer ownership. It does not prove immutable publication,
record visibility, or producer/writer lifetime. The source itself calls this
legacy state “not a producer fence” (`:1575-1577`). **Action:** retain the
`hangDump = 0` gate; if a future integration is authorized, publish an
immutable count/slot prefix with the core protocol or an equivalent reviewed
XNU adapter. Do not repair this by only changing the CAS branch.

### F3 — HIGH: `O_TRUNC` makes a short/error write destroy the previous good file

**Evidence.** `hangWriteRecords()` opens the fixed destination using
`O_WRONLY | O_CREAT | O_TRUNC | ...` before the write
(`kern_igfx.cpp:1529-1541`). It maps a returned residual to `EIO`
(`:1549-1552`), and the core/legacy writer then records failure and disables
future writes (`:1588-1593`). Thus the terminal failure state is persistent in
memory, but the filesystem may already contain a zero-length or partially
written replacement; the previous valid capture is not retained.

**Deterministic backend counterexample.** A file containing complete record A
exists. `vnode_open(... O_TRUNC ...)` succeeds, `VNOP_WRITE` writes only the
first 64 bytes and returns residual. The function returns `EIO`, but the path
now contains a truncated A/B prefix and no complete prior file. A later retry
is forbidden by the terminal state, so the diagnostic is permanently lost.

`IO_SYNC` and successful `vnode_close()` do not turn truncate-plus-write into
an atomic replacement. **Action:** document this as a deliberate
non-transactional backend limitation, or use a unique temporary file followed
by complete write, required sync/close checks, and an atomic rename protocol
with directory durability as appropriate. This is not a reason to add a risky
hardware adapter; it is a release-integrity gate.

### F4 — HIGH: timeout is a result code, not an enforceable bound

**Evidence.** The core defines `TimedOut` and says the backend must return
(`kern_capture36.hpp:13-15`), but the `Write` type cannot interrupt a callback
that has stopped returning. The actual `hangWriteRecords()` performs synchronous
`vnode_open`, `VNOP_WRITE(... IO_SYNC ...)`, and `vnode_close`
(`kern_igfx.cpp:1533-1571`) with no deadline, cancellation, or watchdog.

**Counterexample.** A filesystem stalls in `VNOP_WRITE`. The hang thread call
holds `hangWriting==1` and the write buffer; `close()`/unload cannot make that
call return. Any caller that frees the object after a nominal timeout creates
UAF; any caller that waits for it can hang indefinitely. `TimedOut` is never
produced by this backend. **Action:** do not claim non-returning-I/O safety or
teardown safety. Keep the route disabled, or provide a separately reviewed
backend whose bounded-return property is actually established; never free
buffers while the call may still execute.

### F5 — MEDIUM: accepted publication depends on an external notification not
included in the core

**Evidence.** `publish()` returns `Accepted` after setting `Pending` and says
the caller “must arrange a worker notification” (`kern_capture36.hpp:99-105`).
The core has no executor, notification token, or reliable-callback proof.

**Counterexample.**

```cpp
assert(pipe.publish(record(0), true) == Submit::Accepted);
// caller drops/loses the worker notification
assert(pipe.pending());
// no drain can occur; the record is never written
```

This is not a defect in the isolated state machine: `Pending` remains set and
a later reliable notification can recover it. It is, however, a liveness gate
for an XNU `thread_call` adapter. Cancellation, coalescing, and callback
fencing must be reviewed separately; neither the CPU tests nor this header
prove an XNU cancel/wait protocol. Mark the complete pipeline **PARTIAL**.

### F6 — MEDIUM: `attemptReasons[]` does not retain every attempt

**Evidence.** `HangRecord` documents `attemptReasons[8]` as every attempt
(`kern_igfx.hpp:2813-2815`), but `hangCapture()` zeroes the whole record on
each attempt (`kern_igfx.cpp:1369-1377`), and only afterward the wrapper stores
the current reason (`:1504-1512`).

**Deterministic counterexample.** Attempts 1, 2, and 3 produce reasons
`RegsInvalid`, `ReadFailed`, and `ScanIncomplete`. Each call to
`hangCapture()` erases the previous array; the final record contains only
`attemptReasons[2] = ScanIncomplete`, with slots 0 and 1 zero. This is a
truthfulness/integrity defect in the dormant legacy record, not a UAF. **Action:**
if that route is ever separately integrated, clear once before attempt 1 and
preserve the array across retries; otherwise leave it behind the existing
gate and do not claim the record is a complete retry history.

### F7 — HIGH if enabled: CSB diagnostic writer is another unintegrated
volatile producer / lost-wake protocol

This is separate from the `Capture36` proof and must not be used to upgrade it.
`csbNote()` mutates `csbRec`, increments `csbPending`, and arms a delayed call
(`kern_igfx.cpp:1118-1160`). `csbThread()` writes the same mutable `csbRec`
directly, then clears `csbNextFlush` and `csbPending`
(`:1081-1105`). These fields are volatile/plain rather than a release-published
immutable snapshot.

**Deterministic lost-wake interleaving:**

1. `csbPending == 1`; `csbThread` is writing.
2. A hook records a new entry and leaves `csbPending == 1` (or increments it)
   while `csbNextFlush` is still nonzero.
3. The writer returns and executes `csbNextFlush = 0; csbPending = 0`.
4. The new entry is present in memory but its notification was erased; no later
   flush is necessarily armed. The file may also be a torn mix of old/new
   entries because there was no snapshot.

The same area has a plain `csbNextFlush` read/write across hook and thread-call
contexts. **Action:** treat CSB as legacy/unintegrated; do not represent its
`TGCS` file as a proof of the writer core. If enabled in a future scope, it
needs its own immutable snapshot, atomic pending/arming protocol, and callback
cancel/wait lifetime fence.

### F8 — MEDIUM if enabled: TraceDisk is explicitly non-teardown-safe

The separate `TraceDisk` path keeps a vnode open forever and intentionally does
not free each created `uio` (`kern_igfx.cpp:1838-1864`). It also updates the
same `traceRec` while the thread-call writer can serialize it. Its own comments
say clean shutdown can hang and the machine should be powered off by hand.
This is not evidence against the freestanding core, but it is a concrete
reason not to describe all actual-candidate diagnostics as lifetime-safe. Keep
it outside any `FULL_PIPELINE` claim.

## What is proven versus not proven

### CPU protocol facts

Under the caller contracts in `kern_capture36.hpp`:

- `Producer` serializes publishers; a publisher copies caller input before the
  release publication of `published_` (`:87-105`).
- The writer acquires `Pending`, claims `Running` with CAS, snapshots only the
  published prefix, and does not allow a concurrent writer (`:108-150`).
- New publication racing the owner leaves `Pending` set and is handed off by
  the `Running -> 0` CAS failure path; it is not silently cleared.
- Callback error, short write, and missing callback enter a terminal `Failed`
  state; the first error is retained (`:67-71`, `:123-150`).
- Close prevents new core entry, and active core calls keep `quiescent()` false;
  external queued callbacks still require scheduler fencing (`:153-161`).
- Buffers are append-only/no-reset in this object. This excludes core-level ABA
  reuse only if the object, buffers, and caller access obey the stated lifetime
  contract.

### Not proven by these facts

- XNU thread-call delivery, coalescing, cancellation, or cancel/wait behavior.
- Lifetime of a raw callback parameter after kext/object teardown.
- A backend timeout or interruption of a blocked filesystem operation.
- Atomic/transactional preservation of the previous disk file.
- Actual GPU forcewake, ACK, reset exclusion, MMIO mapping, or fault tuple.

## Invariant matrix

| Invariant | Freestanding CPU core | Actual candidate / evidence | Audit state and action |
|---|---|---|---|
| Exactly one writer | CAS `word_.Running`; tested 2/16 contenders and max callback concurrency 1 | Legacy CAS polarity is corrected at `kern_igfx.cpp:1581`, but only claims `hangWriting` | **CAS_VERIFIED; integration partial**. Do not infer producer safety. |
| Immutable published prefix | release `published_`, acquire load, one producer, append-only slots | `volatile hangCount` and mutable `hangRec`; no release/acquire publication | **CPU verified under contract; actual NOT VERIFIED**. Keep route gated. |
| No lost pending handoff | `Pending` is retained when owner CAS sees a publisher; tested nested handoff | `thread_call_enter1` use has no recorded cancellation/coalescing proof; CSB has a concrete clear-after-new-event race | **CPU liveness conditional; actual partial**. Require executor proof. |
| Failure persistence | first error then `Failed`; no retry; tested error/short/missing/timeout | legacy stores error before `hangWriting=2`, but file may already be truncated | **CPU verified; disk integrity NOT VERIFIED**. Use transactional backend or disclose loss. |
| Short/partial write truthfulness | callback short result becomes `ShortWrite` | `VNOP_WRITE` residual becomes `EIO` after `O_TRUNC` | **Failure is recorded, prior file not preserved**. High-priority release gate. |
| Callback/object lifetime | active leases protect entered calls only | raw `thread_call` self and no cancel/wait/deinit fence in candidate | **NOT VERIFIED**. Fence scheduler before free/unload. |
| No UAF/double-free | no reset API; no internal free | allocation paths have no shown teardown fence; queued callbacks retain raw `this` | **NOT VERIFIED**. Do not claim unload safety. |
| Caller input change | copy makes post-return scratch mutation harmless; stability during call is required | actual legacy writer does not use this core | **CPU contract verified; adapter absent**. Never mutate input/buffers concurrently. |
| Non-returning timeout | only a callback contract; core cannot interrupt it | synchronous `VNOP_WRITE` has no deadline | **NOT VERIFIED**. `TimedOut` enum is not an implementation. |
| File transaction | intentionally outside core | fixed `O_TRUNC` path | **NOT TRANSACTIONAL**. Preserve old file via temp+rename if required. |
| Hardware-safe sample point | not part of core | Track B: all candidates BLOCKED; Track C: all nine gate conditions non-VERIFIED | **DENY**. No risky hardware adapter should be demanded. |

## Track B/C bounded cross-review

- Track B is ready as a bounded static safety review, not a hardware approval.
  Its `SAFE-SAMPLING-POINTS.md:3-35` correctly rejects all candidate points:
  mask 7 is only a software request, a software refcount is not hardware ACK,
  local spinlock release is not object lifetime/reset exclusion, and the old
  `0x4094` clear is not a Gen12 `CEC4/CEB8/CEBC` proof. `CALLGRAPH.md:81-91`
  also records blocking waits and missing global lock/lifetime proof.
- Track C is ready as an offline gate model only. `results.json` records 8/8
  native build/run pairs, but its project assessment keeps
  `CorrectBinary`, `CorrectHookABI`, and `CorrectGTDomain` CONDITIONAL and the
  six runtime/tuple conditions UNKNOWN; admission is false. This is the
  truthful result, not a release claim.
- `FAULT-TUPLE-CONSISTENCY.md:55-74` supplies an important deterministic
  A/B/A same-epoch counterexample: `StableEpoch` does not prove device-side
  tuple coherence and must not be promoted to `VERIFIED`.
- No Track B/C output justifies enabling the actual writer or adding a new
  hardware adapter. Keep the real-MMIO gate closed.

## Required final wording

Recommended final status for the parent integration report:

```text
CAS_VERIFIED = YES (isolated Capture36 CPU protocol; four supplied native
                    release/ASan/UBSan runs, no hardware/XNU backend)
FULL_PIPELINE = PARTIAL / NOT INTEGRATED
ACTUAL_HANG_CAPTURE = DISABLED_BY_SOURCE_GATE (hangDump forced to 0)
HARDWARE_SAFE_POINT = DENY / BLOCKED
DISK_BACKEND = NON-TRANSACTIONAL O_TRUNC; not a durable atomic replacement
LIFETIME = scheduler cancel+wait and raw-callback fence still required
```

Do not call this `FULL_PIPELINE_VERIFIED`, `HARDWARE_READY`, or
`CAPTURE_WRITER_DEPLOYABLE`.
