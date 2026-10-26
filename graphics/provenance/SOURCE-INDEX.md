# Source index

All source and ACPI files below are text. The per-file SHA-256 list for the
whole publication subtree is in [`SHA256SUMS`](SHA256SUMS).

## NootedGreen

`src/NootedGreen/` contains the NootedGreen source files listed below. The
snapshot corresponds to source commit
`f93dc2447631553d2dcc2f6d5a8a495acf57990c`; its upstream base is
`95f81898be65cb9f7b3d370ca78054be4cc8a62d`.

```text
AppleIntelParams.hpp
DisplayMergeNub.cpp
DisplayMergeNub.h
DYLDPatches.cpp
DYLDPatches.hpp
Firmware.cpp
Firmware.hpp
FirmwareADLP.cpp
HDMI.cpp
HDMI.hpp
Info.plist
IntelDPLinkTraining.cpp
IntelDPLinkTraining.hpp
kern_gen11.cpp
kern_gen11.hpp
kern_genx.cpp
kern_genx.hpp
kern_green.cpp
kern_green.hpp
kern_model.hpp
kern_netdbg.cpp
kern_netdbg.hpp
kern_patcherplus.cpp
kern_patcherplus.hpp
kern_start.cpp
```

`IGGucBinary.h` and `IGHucBinary.h` are not included: they contain embedded
firmware data and remain external build inputs. Their recorded fingerprints
are listed in [`MANIFEST.md`](MANIFEST.md), not their contents.

## HookCase

`src/HookCase/` contains the separately vendored source and metadata:

```text
HookCase.cpp
HookCase.h
HookCase.s
Info.plist
```

It is distributed under the included MIT license. The two local source changes
are described independently in [`PATCH-INDEX.md`](PATCH-INDEX.md); neither is
the GA416 L3=6 change.

## Other included source and recipes

- `acpi/SSDT-PNLF-HP-GA419.dsl` is a local text DSL table, not a compiled AML
  table or firmware-extracted ACPI source. It adds a backlight identity device
  under `\_SB.PC00.GFX0` (the table header uses OEM ID `HPTEST` and table ID
  `PNLF419`); the source does not perform GPU MMIO initialization.
- `build/build-hookcase.sh`, `build/build-nootedgreen.sh`, and
  `build/build-offline.py` are text scripts. They require locally supplied
  dependencies and are not evidence that a rebuild succeeds.
- `licenses/` contains the full license texts for the two source components.
- `patches/` contains cumulative provenance diffs and the staged R2–R6,
  GA414-NOAUX, and GA416 L3=6 patch records.

## Deliberate exclusions

This subtree does not include Git history, test/private reports, captured logs,
screenshots, compiled ACPI/AML, EFI or OpenCore files, Apple proprietary driver
source or binaries, any Mach-O/kext, signing identities/keys, or firmware
payloads. Apple TGL graphics driver internals referenced by the local source
were not available as redistributable source; see
[`CRASH-CONTEXT.md`](CRASH-CONTEXT.md).
