# GA42 DRM integration unit

## Delivered

- `b51fe5810215f9789b64f4c24b1dd5dcfaee108f` — `drmIoctl` retries
  `EINTR`/`EAGAIN`, translates the public DRM core request names
  `VERSION`/`GET_UNIQUE`/`GET_CAP` to the NMDRM BSD request numbers, and
  preserves nested user pointers. Unsupported i915/Xe/GEM requests are not
  reported as success.
- `c1d81d925e465bb2ecef0dc4d3943c8e4bee2bad` — real `drmGetBusid` and
  `drmFreeBusid` over NMDRM `GET_UNIQUE`, including bounded lengths and
  overflow failure.
- `2fffbd26553a4760c3e64b2e1511edb7d7a4f43f` and
  `1b3189939fee30ea76a621277ea7f5f0b379a30e` — CMake object-only compile of
  original Mesa `intel_device_info.c`, including
  `intel_get_device_info_from_fd`, using the pinned generated Mesa headers.
- `ed6b3b5adf958314e5c99d75df792f0d246397e7` — regression that unsupported
  `DRM_IOCTL_GEM_CLOSE` returns `-1/ENOTTY` rather than dummy success.
- `14ba6eebda46066a180ee4291373688c264a07fc` — compile-time assertions for
  every nested VERSION/UNIQUE pointer offset, not only aggregate struct size.

The pre-existing discovery guards remain truthful: the CPU transport reports
`drmGetVersion()->name == "nmdrm"`, and the unmodified Mesa
`intel_get_kmd_type()` returns `INTEL_KMD_TYPE_INVALID` for that name. The
control strings `i915` and `xe` remain test-only Mesa controls; no identity
rename or fake i915 claim was added.

## Verification

All commands were run with `python3 -B tools/run_logged.py`; stdout/stderr are
retained under `logs/`.

| Level | Result | Evidence |
|---|---|---|
| CPU transport | PASS | `drm-unsupported-ioctl-test-001`, `drm-busid-test-005`, `drm-direct-test-001`, `drm-wire-offset-test-001` |
| GA41 GEM CPU integration (`GA41_GEM_INTEGRATION`) | PASS | `drm-ga41-test-002`, `drm-sanitize-test-001`, `drm-direct-gem-test-001`, `drm-wire-offset-all-test-001` |
| ASan/UBSan full local CTest | 4/4 PASS | `drm-sanitize-all-test-002` |
| Original Mesa discovery compile | PASS; symbol `intel_get_device_info_from_fd` emitted | `drm-mesa-discovery-build-003`, `drm-mesa-discovery-symbols-003` |
| Native Darwin compile | NOT RUN | No Apple SDK/KDK is available in this offline host |

The injected tests use temporary directory entries and an explicit CPU syscall
table. They never open a real DRM node, issue a real ioctl, access a GPU, or
use SSH/device/remote services. Existing fd identity revalidation still
checks the live fd, path reopen, `st_rdev`, full PCI tuple, and a second live
fd query; the tests cover replacement/reuse, provider disappearance, invalid
PCI coordinates, nested pointer strings, transient interruption, and
hot-unplug `ENXIO`.

## Native contract and limitations

The Darwin wire contract is the fixed NMDRM BSD ABI: 64-byte VERSION, 16-byte
UNIQUE, 16-byte GET_CAP, and 16-byte PCI identity. `drmIoctl` translates only
the three implemented core requests. Nested pointer fields are passed to the
kernel unchanged for its copyin/copyout; no userspace pointer dereference is
used as a success shortcut. i915/Xe/GEM requests remain provider-owned and
must return their real provider error until a corresponding kernel contract
exists.

The original Mesa object is compile evidence only: it is not linked into ANV,
does not enumerate a Vulkan physical device, and does not prove a Darwin ICD,
native kext, GPU memory, submission, Metal, or hardware acceleration.
