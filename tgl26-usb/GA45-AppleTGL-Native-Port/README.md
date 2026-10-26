# GA4.5 — Apple Tiger Lake 16.0.32 Native Port

Offline worktree for native TGL/Tahoe adapter work. Historical GA4.0–GA4.4
trees are read-only. No Apple proprietary binaries are committed. No
installation, loading, target reboot, EFI/NVRAM changes, or GPU experiments
are authorized by this tree.

Source baseline: JulioNectar `54d514f079bad088eb2002eb931686216f141fc5`,
NootedGreen `95f81898be65cb9f7b3d370ca78054be4cc8a62d`, IntelIGPU-Tahoe
`9baa4bbe36c4a0085efac41d07feb420f841ac6a`.

## Current status

- NootedGreen native-TGL identity/layout/RPL-hook gates: `SOURCE_IMPLEMENTED`
  and `CPU_TEST_PASS`; 12 x86_64 `MACHO_OBJECT`s built.
- `libxedrv.dylib`: `DARWIN_DYLIB_LINKED` (real `MH_DYLIB`, unsigned);
  25G83 runtime descriptor values remain `ABI_UNVERIFIED`.
- Compiler adapter/bridge: `DARWIN_DYLIB_LINKED` with dynamic LLVM/old-plugin
  lookup; `ABI_UNVERIFIED`.
- NootedGreen kext: **not linked** (`KEXT_LINKED` not achieved); no
  `MH_KEXT_BUNDLE` linker and no `libcc_kext.a`.
- Donor 16.0.32: 18/18 configured patch bytes/offsets match; see
  `manifests/donor-audit-18.json`.
- Deployment: `DEPLOYMENT_BLOCKED`; no proven legal signing/loading path.
- GPU: `NOT_TESTED_ON_GPU`; no Metal success is claimed.

## Reports and evidence

- `FINAL-REPORT.md` — ten acceptance questions and results
- `reports/BUILD-STATUS.md` — actual toolchain/link/kext results
- `reports/SIGNING-RESEARCH.md` — deployment blocker
- `staging/README.md` and `staging/manifests/components.json` — private
  staging inventory (binaries are Git-ignored)
- `reports/GIT-COMMITS.md` — local commit ledger

The private SDK copy under `toolchain/` and all donor/build binaries under
`staging/private/` or `logs/` are intentionally not tracked.
