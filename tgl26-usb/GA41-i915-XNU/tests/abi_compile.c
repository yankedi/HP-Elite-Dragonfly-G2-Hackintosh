/* SPDX-License-Identifier: MIT
 * Compile the same declarations with Linux and real Darwin kernel headers.
 * No main, no devices, no runtime query constants or hardware data.
 */
#include <stddef.h>
#include <drm.h>
#include <i915_drm.h>
_Static_assert(sizeof(void *) == 8, "LP64 only");
_Static_assert(sizeof(struct drm_i915_gem_create) == 16, "create");
_Static_assert(offsetof(struct drm_i915_gem_create, handle) == 8, "handle offset");
_Static_assert(sizeof(struct drm_gem_close) == 8, "close");
_Static_assert(sizeof(struct drm_i915_query_item) == 24, "query item");
_Static_assert(offsetof(struct drm_i915_query_item, data_ptr) == 16, "user ptr");
_Static_assert(sizeof(struct drm_i915_gem_execbuffer2) == 64, "exec");
_Static_assert(DRM_IOCTL_VERSION == 0xc0406400UL, "version both");
_Static_assert(DRM_IOCTL_I915_GEM_CREATE == 0xc010645bUL, "create both");
#if defined(__APPLE__)
_Static_assert(DRM_IOCTL_GEM_CLOSE == 0x80086409UL, "Darwin input direction");
_Static_assert(DRM_IOCTL_I915_GEM_EXECBUFFER2 == 0x80406469UL, "Darwin exec direction");
_Static_assert(DRM_IOCTL_I915_GEM_GET_APERTURE == 0x40106463UL, "Darwin output direction");
#elif defined(__linux__)
_Static_assert(DRM_IOCTL_GEM_CLOSE == 0x40086409UL, "Linux input direction");
_Static_assert(DRM_IOCTL_I915_GEM_EXECBUFFER2 == 0x40406469UL, "Linux exec direction");
_Static_assert(DRM_IOCTL_I915_GEM_GET_APERTURE == 0x80106463UL, "Linux output direction");
#else
#error unsupported ABI for this probe
#endif
const unsigned long ga41_abi_commands[] = {
    DRM_IOCTL_VERSION, DRM_IOCTL_I915_GEM_CREATE, DRM_IOCTL_GEM_CLOSE,
    DRM_IOCTL_I915_GEM_EXECBUFFER2, DRM_IOCTL_I915_GEM_GET_APERTURE
};
