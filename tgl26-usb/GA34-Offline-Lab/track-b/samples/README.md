# Synthetic core/codec samples

These are explicitly **synthetic CPU-only mock inputs**, not hardware captures.
`sample_fault34.cpp` invokes the existing `Collector`, `encode`, `decode` and
`derive` implementations. It writes five **108-byte** `.bin` files and their
JSON derived receipts: `validPPGTT`, `validGGTT`, `valid0`, `DATA1MBZ`,
`failedread`. Each written binary is reopened, decoded, re-encoded and compared
byte-for-byte before its receipt is emitted. JSON unavailable interpreted
fields are `null`; context ID and PML4 are **unknown/null**, because the core
has no context or page-table access. All metadata and precondition flags are
synthetic caller claims, not proof of live power/locks/ACK.

## Reproduce from the lab root

```sh
python3 track-b/diagnostic-src/build_samples.py --run-name initial
```

The checked-in utility/helper source is adjacent to the core. This command
actually compiles Clang C++17 with ASan+UBSan and runs scanner tests plus sample
production, creating only `track-b/samples/initial/` and
`logs/sample-core/initial/`. It records source, binary, JSON and executable
SHA-256 hashes. Existing run directories are refused to preserve evidence.
For another reproduction use a fresh name, for example `--run-name reproduce-1`.
No whole compiler matrix is rerun.

## Actual initial run

Clang **21.1.8**, `-std=c++17 -O1 -g -Wall -Wextra -Wpedantic -Werror`,
ASan+UBSan with halt-on-error: compile exit 0, run exit 0, no sanitizer
diagnostics. **24 scanner cases passed**, plus the actual collector disabled/
zero-callback integration check and all five file round-trips.

| Sample | Bytes | Status | Validity | Derived view |
|---|---:|---:|---:|---|
| `validPPGTT.bin` | 108 | 0 | 31 | PPGTT VA `0xa12345678000` |
| `validGGTT.bin` | 108 | 0 | 31 | GGTT VA `0xffedcba98000` |
| `valid0.bin` | 108 | 0 | 31 | unavailable, hardware fault-valid=0 |
| `DATA1MBZ.bin` | 108 | 0 | 31 | unavailable, DATA1 MBZ bit9=1 |
| `failedread.bin` | 108 | 15 | 17 | unavailable, DATA0 callback failed |

The failed read retains raw DATA0 `0xdeadc0de` without its validity bit;
DATA1 is unattempted/zero. Its 2 reader calls and 3 epoch observations prove
the expected fail-stop sample path. The other samples use 3 reads/6 observations.

Exact sample/JSON hashes: `initial/sample-hashes.json`, SHA-256
`96f110dddea0b95b3b65c6bb61f9eebf95fab0927e53d4624c1d517da6c55045`.
Build/run log: `../../logs/sample-core/initial/clang-build-run.log`.
Source/executable hashes and unchanged independent-audit input hashes:
`../../logs/sample-core/initial/sample-build-receipt.json`.

## Separate bounded boot-text helper

`diagnostic-src/kern_tglfault34_boottext.hpp` has no global OS access. Its input
is an explicit readable span capped at **1024 bytes including a required NUL**.
Null, zero-length, oversized and unterminated inputs return false. The exact
case-sensitive token `-igfxtglfault34` must be delimited by ASCII whitespace
(space, tab, LF, CR, VT, FF) or string boundaries. Prefixes, suffixes, `=1`,
quotes and substring occurrences do not enable it. Bytes after the first NUL
are outside the text. Caller guarantees the supplied span is readable.

The hosted sample assigns `Request::enabled` from this helper, and tests a
suffix-only input against the actual collector: Disabled, zero callbacks,
zero records. The helper is **not wired to GA3.3, the existing core header or
the existing offline patch**. It is solely a separately reviewable offline
addition for the main session to consider integrating later.

The run records unchanged SHA-256 values for the existing core, existing tests,
record-format document, core provenance and prior header-only patch. It does
not modify those independent-audit inputs or root state/report/manifest files.
