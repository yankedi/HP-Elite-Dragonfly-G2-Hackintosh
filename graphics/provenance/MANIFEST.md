# Build and provenance manifest

## Scope and identity

This manifest links the public text snapshot to the recorded GA416 L3=6 test
artifact. It is provenance documentation, not a signed attestation, build
recipe lockfile, or reproducible-build claim.

| Item | Recorded value |
|---|---|
| NootedGreen upstream | [`sgiammori/NootedGreen`](https://github.com/sgiammori/NootedGreen), commit `95f81898be65cb9f7b3d370ca78054be4cc8a62d` |
| GA416 source commit | `f93dc2447631553d2dcc2f6d5a8a495acf57990c` |
| Pre-GA416 baseline | `c24ed0d67d534e2cdfbe1432da08c9b32688ef43` |
| Recorded changed NootedGreen source file | `kern_gen11.cpp` only |
| GA416 patch SHA-256 | `3a46a73a2746db7b366c0be29718b1d46a20b22f40f58cc1616a2a05d99bcaa4` |
| Tested NootedGreen binary SHA-256 | `e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb` |
| Tested NootedGreen Mach-O UUID | `4C4C44D4-5555-3144-A13A-DFB86EFBE513` |
| Recorded binary size | 459,136 bytes |
| Recorded build status | Cross-built and cross-signed; binary not redistributed here |
| Runtime | macOS 26.6.2, build `25G83`; effective L3=6 logged |
| Runtime topology | 1 slice, 10 subslices, 8 EUs/subslice, 80 EUs; donor L3 field 0 |

The GA416 functional change is the existing gated L3 fallback changing from 8
to 6 for the observed 80-EU/10-SS Tiger Lake configuration. The gate and
surrounding call/return behavior were retained. The source logs mention
`0x9118=0x88` as a prior NixOS measurement; this is not a runtime fuse read.
Separate NOAUX/NOCCS3 changes and the HookCase deltas are not attributable to
the GA416 L3 patch; see the [patch index](PATCH-INDEX.md).

## Build record versus this snapshot

The tested artifact record identifies a cross-build recipe with SHA-256
`209836f22d3c4f1cc2fbf392d541f6bf54cd219dc94d14b4482ae70dd7c4b5df` and an
`rcodesign` executable with SHA-256
`c73c5f13c9d9a343942552af12dbbea629fba30582f881b8fd1b16b8800044f5`. Those
external inputs are not included. The published
[`build/build-offline.py`](../build/build-offline.py) is a sanitized,
publication-adjusted helper, not a byte-identical copy of the recorded recipe;
it externalizes host-specific install-name and SDK inputs. The two shell
recipes are convenience alternatives, not proof of the exact invocation that
produced the recorded binary.

Rebuilding would require compatible external toolchains and dependencies,
including MacKernelSDK, Lilu, signing tools, firmware headers, and (for the
broader helper's userland functions) Apple SDK/donor graphics components. The
two firmware headers were deliberately omitted from this snapshot:

| External firmware build input | Recorded SHA-256 | Published here? |
|---|---|---|
| `IGGucBinary.h` | `959f8e83481927032b254fc7c9f9cc30cbaf7e67786cf19c4546c6113d0e3b95` | No |
| `IGHucBinary.h` | `86a4b8d5e435db269401f4c240107eff6d82ffee8043949de6dcf69149542ddd` | No |

The source-only helper requires external paths through environment variables;
see its comments and the README. No script was run and no build artifacts were
generated while preparing this publication subtree. No independent clean
rebuild, byte-for-byte comparison, or deterministic-build validation is
claimed. The exact tested binary's hash/UUID and runtime observations establish
artifact provenance, not reproducibility from these files alone.

For clarity, the publication-copy helpers accept these external paths/settings:

- `build-hookcase.sh`: `NG_BUILD_INPUTS` (MacKernelSDK dependency directory).
- `build-nootedgreen.sh`: `NG_BUILD_INPUTS` (MacKernelSDK and Lilu) and
  `NG_FIRMWARE_HEADERS` (external pinned firmware-header directory).
- `build-offline.py`: `NG_BUILD_INPUTS`, `SDKROOT`, `CLANG_APPLE`, `LD64_LLD`,
  and `RCODESIGN`; NootedGreen additionally requires `NG_FIRMWARE_HEADERS`.
  `GRAPHICS_BUILD_OUT` is optional. Its userland helper also needs the
  userland-only `GRAPHICS_USERLAND_INSTALL_NAME_DIR`,
  `GRAPHICS_XEDRV_INSTALL_NAME`, `GRAPHICS_PLUGIN_LLVM_INSTALL_NAME`, and
  `GRAPHICS_GPUCOMPILER_TBD` values. The command-line entry point in this
  snapshot builds only `NootedGreen` or `HookCase`; the retained userland helper
  is not invoked by it.

## Runtime-evidence scope

The recorded test evidence associates the source commit, binary hash/UUID,
runtime L3=6 log, and the one bounded R8 test. The Settings/About, Finder, and
Dock scenes were visually reviewed; wallpaper and all-UI pixel validation were
out of scope. Runtime logs report the separate NOAUX/NOCCS3 patches as active.
Those outcomes should not be read as proof of long-term stability or as a
per-resource CCS verdict. Later selected crashes are summarized without raw
logs in [Crash context](CRASH-CONTEXT.md).
