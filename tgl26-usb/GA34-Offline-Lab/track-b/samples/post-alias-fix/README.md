# Post-alias-fix sample reproduction

Executed after the R1/R2 request/callback descriptor snapshots were implemented:

```sh
python3 track-b/diagnostic-src/build_samples.py --run-name post-alias-fix
```

Clang 21.1.8 ASan+UBSan compile/run exit 0; scanner 24 cases and the collector
disabled control pass. Five synthetic 108-byte binary records were produced by
actual Collector/encode/file-readback/decode/derive calls. Each binary and JSON
receipt is byte-identical to the corresponding `../initial/` file; wire version
and size remain 1/108. `sample-hashes.json` is also identical. Context and PML4
remain unknown/null, and there was no hardware or live hook.

New source/guarded-core hashes and exact commands are recorded separately in
`../../../logs/sample-core/post-alias-fix/sample-build-receipt.json` and
`clang-build-run.log` beside it. The initial receipt continues to describe the
old reviewed source hash and has not been rewritten. Use a fresh run name for
another reproduction, as documented in `../README.md`.
