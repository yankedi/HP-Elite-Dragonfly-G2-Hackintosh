# GA41 review-001 follow-up

## Verification performed

I re-read the current `libdrm-darwin/drm_darwin.c`, `nmx/identity.c`, and
`libdrm-darwin/tests/test_drm_darwin.c`, then ran the current CPU-only
sanitizer binaries. No source or original review artifact was changed.

Fresh logs:

```text
audit/review-001/followup-tests-001.log
  f4043530a0c7f542fd5ecfb78f64480cb3c3cd2634dd7c37fc844eae935871c2
audit/review-001/followup-drm-sanitize-001.log
  cebf1b779488d7624311f9f753989bd5c05349e36822636c825b549305bb39b8
audit/review-001/followup-gem-sanitize-001.log
  9fc2e192c73d7ed2b0acf974dd085e0e8bef2dd1d6e39abc464bf5b6b41388d8
audit/review-001/followup-integration-sanitize-001.log
  2c184dcf58f512f00c3ec03f5e098109e98d16b23d89170c4be8420c6187b13f
```

All three current CPU test executables passed under ASan/UBSan options:

* GEM lifecycle: 7 groups passed.
* Darwin discovery: replacement-rdev/full-PCI, conflicting pair/count,
  `dev=32`, disappearance, canonical names, and tail-padding tests passed.
* Combined DRM/GEM CPU integration: passed; no GPU node or hardware ioctl.

The five current ABI objects are Mach-O x86_64 objects (`abi_compile.o`,
`gx_gem.o`, `gx_ioctl.o`, `xnu_copy.o`, and `xnu_memory.o`). This remains
compile evidence only; the adapter is not installed or loaded.

## Closure of the three original findings

### 1. Reopened fd/path identity — addressed

`nm_node` now retains `rdev` (`drm_darwin.c:108-114`). `node_from_path()`
records it only after successful stat and PCI identity query
(`461-491`). `device_from_fd_path()` requires exact `st_rdev` and the full
PCI tuple before accepting the reopened path (`803-808`), and re-queries the
original fd after enumeration to catch provider disappearance or identity
change (`816-823`). The regression at
`tests/test_drm_darwin.c:378-380,391-393` rejects both replacement and gone
provider cases. The former standalone reproducer would now return `-ENODEV`.

### 2. Conflicting same-BDF node folding — addressed

The device list now owns a parallel private `nm_node` identity array
(`drm_darwin.c:116-121`). `add_device()` compares full PCI fields, cdev
major, and the primary/render slot before folding (`558-604`). The current
test mutates the render node's vendor and requires `-ENODEV` for both bounded
and count-only enumeration (`tests/test_drm_darwin.c:381-387`).

I audited the new ownership paths:

* Each successful list entry writes both `items[count]` and
  `identities[count]` only after both arrays are available.
* `free_device_list()` frees every retained device, then both arrays
  (`123-135`). Enumeration errors therefore release private identities.
* `drmGetDevices2()` frees private identities in both count-only and bounded
  return paths (`742-775`); the caller receives only `drmDevice` pointers.
* The `drmGetDevice2()` match path detaches the selected device, frees all
  other devices, and frees the private identity array (`824-848`).
* If the second parallel `realloc()` fails after the first succeeds, the
  updated item pointer and the old count remain available to the error
  cleanup; no extra identity entry is counted or exposed.

No list-identity leak or double-free was found by source audit or the current
sanitizer tests. Allocation-failure injection for the parallel realloc path
was not present, so that path is statically verified rather than dynamically
fault-injected.

### 3. Invalid PCI device number — addressed

`query_pci()` now rejects `pci->dev > 31` (`drm_darwin.c:372-382`). The test
case at `tests/test_drm_darwin.c:388-390` exercises `dev=32` and requires
`-ENODEV`.

## Correction to the original review

The original `REVIEW.md` statement that the public `drmPciBusInfo` layout
had no padding was wrong. It is 6 bytes: a 2-byte domain plus three 1-byte
fields (5 value bytes) and one tail-padding byte at offset 5. The new
fieldwise implementations in `drm_darwin.c:728-739` and `nmx/identity.c:24-35`
are correct. The regression deliberately fills two structs with different
padding and requires both equality helpers to return true
(`tests/test_drm_darwin.c:404-409`). This correction does not reopen a
finding; the parent fix addresses it.

## Remaining must-fix scope

The three discovery findings are closed. The following native integration
limitations remain explicitly unresolved and are still blocking any claim of
a live XNU transport:

* `xnu_memory.cpp:35-49` still requires a retained, authenticated owner task;
  no glue establishes that ownership, and a raw user task integer must never
  reach `createMappingInTask()`.
* `xnu_memory.cpp:72-79` still documents missing task-death cleanup. The
  native close/death path must call `gx_revoke_owner_maps()`, retry failed
  unmaps, and drain before device teardown.
* `gx_ioctl.c:23-31` still relies on unimplemented per-client lifetime and
  close/copyout serialization. The owner must remain alive through copyout;
  failed copyout rollback must complete before releasing that owner.
* `gx_device_destroy()` still requires externally enforced quiescence. The
  native teardown path must stop new calls and drain files/maps before calling
  it.

These are documented glue requirements, not evidence that the CPU GEM
reference transitions or the newly fixed discovery code remain defective.
