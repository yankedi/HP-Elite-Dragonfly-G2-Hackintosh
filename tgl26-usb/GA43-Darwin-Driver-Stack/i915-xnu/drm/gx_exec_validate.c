/* SPDX-License-Identifier: MIT
 * Bounded preflight only. No VM, binding, residency or submit is performed.
 * Every structurally valid request still returns EOPNOTSUPP. A future submit
 * MUST add retained BO/VM/context snapshots and real hardware completion. */
#include "gx_ioctl.h"
#include <errno.h>
#include <drm.h>
#include <i915_drm.h>

#define LIMIT 16U
#define VA_LIMIT (UINT64_C(1) << 48)
_Static_assert(sizeof(struct drm_i915_gem_exec_object2) == 56, "exec object ABI");
_Static_assert(offsetof(struct drm_i915_gem_exec_object2, offset) == 24, "softpin ABI");
_Static_assert(sizeof(struct drm_i915_gem_execbuffer2) == 64, "exec ABI");
_Static_assert(sizeof(struct drm_i915_gem_exec_fence) == 8, "fence ABI");

static int user_range(uint64_t ptr, uint64_t bytes) {
    return ptr && bytes <= UINT64_MAX - ptr;
}
static int gpu_va(uint64_t raw, uint64_t *va) {
    /* i915 UAPI accepts sign-extended canonical 48-bit addresses. These are
     * GPU virtual addresses, never host task pointers or DMA addresses. */
    if (raw >= (UINT64_C(1) << 47) && raw < UINT64_C(0xffff800000000000)) return -EINVAL;
    *va = raw & (VA_LIMIT - 1); return 0;
}
int gx_exec_preflight(struct gx_device *d, gx_file_id owner, uint64_t user,
                      const struct gx_copy_ops *copy, void *ctx) {
    struct drm_i915_gem_execbuffer2 a = {0};
    int ret = copy->in(ctx, user, &a, sizeof(a));
    if (ret) return ret;
    if (!a.buffer_count || a.DR1 || a.DR4 || a.rsvd1 >> 32 ||
        a.flags & (uint64_t)__I915_EXEC_UNKNOWN_FLAGS ||
        ((a.batch_start_offset | a.batch_len) & 7)) return -EINVAL;
    if (a.buffer_count > LIMIT || a.num_cliprects > LIMIT) return -E2BIG;
    const uint64_t allowed = I915_EXEC_RING_MASK | I915_EXEC_NO_RELOC |
        I915_EXEC_HANDLE_LUT | I915_EXEC_BATCH_FIRST | I915_EXEC_FENCE_ARRAY;
    if (a.flags & ~allowed || a.rsvd2 || !(a.flags & I915_EXEC_NO_RELOC)) return -EOPNOTSUPP;
    if ((a.flags & I915_EXEC_RING_MASK) > I915_EXEC_RENDER) return -EOPNOTSUPP;
    if (!(a.flags & I915_EXEC_FENCE_ARRAY) && (a.num_cliprects || a.cliprects_ptr)) return -EINVAL;
    uint64_t bytes = (uint64_t)a.buffer_count * sizeof(struct drm_i915_gem_exec_object2);
    if (!user_range(a.buffers_ptr, bytes)) return -EFAULT;
    /* One bounded snapshot. Never re-read user object/fence entries to compare
     * ranges; concurrent userspace mutation cannot change a checked entry. */
    struct drm_i915_gem_exec_object2 objects[LIMIT];
    uint64_t sizes[LIMIT], offsets[LIMIT];
    ret = copy->in(ctx, a.buffers_ptr, objects, (size_t)bytes);
    if (ret) return ret;
    for (uint32_t i = 0; i < a.buffer_count; i++) {
        struct drm_i915_gem_exec_object2 *o = &objects[i];
        if (o->flags & (uint64_t)__EXEC_OBJECT_UNKNOWN_FLAGS || o->rsvd2) return -EINVAL;
        const uint64_t object_flags = EXEC_OBJECT_PINNED | EXEC_OBJECT_SUPPORTS_48B_ADDRESS | EXEC_OBJECT_WRITE;
        if (o->flags & ~object_flags || !(o->flags & EXEC_OBJECT_PINNED) ||
            o->relocation_count || o->relocs_ptr || o->rsvd1) return -EOPNOTSUPP;
        ret = gx_object_size(d, owner, o->handle, &sizes[i]);
        if (ret) return ret;
        ret = gpu_va(o->offset, &offsets[i]);
        if (ret || (offsets[i] & 4095) || sizes[i] > VA_LIMIT - offsets[i]) return -EINVAL;
        if (o->alignment && ((o->alignment & (o->alignment - 1)) ||
            o->alignment < 4096 || offsets[i] % o->alignment)) return -EINVAL;
        if (!(o->flags & EXEC_OBJECT_SUPPORTS_48B_ADDRESS) &&
            offsets[i] + sizes[i] > (UINT64_C(1) << 32)) return -EINVAL;
        for (uint32_t j = 0; j < i; j++) {
            if (objects[j].handle == o->handle ||
                (offsets[i] < offsets[j] + sizes[j] && offsets[j] < offsets[i] + sizes[i])) return -EINVAL;
        }
    }
    uint32_t batch = (a.flags & I915_EXEC_BATCH_FIRST) ? 0 : a.buffer_count - 1;
    if (a.batch_start_offset >= sizes[batch] || a.batch_len > sizes[batch] - a.batch_start_offset) return -EINVAL;
    if (a.flags & I915_EXEC_FENCE_ARRAY) {
        struct drm_i915_gem_exec_fence fences[LIMIT];
        bytes = (uint64_t)a.num_cliprects * sizeof(fences[0]);
        if (bytes) {
            if (!user_range(a.cliprects_ptr, bytes)) return -EFAULT;
            ret = copy->in(ctx, a.cliprects_ptr, fences, (size_t)bytes);
            if (ret) return ret;
        }
        for (uint32_t i = 0; i < a.num_cliprects; i++) {
            if (!fences[i].handle || !fences[i].flags ||
                fences[i].flags & (uint32_t)__I915_EXEC_FENCE_UNKNOWN_FLAGS) return -EINVAL;
        }
    }
    /* No CPU-signaled fence, sync-file fd, context or GPU binding is produced. */
    return -EOPNOTSUPP;
}
