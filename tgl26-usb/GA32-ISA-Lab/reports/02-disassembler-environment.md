# 02 — Disassembler environment (IGA + Mesa EU reference)

Status: **reference facts and source map, not a conclusion.** This document
records the exact tool commits, command-line surface and observed behaviour of
the two EU disassembly stacks available to this lab, plus the Mesa 23.3.6 API
points they rest on. It deliberately does not decide anything about the Gen11
candidate images; that belongs to the analysis workstreams.

All observations below were made on the local development host with no
hardware access. IGA sources were read and the binary was run; Mesa sources
were read only.

---

## 1. Exact commits

| Component | Pin | Notes |
|---|---|---|
| IGA (Intel Graphics Assembler), inside IGC | `c36a504a4e6c68030c3302646aa396b8b59b22cb` | `intel/intel-graphics-compiler`, visa/iga subtree; `iga64 --help` reports `Intel Graphics Assembler 1.1.0-c36a504`. Subject: `[Autobackout][FunctionalRegression] Revert of change: 55227b75…: Use a corrected register pressure for GRF selection`. |
| Mesa EU compiler (reference) | `863338275d915e867319c3690ffd3272b06303c3` | `mesa-23.3.6`; `src/intel/compiler`. Source-only reference here. |

Both are pinned, not floating. IGA is built by `tools/iga/build.sh`; Mesa is
cloned pristine under `tools/mesa-eu/source` and is not built in this lab.

---

## 2. IGA source layout and build

- Build tree: `tools/iga/source/visa/iga` (CMake). The clone is a **shallow,
  blob-filtered, sparse** checkout at the pin above; sparse paths in use are
  `visa/iga` and `inc`.
- The first build failed with `fatal error: 'common/secure_mem.h' file not
  found` because the sparse checkout lacked `inc` (evidence:
  `logs/iga-build.log`). Adding `inc` (and `visa/iga`) fixed it
  (`logs/iga-build-retry.log`, 101/101 targets).
- **`tools/iga/build.sh`** is the repeatable, non-destructive entry point:
  1. verifies `HEAD == c36a504…` and refuses (without reset) on mismatch;
  2. creates a sparse clone only if `tools/iga/source/.git` is absent, and adds
     `visa/iga`/`inc` only if `inc/common/secure_mem.h` or
     `visa/iga/CMakeLists.txt` is missing;
  3. configures `tools/iga/build` (Ninja, Release) if unconfigured, then builds
     the `iga64` target;
  4. smoke-checks the binary.
  It never runs `git reset`, `git clean`, `git checkout -f`, or deletes the
  build directory. A second run is a no-op on the source tree.
- Output binary: `tools/iga/build/IGAExe/iga64` (linked against
  `libiga64.so` in the same build tree).

---

## 3. IGA CLI

Entry point: `visa/iga/IGAExe/iga_main.cpp`. Title/usage at `:19`-`:40`; option
table defined through `:41`-`:461`.

Core options:

| Option | Meaning | Source |
|---|---|---|
| `-a` / `-d` | force assemble / disassemble | `iga_main.cpp:41`, `:50` |
| `-p PLATFORM` | select platform (see §4) | `iga_main.cpp:130` |
| `-o FILE` | output file (default stdout) | `iga_main.cpp:169` |
| `-n` | numeric labels | `iga_main.cpp:77` |
| `-q` / `-v INT` | verbosity (`-q` = `-v=-1`) | `iga_main.cpp:83`, `:87` |
| `--color` | ANSI colouring (`always`/`never`/`auto`) | `iga_main.cpp:59` |
| `--output-on-fail` | **disassembly only**: print partial listing on error | `iga_main.cpp:174`, `disassemble.cpp:41` |
| `-h`, `-h=p`, `-h=...` | help, platform list, per-option help | see `logs/tool-smoke-iga-help.txt`, `logs/tool-smoke-iga-platforms.txt` |

Mode/platform inference: if `-a`/`-d` is not given, the file extension decides
mode (`asm*`→assemble, `krn*`/`dat*`→disassemble) and platform (`*.asm12p1` ⇒
platform `12p1`); see `iga_main.hpp:222`-`241` and `inferPlatform`
`iga_main.hpp:188`. Platform names are normalised: `12.1`→`12p1`,
`GEN12P1`→`12p1`, `TGLLP`→`tgllp` (`normalizePlatformName`
`iga_main.hpp:177`-`186`; matcher `iga_main.cpp:140`-`167`).

Exit status: `hasError ? EXIT_FAILURE : EXIT_SUCCESS` (`iga_main.cpp:537`). A
decode or assemble error therefore returns non-zero.

`-W…` warnings group: `none`, `all`, `default`, `normal-form`, `regions`,
`types`, `scheduling` (`iga_main.cpp:183`-`:222`).

`-X…` experimental group (`iga_main.cpp:227`-`:449`), relevant to this lab:

- `-Xautocompact` / `-Xno-autocompact` / `-Xforce-no-compact` /
  `-Xwarn-on-compact-fail` — compaction control (§5).
- `-Xauto-deps`, `-Xauto-sbid-counter`, `-Xswsb-mode INT`, `-Xsbid-count INT` —
  dependency/SWSB control (§6).
- `-Xprint-pc`, `-Xset-pc-base INT`, `-Xprint-bits`, `-Xprint-defs`,
  `-Xprint-deps`, `-Xprint-json`, `-Xprint-jsonV1`, `-Xprint-ldst` — output.
- `-Xdsd` (decode send descriptor), `-Xifs` (decode instruction fields),
  `-Xdcmp` (debug compaction), `-Xlist-ops` (op/description table) — standalone
  modes (`iga_main.cpp:271`-`:357`).
- `-Xnative` — use IGA's native encoder/decoder instead of the GED path
  (`iga_main.cpp:358`; see §5/§8 for why this matters).

The encoder/decoder option bits are public API in
`visa/iga/IGALibrary/api/iga.h`: `IGA_ENCODER_OPT_AUTO_COMPACT 0x1`,
`…_AUTO_DEPENDENCIES 0x2`, `…_ERROR_ON_COMPACT_FAIL 0x4`, `…_USE_NATIVE 0x8`,
`…_FORCE_NO_COMPACT 0x10`, `…_AUTO_SBID_COUNTER 0x20` (`iga.h:280`-`296`);
`IGA_DECODING_OPT_NATIVE 0x1` (`iga.h:443`).

---

## 4. Platform support

`iga64 -h=p` (captured `logs/tool-smoke-iga-platforms.txt`) lists:

| Suffix | Aliases |
|---|---|
| `7p5` | `hsw` |
| `8` | `bdw` |
| `9` | `skl` |
| `10` | `cnl` |
| `11` | `icl` |
| `12p1` | `xe`, `xelp`, **`tgl`**, `tgllp`, `dg1` |
| `12p5` | `xehp` |
| `12p71` | `xehpg` |
| `12p72` | `xehpc` |
| `2` | `xe2`, `lnl` |
| `3` | `xe3`, `ptl` |
| `3pxpc` | `xe3pxpc` |

Source of truth: the `Model` table `visa/iga/IGALibrary/Models/Models.cpp:400`-
`:434` and the registered list `ALL_MODELS` at `:436`-`:439`; the string names
come from `Model::names` and are exposed via `iga_platform_names`
(`IGALibrary/api/iga.cpp:162`) and `igax::QueryPlatforms` (used at
`iga_main.cpp:105`). The `Platform` enum is `IGALibrary/IR/Types.hpp:27`-`:57`;
`IGA_GEN12p1` is kept as a binary-compat alias that maps to `IGA_XE`
(`Types.cpp:52`-`:58`, `api/iga.h:114`).

Note: enum values such as `GEN6`, `GEN7`, `GEN8LP`, `GEN9LP`, `GEN9P5` exist but
are **not** in `ALL_MODELS`, so they are not selectable with `-p` (they fold
onto `GEN8`/`GEN9` in `Model::LookupModel`, `Models.cpp:445`-`:455`).

Consequence for this lab: the Tiger Lake target is `-p=12p1` (aliases include
`tgl`), and the existing candidate binaries are Gen11, for which `-p=11` is the
model. Both are served by the same `iga64` binary but by different `Model`
objects, so decoding Gen11 bytes with `-p=12p1` (or the reverse) is a model
mismatch, not a neutral re-decode.

---

## 5. Compaction behaviour

IGA compaction is driven by the GED backend by default. The native compactor
(`IGALibrary/Backend/Native/InstCompactor.cpp`) is implemented only for a
subset; on the family-XE path it returns `CR_NO_FORMAT` and the GED path does
the work (`Backend/Native/InstCompactor.cpp:62`-`:81`).

Assembler decision (`IGALibrary/Backend/GED/Encoder.cpp:306`-`:348`):

1. `-Xforce-no-compact` ⇒ never compact (`mustNotCompact = true`, `:314`);
2. else `{NoCompact}` ⇒ never compact;
3. else `{Compacted}` ⇒ compact or fail;
4. else if `-Xautocompact` ⇒ try to compact; otherwise leave 16 B.

On success the encoder adds `InstOpt::COMPACTED` and emits 8 B; on
`GED_RETURN_VALUE_NO_COMPACT_FORM` with `{Compacted}` it errors, unless
`-Xwarn-on-compact-fail` downgrades it to a warning (`:328`-`:335`). If
compaction fails it falls back to native 16 B encoding (`:340`-`:347`). There is
also a `compactRestrict` prepass to avoid a 16 B instruction straddling a 64 B
cache-line boundary (`Encoder.cpp:114`-`:124`, `:149`-`:239`).

Decoder framing (`IGALibrary/Backend/GED/Decoder.cpp:336`-`:348`): the
instruction length is `getBitField(COMPACTION_CONTROL, 1) ? 8 : 16`; an
over-short tail is reported as `unexpected padding at end of kernel`. An error
instruction created for an 8 B slot is tagged `{Compacted}`
(`Decoder.cpp:2535`-`:2537`).

Observed on this build (evidence `logs/tool-smoke-iga-swsb-compact.txt`):

- the upstream Gen12 kernel (160 B with `-Xforce-no-compact`) becomes **152 B**
  with `-Xautocompact` (one instruction compacts);
- `mov … {Compacted}` and `send … {Compacted}` both fail with
  `error: GED unable to compact instruction` and exit 1; adding
  `-Xwarn-on-compact-fail` turns the same line into `warning: …` and exit 0;
- disassembly marks decoded compact instructions with `{Compacted}`
  (e.g. `logs/vs-11.iga.asm`).

---

## 6. SWSB behaviour

SWSB (`{…}` dependency annotations) encoding modes are defined in
`IGALibrary/api/iga_types_swsb.hpp:27`-`:50` (`SWSB_ENCODE_MODE`:
`SingleDistPipe`=1, `ThreeDistPipe`=2, `FourDistPipe`=3,
`FourDistPipeReduction`=6, `ThreeDistPipeDPMath`=7, `FiveDistPipe`=8,
`FiveDistPipeReduction`=9, `FiveDistPipeCvtToInt`=10,
`FiveDistPipeSWSBCntr`=11, `FiveDistPipeCvtToIntNoFwd`=12). The `SWSB` struct
and its `DistType`/`TokenType`/`InstType`/`SpecialToken` enums are at
`iga_types_swsb.hpp:75`-`:101`.

Default mode per platform (`IGALibrary/Models/Models.hpp:355`-`:372`):

| Platform | Mode |
|---|---|
| XE (`12p1`, incl. TGL) | `SingleDistPipe` |
| XE_HP / XE_HPG | `ThreeDistPipe` |
| XE_HPC (`12p72`) | `FourDistPipeReduction` |
| XE2 (`2`) | `FourDistPipeReduction` |
| XE3 (`3`) | `FiveDistPipe` |
| ≥ XE3P_XPC | `FiveDistPipeCvtToIntNoFwd` |
| others | `SWSBInvalidMode` |

If `swsb_encode_mode` is 0 (the CLI default, `iga_main.hpp:57`) the encoder
derives the mode from the platform (`Backend/GED/Encoder.cpp:56`-`:59`).
`-Xswsb-mode INT` overrides it (`iga_main.cpp:425`); `-Xauto-deps` triggers the
`SWSBAnalyzer` (`Encoder.cpp:64`-`:71`), with `-Xauto-sbid-counter`/`-Xsbid-count`
(default 16, `iga_main.hpp:58`).

Observed on this build (`logs/tool-smoke-iga-swsb-compact.txt`,
`logs/tool-smoke-iga-official-jsonv2.txt`): on `12p72`, a non-zero distance
pipe on a send is rejected as `error: invalid SWSB`:

- `send.gtwy … {EOT,A@1}` ⇒ `invalid SWSB` (also `{A@1}`, `{@1}`, `{I@1}`,
  `{F@1}`, `{L@1}`, `{EOT,@1}`, `{A@2}`);
- `{EOT}` and `{EOT,A@0}` are accepted; `{A@0}` re-disassembles as `{EOT}`;
- the same `A@1`/`F@1` annotations **are** accepted on ALU ops (the `add`/`mul`
  lines of the official example round-trip as `{A@1}`/`{F@1}`).

This is exactly why the verbatim `IGAJSONv2.md` example does not assemble:
its final `send.gtwy … {EOT,A@1}` is rejected here. `tests/samples/` keeps the
verbatim file and a one-token `{EOT}` variant so the difference is reproducible.

---

## 7. Unknown / invalid byte behaviour

Decoder path (`IGALibrary/Backend/GED/Decoder.cpp`):

- `GED_DecodeIns` failure ⇒ `errorT("error decoding instruction")` and an error
  instruction with message `GED error decoding instruction` (`:358`-`:361`);
- `GED_RETURN_VALUE_NO_COMPACT_FORM` ⇒ `unable to decompact` (`:353`-`:356`);
- a valid GED op whose IGA `OpSpec` is invalid ⇒
  `ISA opcode 0x..: unsupported opcode on this platform` or
  `invalid subfuction under <op>` (`:366`-`:380`);
- an unresolvable format / subfunction ⇒ `invalid operation format` /
  `invalid subfunction` (`:474`-`:480`, `:393`-`:396`).

`createErrorInstruction()` (`Decoder.cpp:2520`-`:2540`) builds an `ILLEGAL`
instruction whose comment is `FormatOpBits(...): <message>`; the mnemonic for
`Op::ILLEGAL` is `illegal`/`Illegal` (`IGALibrary/Models/bxml/ModelXe*.hpp`,
e.g. `ModelXe.hpp:310`; declared at `IGALibrary/Models/OpSpec.cpp:18`).
The decoder reports the failure on stderr as `byte offset …: error: …`.

Observed (`logs/tool-smoke-iga-unknown.txt`): eight bytes of `0xFF` on `12p1`:

```
byte offset 0x0: error: error decoding instruction
```

exit 1; with `--output-on-fail` the listing is still printed:

```
L0:
        illegal                       {Compacted} // OP[]7f?:    ff ff ff ff ff ff ff ff : GED error decoding instruction
```

The same happens on `-p=11`. These GED decode failures surface as an `illegal`
line plus a non-zero exit, with partial listing available through
`--output-on-fail`. This is not a universal promise for every invalid input:
the native matrix found that zero-filled `illegal` and some truncated native
inputs can yield exit0. The strict prototype independently checks length and
rejects `illegal`; CLI exit alone is not a validator. See
`analysis/native-matrix.json` and `tools/mesa-eu/README.md`.

---

## 8. Mesa 23.3.6 EU reference (`src/intel/compiler`)

All line numbers are for commit `8633382…` (see `tools/mesa-eu/README.md`).

**Disassembler.** Declared `brw_eu.h:184` (`brw_disassemble_inst`), `:188`
(`brw_label_assembly`), `:191` (`brw_disassemble_with_labels`), `:193`
(`brw_disassemble`); implemented `brw_disasm.c:1919` and `brw_eu.c:518`/`:531`.
Opcode names come from the `opcode_descs[]` table (`brw_eu.c:597`); the
`ILLEGAL` entry is `"illegal"` (`brw_eu.c:599`). `print_opcode()`
(`brw_disasm.c:819`) emits `*** invalid opcode value %d` when no descriptor
matches — Mesa's analogue of IGA's `illegal`. Framing uses
`brw_inst_cmpt_control` (`brw_inst.h:300`, `:1402`); `next_offset()` advances 8
or 16 B (`brw_eu.h:2051`). SWSB rendering calls `tgl_swsb_decode`
(`brw_disasm.c:1832`; struct/helpers `brw_eu_defines.h:1189`-`1282`).

**Validator.** `brw_validate_instruction` (`brw_eu.h:2044`,
`brw_eu_validate.c:2598`) and `brw_validate_instructions` (`brw_eu.h:2047`,
`brw_eu_validate.c:2634`). `brw_validate_instructions` walks the image by
compaction bit, uncompacts into a `brw_inst` with `brw_uncompact_instruction`,
then validates each instruction (unsupported-instruction check first:
`is_unsupported_inst` = `opcode == BRW_OPCODE_ILLEGAL`, `brw_eu_validate.c:433`;
`BRW_OPCODE_ILLEGAL` declared `brw_eu_defines.h:179`). Failures are inserted via
`disasm_insert_error` when a `struct disasm_info` is supplied.

**Compaction.** `brw_try_compact_instruction` (`brw_eu.h:2037`,
`brw_eu_compact.c:1926`), `brw_uncompact_instruction` (`brw_eu.h:2035`,
`brw_eu_compact.c:2294`), `brw_compact_instructions` (`brw_eu.h:2033`,
`brw_eu_compact.c:2480`). The compaction tables are the static arrays in
`brw_eu_compact.c` (`g45_*` `:86`, `gfx6_*` `:226`, `gfx7_*` `:366`, plus
`gfx12_*`/`xehp_*` three-source tables), selected through
`compaction_state`/`compaction_state_init` (`:1067`/`:1076`).
`has_unmapped_bits()` (`:1440`) and `precompact()` (`:1700`) decide/repair
compactability. `brw_compact_instructions` is skipped under
`INTEL_DEBUG=no-compaction` and on pre-g4x.

**Emitter / accessors.** Three-source emission and the destination-file assert
live in `brw_eu_emit.c` (assert around `:826`); per-field accessors are the
generated inline functions in `brw_inst.h`.

**Tests.** `src/intel/compiler/test_eu_compact.cpp` parameterises on
`CompactParams{verx10, align}` (`:32`) and runs
`test_compact_instruction()` (`:57`) plus
`test_fuzz_compact_instruction()` (`:174`) over gfx5…gfx12+
(`INSTANTIATE_TEST_SUITE_P` `:238`). `src/intel/compiler/test_eu_validate.cpp`
provides a `validation_test` fixture with per-instruction checks
(`INSTANTIATE_TEST_SUITE_P` `:106`). Both are registered in
`src/intel/compiler/meson.build` (`:196`-`:213`) as `intel_compiler_tests` and
require Mesa's own build system; they are **not** built in this lab.

---

## 9. Patched vs pristine, and tool safety

- `tools/mesa-eu/source` is the pristine Mesa pin and must not be modified.
- The out-of-tree `tgl-xlate` translator keeps a **patched copy** of the
  compiler source subset, isolated here under `tools/mesa-eu/adapter/eu/` from
  `/tmp/opencode/ga33/tools/tgl-xlate/eu/`, with
  `mesa-brw_eu_emit-acc1.patch` applied and local stubs. Details and the exact
  patch are recorded in `tools/mesa-eu/README.md`; those edits are not upstream.
- `tgl-xlate`'s `dis12` is a Gen11→Gen12 translator front end, not a
  general-purpose disassembler: it sizes instructions from the compaction bit
  and reads a full 16 B `brw_inst` even near a short tail
  (`g11to12.c:13`-`:31`). Do not run it on arbitrary/truncated bytes; use IGA
  (`tools/iga`) or Mesa's disassembler/validator with explicit framing.

For arbitrary byte input, IGA is the tool with a structured decode-error path
(including `illegal` and diagnostics), but independent framing and semantic
acceptance checks remain necessary, as the exit0 counterexamples above show;
`tgl-xlate`'s `dis12` is intended for bytes it produced itself. IGA's
`-Xnative` path was not exercised on arbitrary bytes in this note.

---

## 10. Evidence index

| Path | Content |
|---|---|
| `tools/iga/build.sh` | repeatable pinned IGA build |
| `logs/iga-configure.log`, `logs/iga-build.log`, `logs/iga-build-retry.log` | original build (missing `inc` → fixed) |
| `logs/tool-smoke-iga-help.txt` | `iga64 -h` |
| `logs/tool-smoke-iga-platforms.txt` | `iga64 -h=p` platform list |
| `logs/tool-smoke-iga-official-jsonv2.txt` | official `IGAJSONv2.md` example: verbatim failure, fixed assemble, disassembly, JSON v2 |
| `logs/tool-smoke-iga-igt-gen12.txt` | i-g-t upstream Gen12 kernel on `12p1` |
| `logs/tool-smoke-iga-gen11.txt` | minimal Gen11 kernel on `11` |
| `logs/tool-smoke-iga-swsb-compact.txt` | SWSB accept/reject + compaction probes |
| `logs/tool-smoke-iga-unknown.txt` | invalid-byte decode behaviour |
| `tests/samples/` | sample inputs + `run-smoke.sh` + `README.md` |
| `tools/mesa-eu/README.md` | Mesa API map and patched/pristine separation |

---

## Not concluded here

This document maps the tools; it is not evidence about whether the Gen11
candidate images are valid Gen11 code, whether any translation is correct, or
which disassembler output should be trusted for a given image. Those questions
are out of scope for this environment note and are left to the analysis
workstreams.
