# TGF4 FaultRecord v2

The v2 record is a fixed-size **384-byte**, little-endian, byte-oriented
format.  It uses the existing `TGF4` magic with version `2`; it is not a
reinterpretation of the GA34 v1 structure.  No C/C++ object layout is written
to the wire.  Every integer is encoded explicitly as little-endian and every
reserved byte must be zero.

The exact v1 GA34 header copies are in `source/legacy/` and retain their
original 108-byte `TGF4` version-1 codec unchanged.  The v1 decoder rejects a
v2 header without changing its output parameter.  `dispatch.hpp` strictly
dispatches v1 and v2 and rejects unknown versions.

The historical v1 header necessarily retains its original `derive()` API for
byte/source compatibility.  GA37 does not attach that API to a reader or use
it to authorize a v2 derived VA.  All new v2 derivation goes through
`deriveIfCoherent()`, which has both independent gates.

## Header and offsets

All offsets are byte offsets.  The implementation uses 8-byte alignment for
64-bit fields; padding is explicit and zero-filled.  `u16`, `u32`, and `u64`
mean unsigned little-endian integers.

| offset | size | field | rule |
|---:|---:|---|---|
| 0 | 4 | magic | `TGF4` (`0x34464754`) |
| 4 | 2 | version | exactly `2` |
| 6 | 2 | header size | exactly `16` |
| 8 | 4 | record size | exactly `384` |
| 12 | 4 | header flags | reserved, zero |
| 16 | 8 | presence mask | known field bits only |
| 24 | 8 | unknown mask | disjoint from presence; known bits only |
| 32 | 4 | capture flags | explicit enable/raw-preserved/external-correlation |
| 36 | 4 | validity flags | raw/metadata/derived flags |
| 40 | 4 | record status | complete, partial, or refused |
| 44 | 4 | read attempts | bounded 0..3 |
| 48 | 4 | engine layout | exactly Linux v6.18 five-bit layout (`1`) |
| 52 | 4 | READ_SAFE summary | four-valued status |
| 56 | 4 | coherence summary | four-valued status |
| 60 | 4 | reserved | zero |
| 64 | 8 | sequence | required, nonzero |
| 72 | 8 | monotonic timestamp | required, nonzero |
| 80 | 8 | boot ID | required, nonzero |
| 88 | 8 | hang ID | required, nonzero |
| 96 | 8 | caller ID | required, nonzero |
| 104 | 8 | reset epoch | required, nonzero |
| 112 | 8 | exclusion token | required, nonzero |
| 120 | 4 | raw fault DWORD | raw only |
| 124 | 4 | raw data0 DWORD | raw only |
| 128 | 4 | raw data1 DWORD | raw only |
| 132 | 4 | reserved | zero |
| 136 | 4 | derived flags | bit 0 is derived VA |
| 140 | 4 | derived address space | canonical calculation, not raw |
| 144 | 4 | derived engine v6.18 | canonical calculation |
| 148 | 4 | derived engine v5.15 | canonical calculation |
| 152 | 4 | derived fault type | canonical calculation |
| 156 | 4 | derived source ID | canonical calculation |
| 160 | 4 | derived page size | canonical calculation |
| 164 | 4 | reserved | zero |
| 168 | 8 | derived virtual address | allowed only with both gates PASS |
| 176 | 8 | context identity | optional; never invented |
| 184 | 8 | PML4 | optional; never invented |
| 192 | 8 | ring head | optional; never invented |
| 200 | 4 | engine ID | optional; never invented |
| 204 | 4 | reserved | zero |
| 208 | 8 | allocation generation | optional; never invented |
| 216 | 4 | reset/clear phase | bounded enum |
| 220 | 4 | provenance kind | bounded enum; claim only |
| 224 | 8 | provenance claim/reference | opaque, not authenticated |
| 232 | 48 | 12 READ_SAFE statuses | one u32 per condition |
| 280 | 8 | reserved | zero |
| 288 | 40 | 10 coherence statuses | one u32 per dimension |
| 328 | 8 | independent read timestamp 0 | optional |
| 336 | 8 | independent read timestamp 1 | optional |
| 344 | 8 | independent read timestamp 2 | optional |
| 352 | 8 | sweep epoch | optional |
| 360 | 24 | reserved | zero |

## Presence and unknown semantics

Presence bits identify known fields.  Unknown bits identify fields deliberately
unknown.  A field must not be both.  A field that is absent or unknown is
encoded as canonical zero; a decoder never infers it from another field.
Unknown field bits, reserved header flags, invalid enum values, nonzero
reserved bytes, bad ranges, truncation, extra bytes, and mismatched summaries
are rejected.  Decode and encode use temporary storage and commit only after
all checks, so an output object is unchanged on failure.

Timestamps are ordered only when all three timestamp fields are present and
known.  Missing/unknown timestamps do not acquire a guessed ordering.

## Derived-field contract

Derived fields are canonical calculations from the three raw DWORDs, never
independent truth.  A v2 record carrying `DerivedVAValid` must pass all of the
following 16 source conditions: (1) raw fault presence, (2) raw data0
presence, (3) raw data1 presence, (4) all three raw-valid bits, (5) the fault
valid bit, (6) DATA1 MBZ bits `0xfffffe00` are zero, (7) the DATA1 VA-high
nibble is masked to four bits, (8) the combined page is within the checked
36-bit page bound, (9) address space is the explicit DATA1 GTT bit, (10)
v6.18 engine is the `0x1f000` mask and is at most 31, (11) v5.15 engine is
the `0x7000` mask and is at most 7, (12) fault type is the `0x6` mask and is
at most 3, (13) source ID is the `0x7f8` mask and is at most 255, (14) page
size is the `0x180` mask and is at most 3, (15) stored VA equals
`((DATA1 & 0xf) << 44) | (DATA0 << 12)`, and (16) every stored derived scalar
equals the same canonical calculation.  Encode and decode both enforce this
relation; a false derived VA or out-of-range derived scalar is rejected.

DATA1 MBZ bits do **not** invalidate an otherwise raw, untrusted record when
no derived flag is present.  They only prevent derivation and any derived
claim.  This preserves raw evidence without claiming that it is a valid
address calculation.  The external-correlation flag is bidirectional:
`ExternalCorrelation` provenance requires the flag and a nonzero opaque
reference, while the flag requires that provenance kind.  Neither is
self-authentication.

## Compatibility and strictness

* v1 remains exactly 108 bytes and its original decoder is untouched.
* The old v1 decoder rejects v2 cleanly.
* v2 accepts exactly 384 bytes and version 2.
* Unified dispatch accepts only v1 or v2; unknown versions are rejected.
* There is no permissive future-field mode: unknown field bits and nonzero
  reserved bytes reject, preventing silent reinterpretation.

The source contains no actual reader or backend.  Test records are synthetic
and are labelled as such; they are not device confidence.
