# A2/A3: null stencil and draw semantic evidence

**Result:** a null-stencil reconstruction is supported for the explicitly absent,
disabled resource case; a zero-padded Gen12 stencil packet is wrong. Two valid
draw repairs A/B agree on defined draw and XP values under the conditions below.
Neither result establishes execution equivalence to the malformed captured draw,
nor a bootable/working GPU command stream.

This independent evidence pack reads official Intel PRM text and pinned Mesa
ISL. It does not use the main normalizer as its semantic oracle. Machine-readable
detail: `../stencil-proof.json`, `../draw-proof.json`. Source hashes, reconstructed
official URLs, actual present-file metadata and current revalidation receipts:
`../../reference/track-a/provenance.json`.

## 1. Exact evidence conventions

Offsets such as `0x6ab0` are offsets into the **captured 32768-byte batch window**,
not output offsets or absolute GPU VAs. Historical input is the read-only
`GA32-ISA-Lab/analysis/batch-decoded.json`, also frozen in this lab's
`inputs/batch-decoded.json`, SHA-256
`ba9f3c4c3424423670250a6e14e8f61a582dc6e975875f1f5dc12af0dc503215`.
Static chain reconstruction is not evidence of GPU execution.

Page numbers below are the PRM's **printed Arabic page numbers**, not PDF viewer
page indices. Text line numbers refer to the existing `reference/track-a/*.txt`
files, counted by LF (`splitlines` would incorrectly count embedded PDF form-feed
characters as line breaks). They can be reproduced with `nl -ba`/`sed`.

Mesa commit: `863338275d915e867319c3690ffd3272b06303c3`. Local files were
independently compared with `git show <commit>:<path>` from the pinned existing
source repository. Its working tree is not modified. Original PDF download logs
were not present; provenance never fabricates them. Current official-index/PDF
checks are explicitly a later reconstruction/revalidation.

## 2. A2: source five-DWORD stencil vs TGL eight-DWORD stencil

Captured `+0x6ab0`:

```text
78060003 00000000 00000000 00000000 00000000
```

ICL Vol2a printed pp119–121, text lines4753–4876, defines five DWORDs and
`Stencil Buffer Enable` in packetDW1 bit31. That bit is zero; the packet does
not itself have a SurfaceType field. The ICL command says stencil is Tile-W;
active resources therefore require real layout analysis, not blanket header
conversion.

TGL Vol2a p125, lines5040–5080, explicitly requires `SURFTYPE_NULL` when stencil
is absent and fixes length to8 DWORDs (`DWord Length=6`). TGL Vol2d p101,
lines4511–4547, specifies packetDW1 bits31:29 (bodyDW0): **0 is reserved;
7 is NULL**. Just adding three zeros with header `78060006` leaves an invalid
reserved surface type. Setting only the length is insufficient.

### Ordered companion state from actual capture

| Offset | Command | Relevant facts |
|---|---|---|
| `60c0` | WM_HZ_OP `78520003 0 0 0 1` | Explicit depth/stencil clear and resolve enables zero |
| `6a7c` | HIER_DEPTH_BUFFER `78070003 0 0 0 0` | Zero resource fields; enable lives in DEPTH_BUFFER |
| `6a90` | DEPTH_BUFFER `78050006 e0040000 0 0 0 0 0 0` | NULL surface, D32_FLOAT, depth write0, ICL stencil write0, HiZ enable0, Depth0 |
| `6ab0` | STENCIL_BUFFER `78060003 0 0 0 0` | ICL stencil enable0 |
| `6ad4` | WM_DEPTH_STENCIL `784e0002 0 0 0` | Stencil test/write0, depth test/write0 |

The frozen chain contains no subsequent update of these command families before
the four draws. This is a static fact about recorded bytes, not a claim that the
malformed stream executed as reconstructed. WM_HZ_OP is checked separately from
ordinary WM testing; a zero stencil address by itself is not a resource proof.

TGL Vol2d pp155–157 lines6580–6672 documents WM test/write roles. Stencil
surface write enable and WM stencil-write enable are separate gates. In the
captured `784e0002` header all TGL modify-disable bits are zero, so the zero
body would actively update the enable state rather than leave stale enables.

### ISL independent implementation evidence

In `src/intel/isl/isl_emit_depth_stencil.c`:

* lines110–142 initialize depth state; no depth/stencil surface yields
  `db.SurfaceType=SURFTYPE_NULL`, `db.SurfaceFormat=D32_FLOAT`.
* lines223–227 zero-initialize stencil state with header and explicit `info->mocs`.
* lines232–264 populate active stencil layout, address, dimensions, write and
  compression state. These are not inferred from a zero legacy packet.
* lines265–277 implement the absent-stencil branch:
  `sb.SurfaceType=SURFTYPE_NULL; sb.Depth=db.Depth`.
* lines269–275 explicitly retain a TODO: PRM depth-matching for NULL stencil
  may be a documentation bug. Preserve the conservative `db.Depth` copy.
* lines280–295 handle separate HiZ state; lines411–424 pack depth, stencil,
  HiZ and clear packets separately.

`iris_state.c:3652–3663,3704` passes MOCS even for an unbound depth/stencil
attachment. Do not confuse a NULL resource with permission to leave every
numeric field zero.

### Numeric target with an explicit MOCS condition

For this null-depth Depth0 case, a concrete local Mesa-style target is:

```text
DW0  78060006   fixed length8
DW1  e0000000   SurfaceType7, write/coherency/compression/control/corner/pitch0
DW2  00000000   base low0
DW3  00000000   base high0
DW4  00000000   width/height encoded0
DW5  00000004   Depth0, minimum-array0, MOCS4
DW6  00000000   TiledMode NONE0, mip-tail0
DW7  00000000   view extent/LOD/QPitch0
```

Little-endian bytes (32B):
`06000678000000e0000000000000000000000000040000000000000000000000`.

All reserved/MBZ bits are zero. Width/height/pitch/QPitch are unused NULL-state
encodings copied from ISL's zero-initialization; they are not active surfaces of
those sizes. MOCS4 is from `isl.c:159–165` (TGL internal `2<<1`); the upstream
gen12 XML marks MOCS **nonzero** (`gen12.xml:696`). The captured Apple runtime's
MOCS register programming is unknown. Thus this is a concrete **local pack
example conditional on a verified target MOCS**, not authorization to insert4
in an Apple batch. Parameterize DW5 with the independently validated target
7-bit MOCS; do not silently propagate source0 or call the zero-MOCS form
Mesa-valid.

TGL Vol2d p105 lines4695–4710 says Depth matches the non-null depth buffer;
ISL copies it even for null stencil. Do not hard-code Depth0 for every future
null-stencil conversion. Current null depth has Depth0.

Expansion adds12 bytes. At `6ac4` the original next packet is
`79200000 00010001` (SLICE_TABLE_STATE_POINTERS), followed at `6acc` by
`791e0000 ffff004c` (3D_MODE). They are commands, not missing stencil payload.
Repack and relocate; never overwrite/consume those words.

**Refuse** unknown/present resources, active stencil/HZ operations, unresolved
depth/MOCS or invalid layout. Vol2d p101 lines4538–4543 includes an A-step
post-sync PIPE_CONTROL workaround when stencil surface state changes; actual
stepping/workaround applicability remains a separate runtime condition.

## 3. A3: captured draw is malformed under both ICL and TGL

All four draws at `6df8`, `6ea4`, `6f50`, `6ffc` contain:

```text
7b000008 00000000 00000006 00000000 00000001
00000000 00000000 00000000 00000000 00000000
```

Both ICL Vol2a pp2–4 lines626–687 and TGL Vol2a pp2–3 lines624–680
require: bit11=0 => length5 =>7 total; bit11=1 =>length8 =>10 total.
Captured bit11=0, length8 is contradictory. A genxml decoder accepting length8
does not override the conditional PRM rule. Do not assign defined execution
semantics to this malformed source or claim either repair executes identically.

The two valid local candidates (40B each):

```text
A: 7b000808 00000000 00000006 00000000 00000001
   00000000 00000000 00000000 00000000 00000000
   # 10-DW draw, ExtendedParametersPresent=1, inline XP0=XP1=XP2=0

B: 7b000005 00000000 00000006 00000000 00000001
   00000000 00000000
   00000000 00000000 00000000
   # 7-DW draw, ExtendedParametersPresent=0, then three MI_NOOP commands
```

Common: direct/non-predicated, POSH0, UAV-coherency0, SEQUENTIAL, EndOffset0,
6 vertices, start vertex0, 1 instance, start instance0, base vertex0.
PRM explicitly says when extended parameters are absent they **default to0**
if selected as VF SGV insertion sources (TGL lines631–632, ICL633–634).
Therefore A's inline0 and B's default0 agree for these fields with indirect0.
This is defined-field equivalence of A/B, not timing/packet-count or source
execution equivalence.

TGL Vol2a p1026 lines42563–42599 defines the RenderCS single-DWORD MI_NOOP:
command type0, opcode0, identification-register-write enable bit22=0 leaves
NOP_ID unchanged. Thus the three literal zero DWORDs in B are real no-ops,
not merely assumed inert padding.

### XP0 is not unconditionally BaseVertex; XP1 not unconditionally BaseInstance

TGL Vol2d pp134–136 lines5786–5912; ICL pp98–100 lines4439–4563:

| SGV | Insert gate | Source0 | Source1 |
|---|---|---|---|
| XP0 | bodyDW0 bit15 | draw XP0 parameter | VERTEX_LOCATION: StartVertex for sequential, BaseVertex for random |
| XP1 | bodyDW0 bit31 | draw XP1 parameter | StartInstanceLocation; required if InstanceIDOffsetEnable is set |
| XP2 | bodyDW1 bit15 | draw XP2 parameter | no source-select alternative |

Insertion has programmable VUE element offset/component as well. API names
BaseVertex/BaseInstance/DrawID are shader input contracts, not unconditional PRM
names of the inline XP values. Draw DW6 BaseVertex and DW7 XP0 are distinct.

Actual `VF_SGVS_2 +6c2c = 78560001 10001000 00000000` has **all three
XP enables zero**; XP0/XP1 source-select1 bits are ignored while disabled.
`VF_SGVS +6c24 = 784a0000 00000000` also disables VertexID/InstanceID insertion.
No later SGVS/SGVS_2 update occurs before the four captured draws.

For generalization: with indirect1 and extended-present1, A sources XP values
from `3DPRIM_XP0-2` MMIO, while B uses absent-parameter zero. Those registers
are not captured: refuse the general equivalence unless their equality or
unobservability is separately established. Likewise reject nonzero inline XP,
non-NOOP trailing data, or unresolved VF/shader mappings. Other draw/VF state
must be identical and valid for an A/B defined-field comparison.

## 4. Executed independent pack check and integration boundary

`reference/track-a/pack-proof.c` uses the **actual upstream generated GFX12 pack
functions** from the fixed Mesa source, independently from `command_stream.py`.
`pack-proof.log` records numeric outputs. Note: generated GFX12_3DPRIMITIVE pack
writes10 DWORDs even if DWordLength5; the C harness allocates10, treats the final
three zeros as separate NOOPs in B, and never calls that packer into a7-DW
buffer. This is another reason XML/pack defaults alone are not a semantic proof.

Provenance records the exact generator/compiler command, actual statuses and
hashes. No main parser/schema/tests were edited. Main integration must enforce
all explicit conditions, independently reparse/repack a complete stream and
maintain its own evidence/tests. The unresolved runtime MOCS/resource/stepping
conditions remain explicit rather than obstructing the independent draw proof.
