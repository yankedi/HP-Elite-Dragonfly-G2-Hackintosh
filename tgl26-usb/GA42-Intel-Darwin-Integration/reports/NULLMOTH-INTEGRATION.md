# NullMoth / Intel integration report (M6)

> **Correction:** the earlier NVIDIA-only frontend policy in commits
> `376cfa74`, `1074e1f1`, and `d09b54f7` was incorrect for GA42. The new
> corrective commit `0ba6bd9bcd03d250fa0a1bf5940706fcba5d3ad4` preserves the
> NullMoth NMXAccel → ANV/RADV path and gates only NVIDIA-private helpers.

## Final review corrections (2026-10-22)

Apply the complete ordered patch series `0001` → `0002` → `0003` → `0004` to the pinned
source. `f50efef9061775bc54842e9a9184adbad2b4fd8e` serializes first accelerator
binding and freezes vendor discovery before selecting the one-shot Vulkan
ICD. A later device from another vendor is rejected without changing global
Vulkan identity. `4e547f15ae7c3660ea0df7b63a8bd4eefc1ad555` rejects unknown
identity in the actual initializer before any loader path, preventing
`dlopen(NULL)` and ambient discovery for an unbound process.

`logs/nm-freeze-vendor-003` and `logs/nm-reject-loader-002` PASS the actual
patched vendor functions, 100 concurrent first-binding trials, reverse/late
bindings, frozen unknown discovery and the extracted production pre-loader
initializer guard. This is CPU_TEST with registry callbacks, not a Metal or
Vulkan runtime. Earlier failed patch/harness attempts remain in their unique
log directories. Original independent findings are in
`audit/userspace-review-002/REVIEW.md`; follow-up records the final scope.
`4d7ded258f0b430cb014c541f313dfbc2fe42aee` tightens patch context and enforces
fuzz-free sequential application. `a429a4db6c4a32c5930afbe8075ddec9fb09354f`
rejects conflicting modern/legacy/additional driver environment paths before
known-vendor loader fallback; it checks failure when setting an absent legacy
path. `logs/nm-fuzz0-series-002` and `logs/nm-loader-env-001` PASS. No existing
ambient driver configuration is overwritten. Independent closure is recorded
separately from the original finding and first follow-up.

## Provenance and commits

- GA40 NullMoth source audited read-only at `47f818b11cef59acb480210afdf9065fdd44e356`.
- `sources/nullmoth/AGENTS.md` was read before the audit; GA40 was not edited.
- Mesa provenance observed read-only: `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2` (`26.2.3`).
  NullMoth's own `nvk/MESA_BASE` remains `17ca6174`; this unit does not alter the Mesa/ANV work.
- Integration commits:
  - `376cfa74b2ba704f480fb8074e9e43273f19dc4d` — NVIDIA-only gate and offline harness.
  - `1074e1f12bf4a230afaee3b2bbebbafec79a93c0` — remove the dead Intel registry helper and make the identity boundary explicit.
  - `d09b54f7e2eecd5941e0688e9b838a5e284bbde8` — gate an explicit ICD override by the same NVIDIA identity.
  - `0ba6bd9bcd03d250fa0a1bf5940706fcba5d3ad4` — correction: preserve Intel ANV and gate only NVIDIA-private paths.

## Patch delivered

`nullmoth/patches/0001-nvidia-only-accelerator-gate.patch` applies to the exact
GA40 source above. It is deliberately a small source patch, not a copied
NullMoth tree.

The GA42 architecture intentionally reuses NullMoth's existing
`NMXAccel`→ANV/RADV frontend. The corrected patch keeps authenticated
NMXAccel vendor detection, including Intel `0x8086`, and keeps
`intel_icd.json`/`libvulkan_intel.dylib` selection. It does not add an NMXGPU
manager or a second frontend.

The patch now:

1. records explicit accelerator binding, preserves NMXAccel vendor `0x8086`
   and `0x1002`, and prevents an explicit binding from falling back to a
   different system-wide GPU;
2. fails closed for an unknown accelerator and returns no ICD identity there;
3. keeps `NVMTLDevice` acceptance for matching `0x8086`/ANV, `0x1002`/RADV,
   and `0x10de`/NVK bindings, while refusing only unknown/mismatched devices;
4. permits `NVMTL_ICD_LIB` overrides only for NVIDIA, so Intel cannot import a
   private NVK path while retaining its standard Intel ICD;
5. requires vendor `0x10de` before NVIDIAShared/NVVM and direct SASS can
   enable; and
6. retains existing NVIDIA-only VideoToolbox/NVRM paths and corrects unknown
   `vendorName` reporting to `Unknown`.

The SASS path remains unreachable on Intel ANV: vendor identity must be
`0x10de` before NVK's direct-dispatch hook is considered, and the existing
RTX-50/name and artifact checks still apply. Existing VideoToolbox registration
is already guarded by NVIDIA identity, and the decode-service probe checks an
actual NVIDIA PCI device. No NVRM/GSP kext or firmware code was changed.

## Offline evidence

All commands were run through `tools/run_logged.py`; stdout/stderr and argv are
preserved in the listed directories:

- `logs/nm-007-source-audit/` — exact source/Mesa hashes and original
  NMXAccel/NVAccel/ICD/compiler/SASS locations.
- `logs/nm-037-corrected-vendor-policy-fixed/` — **PASS corrected vendor/ICD policy**.
  The test copies the real GA40 source, applies the patch, extracts the patched
  original C functions including the original PCI vendor helper, compiles
  them with a fake I/O-registry model, and positively exercises Intel ANV,
  AMD RADV, NVIDIA NVK, explicit Intel-over-NVIDIA binding, unknown fail
  closed, and private-ICD override refusal. This is not a grep-count test.
- `logs/nm-038-corrected-diff-check/` — final patch/test `git diff --check`
  passed.
- `logs/nm-045-final-corrected-gate-after-report/` — repeat final corrected
  vendor/ICD policy test passed after the report commit.
- `logs/nm-046-final-owned-path-audit/` — owned `nullmoth/` and `reports/`
  paths are clean; patch whitespace and the preserved parallel staged state
  were audited.
- `logs/nm-023-nvidia-only-gate-override/` records the temporary harness
  prototype-declaration failure; `logs/nm-024-nvidia-only-gate-override-fixed/`
  exposed the missing vendor gate on `NVMTL_ICD_LIB`. Both were corrected
  before the final pass and are retained rather than rewritten.

Earlier failed-policy runs remain historical evidence at `logs/nm-001-nvidia-only-gate/`,
`logs/nm-004-nvidia-only-gate-u0/`, and
`logs/nm-008-nvidia-only-gate-final/`, and `logs/nm-017-final-nvidia-test/`;
they are superseded by the correction and are not evidence for the final
architecture. The correction commit record is
`logs/nm-040-commit-corrected-nvidia-gates/`; earlier commit records are
in `logs/nm-006-commit-nvidia-gate/`,
`logs/nm-015-commit-nvidia-boundary/`, and
`logs/nm-028-commit-nvidia-override/`.

## Explicit limitations and unresolved native work

- This is a Linux-host, offline policy/identity test only. No Apple SDK/KDK
  compile, kext link, macOS load, hardware boot, SSH, download, firmware,
  NVRAM, or remote operation was performed.
- The full NMX source is historically absent. This unit does not invent an
  NMXGPU manager, fake IORegistry personality, `nmxgpu-claimed` property,
  Metal accelerator personality, or continuous Intel shader pipeline.
- The parent unit's planned native service remains limited to diagnostics,
  authenticated IOUserClient plumbing, CPU GEM, and resource reporting.
  Intel GPU queue submission, VM/page tables, interrupts, fences, display
  modes/scanout, power/sleep, hardware video, and actual Vulkan hardware
  execution remain unresolved native capabilities; the existing ANV ICD
  selection path itself is preserved and tested here.
- NVIDIA NVRM/GSP, private NVK hooks, NVVM/NVIDIAShared, SASS artifacts, and
  NVIDIA video libraries remain NVIDIA-only and are not substitutes for those
  Intel capabilities. No claim of Intel Metal acceleration or a continuous
  shader pipeline is made.
- The patch is intentionally pinned to NullMoth `47f818b`; source drift should
  fail patch application and require a fresh audit.
