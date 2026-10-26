# Native lifetime review 001

**Scope.** Read-only review of the native IOUserClient/provider/module and
the per-open task/map lifetime at the requested baseline commits
`57ee46962acd896e23f0320aeaad7dfa1059af10` and
`0f14de6aee450e48b9eb06afdb82c94e3fe65998`. The tree advanced while this
review was running; the final inspected tree was `00b37b69174d1fec84f868a42510bf35c4a9a4ee`,
including the intervening truthful-query and bounded exec-preflight units.
No production source or root tests were changed. No XNU/macOS kernel,
hardware, VM, or network was run.

## Findings

### F1 — HIGH: one-shot task death/termination can permanently quarantine a client

This is a verified lifetime defect at the native integration boundary.

* `GX42UserClient::clientDied()` is only `return revoke()`
  (`i915-xnu/native/GX42Service.cpp:156-157`); the termination message also
  makes one synchronous `revoke` call (`:158-161`).
* `revoke` retains a quarantine reference when `gx_client_close` returns an
  unmap error (`:141-154`). `gx_client_close` deliberately leaves
  `task_held`, the owner token, and failed/rest mappings live for a later
  retry (`i915-xnu/drm/gx_client.c:59-78`; the contract is also stated in
  `i915-xnu/include/gx_client.h:43-45`).
* There is no deferred work item, timer, task-death worker, or provider-side
  retry. `GX42Service::stop` ignores the aggregate return from
  `messageClients` (`:78-86`), and `free` only retries synchronously and then
  panics if the client still owns resources (`:163-170`). A dead task cannot
  call `clientClose` later, and a one-shot provider termination message is not
  a retry mechanism.
* The local public XNU implementation confirms that `IOMemoryMap::unmap()` can
  return the underlying `doUnmap` error (`sources/xnu/iokit/Kernel/IOMemoryDescriptor.cpp:5799-5822`),
  while the adapter turns that into `-EIO` and retains the object
  (`i915-xnu/os-compat/xnu_memory.cpp:52-57`). Thus this is not merely an
  impossible return path.

The bounded CPU-only witness `repro_dead_client.c` models the sole death
callback, injects one failed unmap, and observes `-EIO`, one retained task
reference, one map, one backing object, and `gx_device_destroy() == -EBUSY`.
It then performs an explicit second close only to prove that the existing
retry contract can eventually drain; that second close is precisely what a
dead task cannot initiate. This is a model of the C lifetime unit, not a claim
of XNU runtime execution.

**Required fix:** arrange a provider/client-owned deferred retry or an
equivalent task-death-safe finalization path. It must keep the provider and
client storage alive, serialize with the client gate, retry/finish mapping
reclamation, and only then drop the retained task and quarantine reference.
Do not turn `free`'s panic into silent release of live mappings.

### F2 — MEDIUM/HIGH: public UserClient has no authorization or per-task quota

`GX42Service::newUserClient` rejects only null/kernel tasks and nonzero type
(`i915-xnu/native/GX42Service.cpp:66-76`); its `security` argument is not
checked. The local public IOUserClient header says the base
`initWithTask` currently ignores its arguments (`sources/mackernelsdk/Headers/IOKit/IOUserClient.h:351-359`),
so passing the token through at `:104-105` does not add authorization.

Any task that can open the matched service can therefore allocate the full
bounded device budget: a single BO may be 64 MiB and total CPU-shared BO
backing is 256 MiB (`i915-xnu/gem/gx_gem.c:12-17,90-103`), allocated through
`IOBufferMemoryDescriptor::inTaskWithOptions` in
`i915-xnu/os-compat/xnu_memory.cpp:20-31`. The bound limits damage but does
not prevent an unprivileged process from pinning a substantial amount of
kernel memory and holding it through the death/quarantine path in F1.

**Required fix:** enforce an explicit entitlement/privilege (or document a
deliberate public diagnostic interface), and add a per-task/client quota in
addition to the global bound. The task reference is ownership/liveness, not
authorization.

### F3 — BLOCKER (integration gap, not a hidden UAF): no cdev/devfs transport

There is no registered BSD character device, `cdevsw`, devfs render node, or
`open`/`ioctl` transport in this unit. `i915-xnu/os-compat/xnu_copy.cpp:1-5`
explicitly calls itself an unregistered helper and
`:18-21` only exposes a direct C function. `Info.plist:17-24` publishes an
IOService personality, not a BSD node. Consequently libdrm/ANV cannot open a
render node and reach this lifetime contract; the existing IOUserClient path
is not a cdev replacement.

This is a verified missing transport, not a claim that a cdev must be added
to the CPU-only diagnostic unit without design review. Any future transport
must use the same authenticated task, client gate, close retry, and provider
quiescence rules; it must not call `gx_xnu_user_ioctl` as an un-gated shortcut.

## Non-findings / hypotheses

* I found no verified premature `gx_device` free in the current IOUserClient
  path: the service gate blocks new opens during detach, each successful
  user client retains the provider, and `gx_xnu_destroy` returns `EBUSY` for
  live file/object/map state (`GX42Service.cpp:61-64,78-98`; `gx_gem.c:129-136`).
* The module live-service counter (`native/module.c:5-14`) is only a coarse
  unload guard and does not itself count in-flight methods/start/free calls.
  That is a quiescence concern worth fixing or proving against the kext
  loader, but I did not classify it as a verified UAF without XNU unload
  runtime evidence. The defensive panic in `GX42Service::free` is likewise
  fail-stop behavior, not proof that quiescence is implemented.

## Reproduction and inspection evidence

Commands were run through `tools/run_logged.py`, preserving raw output:

* `logs/review-native-005-build/` — isolated CPU witness compiled, exit 0.
* `logs/review-native-006-run/` — witness passed, exit 0:
  `REPRO: one death/termination cleanup callback leaves task+map pinned on unmap failure`.
* `logs/review-native-007-sanitize-build/` and
  `logs/review-native-008-sanitize-run/` — ASan/UBSan build and run passed,
  exit 0, with no sanitizer diagnostic.
* The earlier `review-native-001/002/003/004` attempts are retained as raw
  provenance (compile-boundary fixes and the intentionally timed-out first
  witness run); they are not runtime evidence.

Source SHA-256 values for the final inspected tree are retained in
`build/review-native/source-sha256-final.txt` (ignored build evidence). The
main reviewed files were:

```
GX42Service.cpp       42e23c5c5a4e2e8a501a7cd4ae47cd2ce9c1694c0193ff26498885f07630e213
GX42Service.h         2ba27f684aa186f7f4b8f39d526534a9761494780db7899704923d4afd9a6f18
module.c              89f936d72489f5c46cfd13dd6311cd344352743f355628f49ae15843e9c801af
gx_gem.c              546bf4fb73d2b0a680082b0a2a8a946fe88da1298e77750f1b1901245af58886
gx_client.c           c97863202eb483c2761155ea9e701e0bbd00b36a04aab31f4b805e26a315a561
xnu_memory.cpp        f57ede926aed352aa3da662003e40283c2d52d9ef1413a3e7a2a3b799c728597
xnu_copy.cpp          5cf9c115d6f499097d38316d9a227b964e905d5f3bd995f45634775286d51858
gx_ioctl.c             be84fd3a64808f2ecdc8f325940f11cf9dfb5c26e1bd41f3b6a455cf32a85ddf
gx_exec_validate.c     fa074d7f559e37c5390a35489f0449d4d898b66d116451457a0d1def8f50b313
```
