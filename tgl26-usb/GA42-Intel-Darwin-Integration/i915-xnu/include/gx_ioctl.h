/* SPDX-License-Identifier: MIT */
#ifndef GA41_GX_IOCTL_H
#define GA41_GX_IOCTL_H
#include "gx_gem.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Standalone copy boundary: user is an opaque address, never dereferenced by
 * the dispatcher. Native glue must provide real XNU copyin/copyout and bind
 * owner to an open file/client. Not registered as a live cdev ioctl handler.
 * Returns negative errno. XNU glue must convert to positive cdev errno.
 */
struct gx_copy_ops {
    int (*in)(void *, uint64_t user, void *kernel, size_t);
    int (*out)(void *, const void *kernel, uint64_t user, size_t);
};
int gx_user_ioctl(struct gx_device *, gx_file_id owner, uint32_t darwin_request,
                  uint64_t user, const struct gx_copy_ops *, void *copy_context);
/* Bounded softpin ABI preflight; valid input still returns EOPNOTSUPP.
 * Caller must hold the per-client gate. No GPU resource or completion. */
int gx_exec_preflight(struct gx_device *, gx_file_id owner, uint64_t user,
                      const struct gx_copy_ops *, void *copy_context);
#ifdef __cplusplus
}
#endif
#endif
