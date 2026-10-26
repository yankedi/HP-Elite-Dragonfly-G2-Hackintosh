/* SPDX-License-Identifier: MIT */
#include "gx_ioctl.h"
#include <errno.h>
#include <drm.h>
#include <i915_drm.h>

/* Request numbers are BSD wire constants, independent of build host macros.
 * Exact sizes/directions required; Linux GEM_CLOSE must not be accepted. */
#define GX_BSD_CREATE UINT32_C(0xc010645b)
#define GX_BSD_CLOSE UINT32_C(0x80086409)
_Static_assert(sizeof(struct drm_i915_gem_create) == 16, "LP64 create ABI");
_Static_assert(sizeof(struct drm_gem_close) == 8, "close ABI");
int gx_user_ioctl(struct gx_device *d, gx_file_id file, uint32_t cmd,
                  uint64_t user, const struct gx_copy_ops *ops, void *ctx) {
    if (!d || !ops || !ops->in || !ops->out) return -EINVAL;
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
