# Coarse-to-fine graphics subtraction: first partition

Date: 2026-10-29. **Ownership and dependency boundaries are defined; new L-OFF
and R-OFF artifacts have not been built or booted.**

The reference is GA419 OpenCore with the cumulative GA416 NootedGreen source
`f93dc2447631553d2dcc2f6d5a8a495acf57990c`, on native Tiger Lake and macOS
25G83. This is an unstable reference, not a known-good control. Historical
F/A/B observations remain in the [experiment record](GRAPHICS-SUBTRACTION-PLAN.md).

## First split

The split follows functional dependencies, including inherited upstream changes,
local changes, installed components and graphics configuration:

- **L — display output and platform integration:** framebuffer, display power,
  DMC, clocks, display-register guards, platform/display identity and providers.
- **R — rendering, resources and user-space graphics:** accelerator, command
  memory, submission/reset, surface compression, Metal and compiler adapters.

This does not split source files in half. `kern_gen11.cpp` contributes to both
sides. Nor does it claim equal line counts or equal failure probability.

| ID | L-owned intervention family | First-level boundary |
| --- | --- | --- |
| L01 | Selected TGL framebuffer bytepatch arrays and XE-VALD | Candidate subtraction; retain the historically justified R2 port-probe compatibility subpatch initially |
| L02 | Framebuffer/scaler/plane/accessor initialization and cache/display-engine hooks | Treat pointer producers and consumers as one dependency group |
| L03 | Platform workaround flags, controller-start display writes and service registration | Candidate subtraction around original calls |
| L04 | TGL DMC upload, C-state/custom-AUX and subsequent DC-exit behavior | Subtract as one coupled group, including the shared `dmcIsAdlp` state |
| L05 | CDCLK, PSR, power-well and DP AUX/lane handling | Candidate subtraction; DP AUX is distinct from surface-compression AUX |
| L06 | Sleep/wake state, LCD properties, online/power/mode wrappers and shutdown stub | Restore original calls; keep the L07 startup contract initially |
| L07 | Early timings worker, boot-mode adaptation and wait-for-stamp bootstrap | Compatibility-retained pending an equivalent startup path |
| L08 | MMIO zero-SURF guards, boot hold and display diagnostics/route-only wrappers | Candidate subtraction; basic MMIO access remains; uncertain route installation stays explicit |
| L09 | PCI/device/stolen-memory integration, AGDP and platform selection | AGDP is a candidate; identity/load infrastructure is initially retained |
| L10 | DisplayMergeNub personality, PNLF and BrightnessKeys | Keep HP display configuration fixed initially; this is a control choice, not proof of necessity |
| L11 | Genx ICL framebuffer route/patch family | No ICL framebuffer in the captured F loaded list; reconsider if load identity changes |
| L12 | HookCase provider, Apple Intel helpers and both local deltas | Retain required exports and port-probe compatibility until an equivalent provider exists |
| L13 | Installed framebuffer binary/metadata differences | Assigned but unresolved binary-level changes remain fixed pending mapping |

| ID | R-owned intervention family | First-level boundary |
| --- | --- | --- |
| R01 | Accelerator SKU acceptance and IOAF2 capability patch | Initially retained load/acceptance contract; distinguish source claims of necessity from tests |
| R02 | Tahoe IOSurface format/plane ABI | Initially retain the compatibility group; plane-offset repair has historical fault/retest evidence |
| R03 | NOCCS3 resolve bypass | Initially retained because the earlier path faulted in `resolve_ccs` |
| R04 | Native HP NOAUX | Candidate subtraction; does not disable R03 |
| R05 | R3 scratch sizing and native topology/L3 fallback | Initially retained compatibility; not permanently exonerated |
| R06 | Command-pool sizing/padding and resource-free pre-processing | Candidate subtraction; preserve original allocation/free calls |
| R07 | Scheduler, GuC selection and accelerator startup/completion contract | Keep scheduler/profile and the completion marker used by L07 consistent |
| R08 | Native GT/forcewake/IRQ/error handling, reset-list RING_MODE writes and engine diagnostics | Candidate subtraction around the retained startup skeleton |
| R09 | PAVP, task/context/Blit3D, queue marker, submit/barrier and route-only wrappers | Candidate subtraction; named compatibility/resource subblocks belong to R02–R06 |
| R10 | DYLD validation hook and VideoToolbox/GVA/HEVC/ICL-Metal page patches | Candidate subtraction while preserving original page validation |
| R11 | Installed Metal bytepatch policies and PoshDisable | Rendering policies are candidates; load commands/compiler paths remain compatible; extra local deltas need mapping |
| R12 | libxedrv resource, compression, stencil, nocopy, fill/copy and diagnostic policies | Source families inventoried; installed-binary mapping must be closed before claiming effective subtraction |
| R13 | libxedrv entry points, descriptor ABI and capability adaptations | Retain compatible 25G83 behavior; do not substitute a 25G241 source recipe as if equivalent |
| R14 | Compiler adapter, LLVM bridge, old-plugin patches and shader resources | Keep ABI/path/re-export contracts; map separable policy changes before removal |
| R15 | GL/VA/VAME/Shared and remaining differences in both installed Metal copies | Explicit unresolved component ownership; recipe presence does not prove patch installation |
| R16 | Installed accelerator binary/metadata and external GuC/HuC inputs | Explicit compatibility/opaque component ownership; removing accelerator attachment is not a valid subtraction |

Shared context is recorded separately: **C01** loader/Lilu/PatcherPlus/ABI and
original-call infrastructure; **C02** OS, non-graphics boot configuration and
diagnostic environment; **C03** unresolved runtime-dependency and binary-mapping
coverage. These are remaining scope, not an untested third side declared innocent.
The external firmware fingerprints remain in the
[provenance manifest](../graphics/provenance/MANIFEST.md).

## Audit corrections and dependencies

- The outer `!isRealTGL` block at `kern_gen11.cpp:5364-5435` gates not just
  MultiForceWake but also compression/GVA property injection. These property
  changes are **inactive** on this native-TGL reference. The separately installed
  NOAUX/NOCCS3 patches remain active.
- `ccont` is assigned in the routed `AppleIntelPowerWellinit` at line 4891.
  Removing a producer without its consumers is not an independent subtraction.
- L07 includes `fbTimingsWorker` at lines 954–1014 and its registration at
  1314–1329. The absent `-ngreenfixbootpatch` is a different path.
- L07's wait-for-stamp wrapper reads R07's `gGfxAccelStartDone`. Keep that
  completion contract even when subtracting accelerator-start side effects.
- libxedrv policies must be disabled both in constructor installation and in
  the late retry worker, or a supposedly disabled hook can be installed again.
- Rebuilt candidates must match their **own** recorded hashes/UUIDs. Unchanged
  components should match the reference; new NG binaries need not share F's UUID.

Native-inactive RPL/Display13 branches, absent `-ngreenxefix` routes, disabled
optional monitor modes, unregistered HDMI, uncompiled netdbg, unselected PHY
helpers and commented HookCase installation code remain documented. They are
not counted as effective OFF variables.

## Coverage evidence and its limit

Local checks assigned every file in the selected inventories:

- 29 published NootedGreen/HookCase source files; NG files match immutable f93
  objects, while HookCase retains its separate vendored/local provenance.
- 19 macOS source/recipe files matching f93 objects.
- 187 files across ten installed graphics-component roots captured during F.
- Every archived OC boot argument, ACPI and kext entry; no OC Kernel/Patch
  entries, and only the recorded IGPU platform property in DeviceProperties.
- The GPUBundles Metal copy matches all 63 files of the sealed baseline; all
  ten MTL17 table replacement positions match its executable. The separately
  prepared GA417 POSH candidate is not that installed baseline.

This is **inventory-level coverage**, not proof that every runtime dependency,
executable block or binary modification has been mapped. In particular, the two
installed Metal copies differ. Source recipe equality does not establish that
the installed libxedrv/compiler artifacts contain precisely those source changes.
Private inventories, raw captures and access information remain outside this tree.

## How the first comparison is constructed

Let E-L and E-R contain **all** removable, dependency-resolved subunits of their
respective sides. The same explicit compatibility base is retained in both:

```text
L-OFF = F minus E-L       (all E-R retained)
R-OFF = F minus E-R       (all E-L retained)
```

Unresolved/fixed units cannot be silently counted as removed. Before creating
the pair, close the installed-component mapping, freeze the exact retention
ledger, implement the two controls and audit every intended delta. User-space
replacement also needs a recoverable component plan; an EFI-only image cannot
perform the entire R subtraction. A rebuilt all-on control must be distinguished
from the historically loaded F artifact.

After reaching a comparable native-TGL working state, use the same workload and
capture protocol and at least a 60-minute no-reproduction observation window.
Keep pmap, watchdog, other panics, GPU errors, freezes and SSH loss separate.
Recursively split only the region supported by repeatable valid comparisons.
Both-fail or both-no-reproduction results require interaction/multiple-fault or
fixed-context checks, not an arbitrary choice. Confirm the eventual candidate
through restoration/reintroduction.

Publication and repository checks passed for this documentation/inventory work:
`python3 scripts/check-publication.py`, `make -C mac-for-elitebook check`, and
`git diff --check`; the original private workspace also passed `make check` and
`git diff --check`. These are static checks, not a candidate build or hardware test.
