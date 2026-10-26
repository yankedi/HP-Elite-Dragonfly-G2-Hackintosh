# GA43 initial native transport and toolchain review

## Scope and result

This is a read-only review of the GA43 native GX42Service/GEM boundary, the
available XNU/MacKernelSDK inputs, and the Darwin probe evidence.  The reviewed
tree was at `9939e3b0d3d9cf918d830276ad5cdb59387362e0`; an unrelated existing
working-tree modification to `tools/anv-darwin-attempt.py` was not touched.  No
production source, test source, VM, target runtime, kext load, GPU, network, or
hardware operation was performed.  The only file created by this review is
this document.

**Bottom line:** the current IOUserClient path is a bounded, CPU-only
diagnostic transport with a coherent authenticated-task lifetime model.  It is
not a BSD render node, does not implement standard GEM mmap-offset semantics,
and does not prove a Darwin kext or GPU path.  A future BSD facade can be kept
thin, but its per-open file context and mmap pager must be established from
exact target KPI evidence rather than inferred from the old public headers.

## Findings

### F1 — Current native path is IOUserClient-only, not libdrm transport

`GX42Service::newUserClient()` accepts only type 0, a non-null non-kernel task,
and a security token that passes administrator privilege
(`i915-xnu/native/GX42Service.cpp:68-85`).  `externalMethod()` exposes one
selector containing `{BSD request, user address}` and returns errno in one
scalar (`:142-157`).  It authenticates the caller by requiring
`current_task() == owner` (`:152`) and uses explicit `copyin`/`copyout`
(`:28-34`, `:153-156`).

There is still no registered `cdevsw`, BSD character device, devfs render node,
or libdrm-to-IOConnect implementation.  The existing status report records
this explicitly (`reports/XNU-NATIVE.md:45-49`), and the DRM report says native
Darwin compilation and real-node access remain untested
(`reports/DRM-INTEGRATION.md:39-45`).  Therefore an ANV/libdrm file descriptor
cannot reach this UserClient merely because the UserClient compiles.

### F2 — The ownership contract that a future transport must preserve

The `gx_client` contract is suitable as the single backend seam:

* `gx_client_ops` supplies locking and task retain/release, while the task is
  authenticated by the transport, not by a user-provided integer
  (`i915-xnu/include/gx_client.h:9-25`).
* `GX42UserClient::start()` opens one client with the retained owner task and
  then drops its provisional reference (`GX42Service.cpp:130-140`).
* The lifecycle lock, provider retain, client gate, and deferred close path
  keep failed unmaps alive for retry (`GX42Service.cpp:159-210`).  A failed
  unmap is deliberately not converted into successful reclamation.
* GEM maps carry the authenticated `gx_file_id` owner.  A map retains its
  object, and `owner_bytes()` counts an object still held by a map even after
  its handle is closed (`i915-xnu/gem/gx_gem.c:119-136`, `:204-237`).  The
  file-id token is monotonic and must not be replaced by a reusable pointer to
  a file-table slot.
* Device detach rejects new operations while cleanup remains possible
  (`gx_gem.c:158-168`, `:243-246`).

Any cdev or alternate IOUserClient front end must therefore create exactly one
per-open `gx_client`, pass the kernel-resolved caller task to it, serialize
operations through its gate, perform explicit bounded copyin/copyout, and
retain the provider/client until all maps have either been unmapped or remain
in an explicit retry quarantine.  It must not call a direct helper around the
gate or accept a task pointer, kernel address, map address, or owner token from
userspace.

### F3 — Recommended thin transport boundary

The clean architecture is a transport adapter over the existing `gx_client`,
not a second GEM implementation:

1. **Registration:** on provider start, register one private character node
   through target-supported `cdevsw`/devfs APIs; on stop, first block admission,
   then remove the node and drain existing per-open clients.  The public SDK
   does expose `devfs_make_node()`/`devfs_remove()`
   (`sources/mackernelsdk/Headers/miscfs/devfs/devfs.h:97-122`) and the
   `cdevsw` slots (`sources/mackernelsdk/Headers/sys/conf.h:178-189`).
2. **Open/close:** allocate transport-owned per-open state and initialize one
   `gx_client`.  The actual caller-task and file-private-data plumbing must be
   selected from the target cdev/fileproc KPI; the public header's callbacks
   alone do not establish that contract.  Close must invoke the same idempotent
   revoke/retry path as the UserClient, not free a context while a map or
   deferred callback remains.
3. **Ioctl:** translate only the fixed Darwin wire requests, validate sizes and
   integer ranges, use kernel copyin/copyout, and pass the authenticated
   per-open context to `gx_client_ioctl()`.  Preserve real unsupported errors;
   do not make Linux i915/GEM requests appear implemented.
4. **Mmap:** do not implement the `d_mmap` slot from the public declaration by
   guesswork.  In this SDK `mmap_fcn_t` is literally an opaque `int(void)`
   typedef (`conf.h:108-123`), so it provides no usable pager signature or
   target ABI proof.  A standard fd mmap path is a separate exact-KPI task.
   Until that KPI is verified, a safe CPU-only map can remain an ioctl operation
   returning a task virtual address and opaque map ID, using the authenticated
   task below.

This gives libdrm a future fd boundary without weakening the existing lifetime
rules.  It does **not** by itself make the node an i915 render node: identity,
query, GEM mmap ABI, GPU VM, submission, synchronization, IRQ, and reset
contracts still need independent implementations and evidence.

### F4 — CPU mapping API is available; kernel addresses must not escape

The current adapter allocates an `IOBufferMemoryDescriptor` solely for
CPU-sharing (`i915-xnu/os-compat/xnu_memory.cpp:20-31`).  It maps through
`createMappingInTask(task, ..., offset, length)` and returns the resulting
`IOMemoryMap` address only after checking the authenticated task and requested
length (`:36-50`).  The public declaration documents that this creates a map
in the supplied task, supports read-only options, and that the map retains its
descriptor while alive (`sources/mackernelsdk/Headers/IOKit/IOMemoryDescriptor.h:611-633`).

The local XNU implementation is consistent with this ownership model:
`IOMemoryMap::unmap()` can return the underlying unmap result while releasing
the task map (`sources/xnu/iokit/Kernel/IOMemoryDescriptor.cpp:5799-5823`),
and `taskDied()` drops the user task mapping (`:5825-5845`).  These are source
semantics, not target-runtime evidence.  The adapter correctly retains the
`IOMemoryMap` on failure and retries it (`xnu_memory.cpp:52-57`).

This facility is **not** `GEM_MMAP_OFFSET`, a Linux mmap pager, a GPU-visible
address, a DMA address, or proof of Metal/acceleration.  The explicit project
ABI says so (`gx_client.h:27-35`).  A future fd mmap implementation must use a
target-verified VM/pager path and return a user mapping, never
`getBytesNoCopy()` or any kernel virtual address.

## Exact KDK and link conclusion

An exact 25G83 KDK is **not intrinsically required merely to serialize a
Mach-O kext unit** if a compatible Darwin Mach-O linker, compatible kmod
runtime inputs, and headers are already available.  The public MacKernelSDK
README documents linking its supplied `libkmod.a`
(`sources/mackernelsdk/README.md:25-35`) and identifies itself as based on the
macOS 11 SDK with older XNU headers (`:72-79`); that is enough to explain why
cross-compilation can emit Mach-O objects and why it is not equivalent to a
Tahoe KDK.

The exact KDK **is required for the target compatibility claim**: resolving the
25G83 KPI symbol set, checking structure/vtable/availability assumptions,
linking against the target-supported kmod/runtime inputs, and validating the
result against the running kernel.  Older/public headers and a successful
object compile cannot establish that ABI.  The current evidence reports nine
Mach-O objects but no linked kext, with the actual link blocked by the missing
Darwin linker and no exact KDK (`reports/XNU-NATIVE.md:57-84`).

Thus the accurate split is:

| Claim | Status |
|---|---|
| Clang can emit x86_64 Mach-O objects | **PASS** |
| A compatible modern Darwin kext link is available locally | **NO** |
| Public SDK declarations for cdev/devfs exist | **YES, old/broad only** |
| 25G83 KPI symbol/ABI compatibility is established | **NO; exact KDK absent** |
| Linked, loadable, or runtime-tested kext | **NO** |

Acquiring a complete Apple user SDK or exact KDK, or a modern linker, would be
a new input/evidence stage.  A Linux SDK, fabricated `.tbd`, public
MacKernelSDK, or an Android LLD diagnostic artifact cannot substitute for it.

## Darwin probe audit

The strict probe result at `logs/darwin-probes-002/result.json` is:

```text
c_object                         0   PASS
minimal_dylib                    1   FAIL
minimal_dynamic_lookup_diag     0   diagnostic-only salvage
libcxx_object                    1   FAIL
libcxx_link                      1   dependency probe FAIL
libsystem_object                 1   FAIL
libsystem_link                   1   dependency probe FAIL
icd_names_object                 0   export-name fixture object PASS
icd_names_link                   1   strict link FAIL
```

`tools/darwin-probes.py:68-89` intentionally records compilation and link
stages separately and labels dynamic lookup as diagnostic-only.  That
distinction is correct, but the generated
`artifacts/darwin-probes-002/DIAGNOSTIC_ONLY.dylib` must not be described as a
successful production dylib: it contains `_ga43_checked_add` but also an
undefined `dyld_stub_binder`.  The old LLD also writes `MH_NOUNDEFS` despite
that undefined symbol, so load-command flags cannot replace an actual symbol
table/undefined-import check.  The project toolchain report records the same
contradiction (`reports/TOOLCHAIN.md:37-45`).

The diagnostic artifact proves only that the cached old LLD can emit a
Darwin-flavored MH_DYLIB under `-undefined dynamic_lookup`.  It does not prove
libSystem, libc++, a complete user SDK, a valid ANV ICD, kext linkage, runtime
loading, or GPU operation.  The probe's own result correctly leaves
`runtime` and `gpu` as `NOT_TESTED` (`logs/darwin-probes-002/result.json:14-18`).

## Required next evidence (without changing this review's scope)

1. Obtain or receive a legally available complete Apple user SDK and exact
   25G83 KDK, recording versions and hashes; do not fabricate system inputs.
2. Use a compatible `ld64`/`ld64.lld` and real kmod/runtime inputs to perform a
   strict no-undefined kext link, then inspect symbols and load commands.
3. Resolve the target cdev/devfs per-open/file-private-data and `d_mmap` KPI
   from exact headers/source or a supplied target SDK before implementing that
   adapter.
4. Keep the first transport milestone CPU-only: authenticated open, bounded
   ioctl, CPU map/unmap, owner close/death, provider detach, and retry/error
   witnesses.  Do not call that milestone i915/GPU/render-node success.
5. Only after link and transport contracts are proven separately should native
   runtime, target loading, GPU VM, submission, and hardware tests be planned.
