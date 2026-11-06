# Patch and source-delta index

The files in `patches/` are retained as provenance text. The staged R-series
patches are development history; the cumulative diffs record source comparison
against pinned upstream. Their presence does not assert that every patch was
independently tested or that the build is reproducible.

## NootedGreen history

The staged progression is:

1. `NG-R2-enable-upstream-f13b.patch` — enables the upstream `f13b` patch
   table entry.
2. `NG-R3-align-blit-scratch.patch` — adjusts the relevant real-TGL/Tahoe
   Blit3D scratch allocation size.
3. `NG-R4-upstream-noccs3-tahoe.patch` — makes the existing NOCCS3 workaround
   available to real Tiger Lake on Tahoe.
4. `NG-R5-preserve-real-tgl-topology.patch` — keeps real TGL fuse-derived
   topology instead of applying the RPL override. Its then-current 80-EU L3
   fallback was 8; it is superseded by the separate GA416 change below.
5. `NG-R6-upstream-pool-real-tgl-tahoe.patch` — applies the upstream pool
   sizing/alignment behavior on real TGL/Tahoe.
6. `GA414-NOAUX-vs-R6.patch` — adds the guarded GA414 NOAUX behavior relative
   to R6. Its HP identity/build guard is separate from the GA416 L3 gate.
7. `GA416-L3-6.patch` — changes the gated fallback value from L3=8 to L3=6 and
   adds explanatory logging. It does **not** add the NOAUX gate or HookCase
   changes.
8. `nootedgreen-elsqwait-20261105.patch` — unconditional `EXECLIST_STATUS [0x2234]`
   bit 30 (`0x40000000`) drain wait (`elsqWait`) and `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`.
9. `nootedgreen-pcfix2-20261105.patch` .. `nootedgreen-pcfix27-20261106.patch` —
   `COCLGen8CommandTransport` 151-dword compute encoder sanitization (`hpSanitizeComputeEncoder`),
   host software mid-batch preemption block (`PCFIX5`), lossless Single-Port RCS
   Execlist scheduler (`HP-SINGLEPORT-RCS` in `PCFIX6`), `CSFLTRK [0x2208]`
   decoupling (`PCFIX14`, `PCFIX16`, `PCFIX19`, `PCFIX20`), Tiger Lake
   `_WA_TABLE` `0x20d8`/`0x7010` cross-context persistence (`PCFIX25`, `PCFIX26`),
   and `ResetPreambleCmds` Packet 3 (`dw[+19] = 0x001000a0U`) GPGPU-mode
   `RT_CACHE_FLUSH` decoupling (`PCFIX27`, corresponding to the current
   `src/NootedGreen/kern_gen11.cpp` snapshot).

`NootedGreen-upstream-to-GA416.diff` is the cumulative source comparison from
NootedGreen upstream commit `95f81898be65cb9f7b3d370ca78054be4cc8a62d` to the
GA416 source snapshot. It includes the broader local source deltas and should
not be interpreted as the GA416 L3-only patch. The GA416 L3 patch itself is
the narrow diff listed in the manifest.

## HookCase deltas (separate component)

`HookCase-vendored-source-to-candidate.diff` records two changes to the
vendored HookCase source:

- `probePortMode` used a static `callback` that is never assigned in this
  vendored source. The candidate reads through the framebuffer controller's
  MMIO mapping instead, with null/bounds checks.
- The `strnstr` declaration/definition is adjusted to the SDK signature and
  C linkage used by the build.

These changes concern HookCase source/build compatibility, are separate from
NootedGreen's `getGPUInfo` L3 fallback, and are not claimed as changes made by
the GA416 L3=6 patch.

## Static provenance check

During preparation, the cumulative NootedGreen and HookCase diffs were applied
to files from the pinned upstream tree and byte-compared against the copied
source. The GA416 patch was reversed and reapplied to `kern_gen11.cpp`; the
round-tripped file matched byte-for-byte. This was a source/diff check only,
not a compile or build validation.
