/* SPDX-License-Identifier: MIT */
#ifndef GA41_GX_XNU_H
#define GA41_GX_XNU_H
#include "gx_gem.h"
#ifdef __cplusplus
extern "C" {
#endif
int gx_xnu_create(struct gx_device **out, void **context);
/* Externally quiesced driver only; EBUSY preserves d/context for retry. */
int gx_xnu_destroy(struct gx_device *, void *context);
/* Unregistered explicit user-copy boundary, NOT a d_ioctl entry point. */
int gx_xnu_user_ioctl(struct gx_device *, gx_file_id, uint32_t command, uint64_t address);
#ifdef __cplusplus
}
#endif
#endif
