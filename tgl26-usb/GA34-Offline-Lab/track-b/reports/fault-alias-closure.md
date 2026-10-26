# Independent R1/R2 alias-fix closure

Date: 2026-10-18. **R1 and R2 are independently CLOSED for the final standalone
mock core.** The original independent reproducer callbacks now produce the
expected fail-stop/pinned-dispatch behavior in Clang Debug and Release with
ASan+UBSan. No new defect was found in this bounded follow-up.

## Reviewed version and scope

Final header: `track-b/diagnostic-src/kern_tglfault34.hpp`.

SHA-256:
`a610ad86b5f8d2f176cefcc51870bc8594b128c79505e24addc0390213de92ac`.

The implementer's `logs/diagnostic-core/alias-fix-closure.json` was read and its
five current-source hashes, two compiler-receipt hashes, eight executable hashes
and final patch hash were independently verified. Both compiler receipts list
four passing configurations with 28 groups each. Those **8 × 28 = 224** author
group invocations and four freestanding builds are existing author evidence;
this reviewer reran the focused alias cases below rather than the full matrix.

The 405-line unattached patch payload reconstructs the final header exactly.
The independently recorded old-to-final header diff contains only input-lifetime
documentation and the entry snapshots:

```cpp
const Request q = request;
const Callbacks cb = callbacks;
```

These snapshots precede preflight and all callbacks. Existing codec/read-loop
semantics are otherwise unchanged. The old independent report and reproducer
files remain intact as evidence for the original header hash
`97b73b0bb6d61f58a3b14b4c41d5b13820268bceb76c91f338e8f6c55ffd7657`.

## Exact original reproducers against the final core

The new `logs/independent-fault-closure/closure.cpp` includes the **unchanged
original independent `review.cpp`**, renaming its main. It therefore executes
the original `Backend::read` and `Backend::observe` definitions, not substitutes
copied from the implementer's regression tests. R1 uses the identical original
request/backend setup and capture call with closure assertions. R2 additionally
executes the exact historical `null-callback` main branch.

| Finding | Observed final-core result in both modes | Closure |
|---|---|---|
| R1: first reader advances observer epoch/token and mutates the caller's request to match | `ResetRace=13`; **1 reader, 2 observations**; stored epoch/token **10/20**, caller/model now **11/21**; validity **17** (`HasMetadata\|HasFault`); DATA0/DATA1 unattempted and zero; no derived result | CLOSED: comparison target stays bound to entry snapshot |
| R2: first observer clears caller-owned `cb.read` after preflight | Caller descriptor is actually null, yet capture returns protocol `Complete`; **3 reads, 6 observations**, structurally valid record; historical main branch returns its original marker **99**, with no crash | CLOSED: reader dispatch stays bound to entry callback tuple |

The R2 marker `99` is a return value consumed by the new harness assertion; the
closure executable itself exits **0**. Its log retains the historical
`COUNTEREXAMPLE R2` introductory message because that original source was not
edited. The earlier crashes remain preserved in the original review directory.

## Descriptor variants and positive controls

Each Debug/Release run executes four focused groups, including:

* **63 descriptor variants:** seven mutations at every one of the nine dynamic
  callback events (`O R O O R O O R O`). Mutations null the reader, null the
  observer, replace context, replace reader, replace observer, replace the whole
  tuple, or clear the whole tuple. All complete using the original three reads
  and six observations in register order. Replacement callbacks and alternative
  contexts receive **zero calls**.
* **Three request variants:** epoch-only change and token-only change each
  produce `ResetRace` after one read/two observations. Replacing the entire
  caller request with defaults while the observer remains stable does not alter
  accepted metadata or interrupt that capture. A subsequent capture sees the
  caller's now-disabled request and refuses before callbacks.
* **Positive control:** an ordinary unchanged request/descriptor performs all
  three reads/six guards, and its record encodes/decodes identically with derived
  interpretation available.

Compiler: Clang **21.1.8**, C++17, strict warnings as errors, no exceptions/RTTI.
Debug uses `-O0 -g`; Release uses `-O2 -DNDEBUG -g`. Both use ASan+UBSan,
nonrecovering sanitizer errors and leak detection. Both focused runs exit 0 with
**no sanitizer diagnostics**. The broader codec/TSan review was not repeated.

## Sample byte compatibility

The existing sample producer was independently rebuilt with the final header
and ASan+UBSan, then run into a new review-owned output directory. Its 24 scanner
cases, disabled-integration check and five synthetic samples pass without
sanitizer diagnostics.

For each sample (`validPPGTT`, `validGGTT`, `valid0`, `DATA1MBZ`, `failedread`),
both `.bin` and `.json` are **byte-identical across all three sources**:

1. `track-b/samples/initial/`;
2. `track-b/samples/post-alias-fix/`;
3. `logs/independent-fault-closure/run-001/generated-samples/`.

Thus all ten artifacts match, including the five 108-byte wire records
(540 total wire bytes). Exact hashes are in `run-001/sample-comparison.json`.

## Evidence, preservation and handoff

Reproduce from the lab root:

```sh
python3 logs/independent-fault-closure/run_closure.py
```

The script creates a new numbered directory and writes only inside
`logs/independent-fault-closure/`. Completed evidence is under `run-001/`:

* `run-debug.log`, `run-release.log`: exact original reproducer outcomes and
  bounded variants/positive controls.
* `results.json`: commands, exit statuses, log hashes and final header hash.
* `header-only-diff.log`: actual minimal source delta.
* `sample-comparison.json`, `run-sample.log`: independent sample regeneration.
* `protected-before.json`, `protected-after.json`: **191 protected files remain
  byte-identical**, including implementation/build outputs, all original review
  evidence, initial/postfix samples and existing sample logs.
* `repository-check.log`: `make check` passes (46 Python, 42 JSON, 27 Markdown),
  a repository hygiene result separate from these external C++ tests.

Implementation/main-owned files were not edited. No hardware, SSH, VM, IMG,
EFI/firmware or GPU operation was performed; source/result IMG are absent.
The new report and logs are the complete reviewer handoff; main owns integration
and final delivery.

**Closure is limited to the two descriptor-alias findings.** Copying descriptors
does not own or prolong the callback context/collector lifetime, synchronize
concurrent access during the copy, create reset exclusion, establish real GT
ACK/power ownership, prevent hidden epoch ABA, or prove atomic same-hang register
coherence. Protocol `Complete` and synthetic sample round-trips retain their
documented standalone meanings. Whole-kext build remains `NOT_BUILT`; real Apple
backend/hook safety remains **UNPROVEN / BLOCKED**.
