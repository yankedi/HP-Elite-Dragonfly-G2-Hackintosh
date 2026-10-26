# GA41 independent review 001

## Scope and evidence

Reviewed only the requested CPU-side sources in `i915-xnu`, `tests/gem*`,
`tests/test_gem.c`, `libdrm-darwin`, and `nmx`.

Verified on the current tree:

* `./build/gem-sanitize/gem_cpu_test`: PASS, 7 groups, including the
  same-file map/close race and owner-map revoke/retry.
* `./build/gem-sanitize/libdrm-darwin/test-drm-darwin`: PASS; fake transport
  only, no GPU node or hardware ioctl.
* `logs/native-abi-001`: the XNU adapter and ABI objects compile as Mach-O
  x86_64 objects with the checked-in MacKernelSDK. This is compile evidence,
  not a loaded/native runtime test.
* `repro_fd_path_swap.c` compiles with `-Wall -Wextra -Wpedantic -Werror`
  and runs CPU-only. Its output is in `repro_fd_path_swap.log`.

## Must-fix findings

### P1 — `drmGetDevice2` can return metadata for a different reopened node

Evidence: `libdrm-darwin/drm_darwin.c:741-796, 800-815`.

`drmGetDevice2()` queries the supplied fd, obtains a path, then
`device_from_fd_path()` queries the fd again but reopens the path through
`node_from_path()`. The original and reopened `struct stat` values are never
compared. The only relationship check is BDF equality at lines 770-771; the
reopened node's `st_rdev` major is not checked, and its vendor/device fields
are not checked either.

The isolated CPU reproducer models a path replacement: fd 400 is an Intel
device on major 240/minor 0; reopening its returned `card0` path yields an
AMD device on major 241/minor 0 with the same BDF. The current implementation
returns success and `vendor=0x1002`:

```text
observed success with replacement vendor=0x1002
```

Thus a caller can receive a successful `drmDevice` whose metadata came from a
different cdev than the fd it supplied. Fix by avoiding the path reopen for
the fd identity, or by requiring the reopened node to match the original
`st_rdev` (major and minor where stable) and the complete PCI identity before
using it. Keep the existing fallback for an unlinked node, but do not use a
BDF-only match to authorize a replaced path.

Reproducer and log hashes:

```text
f81438f98317e8b9d9c7e842d6e66c2703d23278fbc1781f7bb29479f27b98c1  repro_fd_path_swap.c
f62893eeba67e68845a0bcb134941e9d4295bb4c8b56cafd2cc68c97e362f5a5  repro_fd_path_swap.log
```

### P2 — `add_device()` silently folds conflicting PCI metadata

Evidence: `libdrm-darwin/drm_darwin.c:497-535, 538-572`.

Pair folding deliberately keys on domain:bus:device.function only
(`pci_bus_equal_public()` at lines 490-495). When the second node has the
same BDF, `add_device()` returns success without comparing vendor, device,
subvendor, subdevice, or revision (lines 545-555). `deviceinfo.pci` remains
whatever the first node supplied (lines 528-533).

The reproducer also exercises this case: a primary Intel node and a render
node with the same BDF but AMD device fields produce one paired device and
retain the first vendor:

```text
observed same-BDF pair keeps first vendor=0x8086
```

BDF-only deduplication is the right identity key for a normal primary/render
pair, but disagreement in the remaining PCI tuple is evidence of a stale or
inconsistent provider and must not be silently hidden. Compare the full
returned identity when adding the second node and reject/quarantine a
conflicting pair; add a regression where the two nodes disagree.

### P2 — malformed PCI device numbers are accepted

Evidence: `libdrm-darwin/drm_darwin.c:368-379`.

`query_pci()` rejects absent vendor/device values and functions above 7, but
does not reject `pci->dev > 31`, which is outside the PCI device-number range.
The invalid value is then copied into `drmPciBusInfo` and used for device
deduplication. Add the range check (`dev <= 31`) and a CPU transport case for
an invalid PCI tuple before trusting discovery results.

## Native glue blockers (documented, but still unresolved)

These are not disguised as defects in the two extracted Linux function
bodies; they are integration requirements that remain absent from the
current XNU adapter:

* `i915-xnu/os-compat/xnu_memory.cpp:35-49` accepts a raw `uintptr_t` task
  value. The comments require a retained, authenticated IOUserClient owner,
  but the adapter does not establish or enforce that ownership. The eventual
  transport must resolve an opaque owner to a retained task and must never
  pass a user-supplied task integer through `gx_map()`.
* `xnu_memory.cpp:72-79` explicitly says task-death cleanup is not wired.
  `gx_revoke_owner_maps()` now provides the needed retry-preserving drain,
  but no IOUserClient close/death path calls it. Mappings intentionally
  survive `gx_close()`, so a native owner teardown must revoke them before
  releasing the task and before allowing device destruction.
* `i915-xnu/drm/gx_ioctl.c:23-31` performs create, unlocks, then calls
  copyout. It relies on the documented per-client requirement that the owner
  remain alive across the entire operation. `xnu_copy.cpp` is unregistered,
  and no native close/ioctl serialization is present. Without that glue,
  concurrent close can make a successful copyout return a handle that has
  already been destroyed; a failed copyout can race the ignored rollback
  result. The native transport must hold an open-file reference/serialize
  close, then rollback before releasing it.
* `gx_device_destroy()` requires external quiescence (`gx_gem.h:15-17`), and
  `gx_xnu_destroy()` only documents that precondition. Native teardown must
  stop new calls and drain/revoke all files and mappings before invoking it;
  the core's `-EBUSY` check is not a substitute for a quiescence barrier.

## Reviewed and not counted as production findings

* The handle/object/map reference transitions in `gx_gem.c` are serialized by
  the device lock; the current CPU tests cover close-after-map, map/close
  interleaving, failed unmap retry, and owner revoke. No CPU lifetime or
  refcount failure was reproduced.
* `drmDevicesEqual()` and `nmx_pci_identity_equal()` intentionally compare
  PCI bus identity, not vendor/device identity. The local public
  `drmPciBusInfo` layout is 6 bytes with fields at offsets 0, 2, 3, and 4, so
  the current `memcmp()` does not read padding on this ABI. The separate
  `add_device()` consistency issue above is about conflicting node metadata,
  not padding.
* `drmDarwinSetSyscalls()` and the device-directory setter mutate global state
  without synchronization. Their header and README mark them test-only and
  not installed; tests must configure them before starting concurrent work.
  This is a test-hook limitation, not evidence of a native production race.

## Retest required after fixes

1. Run `repro_fd_path_swap.c`; path replacement must fail or use only the
   original fd's identity, and a conflicting primary/render tuple must not be
   silently paired.
2. Add fake-transport cases for `dev=32`, malformed node names, and provider
   disappearance during the second fd/path query; rerun both discovery tests
   and sanitizers.
3. In native glue, race copyout against close while holding the owner
   reference, then exercise task-death revoke with one forced unmap failure;
   only after retry succeeds should `gx_xnu_destroy()` be allowed to pass.
