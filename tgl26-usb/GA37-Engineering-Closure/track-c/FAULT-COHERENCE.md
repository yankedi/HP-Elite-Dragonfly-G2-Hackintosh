# GA37 Track C — independent FAULT_DATA_COHERENT gate

`FAULT_DATA_COHERENT` is independent from `READ_SAFE`.  A read can be safe to
perform while the three fault DWORDs are not proven to be one tuple; a tuple
can be internally described without proving that the reads were safe.  Neither
state is substituted for the other.

The ten four-valued coherence dimensions are:

| dimension | required claim |
|---|---|
| `Tuple` | fault/data0/data1 belong to one captured tuple |
| `SweepEpoch` | all subreads belong to one unique sweep epoch |
| `Latch` | hardware latch/hold semantics cover the whole read window |
| `ABAExcluded` | an A→B→A generation cannot pass as unchanged |
| `Address` | the address interpretation is tied to this tuple |
| `ContextPML4` | context identity and PML4 association are known, not guessed |
| `Engine` | engine identity is known for this tuple |
| `AllocationGeneration` | allocation generation is known and stable |
| `ResetClearPhase` | reset/clear phase is known for the whole tuple |
| `Completeness` | all required reads and metadata are present |

Every dimension must be `PASS` for the coherence gate to pass.  Any `UNKNOWN`
is `BLOCKED`; `CONDITIONAL` is never treated as pass.  Current project state
is `FAULT_DATA_COHERENT=UNKNOWN` with no backend and no device reads.

## Raw and derived values

Raw DWORD fields are separate from derived virtual addresses.  A raw record is
never used to invent context ID, PML4, ring head, engine ID, allocation
generation, or provenance.  Unknown optional fields have canonical zero values
and an explicit unknown bit.  Presence and unknown masks are disjoint.

`deriveIfCoherent()` requires all of:

* a structurally valid complete record;
* explicit read enable and all read-safety conditions `PASS`;
* the record's coherence statuses all `PASS`;
* an independent coherence evidence object whose statuses all `PASS`;
* a valid fault DWORD.

It also enforces the v1/TGL-derived masks, ranges, exact raw-to-derived
calculation, and DATA1 MBZ rule described in `FAULTRECORD-V2.md`.  A record
with MBZ bits may still preserve raw DWORDs as untrusted data, but cannot
produce a derived VA or carry a derived claim.

Without that conjunction it returns no derived VA.  The helper derives only
the VA; it does not create missing identity fields.  A derivable value is not
proof of tuple coherence.

## Offline association

An old v1 report may be retained with an explicit opaque external-correlation
reference.  `associateLegacyExternal()` stores the old record, a refusal-state
v2 metadata shell, and that reference only.  `makeLegacyExternalV2()` marks
the raw tuple and all context/PML4/ring-head/engine/allocation-generation
fields `UNKNOWN` and does not copy raw words into a supposedly safe capture.
It does not fill those fields.  Provenance and correlation values are claims,
not self-authentication.
