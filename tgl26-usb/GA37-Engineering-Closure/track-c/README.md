# GA37 Track C

Offline-only implementation of independent `READ_SAFE` and
`FAULT_DATA_COHERENT` evidence states plus strict TGF4 v2 file codec.

* `READ-SAFETY-GATE.md` — twelve read-safety conditions and current BLOCKED assessment.
* `FAULT-COHERENCE.md` — ten independent tuple/data coherence dimensions and gated derivation.
* `FAULTRECORD-V2.md` / `schema.md` — normative 384-byte layout and endian/offset rules.
* `source/fault_record_v2.hpp` — codec and gate model; `source/dispatch.hpp` — strict v1/v2 dispatch and legacy external association.
* `source/legacy/` — exact GA34 v1 108-byte header copies; do not edit.
* `tests/` — malformed input, atomic output, round-trip, compatibility, gate and canonical-unknown tests.
* `tools/tgf4decode.cpp` — strict offline decoder CLI.

Reproduce with:

```sh
./run_tests.sh
```

The matrix is recorded in `logs/build/matrix.tsv`, commands and exit codes in
`logs/build/commands.log`, and the machine-readable result in `results.json`.
Current result: all Clang/GCC Debug/Release/ASan/UBSan profiles pass; actual
reader/backend are `NONE`, `READ_SAFE=BLOCKED`, and
`FAULT_DATA_COHERENT=UNKNOWN`.
