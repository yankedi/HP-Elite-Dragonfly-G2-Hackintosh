# GA37 Track C — independent READ_SAFE gate

`READ_SAFE` is a safety state, not a fault-data interpretation state.  The
codec has no MMIO reader and no backend; the gate is a pure CPU decision model.
An implementation may connect a reader only when the gate returns `PASS` and
the caller has explicitly enabled it.  The default is disabled.  No current
evidence reaches that state.

## Four-valued evidence

Every condition is exactly one of `UNKNOWN`, `CONDITIONAL`, `PASS`, or
`FAILED`.  Invalid enum values are rejected.  `UNKNOWN` has precedence and
returns `BLOCKED`; otherwise `CONDITIONAL` returns `CONDITIONAL`, `FAILED`
returns `FAILED`, and only all `PASS` values plus explicit enable returns
`PASS`.  A matrix of PASS values never turns enable on by itself.

The twelve independent read-safety conditions are:

1. `CorrectBinary`
2. `CorrectHookABI`
3. `CorrectGTDomain`
4. `ObjectLifetime`
5. `MMIOAddressMapping`
6. `RuntimePowerHeld`
7. `GTReferenceHeld`
8. `SameRequestACK`
9. `ReadSideEffects`
10. `ResetClearTeardownExcluded`
11. `RecoveryUnaffected`
12. `DefaultDisabled`

This retains every GA36 condition without treating unrelated claims as
equivalent: GA36 `MMIOReadSafe` is decomposed into lifetime, address mapping,
read-side-effect and recovery checks; `ResetExcluded` is the reset/clear/
teardown condition; and `FaultTupleConsistencyEstablished` is represented by
the separate coherence gate below.  `CorrectGTDomain`, PM, GT reference and
same-request ACK remain separate read-safety facts.

| GA36 condition | GA37 owner |
|---|---|
| CorrectBinary | READ_SAFE / CorrectBinary |
| CorrectHookABI | READ_SAFE / CorrectHookABI |
| CorrectGTDomain | READ_SAFE / CorrectGTDomain |
| RuntimePowerHeld | READ_SAFE / RuntimePowerHeld |
| ForcewakeReferenceHeld | READ_SAFE / GTReferenceHeld |
| ForcewakeACKConfirmed | READ_SAFE / SameRequestACK |
| ResetExcluded | READ_SAFE / ResetClearTeardownExcluded |
| MMIOReadSafe | READ_SAFE / ObjectLifetime + MMIOAddressMapping + ReadSideEffects + RecoveryUnaffected |
| FaultTupleConsistencyEstablished | FAULT_DATA_COHERENT / ten independent dimensions |

## Current project assessment

The current offline evidence is deliberately:

| condition | state |
|---|---|
| CorrectBinary | CONDITIONAL |
| CorrectHookABI | CONDITIONAL |
| CorrectGTDomain | CONDITIONAL |
| ObjectLifetime | UNKNOWN |
| MMIOAddressMapping | UNKNOWN |
| RuntimePowerHeld | UNKNOWN |
| GTReferenceHeld | UNKNOWN |
| SameRequestACK | UNKNOWN |
| ReadSideEffects | UNKNOWN |
| ResetClearTeardownExcluded | UNKNOWN |
| RecoveryUnaffected | UNKNOWN |
| DefaultDisabled | PASS |

Therefore `READ_SAFE=BLOCKED`.  There is no actual reader connected, no
hardware backend, and no path that treats a mock callback as a device read.
Raw DWORD preservation is accepted by the v2 validator only for a record that
explicitly carries read-safe PASS evidence and explicit read enable.  This is
a format rule, not evidence that such a record currently exists.

The nine GA36 statuses are not silently reused as a single boolean.  In
particular, a caller claim, stable observer epoch, successful codec decode,
absence of a panic, or a static binary match cannot self-promote any condition
to PASS.
