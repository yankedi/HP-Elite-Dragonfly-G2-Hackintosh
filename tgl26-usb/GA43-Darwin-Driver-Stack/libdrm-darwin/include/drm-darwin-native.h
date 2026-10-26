/* SPDX-License-Identifier: MIT */
#ifndef GA43_DRM_DARWIN_NATIVE_H
#define GA43_DRM_DARWIN_NATIVE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Explicit native IOConnect transport. A connection is NOT a POSIX fd and
 * cannot be passed to ordinary libdrm/mmap. No render-node identity is forged.
 * Returns 0 or negative errno. Open publishes only on success. The caller
 * serializes close with all users; IOServiceClose consumes the connection even
 * on a cleanup error. Kernel reaper owns any delayed mapping teardown.
 * The kernel authenticates the creating task and currently requires admin.
 */
int drmDarwinNativeOpen(uint32_t *connection);
int drmDarwinNativeIoctl(uint32_t connection, uint32_t bsd_request, void *argument);
int drmDarwinNativeMapOffset(uint32_t connection, uint64_t cookie, uint64_t length,
                            int writable, uint64_t *address, uint64_t *map_id);
int drmDarwinNativeUnmap(uint32_t connection, uint64_t map_id);
int drmDarwinNativeClose(uint32_t connection);
#ifdef __cplusplus
}
#endif
#endif
