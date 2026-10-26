# tools/mesa-eu

Reference checkout of the Intel execution-unit (EU) compiler sources used to
read Gen11/Gen12 machine code, plus an isolated copy of the reference
Gen11→Gen12 translator. `source/` stays pristine; `adapter/` is actually built
by `bash tools/mesa-eu/build-adapter.sh` into `adapter/build/g11to12`.

## Pinned source

- Repository: `https://gitlab.freedesktop.org/mesa/mesa.git`
- Commit: `863338275d915e867319c3690ffd3272b06303c3`
- Version / tag: `23.3.6` (`mesa-23.3.6`), `src/intel/compiler`
- Layout: partial clone (`--filter=blob:none`) with a sparse checkout
  covering `src/intel/{compiler,dev,genxml,common}`, `src/util`, `src/mesa/main`,
  `src/c11`, `src/compiler`, `include`.
- Licence: MIT.  `git -C tools/mesa-eu/source status` is clean: this tree is
  pristine and must stay that way.

The same commit and licence are what the out-of-tree `tgl-xlate` translator is
built from (`tgl-xlate/setup.sh` clones `--branch mesa-23.3.6`; verified
`git -C mesa describe` = `mesa-23.3.6`).

## Public API map (line numbers are for this commit)

Disassembly and labelling — declared in the Intel compiler header, implemented
partly in the disassembler and partly in the EU common file:

| Symbol | Reference |
|---|---|
| `brw_disassemble_inst()` | `src/intel/compiler/brw_eu.h:184`, `brw_disasm.c:1919` |
| `brw_label_assembly()` | `brw_eu.h:188` |
| `brw_disassemble_with_labels()` | `brw_eu.h:191`, `brw_eu.c:518` |
| `brw_disassemble()` | `brw_eu.h:193`, `brw_eu.c:531` |
| `print_opcode()` / unknown-opcode text | `brw_disasm.c:819` (`*** invalid opcode value %d`) |
| opcode descriptor table (incl. `ILLEGAL` ⇒ `"illegal"`) | `brw_eu.c:597`, `brw_eu.c:599` |
| opcode accessor | `brw_inst.h:1462` |
| `brw_inst_cmpt_control` (compaction bit 29) | `brw_inst.h:300`, `:1402` |
| `next_offset()` (8 vs 16 B from the compaction bit) | `brw_eu.h:2051` |

Validation:

| Symbol | Reference |
|---|---|
| `brw_validate_instruction()` | `brw_eu.h:2044`, `brw_eu_validate.c:2598` |
| `brw_validate_instructions()` | `brw_eu.h:2047`, `brw_eu_validate.c:2634` |
| `is_unsupported_inst()` = `opcode == BRW_OPCODE_ILLEGAL` | `brw_eu_validate.c:433` |
| enumeration of `BRW_OPCODE_ILLEGAL` | `brw_eu_defines.h:179` |

`brw_validate_instructions()` walks the image using `brw_inst_cmpt_control()`,
uncompacts each compact instruction with `brw_uncompact_instruction()`
(`brw_eu_validate.c:2654`..), then validates; the first failing check short-circuits.

Compaction:

| Symbol | Reference |
|---|---|
| `brw_compact_instructions()` | `brw_eu.h:2033`, `brw_eu_compact.c:2480` |
| `brw_uncompact_instruction()` | `brw_eu.h:2035`, `brw_eu_compact.c:2294` |
| `brw_try_compact_instruction()` | `brw_eu.h:2037`, `brw_eu_compact.c:1926` |
| `compaction_state` / `compaction_state_init()` | `brw_eu_compact.c:1067`, `:1076` |
| per-generation control/data-type/subreg/src0/src1 tables | `brw_eu_compact.c:86`.. (g45, gfx6, gfx7, gfx12, xehp) |
| `has_unmapped_bits()` (why an instruction may not compact) | `brw_eu_compact.c:1440` |
| `precompact()` | `brw_eu_compact.c:1700` |

SWSB (Gen12 "scoreboard"/dependency annotations shown as `{…}`):

| Symbol | Reference |
|---|---|
| `struct tgl_swsb` | `brw_eu_defines.h:1189` |
| `tgl_swsb_null`/`_sbid`/`_src_dep`/`_dst_dep` helpers | `brw_eu_defines.h:1201`-`1249` |
| `tgl_swsb_decode()` | `brw_eu_defines.h:1282`; used by the disassembler at `brw_disasm.c:1832` |
| default swsb get/set on the codegen state | `brw_eu.h:160`, `brw_eu.h:176` |

Emitter and instruction accessors (the pieces the translator leans on):
`brw_eu_emit.c` (e.g. the three-source destination assert that the translator
patches, around `:826`), the `brw_<OP>()` macros in `brw_eu.h`, and the
generated field accessors in `brw_inst.h`.

Upstream tests (referenced, not built in this lab):

- `src/intel/compiler/test_eu_compact.cpp` — `CompactTestFixture`
  (`TestWithParam<CompactParams{verx10, align}>`) runs
  `test_compact_instruction()` and `test_fuzz_compact_instruction()` over
  gfx5…gfx12+ variants (`INSTANTIATE_TEST_SUITE_P` at `:238`).
- `src/intel/compiler/test_eu_validate.cpp` — `validation_test` fixture with
  per-instruction checks (`sanity`, `src0_null_reg`, invalid encodings, region
  rules, …); `INSTANTIATE_TEST_SUITE_P` at `:106`.
- Both are registered in `src/intel/compiler/meson.build` (`intel_compiler_tests`
  sources at `:196`-`:213`); they need Mesa's own build system.

## Patched vs pristine

There are two copies of these sources in the wider workspace, and they must not
be confused:

1. **Pristine** — `tools/mesa-eu/source/` (this directory).  At commit
   `8633382…`, `git status` clean, no local patches.  Use this for reading
   upstream behaviour and line references.

2. **Patched working copy** — `tools/mesa-eu/adapter/eu/`, copied from
   `/tmp/opencode/ga33/tools/tgl-xlate/eu/`. A compiler source subset (`brw_disasm.c`, `brw_eu.c`, `brw_eu_compact.c`,
   `brw_eu_emit.c`, `brw_eu_util.c`, `brw_eu_validate.c`, `brw_reg_type.c` and
   their headers) plus build objects, together with:

   - `mesa-brw_eu_emit-acc1.patch` — applied by `tgl-xlate/setup.sh:16`.  In
     `brw_eu_emit.c` it relaxes the three-source-destination assert so that
     `(dest.nr & 0xF0) == BRW_ARF_ACCUMULATOR` (Apple's compiler writes `acc1`
     as a destination), instead of requiring `dest.nr == BRW_ARF_ACCUMULATOR`.
   - `eu-stubs/brw_compiler.h` and `eu-stubs/brw_shader.h` — minimal stand-ins
     substituted for the real headers (`setup.sh:14`).
   - `a1_3src_helpers.h` — four three-source region-decoding helpers copied out
     of `brw_disasm.c`.
   - `build.sh` adds `-DUTIL_ARCH_LITTLE_ENDIAN=1 -DUTIL_ARCH_BIG_ENDIAN=0`
     relative to `build.sh.orig`.

   `python3 tools/verify_mesa_sources.py` saves exact hashes and full differences
   in `analysis/mesa-adapter-provenance.json`: only the two stub headers and
   `brw_eu_emit.c` differ from their matching pristine Mesa files.

   These patches stub/relax the library for the standalone reference build; they
   are **not** upstream Mesa behaviour and must not be quoted as such.

## Do not use `tgl-xlate`'s `dis12` on arbitrary bytes

`tgl-xlate`/`g11to12` (`dis11|dis12|xlate`) is a Gen11→Gen12 translator front
end, not a general-purpose disassembler for untrusted input.  Source inspection
of `/tmp/opencode/ga33/tools/tgl-xlate/g11to12.c:13-31`:

- instruction length is decided solely by the compaction-control bit
  (`brw_inst_cmpt_control`), with no validation of the decode;
- for an uncompacted instruction it copies a full 16-byte `brw_inst`
  (`full = *in;`, `:23`) even when fewer than 16 bytes remain in the buffer;
- the loop stops only on an all-zero first slot or on an EOT send (`:20`, `:28`).

On arbitrary or truncated Gen12 bytes that can over-read past the buffer end or
mis-frame the stream.  For untrusted bytes prefer the lab's IGA build
(`tools/iga`, see `reports/02-disassembler-environment.md`) or Mesa's
`brw_disassemble*`/`brw_validate_instructions()` with explicit framing.  The
tool's own `dis12` is only meaningful for bytes it produced itself.
