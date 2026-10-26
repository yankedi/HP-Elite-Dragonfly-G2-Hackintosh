/* SPDX-License-Identifier: MIT */
#ifndef GA41_GX_GEM_H
#define GA41_GX_GEM_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* A bounded port foundation. No DMA, device, GPU VA, i915 capability or fence
 * is advertised. All errors are negative errno. Public pointers are trusted
 * kernel/API buffers, NEVER raw user addresses. A cdev/user-client must copyin
 * and copyout separately and rollback the handle if copyout fails.
 *
 * A driver file must keep its gx_device alive until all operations/maps drain.
 * destroy requires externally quiesced callers; it returns EBUSY for live state.
 * Callbacks run under a sleepable device lock, never under an IRQ/spin lock.
 */
typedef uint64_t gx_file_id;
typedef uint64_t gx_map_id;
struct gx_device;
struct gx_ops {
    void (*lock)(void *);
    void (*unlock)(void *);
    void *(*alloc_meta)(void *, size_t); /* zeroed; no C++ objects */
    void (*free_meta)(void *, void *, size_t);
    int (*alloc_pages)(void *, uint64_t, void **); /* owned, entirely zeroed */
    void (*free_pages)(void *, void *, uint64_t);
    int (*map_pages)(void *, void *, uintptr_t task, uint64_t offset,
                     uint64_t length, int writable, void **map, uint64_t *address);
    int (*unmap_pages)(void *, void *, uint64_t); /* failure retains all refs */
};
struct gx_map_result { gx_map_id id; uint64_t address, length; };
struct gx_stats { uint64_t objects, bytes, files, maps; };

int gx_device_create(const struct gx_ops *, void *, struct gx_device **);
int gx_device_destroy(struct gx_device *);
int gx_open(struct gx_device *, gx_file_id *);
int gx_close(struct gx_device *, gx_file_id);
int gx_create(struct gx_device *, gx_file_id, uint64_t *size, uint32_t *handle);
int gx_handle_close(struct gx_device *, gx_file_id, uint32_t handle);
int gx_map(struct gx_device *, gx_file_id, uint32_t handle, uintptr_t task,
           uint64_t offset, uint64_t length, int writable, struct gx_map_result *);
/* Mappings survive close(handle) and close(file), as mmap mappings do on Linux.
 * owner is the original per-open token, not a user-asserted identity. */
int gx_unmap(struct gx_device *, gx_file_id owner, gx_map_id);
/* Task/client teardown helper: revoke all mappings for its trusted token.
 * On unmap failure, stop and retain the failed/rest mappings for retry. */
int gx_revoke_owner_maps(struct gx_device *, gx_file_id owner);
int gx_get_stats(struct gx_device *, struct gx_stats *);
/* Explicitly unimplemented hardware-facing contract: always -EOPNOTSUPP. */
int gx_gpu_bind(struct gx_device *, gx_file_id, uint32_t handle);
int gx_exec(struct gx_device *, gx_file_id);

#ifdef __cplusplus
}
#endif
#endif
