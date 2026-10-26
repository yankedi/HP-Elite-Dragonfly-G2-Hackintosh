# GA43 resource / native-link review

## Scope and boundary

Independent read-only review of GA43 `HEAD 1f43ffd` and commits
`1153591fd1c97e62c75eca1d3d688d23b8ccbc84` and
`2ba885eddde55208b8668f655606a4af6acdef89`. Production/tests, Git state,
GA40/41/42 inputs, target, VM, hardware, network, and historical evidence
were not changed. No native XNU execution was available and the user SDK is
absent. Existing CPU/Mach-O evidence was inspected; old tests were not rerun.

The CPU-side VM/GEM paths are bounded and ordinary refcount/quota paths are
internally coherent at source level. Existing VM/mmap results remain limited
to Linux CPU/memfd, injected callbacks, and Mach-O object compilation; they do
not establish GPU VM, native XNU lifetime, BSD fd mmap, or a loadable kext.

## Findings

### F1 — HIGH: native link inputs are not provenance- or ABI-checked

`tools/link-xnu.sh:17-20` accepts arbitrary `GA43_CURRENT_CORE`,
`GA43_VM_OBJECT`, and `GA43_INHERITED_OBJECTS` paths and only records their
hashes. It does not compare them with an expected manifest, producing source
commit, headers, compiler/resource directory, or SDK. It recompiles only the
service (`:16`) but reuses `gx_gem.o`, `gx_ioctl.o`, and `gx_client.o` from the
caller-supplied directory.

This is an ownership ABI boundary. Commit 1153591 inserts `vm_plans` into
`struct gx_client` (`i915-xnu/include/gx_client.h:19-27`) and changes init/close
to create and drain VM state (`i915-xnu/drm/gx_client.c:35-45,93-112`). A
pre-1153591 `gx_client.o` has the same symbol names but old field offsets; it
can link with a newly compiled service and then misread `initialized`,
`closing`, or `task_held`, corrupting native close/lease ownership. A stale
VM object is similarly invisible to the linker.

**Fix:** compile all changed units together, or reject inputs unless a checked
manifest verifies expected object/source/header/toolchain/SDK hashes and the
target triple. Recording an unexpected hash is not verification.

### F2 — HIGH: the “strict” Darwin probe is not an enforced strict-link gate

`tools/darwin-probes.py:59-70` builds dylib links without an explicit
no-undefined policy. `run()` (`:36-50`) records only process exit status; the
inspection loop (`:90-93`) cannot fail the result. `result.json` (`:94-98`)
contains only stage numbers and an SDK string, not output existence, Mach-O
type/architecture, or an approved import set.

`tools/anv-darwin-attempt.py:76-81` gates Meson solely on those numbers. A
linker accepting unresolved dylib imports, or a wrapper returning success
without the expected output, can satisfy “successful strict probes.” Existing
`logs/darwin-probes-002/inspect-DIAGNOSTIC_ONLY.dylib` demonstrates why load
commands are insufficient: that diagnostic artifact has undefined
`dyld_stub_binder` despite `MH_NOUNDEFS`.

**Fix:** pass the exact linker no-undefined option (for example
`-undefined error`), verify every expected output, inspect symbols/imports and
allowlist dependencies, and make inspection failures part of the gate.
Keep `dynamic_lookup` diagnostic-only.

### F3 — HIGH: the ANV gate trusts an unbound, caller-supplied probe receipt

`tools/anv-darwin-attempt.py:61-81` accepts arbitrary `DARWIN_PROBE_RESULT` JSON
and checks only `probe.sdk` plus eight integer stage values. The schema emitted
by `tools/darwin-probes.py:94-98` contains no compiler/linker/LLVM hashes,
SDK manifest hash, command hash, or output hash. The gate checks that the
*current* linker exists (`anv-darwin-attempt.py:82-88`) but never proves it is
the linker used for the receipt. A stale or edited receipt can therefore pass
and permit Mesa configuration without current inputs passing probes.

This is a gate/provenance defect, not evidence that this host passed: the
existing GA43 invocation correctly stopped at exit 2 without SDK/receipt/
linker inputs.

**Fix:** run probes inside the gate, or require canonical paths and SHA-256
values for the exact SDK, compiler, linker, LLVM tools, probe sources,
commands, and outputs, and verify them before accepting the receipt.

### F4 — MEDIUM/HIGH native blocker: retry scheduling treats a fallible API as infallible

`gx_client_reap()` clears `pending` and invokes `ops->schedule`
(`i915-xnu/drm/gx_client.c:118-133`). Native `queueCleanup()` ignores the
return value of `thread_call_enter_delayed()` (`i915-xnu/native/GX42Service.cpp:
159-164`), and the callback always releases its current retain (`:165-171`).
If the regular call implementation rejects/coalesces a resubmission while the
previous callback is running, `pending` can remain set without a future
callback, leaving maps/task/provider quarantined until `free()` reaches its
panic checks (`:195-206`).

The comments impose a “schedule cannot fail” contract and the CPU witness
exercises an injected scheduler, but no exact-XNU KDK/runtime evidence proves
that contract for this call type. This is a native-runtime blocker, not a
demonstrated Linux CPU failure.

**Fix:** check/model the actual return; use a target-documented non-coalescing
or two-call scheme, or a retry record that cannot be lost. Add an exact-target
test for callback resubmission/coalescing, provider stop, and final free.

### F5 — MEDIUM: alternate file teardown can permanently strand maps

`gx_client_close()` frees VM leases, then requires `gx_close()` before reaching
`gx_revoke_owner_maps()` (`i915-xnu/drm/gx_client.c:93-108`). If another
trusted teardown has already called `gx_close(d, c->owner)`, `gx_close()` gives
`-EBADF` (`i915-xnu/gem/gx_gem.c:193-201`); `file_closed` stays false and every
retry takes the same branch. Owner maps, object references, and the task never
reach revoke. The current native call graph gives the client sole file
ownership, so this is an alternate-transport contract hole rather than an
observed current-path failure.

**Fix:** make file close explicitly one-shot, or treat `-EBADF` after a prior
trusted close as already closed and continue map revocation. Add a CPU witness
for this order and document that alternate transports must not raw-close the
client's token.

### F6 — LOW/MEDIUM wording: mmap-offset is not standard fd mmap

The implementation creates a GEM-style cookie but resolves it only through
private `GX_OFFSET_MAP` (`i915-xnu/include/gx_client.h:38-44`,
`i915-xnu/drm/gx_client.c:55-66`). `gx_gem.h:60-67` explicitly says no BSD
`d_mmap` pager is installed. `reports/GA43-TRANSPORT.md:8-18` acknowledges the
missing fd/pager/libdrm transport, but “standard mmap-offset protocol ... to a
real XNU resource backend” can be read as completed standard mmap support.

**Fix:** call this “standard cookie generation plus a private IOUserClient
CPU-map operation,” and keep fd mmap/pager, render node, and native libdrm
integration BLOCKED until implemented and tested. Do not advertise it as GPU
mapping.

## Test/evidence gaps

* `tests/test_vm.c:51-105` calls VM APIs through `f.c.vm_plans` without taking
  the client gate, although `i915-xnu/include/gx_vm.h:10-14` requires the gate
  for every call. It tests single-thread accounting, not concurrent VM/close.
* `tests/test_client.c:248-296` uses an injected scheduler; it cannot validate
  XNU `thread_call_t`, IOLock, task death, provider termination, or
  `IOMemoryMap::unmap()`. CPU PASS must remain CPU-only.
* `tools/anv-darwin-attempt.py:177-190` uses `-fsyntax-only` while its receipt
  names an object path (`:215-228`). If an object milestone is intended, use
  `-c -o` and inspect Mach-O; otherwise name it syntax-only.
* `tools/darwin-probes.py:55-58,94` stores `str(a.sdk)` but uses
  `a.sdk.resolve()` for compilation. `anv-darwin-attempt.py:69,79` compares
  against the resolved path, so relative/symlink SDK paths are rejected
  spuriously. Canonicalize before writing/comparing.

## Bounded claims and blockers

The source-level lease/refcount/quota paths are CPU-testable: leases retain
the same GEM object, handle close does not release a live lease/map, and VM
close drains contexts before VM names and GEM handles. Existing evidence does
not establish native XNU execution or GPU ownership. The GA43 module attempt
is blocked by the old linker’s unsupported `-kext` mode and unresolved
IOKit/libkern/kernel imports (`reports/GA43-XNU-LINK.md:11-19`,
`logs/native-module-link-ga43-001/`); its successful `-r` output is only
`MH_OBJECT`. There is no exact 25G83 KDK/export/ABI validation, BSD fd/render
node transport, native runtime, or GPU/Metal/ANV execution.

## Conclusion

GA43 has a useful CPU-only ownership/planning layer and honest explicit
GPU-operation refusals. It is not ready to call the native resource path
linked, loadable, or GPU-capable. F1–F4 are release-blocking corrections for a
trustworthy native/toolchain gate; F5 is an alternate-transport lifetime
precondition; F6 and the test gaps are evidence-boundary corrections.
