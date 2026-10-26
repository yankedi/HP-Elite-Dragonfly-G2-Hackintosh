# NMDRM Darwin libdrm subset

This directory contains the M2 CPU-side libdrm boundary for the fixed GA40
NMDRM ABI.  It exports the existing public libdrm types and the small API
surface used by the current ANV discovery path:

- `drmGetVersion` / `drmFreeVersion`;
- `drmGetDevices2`, `drmGetDevice2`, `drmGetDevice`;
- `drmFreeDevice`, `drmFreeDevices`, `drmDevicesEqual`;
- `drmGetNodeTypeFromFd`, `drmGetCap`, and the low-level `drmIoctl` wrapper.

The production implementation scans `/dev/dri/cardN` and
`/dev/dri/renderD(128+N)`, opens each candidate, checks that it is a character
device, asks NMDRM for `VERSION` and the BSD `_IOR('d', 0x15, pciinfo)`
identity, and folds the primary/render pair by PCI domain:bus:device.function.
An fd is queried again for `drmGetDevice2`; a gone NMDRM provider therefore
returns `-ENXIO` rather than stale PCI metadata.  Unsupported NMDRM
capabilities retain the kernel's negative errno (`-EINVAL` for capabilities
other than `DRM_CAP_PRIME`).

The syscall and device-directory hooks in `drm-darwin-test.h` are test-only and
are not installed.  `tests/test_drm_darwin.c` uses a temporary directory and
an explicit CPU transport stub.  It does not open a GPU node or issue a real
ioctl.  The test also compiles the unmodified Mesa
`src/intel/dev/intel_kmd.c`; `nmdrm` is expected to produce
`INTEL_KMD_TYPE_INVALID`, while control strings `i915` and `xe` exercise the
two recognized Mesa personalities.

`make check` is a portable Linux-host compile/test.  `make sanitize` adds
AddressSanitizer and UndefinedBehaviorSanitizer.  A native Darwin build is
not claimed here: the Apple SDK was absent from the bounded initial search.
The Darwin conditional path is source-level only until a legally available
SDK is provided.

The `nmx/` helper is intentionally only a source-level PCI identity/personality
check for Intel (`0x8086`) and AMD (`0x1002`).  It does not fabricate IORegistry
topology, NMXGPU, Metal, execution, or memory capabilities.
