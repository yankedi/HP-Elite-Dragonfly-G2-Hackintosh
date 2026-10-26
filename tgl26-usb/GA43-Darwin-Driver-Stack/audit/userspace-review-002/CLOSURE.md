# Userspace review 002 closure — NullMoth bounded corrections

## Scope and provenance

This closure reviews GA42 HEAD
`a429a4db6c4a32c5930afbe8075ddec9fb09354f`, including the two latest
corrections:

- `4d7ded258f0b430cb014c541f313dfbc2fe42aee` — adds the missing trailing
  context to `0002-freeze-vulkan-vendor.patch` and requires `--fuzz=0` in the
  ordered harness;
- `a429a4db6c4a32c5930afbe8075ddec9fb09354f` — adds
  `0004-pin-loader-fallback.patch` and its ambient-loader checks.

The full `0001`–`0004` series applies to sealed NullMoth
`47f818b11cef59acb480210afdf9065fdd44e356` in a private copy with
`--fuzz=0`.  The independent rerun passed at
`logs/review-userspace4-harness/` (exit 0); the parent evidence
`logs/nm-fuzz0-series-002/` also passed.  The resulting production source was
inspected at `logs/review-userspace4-source/` (exit 0).  The application emits
offsets but no fuzz or rejected hunk.

This review did not change source, index, prior audit/report, continuation
file, target, hardware, VM, or network.  `REVIEW.md` and `FOLLOWUP.md` remain
historical records; this file is the closure only.

## Fuzz finding: resolved

The corrected three-line trailing context in `0002` makes the intended vendor
freeze hunk apply cleanly.  The harness now passes `--fuzz=0` while applying
the entire sorted patch series, so the earlier silent fuzz acceptance is
closed.  The final source contains the serialized first binding and the
freeze before loader selection; no patch-integrity correction remains.

## Known-vendor ambient-loader finding: resolved

The applied `0004` production function performs exact string checks against
the selected vendor JSON for both `VK_DRIVER_FILES` and
`VK_ICD_FILENAMES`.  Consequently, unrelated paths, lists, and empty values
are rejected.  Any nonempty `VK_ADD_DRIVER_FILES` is rejected as an additional
ambient driver source; an absent or empty value is allowed as intended.

The check runs on the general-loader fallback path before
`dlopen(NVMTL_LOADER)`.  If the legacy variable is absent, the code sets it to
the already selected JSON and rejects `setenv` failure.  Existing matching
values are left untouched, while conflicting values are rejected, so no
environment restoration is needed.  Direct ICD loading still uses the frozen
`selected_lib`.

The harness exercised the production-extracted matcher with absent values,
an unrelated legacy path, the exact selected legacy path, an unrelated and
then matching modern path, and a nonempty additional-driver path.  The
source inspection confirms the guard precedes the fallback loader call.  The
previously verified known-vendor ambient-path gap is therefore closed; no
additional bounded loader correction is required.

## Limits and verdict

This is source-level and CPU-harness evidence only.  There was no Apple SDK or
Darwin linker, native Vulkan loader invocation, physical-device enumeration,
macOS runtime, hardware, or target access.  The existing source-level
concurrency limits and the separate ANV/NMDRM runtime blockers remain; these
corrections do not claim to resolve them.

**Closure:** the F1/F2 corrections, known-vendor ambient-loader correction,
and fuzz-free ordered patch application are independently verified within the
bounded review scope.  No required correction remains for this review unit.
