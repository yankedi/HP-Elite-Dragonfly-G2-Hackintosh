# Userspace review 002 follow-up — NullMoth F1/F2

## Scope and evidence

This follow-up reviews the sequential NullMoth layer at GA42 HEAD
`38b3ff1f8178fbe3d56e2de82a6d233066d5d322`, including parent fixes
`f50efef9061775bc54842e9a9184adbad2b4fd8e` and
`4e547f15ae7c3660ea0df7b63a8bd4eefc1ad555`.  All three patches were applied
in order to a private copy of sealed NullMoth
`47f818b11cef59acb480210afdf9065fdd44e356`.  No source, index, shared report,
continuation file, target, hardware, VM, or network was changed.

The fresh production-function harness passed at
`logs/review-userspace3-corrected/` (exit 0).  The applied production source
and the actual initializer prefix were inspected at
`logs/review-userspace3-final-source/` (exit 0).  The prior failed attempts
remain preserved at `logs/nm-freeze-vendor-001/002/`,
`logs/nm-reject-loader-001/`, and the passing repairs at
`logs/nm-freeze-vendor-003/` and `logs/nm-reject-loader-002/`.

## Resolution of the original findings

### F1 — vendor identity diverging from one-shot Vulkan state: resolved

The applied `0002-freeze-vulkan-vendor.patch` now protects the vendor state
with `g_vendor_lock`, makes the first explicit binding win, and freezes
discovery at the beginning of the real `nvmtl_vk_initialize()` before ICD
selection or any loader call.  A later binding still returns its own vendor
for the `NVMTLDevice` comparison, but cannot mutate `g_vendor`; the patched
device gate therefore rejects late/reverse cross-vendor bindings.

This is supported by the extracted production functions, not a substitute
model: the harness exercised 100 simultaneous Intel/NVIDIA first-bind races,
late and reverse mismatches, and frozen-unknown behavior.  No remaining F1
state-divergence defect was verified.  This remains source-level evidence;
there is no Darwin runtime or hardware verification.

### F2 — unknown identity reaching a loader: resolved for the bounded case

The actual initializer now freezes the identity, obtains `selected_lib` and
`selected_json`, and returns failure when either is NULL before the existing
timeout/cache environment setup, `dlopen`, or loader fallback.  Direct loading
uses `selected_lib`; fallback configuration uses `selected_json`.  The fresh
harness passed unknown startup rejection (including repeat initialization),
explicit-unknown refusal despite discovered NVIDIA, and the Intel pre-loader
guard.

Thus the original `dlopen(NULL)` and unknown-to-ambient-loader path is closed.
The test does not claim a native Vulkan load or physical-device enumeration.

## Remaining verified issue — ambient `VK_ICD_FILENAMES` on known-vendor fallback

The fallback in `0003-reject-unbound-loader.patch` remains:

```c
if (!getenv("VK_ICD_FILENAMES")) setenv("VK_ICD_FILENAMES", selected_json, 1);
g_lib = dlopen(NVMTL_LOADER, RTLD_NOW | RTLD_LOCAL);
```

When a supported vendor is selected but its direct `selected_lib` fails to
open or lacks the entry point, an already-present `VK_ICD_FILENAMES` is
retained.  The general loader can then select an ambient ICD unrelated to the
frozen vendor.  This is a separate, verified loader-isolation gap; the new
NULL guard only proves the unknown-vendor case.  The fallback must either
reject/validate an ambient value or establish the selected JSON with explicit
environment restoration semantics before using the general loader.

## Patch application quality

The default `patch` application succeeds, but it is not fuzz-free:
`0002-freeze-vulkan-vendor.patch` reports `Hunk #3 succeeded ... with fuzz 2`
in both the fresh run and the retained runs.  A fresh `--fuzz=0` dry run exits
1 at `logs/review-userspace3-fuzz0/`.  The resulting default-applied source
contains the intended lock/freeze implementation, so this is not evidence of
a semantic misapplication in this review; it is nevertheless a reproducibility
and patch-integrity defect.  The patch should be regenerated/tightened and
the harness should reject fuzz rather than accepting it silently.

## Conclusion

F1 is corrected at source level.  F2 is corrected for unknown identity before
any loader path.  NullMoth isolation is not fully closed until the known-vendor
fallback cannot honor an unrelated ambient `VK_ICD_FILENAMES`, and the
sequential patch layer applies without fuzz.  The original ANV Darwin SDK/
NMDRM runtime blockers remain unchanged and were not reclassified by these
policy fixes.
