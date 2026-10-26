# Independent CPU-only review of the GA3.4 fault core

Date: 2026-10-18. Scope: `track-b/diagnostic-src/kern_tglfault34.hpp` and
`test_tglfault34.cpp`, with the record-format, build receipt and pinned provenance
read independently. **Original implementation, tests, patch, build outputs and
historical sources were preserved.** All new artifacts are inside this lab.

## Result

The supplied 23-group suite passes independently under Clang 21.1.8 Debug and
Release with ASan+UBSan. Eight additional independent groups pass, including a
trace-reachability oracle for the codec. Two **conditional input-alias robustness
findings** have concrete single-threaded reproducers:

| ID | Severity / boundary | Expected | Actual |
|---|---|---|---|
| R1 | Medium record-integrity issue if callback-visible `Request` can change; low if immutable-input lifetime is an explicit enforced caller rule | Reset epoch/token changes relative to the accepted request produce `ResetRace` | `Complete`, all 3 reads, and a valid/encodable record carrying the old epoch/token |
| R2 | Medium standalone availability/robustness issue if callback descriptors can change; low under explicit enforced immutability | A preflight-validated callback stays pinned, or a changed/missing callback is refused | Observer clears caller-owned `cb.read`; next reader invocation faults at header line 219 |

Both require a callback to modify an object reachable through a non-const alias.
Neither reproducer needs threads, exceptions, blocking, allocation, hardware,
invalid pointer storage, or a dangling object before the failure. The existing
contract requires serialized collector access and coherent bounded mocks but
does **not explicitly require the `Request` and `Callbacks` objects themselves
to remain unchanged throughout capture**. These findings identify that missing
API assumption; they do not establish an exploit against a deployed driver.

No counterexample was found to the ordered-read fail-stop behavior, GT/ACK gates,
fixed-eight/no-overwrite behavior, sequence overflow refusal, or the structural
codec under stable inputs. Hidden epoch ABA and cross-generation register words
are demonstrably outside what this observer scheme proves. Apple integration
remains **UNPROVEN / BLOCKED**, independently of the standalone results.

## Reproduction and artifacts

From the lab root:

```sh
python3 logs/independent-fault-review/run_review.py
```

This creates a fresh `run-*` directory and does not invoke the core's own build
or delivery scripts. Completed evidence for this review is in
`logs/independent-fault-review/run-003/`:

* `results.json`: exact commands, exits, log hashes and protected-source hashes.
* `run-{original,independent}-{debug,release}.log`: passing suite outputs.
* `null-callback-{debug,release}.log`: intentional isolated crash reproducers.
* `null-callback-symbolized.log`: Debug fault resolves to
  `kern_tglfault34.hpp:219` and the standalone review's call site.
* `tsan-contract-violation.log`: intentional unsupported-concurrency race.
* `freestanding-undefined.log`: `nm -u` produced **no undefined symbols** for
  the independently compiled Release freestanding probe.
* `protected-before.json`, `protected-after.json`: **40 protected files unchanged**.
* `provenance-verification.json`: **10 source/text/base-copy hashes match** their
  existing pinned provenance, including all four GA3.3 snapshot files.
* `repository-check.log`: `make check` exit 0; repository hygiene only, not C++ coverage.

Review sources are `logs/independent-fault-review/review.cpp`, `concurrency.cpp`
and `run_review.py`. The original supplied suite was compiled directly, without
editing or including its helpers in the independent tests.

All four normal suite executions exit 0 without ASan/UBSan diagnostics. Both
intentional null-callback subprocesses abort with ASan SEGV (subprocess return
code `-6`), and the intentionally unsupported concurrent use exits 66 with a
ThreadSanitizer data-race diagnostic. Those diagnostic logs are counterexample
evidence, **not sanitizer-clean results**.

The R2 reproducer was additionally compiled without sanitizers: the same
`null-callback` mode exits `-11` (SIGSEGV). Commands and exits are in
`run-003/plain-counterexample-results.json`; this is not an instrumentation-only
failure.

The initial harness attempt is retained in the parent log directory, including
its failure output. Its synthetic mixed-generation sample accidentally set
DATA1 MBZ bits, so `derive()` correctly refused it. Only the new review harness
was corrected to change DATA0. The complete successful rerun is `run-003`;
original core sources never changed. Directory numbering reflects the runner's
existing `run-*` artifact count, not three completed runs.

## R1 — mutable request moves the guard's comparison target

Locations: header lines 164, 202–209, 216/224 and 235–239.

`capture()` copies initial request metadata into `FaultRecord r`, but passes the
borrowed `const Request &q` back to `checkEpoch()` at every boundary. Constness
through that reference does not freeze the original non-const object.

Exact reproducer: `borrowed_request_counterexample()` in `review.cpp`, and
`Backend::read()` with `mutateRequest=true`:

1. A normal caller-owned request has epoch 10, token 20. All gates pass.
2. The first observer returns coherent epoch 10/token 20.
3. The first bounded mock reader advances its model to epoch 11/token 21 and
   updates the original request's epoch/token through a valid non-const alias.
4. All later observers return coherent epoch 11/token 21, without epoch reuse.

Expected against the **initially accepted** request: the first post-read guard
returns `ResetRace`, no DATA0/DATA1 reads occur, stable validity is absent.

Actual in both optimization modes:

```text
actual=0 reads=3 observations=6 stored_epoch=10 observed_epoch=11
stored_token=20 observed_token=21
```

The resulting record passes `validRecord()`, has `CompleteValidity`, and derives
successfully. Thus its retained initial epoch/token do not describe the epoch
accepted by the last five checks. This is different from hidden ABA: the
observer actually exposes an increment, but the comparison target also moves.

Suggested integration fix: snapshot the request by value before validation and
use that immutable snapshot for both stored metadata and all guard comparisons;
also specify caller-side lifetime and exclusion rules. A lock is still needed
for real reset exclusion; copying a request would not establish such a lock.
No implementation fix was made by this reviewer.

## R2 — callback table is checked once but borrowed for later dispatch

Locations: header lines 164, 185, 216, 219 and 237.

Exact reproducer:

```sh
logs/independent-fault-review/run-003/independent-debug null-callback
```

The mode creates a live non-const `Callbacks cb` and gives the mock observer a
pointer to it. Both callbacks are non-null at preflight. On its first call the
bounded, nonthrowing observer executes `cb.read = nullptr`, supplies a coherent
valid observation and returns true. Header line 219 reloads the changed
`cb.read` and calls it. ASan reports SEGV in Debug and Release.

Expected: immutable pinned dispatch, or an explicit refusal if mutation is an
allowed operation. Actual: null function-pointer dispatch after a successful
`MissingCallbacks` gate. This is a preflight/use gap in borrowed descriptors,
not a claim that ASan found arbitrary memory corruption in normal mock usage.

Suggested integration fix: copy the callback descriptor by value at entry and
use that snapshot consistently, while keeping the pointed-to context alive.
Alternatively document and enforce that descriptors cannot change during the
call. Rechecking only `read` would not stabilize the context/observer pair.
No implementation fix was made by this reviewer.

## Independent positive and negative coverage

| Area | Independent evidence / conclusion |
|---|---|
| Entry fail-stop | 20 malformed request/callback cases: no observer, no reader, no stored slot. Render/media and arbitrary high bits cannot substitute for GT. GT ACK checked independently. Extra domain bits **with GT** are accepted as mask claims, not interpreted as unsupported enum values. |
| Dynamic fail-stop | 7 observer anomalies × all 6 boundaries = 42 cases; each stops exactly there. All 3 reader failures have exact callback trace (`OR`, `OROOR`, `OROOROOR`); no post-failure observer/read. Partial words retained and derived interpretation suppressed. |
| Publication within a serialized call | Every callback sees `Capturing`, the old count and `record(next)==nullptr`. Previously published record 0's pointer and contents survive all eight later/failed append operations. This is same-thread observation, not acquire/release publication proof. |
| Capacity / sequences | Mixture of successful and failed captures fills exactly 8 slots without overwrite, with sequences through `UINT64_MAX`. When Full and sequence-exhausted coincide, Full wins by gate order. Failed initial observation consumes the maximum sequence and the next otherwise-valid attempt gets `SequenceOverflow`, without callbacks. |
| Identity / time | Even a stored pre-read observer failure binds boot/caller ID and last hang/time. Reused hang ID, equal timestamp and changed boot ID are refused. Supplied original tests additionally cover missing/zero/backward/wrapped timestamps and ID variants. |
| Codec reachability | **10,725** independent status/read-count/valid-mask combinations checked on both encode and hand-mutated decode. Exactly **24** structural combinations reachable from the capture traces are accepted. Unknown/refusal-only statuses, extra validity bits, impossible partial prefixes and inappropriate stable bits are rejected transactionally. Raw words are zero in the oracle fixture to avoid conflating trace reachability with unattempted-word constraints. |
| Raw vs derived | 32 independent DATA0 bit-position checks, all 512 defined DATA1 combinations, **23,552** fault-valid/MBZ round-trips; anomalous raw bits survive codec while interpretation is unavailable. Oversized page helper inputs preserve the output sentinel. Original tests separately cover engine/source/type masks, maximum VA, failed callback's untrusted word and never-attempted raw zero constraints. |
| Reentrancy | Reentry from the observer, in addition to original suite reentry from the reader, returns `Reentrant`; outer capture still succeeds and counters match. |
| Allocation / dependencies | Review overrides global `new`/`new[]`; capture, encode, decode and derive add zero calls. Independently compiled freestanding probe has no undefined symbols. Static header inspection has no allocation, filesystem, thread, MMIO/reset/clear backend or driver hook. The test harness's hosted I/O/thread/sanitizer runtime is not a core dependency. |

Original tests are useful but the 20,000 codec mutations chiefly assert
self-consistency (`decode` and `validRecord` share validation). The independent
trace oracle adds an external structural expectation, rather than treating a
shared validator's acceptance as proof by itself.

## Demonstrated limits, not newly discovered compliant-use bugs

### Epoch ABA / snapshot consistency

`aba_and_triplet_limits()` increments then restores epoch/token inside the first
reader. All six observer calls return the original pair and capture returns
`Complete`. This intentionally violates the documented observer no-reuse/ABA
obligation; it confirms the core cannot detect concealed reset history.

A second mock changes DATA0 independently of the fault/DATA1 words under one
stable reset epoch, modeling a mixed-generation triplet. Capture still returns `Complete` and
`derive().available=true`. Reset-epoch stability alone cannot prove atomicity of
three different registers or attribution to one context. The core performs no
final fault reread, latch acknowledgement or hardware-identity verification.
These are mock-contract limits, not an assertion that this sequence happened on
the EliteBook. Re-reading identical values would not solve ABA either.

### Concurrency and lifetime

`concurrency.cpp` intentionally calls a disabled collector from two threads
without caller serialization. TSan reports a race at `saturateIncrement()` /
`capture()` lines 134/165 on `attempts`, before any reader callback. This is a
concrete demonstration of the documented unsupported usage, **not a defect
under the serialized caller contract**. The busy flag is an ordinary `bool` and
does not make concurrent calls safe. `size()`, `state()`, `record()` and
`counters()` likewise have no acquire/release or lifetime protocol for an
asynchronous consumer. Testing same-thread publication cannot grant one.

The collector owns inline storage; `record()` returns a borrowed pointer and
`counters()` a borrowed reference. Their lifetime ends with the owning object;
destruction/replacement during callbacks or export is not prevented. No async
worker, retained platform mapping, ownership transfer, or release callback
exists in this core. A copied record can be exported only under an external
synchronization/lifetime protocol. No claim of a compliant-use UAF is made.

### Timestamp, PML4 and Apple identity

`monotonicNs` is one caller-supplied nonzero increasing value, not a clock read
before/after each MMIO access. No elapsed-time anomaly, future timestamp or
cross-source timebase validation is performed. Boot/hang/caller IDs are claims,
not authenticated Apple driver/context identities. Per-record codec validation
does not enforce chronology across separately decoded records.

There is **no PML4, actual context ID, context-generation identity or capture
phase field** in this 108-byte record. `HasMetadata` covers its listed fields;
it must not be read as validity of absent PML4/current-context information.
The zero-extended VA is not proof of a mapping or safe page-table access. The
actual core cannot establish fault-to-RCS/PML4 attribution by itself. The main
session's updated `diagnostic-design.md:22` now explicitly documents the actual
three raw reads/six guards, lack of a second fault read/device clock pair, and
absence of atomic same-hang/latch proof. These are acknowledged design limits,
not discrepancies newly attributed to that updated document.

### No live safety signoff

The header provides an injectable **mock** reader, not an MMIO backend. Its
independent boot-argument string is not a boot-argument parser. The four
GA3.3 base files contain no inclusion/reference attaching the new header.
No complete kext was built, loaded or exercised. No hardware/SSH/VM, Nix source
change, IMG creation, firmware/EFI/USB change or GPU write occurred.

Pinned Linux register/domain facts and Intel DATA1 layouts were hash-verified
locally. They do not prove Apple's numeric domain mapping, GT ACK ownership,
power reference, reset/clear exclusion, lock order, MMIO mapping lifetime or
exact-25G83 call context. The existing live-integration BLOCKED conclusion
remains warranted; no result here authorizes a new physical experiment.

## Durable handoff

Reviewed header SHA-256:
`97b73b0bb6d61f58a3b14b4c41d5b13820268bceb76c91f338e8f6c55ffd7657`.
Reviewed original test SHA-256:
`498b1e94e25d9d17c02b0a2885f893454d4cf1c3094726d36b0d8711b6de0f43`.

Exact changed variable in the product: **none**. New variables exist only in
isolated CPU mocks and review harnesses. Source/result IMG: **none**.
Observed result: baseline/independent checks pass with the two conditional
alias-input counterexamples and the explicitly unsupported concurrency/ABA
limits above. Next action belongs to the main session: decide whether to pin
borrowed input descriptors or explicitly enforce immutability, integrate these
findings into lab state/final manifest, and keep real Apple attachment blocked
until its separate prerequisites are proven. This reviewer did not edit the
main-owned state, continuation, history or other tracks.

## Steering addendum — bounded boot-text scanner and synthetic samples

The main session subsequently added separate `kern_tglfault34_boottext.hpp`,
`sample_fault34.cpp` and `build_samples.py`; the reviewed core/patch stayed
unchanged. These additional files were read, and tested without writing to the
main-owned `track-b/samples/initial` or `logs/sample-core/initial` directories.

Evidence is in `logs/independent-fault-review/steering-samples/`:

* `boottext_review.cpp` lives in the parent review directory. It performs
  **9,431 independent scanner checks**, including all 1..1024 exact allocation
  sizes with missing/present NUL, every maximum-span token placement, all 256
  byte values at each token boundary, every single-byte token mutation, embedded
  NUL and oversize/zero/null spans. Clang ASan+UBSan execution exits 0 without
  diagnostics. The 1,024 exact-size allocations exercise the readable boundary
  with sanitizer redzones; no unbounded-string assumption is introduced.
* The supplied sample producer was independently compiled with ASan+UBSan and
  run into `steering-samples/generated-samples/`. Its 24 scanner cases,
  scanner-to-disabled-collector check and all five samples pass. All five
  `.bin` and five `.json` files are byte-identical to the initial delivery.
* `verification.json` records an independent Python little-endian unpack of
  each original wire record, its masks/status/IDs/time/epoch/token/raw words,
  VA formula and JSON correspondence. Five records are **108 bytes each,
  540 wire bytes total**. Original sample hashes match. All 39 guarded
  core/sample/producer-log files in this addendum remain unchanged.

No scanner defect was found in this bounded contract. It recognizes exactly
one case-sensitive ASCII-whitespace-delimited token in the prefix before the
first NUL, requires a NUL inside a caller-readable span no larger than 1024,
and rejects suffixes, assignment forms and quoted forms. It is an offline text
helper: it neither fetches OS boot arguments nor proves that the text came from
the current machine. `Request::enabled` remains a caller claim; it does not
bypass any core gate. The separate header is not included by the core or its
unchanged delivery patch.

Samples explicitly mark `SYNTHETIC_MOCK_ONLY`, `hardware_observation=false`,
`live_locks_proven=false`, and `context_id`/`pml4` null. Raw invalid/failed/MBZ
records retain their words while interpreted JSON fields are null. A sample's
protocol `Complete` is not evidence of actual coherence, same-hang attribution,
real locks, GT ACK ownership or current-device identity. The hosted sample
producer allocates strings and writes files by design; that does not add those
dependencies to the freestanding core or scanner.
