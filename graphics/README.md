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

## 2026-11-05 ~ 2026-11-06 Update (Complete 8/8 Geekbench 6.5.0 Metal Breakthrough, Single-Port RCS Scheduler & `CSFLTRK` Decoupling)

- `src/NootedGreen/` has been updated to the 2026-11-06 `R32-PCFIX25` snapshot (`kern_gen11.cpp` SHA-256 `f6e850103c49b45210f1a01da99958a41b91d9ae75b38a4a2a8a162336603877`, `hp_repair_policy.hpp` SHA-256 `8afdeeb24873cca2d6662dfd66634ce0a80ad50d3ea56f88e2fc3fcadeb91d3a`, tested `NootedGreen` UUID `4C4C440F-5555-3144-A10A-0B0DCEEB899C`, binary SHA-256 `d609903d06163ae8c38dc4912d8ac913d9d3509a198662852c904f868e9349f2`), building on the 2026-11-05 `R32-PCFIX2` (`f52f0d44d304e55e95b9875adb2c198b0950578b0ce4cc07191cc534962b1a54`) and 2026-11-06 `R32-PCFIX14` (`0631618dd93486600fd5b8ebefeb357c9ec22ed1cf754c90377c976bf2542038`), `R32-PCFIX16` (`d380de51e5b1c5f9b4d3f6de3c072323fd1fd3b2e335c36d19a4c9fc3d23ff4d`), `R32-PCFIX19` (`44aa1af5d8a5c9dfec326447dbb02235102141d3197b60ce0d84a05584ef22ec`), and `R32-PCFIX20` (`1cde1d6ec70d22394101841bccd96c309afed33741af348cdd23ef5474b00020`) milestones.
- Incremental patches (`patches/nootedgreen-elsqwait-20261105.patch` and `patches/nootedgreen-pcfix2-20261105.patch` .. `patches/nootedgreen-pcfix25-20261106.patch`):
  - [`patches/nootedgreen-elsqwait-20261105.patch`](patches/nootedgreen-elsqwait-20261105.patch) (Unconditional `EXECLIST_STATUS [0x2234]` bit 30 wait `elsqWait` + `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`)
  - [`patches/nootedgreen-pcfix2-20261105.patch`](patches/nootedgreen-pcfix2-20261105.patch) (Complete 8/8 Geekbench 6.5.0 Metal single-run zero-hang breakthrough via `hpSanitizeComputeEncoder`)
  - [`patches/nootedgreen-pcfix5-20261105.patch`](patches/nootedgreen-pcfix5-20261105.patch) (Host software mid-batch preemption block in `IGScheduler5::updateOptions` / `allowPreemption` / `isPreemptionAllowed`)
  - [`patches/nootedgreen-pcfix6-20261105.patch`](patches/nootedgreen-pcfix6-20261105.patch) (`HP-SINGLEPORT-RCS` lossless single-port RCS Execlist scheduler eliminating `Port1`, `LITE_RESTORE`, and `0x40002098` freezes + 100% clean `XeNG GPUREC: reset RCS ret=1`)
  - [`patches/nootedgreen-pcfix14-20261106.patch`](patches/nootedgreen-pcfix14-20261106.patch) (Endurance Stage 1 Run 1 100% zero-hang `25,088` encoders + Stage 1 Run 2 `enc=32,202` + `MEDIA_STATE_FLUSH` clearing `CSFLTRK` bits `28, 26, 25` to `0x08000001`)
  - [`patches/nootedgreen-pcfix16-20261106.patch`](patches/nootedgreen-pcfix16-20261106.patch) (`HP-SLICE` 5 DualSubslices / 80 EU `0xffffffff` 100% idle verification)
  - [`patches/nootedgreen-pcfix20-20261106.patch`](patches/nootedgreen-pcfix20-20261106.patch) (Endurance Stage 1 Run 1 100% zero-hang `25,088` encoders + Stage 1 Run 2 `enc=32,196` + 2-packet `AddPipeFlushCmd` clearing `CSFLTRK` bits `27, 26, 25` to `0x10000001`)
  - [`patches/nootedgreen-pcfix25-20261106.patch`](patches/nootedgreen-pcfix25-20261106.patch) (`_WA_TABLE` 64-bit shifted `that[0xf5f] |= 0x80` + `that[0xf68] |= 0x01` + `0x20d8`/`0x7010` persistence clearing all `CSFLTRK` cache bits `31..1` to `0x00000001`)
