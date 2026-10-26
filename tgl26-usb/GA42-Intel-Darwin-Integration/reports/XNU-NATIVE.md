# GA42 native lifetime and module target

## Actual implementation

`57ee46962acd896e23f0320aeaad7dfa1059af10` adds the per-open client gate to
the inherited GEM foundation. It serializes input, publication, explicit
copyout/rollback and close; maps use only the transport-authenticated task.
Close/death closes handles, revokes maps, then drops task. Failed unmap keeps
task/pages/map and rejects new requests until close is retried. Device detach
is an irreversible admission barrier; cleanup remains available.

`native/GX42Service.cpp` connects the same client to genuine IOUserClient
`initWithTask`, `task_reference/task_deallocate`, `clientClose/clientDied`,
provider termination, IOLocks and explicit `copyin/copyout`. The per-client
lifecycle lock serializes quarantine reference transitions with close. The
provider is retained until client destruction; failed unmap pins client and
provider rather than freeing live resources. The initial one-shot cleanup
defect is preserved in `audit/native-review-001/REVIEW.md`. Commit
`f676974c824ee3bafefaa4469134596d0cd48fcf` adds a preallocated ONCE thread call:
failed close schedules a retained 100ms retry, repeated messages share it,
and every callback either drains resources or schedules one replacement
retain. An early successful external close leaves queued work to drain its
own reference. The callback may free its thread call at its final release
under the public XNU contract; free never waits on its own callback. A
persistent kernel unmap error continues retaining resources and retrying,
never reports falsely successful reclamation. The allocation choice was
subsequently refined by `520fe1156be71a97d8e164ec2d4e50571d0459ef` to the
documented `thread_call_allocate_with_priority` / `thread_call_free` pair.
Regular callback overlaps are serialized by the lifecycle lock, with a
separate retain for every running/queued callback. A bounded overlapping
callback witness passes ASan/UBSan. Independent review and its original
findings remain in `audit/native-review-002/{REVIEW,FOLLOWUP}.md`; no verified
source-state-machine defect remains at this CPU/compile evidence level.

Commit `3e513b104b5b4b4e7098862903972989d2be6c68` requires administrator
privilege for this pinned CPU-memory diagnostic interface and limits each
client to 16MiB. Maps whose handle was closed still count, with multiple
maps of the same object counted once. This is per-client, not a per-task
aggregate across multiple opens; the global 256MiB bound also remains.
`41f0cae2c1b6ea12b733d4049e63b4e54fce7cb4` explicitly consumes the supplied
non-null `security` token. The SDK parameter name alone does not prove that
a task-derived token value is invalid. Actual allow/deny authorization
behavior still needs exact-target runtime verification.

Selector 0 accepts two scalars `{BSD request, user address}` and returns one
errno scalar. Transfer/inheritance to a different current task is rejected.
CPU-map extension is explicit, not GEM_MMAP_OFFSET or a cdev mmap pager.
No render devfs node or libdrm→IOConnect transport exists yet. Both must share
this same ownership model before ANV mapping can work.

The PCI-matched service is CPU GEM diagnostics, not NMXGPU/NMXAccel or a GPU
resource manager. It neither opens PCI resources nor publishes Metal plugin
properties. Module stop refuses while native services remain live. Defensive
free assertions panic on an impossible ownership violation; they are not
proof of runtime quiescence.

## Evidence and blocker

* `logs/gem-client-unit-001`: **CPU_TEST PASS**, four sanitizer targets,
  including actual client-gate success/failing copyout close race, task hold
  failure, map/close retry, detach and full file table rollback.
* `logs/xnu-userclient-001`: **CROSS_COMPILE PASS**, seven Mach-O objects.
* `logs/native-module-link-001`: **CROSS_COMPILE PASS**, eight Mach-O objects
  with kernel/no-red-zone/C++ kext flags, genuine headers, module metadata,
  PCI personality check and unresolved-symbol inventory. **DARWIN_LINK
  BLOCKED**: real Clang diagnostic `invalid linker name in argument
  '-fuse-ld=lld'`. No local `ld64`/`ld64.lld` was found; no download authorized.
* Public MacKernelSDK pin `3f750085caa17ec3a7880f11c11bf4f48cd6a164` is not
  the Tahoe 25G83 KDK. Target symbol/ABI resolution is independently blocked.
* **XNU_NATIVE_RUNTIME NOT_RUN**, **GPU_HARDWARE NOT_RUN**, GPU resources **NO**.
* `logs/resume-quota-cpu-test-001` and `logs/deferred-reap-cpu-test-001`:
  **CPU_TEST PASS**, four ASan/UBSan targets. Actual production reaper tested
  with an explicitly injected deterministic scheduler: one death event,
  repeated messages/failures, provider detach, eventual unmap recovery, and
  external close succeeding before pending callback. Not an XNU scheduler run.
* `logs/deferred-reap-native-001`: **CROSS_COMPILE PASS**, nine Mach-O objects.
  `logs/deferred-reap-link-001`: fresh actual link still **FAIL/BLOCKED** with
  `invalid linker name in argument '-fuse-ld=lld'`; no linked kext artifact.
* `logs/native3-f1-native-compile`: final nine objects PASS, privately retained
  at `artifacts/native-final-001/`. `logs/native3-f1-overlap-run` validates
  retained overlapping production-reaper callbacks with an injected scheduler.

This is a WIP native module target and actual compile evidence, not a linked
or loadable kext. No installation, loading, target SSH or hardware access.
