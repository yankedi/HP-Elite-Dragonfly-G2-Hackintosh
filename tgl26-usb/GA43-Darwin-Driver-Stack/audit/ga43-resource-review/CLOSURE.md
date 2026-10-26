# GA43 resource/toolchain review closure

Date: 2026-10-25

Reviewed HEAD:
`21d05baf6da66f0ee0100dd3091204d58d8a1ebf`.

This closure is an offline, read-only source/evidence review. No tests were
rerun and no production, test, Git-history, network, target, VM, hardware, or
GPU state was changed. The original `audit/ga43-resource-review/FOLLOWUP.md`
was preserved unchanged (SHA-256
`b55822d54477e43d88bfcae28015f1d5712f42a3f6cec6379c1a003a0e6c9872`).

## R1 correction: withdrawn, not a remaining defect

The prior R1 finding was incorrect. `gx_vm_plan_create()` rejects creation
when `s->vm_objects >= VM_LIMIT` (`i915-xnu/gem/gx_vm.c:95-110`). Every VM
name starts with one reference, contexts and requests add references, and
`i915_vm_put()` decrements `vm_objects` only on the final reference
(`:55-63,130-147,204-210,239-248`). Therefore request-held and
context-held orphan VMs are included in the same 16-object limit; more than
16 distinct live VM pointers cannot be created through this API.

The new witness creates 16 distinct request-held orphan VMs, confirms the
17th creation returns `-ENOSPC`, and confirms counts of 16 objects/requests/
bindings without overflow (`tests/test_vm.c:147-165`). Existing
`logs/review-admission-tests-001/` records the fresh two-target ASan/UBSan
PASS. The explicit `seen` capacity checks at `gx_vm.c:278-293` are defensive
fail-closed checks for a future invariant/table change; they are not evidence
that the earlier array overflow was reproduced. **R1 is closed and must not be
carried forward as an active bug.**

## R2 closure: detached admission is source-consistent and evidenced

`gx_vm_ops.admit` is now required and is supplied by `plan_admit()` through
`gx_file_check()` (`i915-xnu/include/gx_vm.h:17-25`,
`i915-xnu/drm/gx_client.c:23-26`). VM-state creation, VM/context creation,
binding, request preparation, and submit all check it
(`i915-xnu/gem/gx_vm.c:79-100,119-125,151-156,190-196,250-254`).
Cleanup operations intentionally do not check admission, so destroy, unbind,
fail/status/release, and client close remain possible after detach.

`gx_file_check()` and `gx_device_detach()` use the same device lock. The
callback is therefore a source-level linearization point: a check completed
before detach may finish, while a check after detach returns `-ENODEV`.
`logs/review-admission-tests-001/` records the two CPU targets PASS and
`logs/review-admission-native-001/` records the two changed units as x86_64
Mach-O objects. The CPU test is not a concurrent XNU/device-lock runtime
test, but no remaining source defect was found in the stated admission
ordering.

## G1/G2/G3 closure: strict gate corrections present

* `tools/darwin-probes.py:73-81,131-138` now records compiler-version,
  compiler-target, and linker-help exits, requires recognizable Clang/x86-64
  output and nonempty linker help, and includes `tool_identity_valid` in
  `strict_pass`. `logs/darwin-probes-004/result.json` correctly remains
  `strict_pass: false`: the old linker returns linker-help exit 1 and no
  complete SDK is present.
* `tools/inspect-darwin-probe.py:34-39` now includes
  `LC_LAZY_LOAD_DYLIB` (`0x20`) in dependency and import-ordinal checking.
  Its exact-rpath check at `:67` rejects extra search paths, and the minimal
  probe requires `_ga43_checked_add` at `darwin-probes.py:114`.
* `logs/probe-lazy-rpath-witness-001/` reports rejection of both an
  unapproved lazy dependency and an extra rpath using an explicitly
  `NOT_FOR_LOADING` mutated diagnostic carrier. The original diagnostic
  artifact/logs remain unchanged; this is a contract-unit negative witness,
  not a link, load, SDK, or runtime success.
* The no-output witness remains valid: `logs/negative-no-output-002/` has all
  tool-substitute stages exit 0 but all artifact contracts and `strict_pass`
  reject, with the assertion recorded in
  `logs/probe-negative-witness-assert-001/`. Optimized Python is explicitly
  rejected by the probe, inspector, and inherited-object gates; the negative
  result is recorded in `logs/probe-optimized-rejection-001/` and
  `logs/inherited-optimized-rejection-001/`.

Relative SDK canonicalization, fresh in-gate probes, and rejection of the
caller-supplied probe receipt remain present. No positive strict gate is
claimed: the legal SDK/modern linker branch was not available.

## ANV boundary

`tools/anv-darwin-attempt.py:82-99` now requires matching compiler binary
hashes/resource identity rather than path identity, and `:224-227,239-243`
inspects a successful real `-c -o` translation-unit result as an x86_64
Mach-O object. The branch remains unexecuted because the complete SDK,
modern Darwin linker, and inspection tool set are absent; this is an input
blocker, not an ANV code failure. No ANV, kext, native fd/pager, XNU runtime,
GPU VM, execution, completion, fence, reset, or Metal evidence exists.

F4 remains withdrawn per `F4-CLARIFICATION.md`. F6 wording remains explicitly
limited to standard cookie generation plus a private IOUserClient CPU map in
`reports/GA43-TRANSPORT.md:15-19,42`; standard fd/pager/render-node/libdrm
integration remains blocked.

## Closure result

No actual reproducible source defect remains among R1, R2, G1, G2, or G3 at
this HEAD. The remaining limitations are unexecuted native/GPU paths and
unavailable SDK/linker inputs, not silently accepted source success claims.

Current reviewed-source hashes:

```text
2243b6d467223a9d41aed3f193e3cfbbf26e997dc42c47431e190dcff2927728  i915-xnu/gem/gx_vm.c
593d11fef13118d91d08986677027b19e2d545589746042fb054817f8bce7d70  i915-xnu/include/gx_vm.h
907cb458d7c54a761f0ad4f54f3dbbb05723251f609060a2ce10ccc17b00f81d  i915-xnu/drm/gx_client.c
10fefecc96bb0750eee9d9f50845c9e5b297127e857ea09f2981dc5ca48e4821  tests/test_vm.c
fef6de4194312ef40520d490082457d8c62e7cde52429e0ae4a29208bccc1664  tools/darwin-probes.py
de95952645366f28688df67f6257dea4b1dba905371da8bd8d70c08182e85394  tools/inspect-darwin-probe.py
8c2b486b7a1ab5cb60527f31c36c81fe9a31ba062b4d006b9cbdab47a042e9b1  tools/anv-darwin-attempt.py
96c2697c43774737ac800c747097f8cd9661b2a3d840e88aeb0c650ecc16b38c  reports/GA43-TRANSPORT.md
```
