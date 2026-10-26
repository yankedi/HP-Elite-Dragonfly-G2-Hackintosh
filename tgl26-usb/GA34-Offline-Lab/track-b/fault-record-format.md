# FaultRecord v1 — standalone mock contract

Implementation: `diagnostic-src/kern_tglfault34.hpp`, namespace `TglFault34`.
Status: **OFFLINE_PASS, UNATTACHED**. The header is adjacent to the immutable
`diagnostic-src/ga33-base/` snapshot. No existing source includes it. Independent
boot-argument name: `-igfxtglfault34`; `Request::enabled` defaults to false. The
header exposes the name and a mock enable claim; no live boot-argument parser or
hook is installed.

## Raw registers and extraction provenance

Read order is `0xCEC4` fault, `0xCEB8` DATA0, `0xCEBC` DATA1. Each is a separate
raw 32-bit field. Linux v6.18 `intel_gt_regs.h` defines fault valid `0x1`, type
`0x6` (shift 1), source `0x7f8` (shift 3), engine `0x1f000` (shift 12), DATA1 VA
high `0xf` and GGTT selector `0x10`. Exact Linux `intel_gt.c` byte VA:

```text
((uint64_t)(DATA1 & 0xf) << 44) | ((uint64_t)DATA0 << 12)
```

This gives a zero-extended, page-aligned 48-bit value; no sign extension or
faulting-byte offset is inferred. `checkedFaultPageToVa()` refuses wider than
36-bit page numbers without modifying output. Masked raw input cannot overflow.

Intel 703046, printed p906, specifies DATA1 bits 8:7 page size (0=4K, 1=64K,
2=2M, 3=1G), bit 6 entry-present, bit 5 entry-valid, bit 4 GGTT/PPGTT, bits 3:0
VA47:44. **Bits 5–8 are legitimate.** Known DATA1 mask is `0x1ff`; bits 31:9
are MBZ. The record and codec retain every raw bit. As an explicit conservative
policy, MBZ anomalies suppress interpreted fields and expose `data1MbzBits`.
Entry-valid and fault-valid are distinct; entry-valid=0 does not discard a
fault-valid=1 snapshot.

Wire engine-layout value 1 explicitly means **Linux v6.18 five-bit extraction**.
The derived view also labels the older v5.15 three-bit extraction separately
(`engineIdV515`). Neither numeric value is asserted to be a supported live TGL
engine enumeration; no undocumented future IDs are silently rejected or renamed.
Pinned sources, hashes, pages and line anchors are in
`../reference/diagnostic-core/core-provenance.json`.

## Preconditions and bounded capture

Every attempt checks enable, supported-TGL claim, known active power,
**GT** forcewake ownership plus GT ACK, not-resetting, known nonzero exclusion
token/epoch, known stable nonzero boot/hang/caller IDs, known nonzero monotonic
timestamp, callback availability, capacity and sequence exhaustion before the
first callback. Local domain labels are GT=1, Render=2, Media=4, All=7; these
are not platform ABI constants. GT alone suffices; All is accepted when it
includes GT. Render alone cannot satisfy the register range's GT requirement.

Caller must serialize the collector and provide a bounded, nonthrowing mock
reader plus a **synchronized coherent epoch observer**. At capture entry, before
any callback, the complete `Request` and `Callbacks` descriptors are copied by
value into immutable locals. All preflight checks, retained metadata and epoch
comparisons use that initially accepted request snapshot; all dispatch uses the
same snapshotted reader/observer/context tuple. A callback's single-threaded
mutation of the caller-owned request cannot move the accepted epoch/token;
mutation/nulling of the caller-owned callback table cannot retarget dispatch.
The caller must keep inputs readable and serialize access during the entry
copies. The context itself is borrowed, not cloned or owned: caller keeps it,
the collector and its mappings alive throughout capture, and supplies coherent
synchronized observations. Copies confer no live locking, concurrent safety,
asynchronous publication or ownership transfer.

Before and after each
successful register read, the observer checks the same reset epoch and exclusion
token, not-resetting, active power, GT ownership and ACK. An observer failure or
change stops capture immediately. A reader failure stops immediately, including
no post-failure observer callback; the untrusted returned word is retained but
its validity bit stays clear. There are at most **3 reader callbacks and 6 epoch
observations per stored capture**, with no retry. Raw words already obtained are
retained on reset race and other failures; derived fields are unavailable.

The observer must not conceal a reset by epoch reuse/ABA. Numeric tokens and
boolean flags are **caller claims, not proof of actual Apple locks, GT ACK or
power references**. The offline core neither establishes these prerequisites
nor supplies a live backend. No allocation, I/O, thread calls, MMIO writes,
fault clear, reset operation, or old reset-behavior change occurs in the header.

State transitions: Ready → Capturing → Ready, Full, or SequenceExhausted.
Precondition refusals retain no record and call no callbacks. Accepted attempts
append one record, including partial captures and failures, to fixed storage for
**8 records**. Record zero is preserved; there is no overwrite/clear/reset API.
Full and sequence-overflow attempts invoke no callbacks. Sequence zero is never
emitted; `UINT64_MAX` can be emitted once, then further captures are refused.
The optional constructor sequence seed is for offline boundary/checkpoint tests.

Boot ID and caller ID bind on the first stored record. Subsequent hang IDs and
timestamps must strictly increase, including after failed captures. A timestamp
wrap is refused rather than normalized. Counters saturate at `UINT64_MAX`:
attempts, preflight/refusal-only failures, stored capture failures, full refusals,
sequence-overflow refusals. Reentrant mock calls are refused; the busy flag is
not an interthread synchronization primitive. Full/sequence counters apply when
an otherwise valid request reaches those gates.

## Wire layout (108 bytes)

All scalars are unsigned, explicitly little-endian; there are no packed-struct
dumps, host-endian assumptions, pointers, strings, padding bytes, or derived
fields in the wire representation.

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 4 | Magic bytes `54 47 46 34` (`TGF4`) |
| 4 | 2 | Version = 1 |
| 6 | 2 | Size = 108 |
| 8 | 4 | Validity mask |
| 12 | 4 | Caller-claims mask |
| 16 | 4 | Capture status |
| 20 | 4 | Read attempts (0..3; failed read counts) |
| 24 | 4 | Engine layout = 1 (LinuxV618FiveBit) |
| 28 | 4 | Claimed forcewake-held domains |
| 32 | 4 | Claimed forcewake-ACK domains |
| 36 | 8 | Sequence |
| 44 | 8 | Caller monotonic timestamp, ns |
| 52 | 8 | Caller boot ID |
| 60 | 8 | Caller hang ID |
| 68 | 8 | Stable caller ID |
| 76 | 8 | Expected reset epoch |
| 84 | 8 | Claimed reset-exclusion token |
| 92 | 4 | Raw fault register |
| 96 | 4 | Raw DATA0 |
| 100 | 4 | Raw DATA1 |
| 104 | 4 | Reserved, must be zero |

Validity bits: 0 fault read succeeded, 1 DATA0 succeeded, 2 DATA1 succeeded,
3 all epoch boundaries stable, 4 metadata known. Complete = `0x1f` and 3 reads.
Hardware fault-valid is independent of this mask. Partial raw validity must be
a contiguous prefix of the ordered reads. Reader-failure status requires the
corresponding attempt count and excludes the failed word's validity bit. Epoch,
power, GT and ACK failures have exactly the validity of preceding successful
reads. No failed capture may claim stable epoch. Never-attempted raw words are
zero; a failed reader's untrusted word is retained.

Caller-claims bits: 0 enabled, 1 supported TGL, 2 active power, 3 not resetting,
4 exclusion known, 5 identity known, 6 timestamp known. Every stored record has
`0x7f`. Dynamic observer failures do not retroactively rewrite initial claims.

Status numeric values: Complete=0, Disabled=1, UnsupportedTgl=2, PowerUnknown=3,
GtForcewakeMissing=4, GtAckMissing=5, Resetting=6, ExclusionUnknown=7,
BadIdentity=8, IdentityChanged=9, BadTimestamp=10, MissingCallbacks=11,
EpochUnavailable=12, ResetRace=13, FaultReadFailed=14, Data0ReadFailed=15,
Data1ReadFailed=16, BufferFull=17, SequenceOverflow=18, Reentrant=19.
Only 0, 3–5, 12–16 can appear in stored records; the rest describe preflight
refusals and are impossible wire records.

Both codec operations require exactly 108 bytes. Decode rejects unknown
versions, magic/size mismatch, truncation/trailing bytes, reserved fields,
unsupported enums, unknown validity/claim bits, impossible status/read/mask
combinations, missing identity/time/epoch/token, or missing GT claim/ACK.
Validation finishes before the destination is modified. Encode stages locally
and validates before writing any destination byte. Raw invalid snapshots and
DATA1 MBZ anomalies remain encodable; interpretation is a separate operation.
Per-record decode cannot prove cross-record chronology or live provenance.

`derive()` returns unavailable for malformed/failed captures, fault-valid=0, or
DATA1 MBZ anomalies. Callers must consult `available` before using VA, address
space, numeric engine/source/type, or optional entry fields. Failed captures
do not derive a fault-valid claim from partial raw data.

## Reproduction

```sh
bash track-b/diagnostic-src/build_core.sh
python3 track-b/diagnostic-src/deliver_core.py
```

Commands run from the lab root. The first builds Clang and GCC Debug/Release,
plain and ASan+UBSan, plus freestanding Debug/Release objects. The second checks
build/source hashes and all four unchanged baseline files, generates the
header-only patch, runs `git apply --check`, checks single-file numstat, and
reconstructs the patch payload without modifying the baseline. Detailed actual
results: `reports/core-build.md` and `logs/diagnostic-core/`.
