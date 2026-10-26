# GA43 new-input / Darwin ANV review

Date: 2026-10-25

## Scope and evidence boundary

This is an offline, read-only source and evidence review.  The requested
baseline was `13ea6e7c35fce2d2679c4449419dfa3d249c7c9f` plus the uncommitted
`tools/link-darwin-anv.py` and weak-link probes.  The checkout had subsequently
advanced to `45906fe`; that later syncobj unit and unrelated working-tree
changes are not used to silently upgrade this review.  The untracked WSI
framework patch is noted as pending, not as a successful ANV link.

The old “no SDK/modern linker” conclusion is not applicable to this review.
The real local inputs are:

* `GA45-AppleTGL-Native-Port/toolchain/MacOSX26.5.sdk`,
  `SDKSettings.json` SHA-256
  `f8d005f09381389167f9e0aeaa169bc9e7dff162ef22ca2fd8e98df7ff1acafe`;
* GA46 PR204805 `ld64.lld`, SHA-256
  `f1b7547756dc64555c580dd8e30d1437a71a9c4c7bab7a13e496f9df95180661`;
* `logs/darwin-new-inputs-001/result.json`: all 11 recorded stages zero,
  `tool_identity_valid=true`, `strict_pass=true`.

Those probes establish strict user-space C/C++/libSystem Mach-O input
validity only.  No native XNU API/fd/pager execution, ANV initialization,
GPU VM/command/completion/fence/reset, or Metal runtime was performed.

## Findings

### N1 — MEDIUM: optional-link definition closure omits dynamic inputs

`tools/link-darwin-anv.py:46-50` defines the inspected input set as tokens
ending in `.a` or `.o`.  The actual Ninja command recorded in
`artifacts/anv-optional-link-003/contract.json` also links an explicit
`libdrm.dylib`, `-lSystem`, zlib/expat, and framework inputs, but none of
those are passed to `llvm-nm` or represented in the `inputs` set used to
compute `defined`.

This violates the tool’s stated condition that a NULL address is generated
only when the weak symbol has “no definition anywhere in the exact link
inputs.”  If a future generated `VK_ENTRY_WEAK` name is supplied by a dylib
or framework, the tool can still emit its local absolute-zero definition;
the result may conflict with or hide the provider according to linker symbol
resolution.  The current run does not show a wrong optional binding: the
omitted libdrm artifact has no `_anv_`, `_gfx*`, `_vk_common_`, or `_wsi_`
provider, and the actual link failed on required framework and syncobj
symbols instead.

**Correction:** resolve every explicit dylib, `-l`, and `-framework` input
using the exact command search paths/sysroot, inspect its exports, and include
those definitions in the closure; alternatively fail closed whenever an
uninspected non-object input is present.  Keep the existing “no stubs,
no dynamic lookup, strong errors remain linker errors” policy.

### N2 — LOW: Darwin address-wait wrapper leaks Apple’s waiter-count return

The public SDK contract for
`os_sync_wait_on_address[_with_timeout]` says a successful wait returns the
number of outstanding waiters, not necessarily zero
(`os/os_sync_wait_on_address.h:106-111,251-263`).  `0006` returns that value
directly at `src/util/futex.c` in both the indefinite and timed branches.
Mesa’s current `u_queue.c:132-139` only tests `r < 0`, so the observed ANV
call sites tolerate a positive value, but this is not the existing futex
success contract (Linux and Windows paths return zero on a successful wait).

**Correction:** map every nonnegative Apple wait result to zero while
preserving `-1` and `errno`; keep the existing compare-and-wait, timeout
validation, relative-nanosecond conversion, and `ENOENT` wake handling.
This is a host-synchronization contract issue, not evidence of a GPU fence.

### N3 — MEDIUM evidence gap: the final-link helper has no post-link contract

After invoking the linker, `tools/link-darwin-anv.py:77-80` records only the
exit code.  It does not inspect a successful output as an x86_64 Mach-O
dylib, verify its final undefined-symbol set/dependency ordinals, install
name/rpaths, or the required Vulkan exports.  Therefore a future zero exit
would be a strict linker result, but not by itself a strict ANV artifact
contract.

This is not a false-success observation: `logs/anv-optional-null-link-003/`
has exit 1.  The run emitted 10,825 generated absolute-zero optional slots,
then still rejected the required `_drmSyncobj*`, CoreGraphics, and Foundation
imports.  No ANV dylib was produced.

**Correction:** on exit zero, run the existing Mach-O inspector against the
new output with the exact expected dependency/export/rpath contract and make
inspection failure part of the helper’s result.  Keep the current failed
link as failed evidence.

## Positive reassessment

The optional dispatch logic itself is sound for the inspected object/archive
closure:

* `symbols()` distinguishes weak undefined references from definitions and
  intersects them with generated `VK_ENTRY_WEAK` declarations;
* `optional-null.s` contains absolute addresses only, with no function body
  or fallback API implementation;
* `logs/darwin-optional-null-001/` shows the absent weak address resolves to
  a zero data pointer;
* `logs/anv-optional-selection-witness-001/` passes the negative witness that
  a real strong object definition removes the symbol from the NULL set;
* `logs/anv-optional-null-link-003/` reports only real required unresolved
  symbols after the optional set is supplied.  It does not turn those errors
  into success.

The `0004` build-ID gate correctly admits the existing Apple `dladdr` plus
Mach-O `LC_UUID` implementation without defining `HAVE_DL_ITERATE_PHDR`.
`0005` restores the upstream DRM modifier field, initialization, and query
under the same explicit Darwin build macro.  `d56e01f`’s Apple feature-macro
and `sys/ioctl.h` correction is supported by the strict
`logs/libdrm-darwin-cross-002/` link and CPU-only host tests.  `4e0f0b4`
hash-checks the sealed same-source `mesa_clc` and `vtn_bindgen2` binaries and
uses Mesa’s `mesa-clc=system` mode; the integrated build generated real
Darwin Intel compiler/shader objects before its later source/link blockers.
The framework addition in untracked `0007` matches the currently observed
CoreGraphics/Foundation undefined symbols, but has not been applied and
verified by a complete ANV link.

## Final status

N1 and N3 are tooling/evidence corrections.  N2 is a small host-wait API
contract correction.  No defect was found in the optional NULL dispatch
selection or in the strict propagation of required strong linker errors.
The available evidence supports only source-level host synchronization,
bounded static link reasoning, strict user-space probe success, and CPU-only
libdrm marshaling.  It does not support a claim of a loadable, initialized,
GPU-capable, fence-producing, or Metal-running ANV driver.

## Reviewed-source hashes

```text
ae05ccfad32dd78e9c7a4f21b7b40094820b43c665ff2bd99bc75ff23c031977  tools/link-darwin-anv.py
ada86177dcee7390068f43bfb1c88a855d6e864c1b56ad3a4879dfc24bc37cd0  anv/patches/0004-anv-darwin-build-id.patch
0092eb4c6b08e54fe4fc563707278ab6928fc695f18a52bdaaad8c93184e77aa  anv/patches/0005-anv-darwin-image-modifier.patch
090e929a4861c74d2709691a22645e1cec8cf4a7a0deaa1396a2b6112ba56527  anv/patches/0006-anv-darwin-address-wait.patch
b06bb0eefb99d5746bcf88a1b82c9bac03cf70522d996f952329faf2c495ad1a  libdrm-darwin/drm_darwin.c
83c72cdc1f7f7e6ba5a0777ca789afa2c61248f46d2e264b708626d513dc4a59  artifacts/anv-optional-link-003/input-symbols.txt
a45855bc82f3de00a731be7c5e7c93b2de0152329dfd134617d6fd6de2f1e5f2  artifacts/anv-optional-link-003/optional-null.s
5cc319f54b05a38799195a491c303aa686eab7caccfdbbf1e8b8c07405cb7392  artifacts/anv-optional-link-003/link-exit.json
```
