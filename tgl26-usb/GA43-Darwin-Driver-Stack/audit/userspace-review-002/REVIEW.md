# Userspace review 002 — ANV/Darwin and NullMoth isolation

## Scope and provenance

This is an independent, read-only review of GA42 at parent HEAD
`3e513b104b5b4b4e7098862903972989d2be6c68`.  The ANV source input is the
sealed GA40 Mesa tree at `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`; the
NullMoth input is the sealed GA40 tree at
`47f818b11cef59acb480210afdf9065fdd44e356`.  GA40, GA41, the target, and
 hardware were not changed or accessed.  No reviewed source/build tree was
 modified; this file is the only output added by this review.

## Findings

### F1 — HIGH: corrected vendor binding can mutate identity after Vulkan state is fixed

This is a verified state-consistency defect in the corrected NullMoth patch.

The patch adds `g_accelerator_bound`, but the explicit-binding branch still
does an unconditional `g_vendor = v` (`nullmoth/patches/0001-nvidia-only-accelerator-gate.patch:17-30`).
It therefore does not make the identity immutable after the first binding or
after Vulkan initialization.  The Vulkan state is one-shot: `g_state` is set
to `1` after creating `g_lib`, `g_inst`, `g_pdev`, and `g_dev`, and
`nvmtl_vk_init()` subsequently only calls `pthread_once`
(`GA40-NullMoth-Intel/sources/nullmoth/plugin/nvmtl_vk.c:683-705,1068-1077`).

Concrete counterexample:

1. Bind an Intel `NMXAccel` and initialize Vulkan.  The ICD and all global
   handles are Intel/ANV and `g_state == 1`.
2. A second `NVMTLDevice` bind calls `nvmtl_vk_set_accelerator()` with an
   NVIDIA `NVAccel`.  The patched function changes only `g_vendor` to
   `0x10de`; it does not recreate or replace the already-initialized Vulkan
   objects.
3. `NVMTLDevice` then compares `mine` with `live`, sees NVIDIA for both, and
   accepts the second device (`NVMTLDevice.m:557-583`).  Its later
   `nvmtl_vk_init()` returns success from the old Intel initialization, while
   vendor gates now observe NVIDIA.  This can enable NVIDIA-only VideoToolbox,
   NVVM, or SASS paths against an Intel Vulkan backend.

The reverse ordering is also inconsistent: an earlier system-wide
`nvmtl_vk_vendor()` discovery and NVK initialization can be followed by an
explicit Intel bind, changing the reported vendor while `g_lib`/instance/device
remain NVIDIA.  The existing policy test covers explicit Intel binding *before*
discovery (`nullmoth/tests/test_nvidia_only_gate.py:153-167`), but has no
post-`nvmtl_vk_init()` bind or second-binding case.

**Required fix:** make the selected vendor immutable once bound or once Vulkan
initialization begins.  A later binding must be accepted only when it matches
the existing identity; otherwise return failure before changing global state.
The check and state transition also need serialization if Metal/Vulkan setup
can run concurrently.

### F2 — MEDIUM: unknown vendor can fall through to the Vulkan loader

The corrected patch intentionally makes unknown identity fail closed by
returning `NULL` from both `nvmtl_vk_icd_json()` and `nvmtl_icd_lib_path()`
(`nullmoth/patches/0001-nvidia-only-accelerator-gate.patch:38-57`).  The
initialization path does not handle that sentinel, however:

* `g_lib = dlopen(NVMTL_ICD_LIB, ...)` is called unconditionally
  (`GA40-NullMoth-Intel/sources/nullmoth/plugin/nvmtl_vk.c:705`).  On Darwin,
  `dlopen(NULL, ...)` means the main program image rather than “refuse this
  backend”.
* If no entry point is found, the fallback then calls
  `setenv("VK_ICD_FILENAMES", NVMTL_ICD, 1)` and loads the general loader
  (`:727-733`).  `NVMTL_ICD` is also `NULL` for the unknown vendor.  If the
  process already supplied `VK_ICD_FILENAMES`, it is deliberately retained;
  otherwise the invalid `setenv` call is ignored and loader default discovery
  can select an ambient ICD.

Thus the unknown-binding policy is not end-to-end fail-closed for callers that
reach `nvmtl_vk_init()` without the `NVMTLDevice` constructor gate.  The
selected physical device is also simply the first device returned by the
loader (`:744-753`), with no vendor revalidation against the zero identity.

**Required fix:** before either `dlopen` or `setenv`, require a non-NULL,
authenticated ICD library and JSON path.  If vendor identity is zero, log and
return initialization failure; never invoke `dlopen(NULL, ...)`, retain an
ambient `VK_ICD_FILENAMES`, or fall back to unrestricted loader discovery.

## ANV and Darwin transport assessment

The three ANV patches are source-layer changes, not a complete Darwin ANV
backend:

* `0001-meson-intel-darwin.patch` adds an opt-in Darwin condition, a staged
  libdrm dependency, and Intel source-subtree selection.
* `0002-anv-darwin-syscalls.patch` routes the common `intel_ioctl()` helper to
  the public `drmIoctl()` only under `__APPLE__`; Linux remains unchanged.
* `0003-anv-darwin-exports.patch` supplies the three Mach-O loader-facing
  exports.

The central discovery limitation remains verified and should be reported as an
integration blocker, not disguised as a successful ANV build.  The Darwin
libdrm layer truthfully reports `"nmdrm"`
(`libdrm-darwin/drm_darwin.c:490-509`).  Unmodified Mesa
`intel_get_kmd_type()` accepts only `"i915"` and `"xe"`
(`GA40-NullMoth-Intel/sources/mesa/src/intel/dev/intel_kmd.c:31-51`), and
`intel_get_device_info_from_fd()` rejects `INTEL_KMD_TYPE_INVALID`
(`.../intel_device_info.c:1957-1961`).  The patches do not add an NMDRM KMD
personality or driver-specific i915/Xe ioctl implementation.  The transport
therefore cannot yet reach ANV device initialization without either a real
future KMD contract or a separately reviewed Mesa backend change.  This is a
transport/backend gap, not a reason to rename `nmdrm` to a false `i915`/`xe`
identity.

The retained source verification passed, but native acceptance remains
blocked: `logs/anv-055-verify-meson-order` is source-only, and
`logs/anv-065-darwin-build-attempt` records the absent Apple user SDK and
Darwin linker.  No Mach-O artifact, Vulkan enumeration, submission, or
hardware result exists.

## Darwin libdrm review

No additional memory-safety or device-pairing defect was verified in the
reviewed transport.  The implementation conservatively:

* asserts the wire sizes and nested pointer offsets
  (`libdrm-darwin/drm_darwin.c:84-117`);
* bounds string lengths before allocation and rejects returned lengths that
  exceed the supplied capacity (`:319-415,435-468`);
* retries only `EINTR`/`EAGAIN` (`:299-307`); and
* rechecks the live fd, path/rdev, full PCI tuple, and paired card/render
  identity (`:663-709,893-954`).

One compatibility caveat is worth retaining for a future ABI decision:
`drmGetCap()` returns negative errno from `call_ioctl()`
(`libdrm-darwin/drm_darwin.c:1001-1013`), whereas upstream libdrm's common
implementation returns the raw `drmIoctl()` result (`-1` with `errno` set) for
this legacy API.  Current Mesa callers only test nonzero, and the existing
CPU tests deliberately assert the GA42 negative-errno convention, so this is
not classified as a current ANV blocker; it should not be described as exact
upstream return-value compatibility without an explicit decision.

## Non-findings and evidence limits

The decode-service constructor is not classified as an isolation defect.  It
is deliberately a `VTDecoderXPCService` exception for processes that have no
Metal/Vulkan device, and it registers only after finding a real NVIDIA PCI
display-class device (`GA40-NullMoth-Intel/sources/nullmoth/plugin/NVMTLDevice.m:390-427`).
That service-specific behavior does not establish Intel rendering support and
should remain separately audited.

The retained corrected NullMoth harness passed at
`logs/nm-045-final-corrected-gate-after-report/`, including Intel ANV, AMD
RADV, NVIDIA NVK, explicit Intel-over-NVIDIA selection, unknown fail-closed
identity, and private-ICD override refusal.  It does not cover F1 or F2's
initialization/order cases.  The retained DRM CPU and sanitizer evidence is
summarized in `reports/DRM-INTEGRATION.md:30-47`; it never opens a real DRM
node or executes a real ioctl.

## Conclusion

The corrected policy preserves Intel/AMD NMXAccel ICD selection and does not
intentionally route Intel through NVIDIA-private compiler, SASS, or normal
VideoToolbox paths in the tested ordering.  It is not yet safe to call the
policy complete: F1 permits global backend identity to diverge from the
one-shot Vulkan objects, and F2 leaves an unknown identity with a loader
fallback.  ANV native build/runtime and NMDRM driver-specific execution remain
separate documented blockers.
