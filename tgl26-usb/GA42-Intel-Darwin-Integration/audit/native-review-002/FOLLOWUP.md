# Native lifetime review 002 follow-up

Date: 2026-10-22

## Corrections committed

### Authorization gate — `41f0cae2c1b6ea12b733d4049e63b4e54fce7cb4`

`GX42Service::newUserClient()` now rejects a null supplied `security` token
and passes that exact token to
`IOUserClient::clientHasPrivilege(..., kIOClientPrivilegeAdministrator)`.
This is an explicit token-consumption correction, not a claim that `task_t`
can never be the security-token value: the cached public header only gives the
parameter type/name, common IOKit implementations may supply task-derived
security data, and no exact-target implementation or runtime is available.
The diagnostic policy remains administrator access, 16 MiB per-client quota,
and 256 MiB global bound. No aggregate per-task quota was added.

Native source evidence: `logs/native3-gate-compile/` exit 0, nine
x86_64-Apple Mach-O objects. This is a public-header cross-compile only; no
native authorization runtime test was possible.

### Deferred cleanup — `520fe1156be71a97d8e164ec2d4e50571d0459ef`

The preallocated cleanup item now uses the documented
`thread_call_allocate_with_priority` / `thread_call_free` pairing instead of
`thread_call_allocate_with_options`. Comments in `GX42Service.cpp/.h` now
state the regular-call overlap rule: a callback resubmission may overlap the
prior callback, the `lifecycle` lock serializes `gx_client_reap`, and every
scheduled/running callback owns one retained UserClient reference. The
no-cancel contract remains unchanged. `xnu_memory.cpp` now describes the
native task-death retry instead of saying it is unwired.

`audit/native-review-002/repro_overlapping_reaper.c` drives the production
`gx_client_reap()` state machine with an injected asynchronous scheduler. A
failed callback reschedules while the first callback is still active; the
replacement blocks on the lifecycle lock, has its own retain, and the final
release is observed only after all callbacks drain. It passed ASan/UBSan with
no diagnostic in `logs/native3-f1-overlap-run/`.

## Verification

* `logs/native3-f1-overlap-build/` — bounded production-reaper witness,
  ASan/UBSan build, exit 0.
* `logs/native3-f1-overlap-run/` — overlap, retain-per-callback, and final
  drain witness, exit 0; stdout SHA-256
  `c931d3b767e9a6b216b768632988181d45380f48cdb183631360177e9fed51fd`.
* `logs/native3-f1-native-compile/` — nine public-MacKernelSDK x86_64 Mach-O
  objects, exit 0; stdout SHA-256
  `a0db7aec980e6261b2573ff82b5b2cbb01d7c6686bd0e9ad1f02e281dec8addf`.
* `git diff --check` passed for each correction unit before its
  `tools/commit_unit.py` commit.

## Evidence boundary and remaining status

The corrections are validated to CPU/source-compile evidence level only.
There is still no exact-target KDK link, kext load, XNU `thread_call_t`
execution, IOUserClient authorization runtime, target access, hardware, VM,
or native transport test. The bounded witness is not an XNU runtime
simulation and does not prove OSObject or target scheduler behavior.

No additional verified source lifetime bug remains in the reviewed native
state machine at this evidence level. Native runtime/KDK and transport gaps
remain explicit blockers; no claim of native runtime readiness is made.

## Changed-source hashes

```text
b11624ff1a265bbc9d30e176f9367d206aaf70fcbfc4f3f59d23eada125680c4  i915-xnu/native/GX42Service.cpp
a13e2bb6260ee52bdc88def4f29444ce0b0d5d6f43192c2da328456c531df2b3  i915-xnu/native/GX42Service.h
3c32057334fe03811be49018d9109a28a3530e168940a9fe4008af5c132856b4  i915-xnu/os-compat/xnu_memory.cpp
12dba2c33c41db53108a782b76cd2bac03558ba11dc36c47252b6b41d6d591b3  audit/native-review-002/repro_overlapping_reaper.c
```
