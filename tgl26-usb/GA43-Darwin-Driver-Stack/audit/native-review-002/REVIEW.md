# Native lifetime review 002

## Scope and boundary

Read-only review of the two new commits on
`ga42/intel-darwin-integration`:

* `3e513b104b5b4b4e7098862903972989d2be6c68` — 16 MiB per-client quota and
  administrator gate.
* `f676974c824ee3bafefaa4469134596d0cd48fcf` — retained preallocated
  `THREAD_CALL_OPTIONS_ONCE` deferred cleanup.

The inspected tree was clean at `f676974c824ee3bafefaa4469134596d0cd48fcf`.
No production source, test source, EFI/media, target system, hardware, VM,
network, kext load, or runtime XNU operation was performed. Only this review
directory, its two bounded witnesses, and the explicitly requested
`run_logged.py` evidence directories were created; temporary build output was
placed under `/tmp/opencode`.

## Executive result

| Prior finding | Result at this evidence level |
|---|---|
| F1 — one-shot task-death cleanup quarantine | **Core retry/state ownership is fixed in source and CPU tests, but F1 is not production-resolved yet.** The cached SDK documents a mismatch in the new `thread_call_free` allocation path, and no XNU callback/runtime evidence exists. |
| F2 — missing authorization and quota | **Not resolved as written.** The quota accounting is tested and works per `drm_file`, but the privilege call passes the task where the SDK API requires the `securityToken`; there is also no aggregate per-task quota across repeated opens. |
| F3 — missing cdev/devfs transport | **Unchanged.** The commits do not add a transport, so ANV/libdrm still cannot reach this UserClient through a render node. |

## F1 findings: deferred reaping

### What is now correct

The C reaper in `i915-xnu/drm/gx_client.c:81-97` and the native wrapper in
`i915-xnu/native/GX42Service.cpp:154-180` establish the intended ownership
contract under the `lifecycle` lock:

1. A failed close publishes `pending` before scheduling and takes exactly one
   retained `GX42UserClient` reference.
2. Repeated external close/death/provider messages see `pending` and do not
   enqueue duplicate work or references.
3. A retry clears `pending` before closing. A failed retry re-publishes one
   replacement retain and requeues the same call; a successful retry leaves
   the scheduled retain for the callback to drop.
4. An external close that succeeds while the callback is queued does not
   cancel the call. The callback still consumes its retain and performs the
   final idempotent close.
5. `GX42Service::stop()` detaches admission before `messageClients()` and the
   UserClient retains its provider for the entire client lifetime. `free()`
   refuses to release a pending callback or live client state.

The new `tests/test_client.c:248-296` covers repeated external messages,
four persistent callback failures, `gx_device_destroy() == -EBUSY` while the
mapping is retained, and the queued-callback-after-external-close-success
case. An additional review witness issued two concurrent external calls and
observed exactly one retained retry.

### Required correction: SDK allocation/free contract is not proven

`GX42UserClient::initWithTask()` allocates with
`thread_call_allocate_with_options(..., THREAD_CALL_OPTIONS_ONCE)` at
`GX42Service.cpp:119-121`, while `free()` calls `thread_call_free()` at
`:194-196`. The cached public SDK header says:

* `THREAD_CALL_OPTIONS_ONCE` defers a self-resubmission until the callback
  returns (`sources/mackernelsdk/Headers/kern/thread_call.h:76-79`).
* `thread_call_free()` is documented as usable only for calls allocated by
  `thread_call_allocate` or `thread_call_allocate_with_priority`, explicitly
  omitting `thread_call_allocate_with_options` (`:221-233`).
* The same documentation says self-free from a callback is safe (`:227-229`).

Therefore the self-free assertion in the commit is supported only for the
callback-safety part, not for this allocation/free pairing. The implementation
must either use an SDK-supported allocation/free pairing while preserving
non-overlap, or provide exact-target XNU source/KDK evidence that
`thread_call_free` also accepts an `allocate_with_options` call. Until then,
the cleanup path cannot be called production-safe. `thread_call_enter_delayed`
also returns a `boolean_t`; the source contract currently relies on the
documented non-failing asynchronous scheduler contract and ignores that
return value, which should remain an explicit invariant in any correction.
The generic backend comment at `i915-xnu/os-compat/xnu_memory.cpp:73-74`
still says task-death cleanup is “not wired yet”; it is now stale for this
native `GX42UserClient` path and should be clarified rather than used as
runtime evidence.

### F1 status

**Partially resolved:** the prior permanent-quarantine defect is resolved in
the C state machine and native source structure to CPU/source-compile
evidence level. It is **not resolved to native runtime/production level**
until the SDK allocation/free issue and an exact XNU callback execution are
settled. The CPU tests do not execute `thread_call_t`, `IOLock`,
`IOUserClient`, task death, provider termination, or `IOMemoryMap::unmap()`.

## F2 findings: privilege and quota

### Required correction: wrong argument to `clientHasPrivilege`

At `i915-xnu/native/GX42Service.cpp:68-76`, the new gate is:

```cpp
IOUserClient::clientHasPrivilege(task, kIOClientPrivilegeAdministrator)
```

The cached SDK declaration is:

```cpp
static IOReturn clientHasPrivilege(void *securityToken,
                                   const char *privilegeName);
```

(`sources/mackernelsdk/Headers/IOKit/IOUserClient.h:323-327`). The
`newUserClient` parameter named `security` is the security token and is also
passed to `initWithTask`; `task_t` is not that token. Passing `task` is a
source/API contract error, not an authorization test. The correction must
check the actual `security` token (or use a separately documented task-based
authorization API), followed by a native authorization test with accepted
and rejected clients.

### What the quota implementation proves

`owner_bytes()` in `i915-xnu/gem/gx_gem.c:119-136` counts each object once
across live handles and owner maps. This correctly preserves quota after a
handle close while a map retains the object. The check is under the device
lock and uses the same page rounding as object creation. Allocation failure
does not reserve quota because the check is read-only and object accounting
occurs only after successful page allocation.

The bounded `quota_review_witness.c` confirms:

* metadata allocation failure and page allocation failure leave bytes and
  objects unchanged;
* a client can reach exactly 16 MiB but not create one more page;
* two independent open-file records can each reach 16 MiB.

The last point is also the remaining scope gap: the accounting key is
`struct drm_file *`/`gx_file_id`, not `task_t`. The native UserClient can be
opened repeatedly by the same task, and neither `gx_device` nor `gx_client`
aggregates quota by task. Thus this is a **per-client quota**, not the
per-task aggregate quota required by the original F2 wording. If the intended
policy is deliberately per-client, that narrower property is CPU/source
validated; if it is per-task, an additional task-keyed budget is required.

### F2 status

**Not resolved.** Per-client quota mechanics pass CPU and sanitizer evidence,
but the administrator check uses the wrong SDK argument and no per-task
aggregate is enforced. The prior unprivileged public interface finding must
remain open until the token call is corrected and native authorization is
tested.

## Evidence and checks

All probes were offline and invoked through `tools/run_logged.py` with unique
`review-native2-*` labels:

* `logs/review-native2-cpu-build/` and
  `logs/review-native2-cpu-test/`: independent CPU build; all 4 CTest targets
  passed. Test stdout SHA-256:
  `5cd100bc30344842e355f3285621b3b26f5d9db4e766e6d987230f140d2a19dd`.
* `logs/review-native2-cpu-sanitize-build/` and
  `logs/review-native2-cpu-sanitize-test/`: independent ASan/UBSan build and
  run; all 4 targets passed with no sanitizer diagnostic. Test stdout SHA-256:
  `7da1f14de96c4ce82ce543542ad0200a9b34c76683c3788d89464d5cb8180b14`.
* `logs/review-native2-quota-witness-build-002/` and
  `logs/review-native2-quota-witness-run/`: allocation rollback and
  independent per-file 16 MiB budget witness passed. Run stdout SHA-256:
  `a9e8dae2234d9bac8d546ce7cab5acd82c5578a5ae70bf301a0f98a34c11a95e`.
* `logs/review-native2-reaper-witness-build/` and
  `logs/review-native2-reaper-witness-run/`: concurrent external notification
  deduplication witness passed.
* `logs/review-native2-reaper-witness-san-build/` and
  `logs/review-native2-reaper-witness-san-run/`: same witness under
  ASan/UBSan; passed with no diagnostic. Run stdout SHA-256:
  `7d8949df6c20eda53401c653e53cc29fd82cf249462312d4030574a53bf69e9a`.
* `logs/review-native2-native-compile/`: independent public MacKernelSDK
  compile of nine x86_64 Mach-O objects, including the changed native and C
  units; exit 0. This is not a KDK link or runtime test. Stdout SHA-256:
  `29bd650f9bfa33dbe85949671826ac7fdb66b7c5ee8a7d436d549556a7781b9d`.

The tracked production source remained unchanged after the review. Relevant
HEAD source hashes are:

```text
c75b8c8876b1e476563619284fc7ee2a75d8dfba03f83984adfb1a584836c8b9  i915-xnu/native/GX42Service.cpp
bcc505fd84bf16b6b576dbafb506b4cb8f0a60f6d2c81119b3d52af73118b6ec  i915-xnu/native/GX42Service.h
449ed682d0c5b17bffbb53db563a8b18cd5901b7f507757a84848ed82e270b50  i915-xnu/drm/gx_client.c
f354686eb4c22555b05bddaeb43ef535432ae88e997c1fcfca4f9e7fa0489a51  i915-xnu/include/gx_client.h
894548f803042df3d96f671f9951bc686897179e129cea2dce1e47f300683817  i915-xnu/gem/gx_gem.c
f57ede926aed352aa3da662003e40283c2d52d9ef1413a3e7a2a3b799c728597  i915-xnu/os-compat/xnu_memory.cpp
91d9764b9f94c43e377807723f24787975f233fd9aa88d27e40f5e8327e08709  tests/test_client.c
418e366dd97d39b3e899f00c488934b6c146cbd0d0c1b323233f403f6db88e43  sources/mackernelsdk/Headers/kern/thread_call.h
```

## Explicit limitations and next corrections

1. Correct the `clientHasPrivilege` argument and add a native accepted/rejected
   privilege test.
2. Resolve the `thread_call_allocate_with_options` versus `thread_call_free`
   SDK contract before calling F1 complete.
3. Decide whether quota is intentionally per-client or must be per-task; add
   task-keyed accounting if the original F2 requirement remains.
4. Preserve F3 as an integration blocker: no cdev/devfs/render-node transport
   was added or validated.
5. Do not describe the nine Mach-O objects or CPU tests as native runtime,
   exact-KDK, kext, target, or hardware evidence.
