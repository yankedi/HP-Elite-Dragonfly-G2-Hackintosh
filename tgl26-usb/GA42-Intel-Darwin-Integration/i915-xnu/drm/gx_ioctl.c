/* SPDX-License-Identifier: MIT */
#include "gx_ioctl.h"
#include <errno.h>
#include <drm.h>
#include <i915_drm.h>

/* Request numbers are BSD wire constants, independent of build host macros.
 * Exact sizes/directions required; Linux GEM_CLOSE must not be accepted. */
#define GX_BSD_CREATE UINT32_C(0xc010645b)
#define GX_BSD_CLOSE UINT32_C(0x80086409)
#define GX_BSD_GETPARAM UINT32_C(0xc0106446)
#define GX_BSD_GET_TILING UINT32_C(0xc0106462)
#define GX_BSD_GETCAP UINT32_C(0xc010640c)
#define GX_BSD_EXEC UINT32_C(0x80406469)
#define GX_BSD_EXEC_WR UINT32_C(0xc0406469)
_Static_assert(sizeof(struct drm_i915_gem_create) == 16, "LP64 create ABI");
_Static_assert(sizeof(struct drm_gem_close) == 8, "close ABI");
int gx_user_ioctl(struct gx_device *d, gx_file_id file, uint32_t cmd,
                  uint64_t user, const struct gx_copy_ops *ops, void *ctx) {
    if (!d || !ops || !ops->in || !ops->out) return -EINVAL;
    int live = gx_file_check(d, file, cmd == GX_BSD_CLOSE);
    if (live) return live;
    if (cmd == GX_BSD_EXEC || cmd == GX_BSD_EXEC_WR)
        return gx_exec_preflight(d, file, user, ops, ctx);
    if (cmd == GX_BSD_GETPARAM) {
        struct drm_i915_getparam a = {0};
        int ret = ops->in(ctx, user, &a, sizeof(a));
        if (ret) return ret;
        int32_t value = 0;
        if (a.param == I915_PARAM_CHIPSET_ID) {
            uint16_t vendor, device;
            ret = gx_device_get_pci_id(d, &vendor, &device);
            if (ret) return ret;
            if (vendor != 0x8086) return -ENODEV;
            value = device;
        } else if (a.param == I915_PARAM_CS_TIMESTAMP_FREQUENCY) {
            return -EOPNOTSUPP; /* needs genuine initialized GT clock state */
        } else {
            return -EINVAL; /* no invented topology/context/exec capabilities */
        }
        return ops->out(ctx, &value, (uint64_t)(uintptr_t)a.value, sizeof(value));
    }
    if (cmd == GX_BSD_GET_TILING) {
        struct drm_i915_gem_get_tiling a = {0}; uint64_t size = 0;
        int ret = ops->in(ctx, user, &a, sizeof(a));
        if (ret) return ret;
        ret = gx_object_size(d, file, a.handle, &size);
        if (ret) return ret;
        /* Existing BOs have CPU-only linear backing; no SET_TILING exists. */
        a.tiling_mode = I915_TILING_NONE;
        a.swizzle_mode = a.phys_swizzle_mode = I915_BIT_6_SWIZZLE_NONE;
        return ops->out(ctx, &a, user, sizeof(a));
    }
    if (cmd == GX_BSD_GETCAP) {
        struct drm_get_cap a = {0};
        int ret = ops->in(ctx, user, &a, sizeof(a));
        if (ret) return ret;
        /* Explicitly maintained unsupported capabilities, never fake handles
         * or immediately signaled GPU fences. Unknown cap IDs are invalid. */
        switch (a.capability) {
        case DRM_CAP_DUMB_BUFFER:
        case DRM_CAP_PRIME:
        case DRM_CAP_SYNCOBJ:
        case DRM_CAP_SYNCOBJ_TIMELINE:
            a.value = 0; break;
        default: return -EINVAL;
        }
        return ops->out(ctx, &a, user, sizeof(a));
    }
    if (cmd == GX_BSD_CREATE) {
        struct drm_i915_gem_create a = {0};
        int ret = ops->in(ctx, user, &a, sizeof(a));
        if (ret) return ret;
        if (a.pad) return -EINVAL;
        /* Input handle is output-only, as in the upstream create ioctl. */
        uint64_t size = a.size; uint32_t handle = 0;
        ret = gx_create(d, file, &size, &handle);
        if (ret) return ret;
        a.size = size; a.handle = handle; a.pad = 0;
        ret = ops->out(ctx, &a, user, sizeof(a));
        if (ret) {
            /* Per-client glue must keep owner alive across this operation.
             * Concurrent close is safe: either close owns cleanup or we do. */
            (void)gx_handle_close(d, file, handle);
        }
        return ret;
    }
    if (cmd == GX_BSD_CLOSE) {
        struct drm_gem_close a = {0};
        int ret = ops->in(ctx, user, &a, sizeof(a));
        if (ret) return ret;
        if (a.pad) return -EINVAL;
        return gx_handle_close(d, file, a.handle);
    }
    return -ENOTTY; /* Query/VM/exec/sync/mmap are explicitly NOT advertised. */
}
