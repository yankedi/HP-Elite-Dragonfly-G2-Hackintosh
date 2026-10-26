# GA36 Track A legacy writer tests

This directory is an independent, offline test of the **legacy** capture callbacks in
`track-a/baseline/kern_igfx.cpp` and `track-a/candidate/kern_igfx.cpp`. It does not
modify either source, the primary Capture36 core, or any hardware state.

## What is actually tested

`run_tracka.py` extracts the exact `hangWriteRecords()` and `hangThread()` function
bodies from the frozen sources with a brace/lexer scan and inserts those slices into
a generated single translation unit. The algorithm is not re-typed by hand; the
extracted-text SHA-256 values are recorded in `logs/legacy/tracka-results.json`.

The harness supplies only:

* a fake `IGFX::TigerLakeRegisterMap` with the members those bodies read/write;
* `OSCompareAndSwap` implemented as a real atomic `__atomic_compare_exchange_n`
  (true = acquired), so the baseline's inverted use and the candidate's ownership
  test are exercised as written;
* mock `vfs_context_create/rele`, `vnode_open/close`, `uio_create/addiov/resid/free`
  and `VNOP_WRITE`, with deterministic fault injection and counters;
* a pthread driver for the concurrency scenarios.

**These are mocks, not XNU.** `hangThread()` is not invoked by a real `ThreadCall`.
No kernel vnode, uio, filesystem, GPU, MMIO or ThreadCall code runs. The mock
`HangRecord` is much smaller than the real 0xC2A0/0xC2F8 wire record, so any
`sizeof` printed by the harness is native-mock-only and must not be used as a THAG
wire size.

## Scenarios

Baseline (expected to expose the GA33 inversion):

* first successful CAS returns without writing and leaves `hangWriting == 1`;
* the next CAS loser performs the write;
* after that seed, two CAS losers overlap in `VNOP_WRITE` on the same snapshot
  buffer (backend gate, `maxActiveWrites == 2`);
* a failed write is recorded, but the separate early `hangWriteError` guard (checked
  before the inverted CAS) blocks later sequential calls; that guard is still not
  the candidate's atomic terminal state.

Candidate:

* one CAS owner writes exactly once;
* 2 and 16 concurrent callers produce one write, one winner, 1/15 losers;
* a write error publishes `hangWriteError` and leaves `hangWriting == 2`; later
  calls do not retry or reopen;
* a short write is a terminal failure;
* a missing `uioFree` is refused before `vfs_context_create`/`O_TRUNC`.

Both implementations, backend fault matrix:

`success`, `vfs_context == null`, `vnode_open` failure, open-success-with-null-vp,
`uio_create` failure, `uio_addiov` failure, `VNOP_WRITE` error, short write,
`vnode_close` error, and missing-uio-pointer. For every case the harness checks the
return, one close per acquired vnode, vfs release, uio free, write count, and that
only a zero return is treated as completion.

## Run

```sh
python3 tests/legacy/run_tracka.py
```

The runner derives all paths from `__file__`, writes generated sources/binaries to
`tests/legacy/build/`, and writes build/run logs plus `tracka-results.json` to
`track-a/logs/legacy/`. It compiles release and `-fsanitize=address,undefined`
variants with each available Clang and GCC. ASan leak detection is disabled because
the baseline missing-uio-pointer case intentionally leaks the mock uio.

## Optional parser regression

`test_thag_parser.py` uses the frozen GA33 parser and the real GA32b v2 capture
read-only. It checks the parser source SHA-256/constants, v2 record-size detection,
real index order, one-byte truncation rejection, index-swap warning, a synthetic v3
layout header with `diag.version/size`, and v3 truncation. It is run by the main
runner but is independent of the writer harness.

## Expected result

All candidate checks pass; baseline checks encode the observed buggy behaviour and
also pass as a regression lock. Any failure means the extracted source no longer
matches the recorded behaviour, not that a real kext was validated.
