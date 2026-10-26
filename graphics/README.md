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
