# Graphics source and provenance

This directory is a source-only publication snapshot for the graphics work on
the HP Elite Dragonfly G2 (GA416). It documents the NootedGreen source used for
the tested GA416 L3=6 NootedGreen artifact, its local patch history, the
separately vendored HookCase source, and the HP PNLF ACPI source.

**This is not a binary release, a complete build environment, or a claim that a
clean rebuild will reproduce the tested binary.** No graphics kext, Mach-O,
Apple driver binary, firmware payload/header, full build log, crash log, or
personal or serialized device identity is included. The source contains public
platform/model identifiers where its code requires them. The binary's SHA-256
and UUID below are artifact identifiers recorded from the test evidence; the
binary itself is intentionally absent.

## Recorded result and limitations

The recorded test used NootedGreen source commit
`f93dc2447631553d2dcc2f6d5a8a495acf57990c` and a cross-signed kext with SHA-256
`e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb` and UUID
`4C4C44D4-5555-3144-A13A-DFB86EFBE513`. On macOS 26.6.2 build `25G83`, the
runtime evidence records a 1-slice, 10-SS, 80-EU Tiger Lake device and effective
L3=6. The earlier `0x9118=0x88` fuse observation came from NixOS; the macOS
runtime log repeats that prior static measurement and is **not** a live fuse
read.

The observed Settings/Finder/Dock scenes no longer showed the previously
reported graphics artifacts, and one bounded R8 render comparison passed. This
does not establish all-UI correctness or long-term stability. Later evidence
records memory-management assertions and a watchdog timeout; it does not prove
that NootedGreen caused them. See [the crash context](provenance/CRASH-CONTEXT.md)
for the limits and public XNU reference. No deterministic rebuild is claimed;
the build and external-input caveats are in
[the provenance manifest](provenance/MANIFEST.md).

## Contents

- `src/NootedGreen/` — text source snapshot, excluding the embedded GuC/HuC
  firmware headers.
- `src/HookCase/` — text source and two separately documented local source
  deltas; these changes are not the GA416 L3=6 patch.
- `licenses/` — the included NootedGreen Thou Shalt Not Profit License 1.0 and
  HookCase MIT license. The NootedGreen license is non-profit-restricted;
  this project's source-distribution declaration and attribution are in
  [NOTICE.md](NOTICE.md). The original license remains unchanged and applies
  to subsequent redistribution.
- `acpi/SSDT-PNLF-HP-GA419.dsl` — text ACPI source for the identity-only PNLF
  device under the HP graphics device namespace.
- `build/` — publication-adjusted convenience build recipes. They have not
  been run as part of preparing this snapshot and do not supply their
  dependencies.
- `patches/` — staged local patches and cumulative source-provenance diffs.
- `provenance/` — source index, patch index, test/build facts, crash context,
  and file checksums.

See [Source index](provenance/SOURCE-INDEX.md),
[Patch index](provenance/PATCH-INDEX.md), and
[SHA256SUMS](provenance/SHA256SUMS) for the detailed inventory. From this
directory, verify the recorded files with `sha256sum -c provenance/SHA256SUMS`.
That checksum list intentionally excludes itself.

## 2026-11-05 ~ 2026-11-06 Update (100% Three-Stage GPU Endurance Breakthrough `R32-PCFIX27`, Single-Port RCS Scheduler & `CSFLTRK` Decoupling)

- `src/NootedGreen/` has been updated to the final 2026-11-06 `R32-PCFIX27` snapshot (`kern_gen11.cpp` SHA-256 `5749ea41e6ead86e240b81d6c4f12f092488ecdf5a2782477dd12d59978e4882`, `hp_repair_policy.hpp` SHA-256 `8afdeeb24873cca2d6662dfd66634ce0a80ad50d3ea56f88e2fc3fcadeb91d3a`, tested `NootedGreen` UUID `4C4C44D2-5555-3144-A1F9-D192CDF39360`, binary SHA-256 `56c2d0758770803190b70b897e06b1ed5ab5318df97fef0c1fc4c07a2de2ffd9`), which passed 100% of all three stages of the Real-Machine GPU Stability & Endurance Test Plan (`705,024` compute encoders, 0 GPU hangs, 0 `GPURestart`), building on `R32-PCFIX2` (`f52f0d44d304e55e95b9875adb2c198b0950578b0ce4cc07191cc534962b1a54`), `R32-PCFIX14` (`65e44608b815b83b7b5582210a8367462cae35883d0304b8f1e5048df15a384e`), `R32-PCFIX16` (`b5fd7fee009da89b52ec7528a4f57022ef9c34b47da7c6d113e1fefd1bb270f6`), `R32-PCFIX19` (`44aa1af5d8a5c9dfec326447dbb02235102141d3197b60ce0d84a05584ef22ec`), `R32-PCFIX20` (`1cde1d6ec70d22394101841bccd96c309afed33741af348cdd23ef5474b00020`), `R32-PCFIX25` (`d609903d06163ae8c38dc4912d8ac913d9d3509a198662852c904f868e9349f2`), and `R32-PCFIX26` (`aed26c63ed9a82386280fe920503fd4913767c2be73f8b51730034a6134aea5b`).
- Incremental patches (`patches/nootedgreen-elsqwait-20261105.patch` and `patches/nootedgreen-pcfix2-20261105.patch` .. `patches/nootedgreen-pcfix27-20261106.patch`):
  - [`patches/nootedgreen-elsqwait-20261105.patch`](patches/nootedgreen-elsqwait-20261105.patch) (Unconditional `EXECLIST_STATUS [0x2234]` bit 30 wait `elsqWait` + `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`)
  - [`patches/nootedgreen-pcfix2-20261105.patch`](patches/nootedgreen-pcfix2-20261105.patch) (Complete 8/8 Geekbench 6.5.0 Metal single-run zero-hang breakthrough via `hpSanitizeComputeEncoder`)
  - [`patches/nootedgreen-pcfix5-20261105.patch`](patches/nootedgreen-pcfix5-20261105.patch) (Host software mid-batch preemption block in `IGScheduler5::updateOptions` / `allowPreemption` / `isPreemptionAllowed`)
  - [`patches/nootedgreen-pcfix6-20261105.patch`](patches/nootedgreen-pcfix6-20261105.patch) (`HP-SINGLEPORT-RCS` lossless single-port RCS Execlist scheduler eliminating `Port1`, `LITE_RESTORE`, and `0x40002098` freezes + 100% clean `XeNG GPUREC: reset RCS ret=1`)
  - [`patches/nootedgreen-pcfix14-20261106.patch`](patches/nootedgreen-pcfix14-20261106.patch) (Endurance Stage 1 Run 1 100% zero-hang `25,088` encoders + Stage 1 Run 2 `enc=32,142` + `MEDIA_STATE_FLUSH` clearing `CSFLTRK` bits `28, 26, 25` to `0x08000001`)
  - [`patches/nootedgreen-pcfix16-20261106.patch`](patches/nootedgreen-pcfix16-20261106.patch) (Endurance Stage 1 Run 1 100% zero-hang `21,504` encoders with `fDisableCommandCoalescing=1` + Stage 1 Run 2 `enc=27,348`)
  - [`patches/nootedgreen-pcfix20-20261106.patch`](patches/nootedgreen-pcfix20-20261106.patch) (Endurance Stage 1 Run 1 100% zero-hang `25,088` encoders + Stage 1 Run 2 `enc=32,196` + 2-packet `AddPipeFlushCmd` clearing `CSFLTRK` bits `27, 26, 25` to `0x10000001`)
  - [`patches/nootedgreen-pcfix25-20261106.patch`](patches/nootedgreen-pcfix25-20261106.patch) (`_WA_TABLE` 64-bit shifted `that[0xf5f] |= 0x80` + `that[0xf68] |= 0x01` + `0x20d8`/`0x7010` persistence clearing all `CSFLTRK` cache bits `31..1` to `0x00000001`)
  - [`patches/nootedgreen-pcfix26-20261106.patch`](patches/nootedgreen-pcfix26-20261106.patch) (Golden context image `_safeHardwareContextBufferRCS` persistence of `CS_DBG1`/`CHKN3` across 7,158 context switches without runtime MMIO writes, isolating `0x7010`/`0x20d8`/`0x2050` regression)
  - [`patches/nootedgreen-pcfix27-20261106.patch`](patches/nootedgreen-pcfix27-20261106.patch) (Final 100% 3-Stage Endurance pass across `705,024` encoders by preserving `ResetPreambleCmds` Packet 1 `dw[+1] = 0x001010a0U` while stripping `0x1000 RT_CACHE_FLUSH` from GPGPU-mode Packet 3 `dw[+19] = 0x001000a0U` on the clean `PCFIX20` baseline)
