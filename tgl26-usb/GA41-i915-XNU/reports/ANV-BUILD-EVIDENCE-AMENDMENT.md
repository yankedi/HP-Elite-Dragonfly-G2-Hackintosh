# ANV build evidence amendment

Date: 2026-10-21

This amendment supplements `reports/ANV-BUILD.md` without changing the
successful ICD or its existing successful logs.

Parent integration preserved the four exact managed transcript JSON readbacks
inside `logs/anv-failures/managed-readbacks/`, with hashes matching the original
SQLite records in RAW-LOG-STATUS.md. These contain partial original output,
not the missing complete per-run raw streams. They can now migrate with GA41
without depending on the external OpenCode database.

* The raw failed configure/build logs from the fixed-path first script were
  overwritten before evidence hygiene was requested.  They are explicitly
  recorded as missing; no reconstructed text is claimed as a raw log.
* Provenance for the available managed readbacks and their hashes is in
  `logs/anv-failures/RAW-LOG-STATUS.md`.
* `anv/build_anv.sh` now uses unique per-run build, artifact, temporary, and
  log paths by default; it has no `rm -rf` cleanup and refuses existing paths.
  `--resume` is explicit and still requires fresh log/artifact destinations.
* Configure and Ninja status are captured through conditional commands, so
  `set -e` cannot exit before `configure_rc`/`build_rc` is written.
* Future environment evidence is a restricted compiler/build-path record, not
  a complete shell environment dump.

Static verification performed without invoking a build: `bash -n
anv/build_anv.sh` returned `bash-n-ok`.  Amended script SHA-256:
`09556b6da34d46d0387922b39a7eb97fccd150ad1e3bbf80b0b870f8ddc8ec3c`.

The existing final artifact hashes remain:

```text
e8c99be081ec15eeae6b7fdc5178c2c1871f5d1c79a5e5dd7dff50e69e15fe5a  anv/artifacts/lib/libvulkan_intel.so
f29074f09b7e0b5283a7b842f07ecf8b79395908b0c7b382084d695c3fb27736  anv/artifacts/share/vulkan/icd.d/intel_icd.x86_64.json
```
