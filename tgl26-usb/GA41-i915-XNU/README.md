# GA4.1 — i915/XNU + ANV engineering

Target: HP Elite Dragonfly G2, i5-1135G7, Tiger Lake 8086:9A49,
Tahoe 26.6.2 / 25G83, x86_64.

This directory is the only writable engineering tree. GA40 and earlier labs
are sealed read-only inputs. No installation, driver loading, target SSH,
MMIO/BAR/page-table access, engine initialization, GPU submission, firmware or
boot/security changes are authorized.

The user explicitly authorized network retrieval of source and necessary open
build dependencies in the follow-up clarification on 2026-10-21. This replaces
the initial offline-download restriction. Pin origins, versions and hashes.
Apple SDKs remain limited to legally available local/user-provided copies.

Primary objective: reuse official i915 and existing NullMoth/Mesa components,
build the actual transport and GEM ownership foundation, distinguish native
platform source from compiled code and CPU-only tests. Never claim a CPU page
is GPU-visible or advertise i915 capabilities without their backend.

See `state.json`, `history.json`, `continuation.md`, and milestone reports.

## Reproduce isolated checks

Use new build/output directories to preserve delivery evidence:

```sh
cmake -S . -B build/new-cpu-check -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_BUILD_TYPE=Debug
cmake --build build/new-cpu-check -v
ctest --test-dir build/new-cpu-check --output-on-failure -V
GA41_XNU_OUT="$PWD/build/new-native-check" bash tools/compile-xnu.sh
```

The first three commands run only Linux CPU/injected transport tests. The
last command cross-compiles real native adapters with the pinned public
kernel-header kit and does not link or load a kext. It also statically checks
Linux/BSD ioctl request differences and LP64 structure layouts.

`anv/build_anv.sh` is the fixed-input ANV build recipe; new invocations use
fresh paths and retain failures. Original successful Linux ICD is under
`anv/artifacts/`. See `reports/ANV-BUILD-EVIDENCE-AMENDMENT.md` for the precise
failure-log retention defect in its first version.
