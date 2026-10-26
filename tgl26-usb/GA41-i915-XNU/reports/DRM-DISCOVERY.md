# DRM discovery / M2 result

## Status

`implemented_cpu_tested`, **not Darwin-native-tested** and **not hardware-
tested**.

Later GA41 work retrieved the public **kernel-header** MacKernelSDK source kit;
four GEM/XNU units compile to Mach-O with it (`XNU-COMPILE.md`). This is not the
missing complete Darwin **userspace SDK**, and does not retroactively turn this
libdrm userspace subset into a Darwin-compiled or tested library.

The new `libdrm-darwin/` subset is a real production-shaped Darwin C path,
compiled and sanitizer-tested on the Linux development host.  The Apple SDK
was not present: a cross-target syntax probe stopped because
`sys/ioccom.h` was unavailable.  No claim is made that the source has been
compiled against the SDK or loaded on macOS.

## Implemented boundary

The code uses standard libdrm public types from the pinned local 2.4.131
headers.  It scans only the NMDRM node forms `/dev/dri/cardN` and
`/dev/dri/renderD(128+N)`, checks `fstat()` for a character device and the
expected NMDRM minor, then performs the exact NMDRM BSD ABI calls:

| Operation | NMDRM request on Darwin | Result |
|---|---:|---|
| VERSION | `0xc0406400` | two-pass version/name/date/description |
| GET_UNIQUE | `0xc0106401` | ABI documented; not needed to form `drmDevice` |
| GET_CAP | `0xc010640c` | PRIME returns 0; other capabilities retain `-EINVAL` |
| GET_PCIINFO | `0x40106415` | domain, bus, device, function and PCI IDs |

`drmGetDevices2()` opens candidates through the production syscall boundary,
rejects any driver name other than `nmdrm`, validates PCI identity, and folds
the primary/render pair by domain:bus:device.function.  `drmGetDevice2()`
queries the supplied fd and checks its path/node identity; if a provider has
gone away the NMDRM ioctl failure is returned as `-ENXIO`, rather than
reusing stale identity.  Allocation/freeing covers all node and PCI info
members of the public `drmDevice` type.

The two-pass version helper starts with zero-length buffers (matching NMDRM's
length semantics), allocates `reported_length + 1`, and supplies a trailing
NUL in user space because NMDRM copies string bytes but not a NUL terminator.
Returned lengths are checked against the allocated capacities and a bounded
maximum.

## NMX boundary

`nmx/identity.c` provides only source-level PCI identity equality and vendor
personality (`0x8086` Intel, `0x1002` AMD).  It does not claim an IORegistry
topology, an `NMXGPU` implementation, Metal, GEM, execution, or memory
capability.  This keeps the absent GA40 NMXGPU/NMXAccel implementation an
explicit blocker rather than fabricating one.

## Evidence

- `logs/drm-source.txt`: pinned source/header origins and hashes, plus SDK
  probe failure.
- `logs/drm-build.txt`: Makefile, CMake, sanitizer and Mesa integration
  results.
- `libdrm-darwin/README.md`: API and production/test boundary.
- `libdrm-darwin/PROVENANCE.md`: fixed inputs and license boundary.
- `GA40-NullMoth-Intel/drm/NMDRM-AUDIT.md`: read-only source audit of the
  four NMDRM ioctls and lifetime behavior.

The test executable uses a temporary regular-file directory plus injected
`open`/`fstat`/`ioctl`/path callbacks.  It never opens `/dev/dri`, sends a real
ioctl, accesses MMIO, starts a VM, loads a kext, or touches target hardware.
