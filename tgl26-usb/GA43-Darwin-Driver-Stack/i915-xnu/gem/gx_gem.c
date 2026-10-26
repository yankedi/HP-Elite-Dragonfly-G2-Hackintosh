/* SPDX-License-Identifier: MIT
 * GA41 OS-native boundary for a narrow Intel create/publish path.
 * Not an implementation of the complete Linux DRM or i915 driver.
 */
#include "gx_gem.h"
#include <errno.h>
#include <stdbool.h>
#include <string.h>
#include <drm.h>
#include <i915_drm.h>

#define GX_FILES 32
#define GX_HANDLES 128
#define GX_MAPS 256
#define GX_LEASES 256
#define GX_PAGE UINT64_C(4096)
#define GX_MAX_BO (UINT64_C(64) << 20)
#define GX_MAX_TOTAL (UINT64_C(256) << 20)
#define GX_MAX_CLIENT (UINT64_C(16) << 20)
typedef __u64 u64;
typedef __u32 u32;
struct drm_device { struct gx_device *gx; };
struct drm_gem_object { u64 size; };
struct drm_i915_gem_object {
    struct drm_gem_object base;
    struct gx_device *dev;
    void *pages;
    uint64_t refs;
};
struct handle_entry { uint32_t id; struct drm_i915_gem_object *obj; uint64_t mmap_offset; };
struct drm_file {
    gx_file_id id;
    struct gx_device *dev;
    struct handle_entry handles[GX_HANDLES];
};
struct intel_memory_region { struct gx_device *dev; };
struct drm_i915_private { struct gx_device *gx; };
struct map_entry {
    gx_map_id id;
    gx_file_id owner;
    uint64_t length;
    void *mapping;
    struct drm_i915_gem_object *obj;
};
struct lease_entry {
    uint64_t id;
    gx_file_id owner;
    struct drm_i915_gem_object *obj;
};
struct gx_device {
    struct gx_ops ops;
    void *ctx;
    struct drm_device drm;
    struct drm_i915_private i915;
    struct intel_memory_region system;
    struct drm_file files[GX_FILES];
    struct map_entry maps[GX_MAPS];
    struct lease_entry leases[GX_LEASES];
    uint64_t next_lease;
    uint64_t next_mmap_offset;
    uint64_t next_file, next_map, next_handle;
    struct gx_stats stats;
    bool detached;
    uint16_t pci_vendor, pci_device;
};

/* The following types and hooks are a private, explicit subset port ABI.
 * They are NOT layout-compatible substitutes for kernel drm_file/i915 structs.
 * Only two upstream functions consume them; no other Linux object is linked. */
#define INTEL_MEMORY_SYSTEM 0
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
static struct drm_i915_private *to_i915(struct drm_device *dev) { return &dev->gx->i915; }
static struct intel_memory_region *intel_memory_region_by_type(struct drm_i915_private *i915, int type) {
    return type == INTEL_MEMORY_SYSTEM ? &i915->gx->system : NULL;
}
static void i915_gem_object_put(struct drm_i915_gem_object *obj) {
    if (--obj->refs) return;
    struct gx_device *d = obj->dev;
    d->ops.free_pages(d->ctx, obj->pages, obj->base.size);
    d->stats.objects--;
    d->stats.bytes -= obj->base.size;
    d->ops.free_meta(d->ctx, obj, sizeof(*obj));
}
static int drm_gem_handle_create(struct drm_file *file, struct drm_gem_object *base, u32 *out) {
    struct drm_i915_gem_object *obj = (struct drm_i915_gem_object *)base;
    struct gx_device *d = file->dev;
    if (d->next_handle > UINT32_MAX) return -ENOSPC;
    for (size_t i = 0; i < GX_HANDLES; i++) {
        if (file->handles[i].id) continue;
        file->handles[i].id = (uint32_t)d->next_handle++;
        file->handles[i].obj = obj;
        obj->refs++;
        *out = file->handles[i].id;
        return 0;
    }
    return -EMFILE;
}
static struct drm_i915_gem_object *__i915_gem_object_create_user(
    struct drm_i915_private *i915, u64 size, struct intel_memory_region **regions,
    unsigned int count) {
    struct gx_device *d = i915->gx;
    if (count != 1 || regions[0] != &d->system || !size) return ERR_PTR(-EINVAL);
    if (size > GX_MAX_BO) return ERR_PTR(-E2BIG);
    size = (size + GX_PAGE - 1) & ~(GX_PAGE - 1);
    if (size > GX_MAX_TOTAL - d->stats.bytes) return ERR_PTR(-ENOMEM);
    struct drm_i915_gem_object *obj = d->ops.alloc_meta(d->ctx, sizeof(*obj));
    if (!obj) return ERR_PTR(-ENOMEM);
    int ret = d->ops.alloc_pages(d->ctx, size, &obj->pages);
    if (ret) { d->ops.free_meta(d->ctx, obj, sizeof(*obj)); return ERR_PTR(ret); }
    obj->base.size = size; obj->refs = 1; obj->dev = d;
    d->stats.objects++; d->stats.bytes += size;
    return obj;
}
#include "upstream_create.inc"

static struct drm_file *file_find(struct gx_device *d, gx_file_id id) {
    if (!id) return NULL;
    for (size_t i = 0; i < GX_FILES; i++) if (d->files[i].id == id) return &d->files[i];
    return NULL;
}
static struct handle_entry *handle_find(struct drm_file *f, uint32_t id) {
    if (!id) return NULL;
    for (size_t i = 0; i < GX_HANDLES; i++) if (f->handles[i].id == id) return &f->handles[i];
    return NULL;
}
/* Count each still-owned BO once, including mappings whose handle was closed.
 * No pointer to a file-table slot is stored in a BO: closed slots can be reused
 * while an old owner token's map still keeps its allocation alive. */
static uint64_t owner_bytes(struct gx_device *d, struct drm_file *f) {
    uint64_t bytes = 0;
    for (size_t i = 0; i < GX_HANDLES; i++)
        if (f->handles[i].id) bytes += f->handles[i].obj->base.size;
    for (size_t i = 0; i < GX_MAPS; i++) {
        struct map_entry *m = &d->maps[i];
        if (!m->id || m->owner != f->id) continue;
        bool counted = false;
        for (size_t j = 0; j < GX_HANDLES; j++)
            if (f->handles[j].id && f->handles[j].obj == m->obj) counted = true;
        for (size_t j = 0; j < i; j++)
            if (d->maps[j].id && d->maps[j].owner == f->id && d->maps[j].obj == m->obj) counted = true;
        if (!counted) bytes += m->obj->base.size;
    }
    for (size_t i = 0; i < GX_LEASES; i++) {
        struct lease_entry *l = &d->leases[i];
        if (!l->id || l->owner != f->id) continue;
        bool counted = false;
        for (size_t j = 0; j < GX_HANDLES; j++)
            if (f->handles[j].id && f->handles[j].obj == l->obj) counted = true;
        for (size_t j = 0; j < GX_MAPS; j++)
            if (d->maps[j].id && d->maps[j].owner == f->id && d->maps[j].obj == l->obj) counted = true;
        for (size_t j = 0; j < i; j++)
            if (d->leases[j].id && d->leases[j].owner == f->id && d->leases[j].obj == l->obj) counted = true;
        if (!counted) bytes += l->obj->base.size;
    }
    return bytes;
}
int gx_device_create(const struct gx_ops *ops, void *ctx, struct gx_device **out) {
    if (!out) return -EINVAL;
    *out = NULL;
    if (!ops || !ops->lock || !ops->unlock || !ops->alloc_meta || !ops->free_meta ||
        !ops->alloc_pages || !ops->free_pages || !ops->map_pages || !ops->unmap_pages) return -EINVAL;
    struct gx_device *d = ops->alloc_meta(ctx, sizeof(*d));
    if (!d) return -ENOMEM;
    d->ops = *ops; d->ctx = ctx; d->drm.gx = d; d->i915.gx = d; d->system.dev = d;
    d->next_file = d->next_map = d->next_handle = 1;
    d->next_lease = 1;
    d->next_mmap_offset = UINT64_C(1) << 32;
    *out = d; return 0;
}
int gx_device_destroy(struct gx_device *d) {
    if (!d) return -EINVAL;
    d->ops.lock(d->ctx);
    bool busy = d->stats.objects || d->stats.files || d->stats.maps;
    d->ops.unlock(d->ctx);
    if (busy) return -EBUSY;
    struct gx_ops ops = d->ops; void *ctx = d->ctx;
    ops.free_meta(ctx, d, sizeof(*d)); return 0;
}
int gx_open(struct gx_device *d, gx_file_id *out) {
    if (!d || !out) return -EINVAL;
    *out = 0; d->ops.lock(d->ctx);
    if (d->detached) { d->ops.unlock(d->ctx); return -ENODEV; }
    int ret = -EMFILE;
    if (d->next_file != UINT64_MAX) for (size_t i = 0; i < GX_FILES; i++) {
        if (d->files[i].id) continue;
        d->files[i].id = d->next_file++; d->files[i].dev = d;
        *out = d->files[i].id; d->stats.files++; ret = 0; break;
    }
    d->ops.unlock(d->ctx); return ret;
}
int gx_close(struct gx_device *d, gx_file_id id) {
    if (!d) return -EINVAL;
    d->ops.lock(d->ctx); struct drm_file *f = file_find(d, id);
    if (!f) { d->ops.unlock(d->ctx); return -EBADF; }
    for (size_t i = 0; i < GX_HANDLES; i++) if (f->handles[i].id) {
        struct drm_i915_gem_object *obj = f->handles[i].obj;
        memset(&f->handles[i], 0, sizeof(f->handles[i])); i915_gem_object_put(obj);
    }
    memset(f, 0, sizeof(*f)); d->stats.files--; d->ops.unlock(d->ctx); return 0;
}
int gx_create(struct gx_device *d, gx_file_id id, uint64_t *size, uint32_t *handle) {
    if (!d || !size || !handle) return -EINVAL;
    *handle = 0; d->ops.lock(d->ctx); struct drm_file *f = file_find(d, id);
    if (d->detached) { d->ops.unlock(d->ctx); return -ENODEV; }
    if (!f) { d->ops.unlock(d->ctx); return -EBADF; }
    struct drm_i915_gem_create args = {.size = *size};
    if (*size && *size <= GX_MAX_BO) {
        uint64_t rounded = (*size + GX_PAGE - 1) & ~(GX_PAGE - 1);
        if (rounded > GX_MAX_CLIENT - owner_bytes(d, f)) {
            d->ops.unlock(d->ctx); return -EDQUOT;
        }
    }
    int ret = i915_gem_create_ioctl(&d->drm, &args, f);
    if (!ret) { *size = args.size; *handle = args.handle; }
    d->ops.unlock(d->ctx); return ret;
}
int gx_handle_close(struct gx_device *d, gx_file_id id, uint32_t handle) {
    if (!d) return -EINVAL;
    d->ops.lock(d->ctx); struct drm_file *f = file_find(d, id);
    struct handle_entry *h = f ? handle_find(f, handle) : NULL;
    int ret = !f ? -EBADF : !h ? -ENOENT : 0;
    if (h) { struct drm_i915_gem_object *obj = h->obj; memset(h, 0, sizeof(*h)); i915_gem_object_put(obj); }
    d->ops.unlock(d->ctx); return ret;
}
static int map_locked(struct gx_device *d, gx_file_id id, uint32_t handle, uintptr_t task,
           uint64_t offset, uint64_t length, int writable, struct gx_map_result *out) {
    if (!d || !out) return -EINVAL;
    memset(out, 0, sizeof(*out));
    if (!length || ((offset | length) & (GX_PAGE - 1)) || (writable != 0 && writable != 1)) return -EINVAL;
    struct drm_file *f = file_find(d, id);
    if (d->detached) return -ENODEV;
    struct handle_entry *h = f ? handle_find(f, handle) : NULL;
    int ret = !f ? -EBADF : !h ? -ENOENT : 0;
    if (ret) goto done;
    if (offset > h->obj->base.size || length > h->obj->base.size - offset) { ret = -EINVAL; goto done; }
    struct map_entry *m = NULL;
    for (size_t i = 0; i < GX_MAPS; i++) if (!d->maps[i].id) { m = &d->maps[i]; break; }
    if (!m || d->next_map == UINT64_MAX) { ret = -ENOSPC; goto done; }
    void *mapping = NULL; uint64_t address = 0;
    ret = d->ops.map_pages(d->ctx, h->obj->pages, task, offset, length, writable, &mapping, &address);
    if (ret) goto done;
    m->id = d->next_map++; m->owner = id; m->mapping = mapping; m->length = length; m->obj = h->obj;
    m->obj->refs++; d->stats.maps++;
    out->id = m->id; out->address = address; out->length = length;
done:
    return ret;
}
int gx_map(struct gx_device *d, gx_file_id id, uint32_t handle, uintptr_t task,
           uint64_t offset, uint64_t length, int writable, struct gx_map_result *out) {
    if (!d) return -EINVAL;
    d->ops.lock(d->ctx);
    int ret = map_locked(d, id, handle, task, offset, length, writable, out);
    d->ops.unlock(d->ctx); return ret;
}
int gx_mmap_offset(struct gx_device *d, gx_file_id owner, uint32_t handle, uint64_t *out) {
    if (!d || !out) return -EINVAL;
    *out = 0; d->ops.lock(d->ctx);
    struct drm_file *f = file_find(d, owner);
    struct handle_entry *h = f ? handle_find(f, handle) : NULL;
    int ret = d->detached ? -ENODEV : !f ? -EBADF : !h ? -ENOENT : 0;
    if (!ret && !h->mmap_offset) {
        /* Reserve a whole maximum-BO interval, never reuse cookies. Signed
         * off_t range is intentional for a future native fd mmap facade. */
        if (d->next_mmap_offset > INT64_MAX - GX_MAX_BO) ret = -ENOSPC;
        else { h->mmap_offset = d->next_mmap_offset; d->next_mmap_offset += GX_MAX_BO; }
    }
    if (!ret) *out = h->mmap_offset;
    d->ops.unlock(d->ctx); return ret;
}
int gx_map_offset(struct gx_device *d, gx_file_id owner, uint64_t offset, uintptr_t task,
                  uint64_t length, int writable, struct gx_map_result *out) {
    if (!d || !out) return -EINVAL;
    memset(out, 0, sizeof(*out));
    if (!offset || (offset & (GX_PAGE-1))) return -EINVAL;
    d->ops.lock(d->ctx);
    struct drm_file *f = file_find(d, owner);
    int ret = d->detached ? -ENODEV : !f ? -EBADF : -ENOENT;
    if (!d->detached && f) for (unsigned i = 0; i < GX_HANDLES; i++) {
        struct handle_entry *h = &f->handles[i];
        if (!h->id || !h->mmap_offset || offset < h->mmap_offset ||
            offset - h->mmap_offset >= h->obj->base.size) continue;
        ret = map_locked(d, owner, h->id, task, offset - h->mmap_offset, length, writable, out);
        break;
    }
    d->ops.unlock(d->ctx); return ret;
}
int gx_unmap(struct gx_device *d, gx_file_id owner, gx_map_id id) {
    if (!d) return -EINVAL;
    d->ops.lock(d->ctx); int ret = -ENOENT;
    for (size_t i = 0; i < GX_MAPS; i++) {
        struct map_entry *m = &d->maps[i];
        if (!id || m->id != id || m->owner != owner) continue;
        ret = d->ops.unmap_pages(d->ctx, m->mapping, m->length);
        if (!ret) { struct drm_i915_gem_object *obj = m->obj; memset(m, 0, sizeof(*m)); d->stats.maps--; i915_gem_object_put(obj); }
        break;
    }
    d->ops.unlock(d->ctx); return ret;
}
int gx_get_stats(struct gx_device *d, struct gx_stats *out) {
    if (!d || !out) return -EINVAL;
    d->ops.lock(d->ctx); *out = d->stats; d->ops.unlock(d->ctx); return 0;
}
int gx_device_detach(struct gx_device *d) {
    if (!d) return -EINVAL;
    d->ops.lock(d->ctx); d->detached = true; d->ops.unlock(d->ctx);
    return 0;
}
int gx_device_set_pci_id(struct gx_device *d, uint16_t vendor, uint16_t device) {
    if (!d || !vendor || vendor == UINT16_MAX || !device || device == UINT16_MAX) return -EINVAL;
    d->ops.lock(d->ctx);
    int ret = d->detached ? -ENODEV : (d->pci_vendor || d->stats.files) ? -EBUSY : 0;
    if (!ret) { d->pci_vendor = vendor; d->pci_device = device; }
    d->ops.unlock(d->ctx); return ret;
}
int gx_device_get_pci_id(struct gx_device *d, uint16_t *vendor, uint16_t *device) {
    if (!d || !vendor || !device) return -EINVAL;
    *vendor = *device = 0;
    d->ops.lock(d->ctx);
    int ret = (d->detached || !d->pci_vendor) ? -ENODEV : 0;
    if (!ret) { *vendor = d->pci_vendor; *device = d->pci_device; }
    d->ops.unlock(d->ctx); return ret;
}
int gx_object_size(struct gx_device *d, gx_file_id owner, uint32_t handle, uint64_t *out) {
    if (!d || !out) return -EINVAL;
    *out = 0; d->ops.lock(d->ctx);
    struct drm_file *f = file_find(d, owner);
    struct handle_entry *h = f ? handle_find(f, handle) : NULL;
    int ret = d->detached ? -ENODEV : !f ? -EBADF : !h ? -ENOENT : 0;
    if (!ret) *out = h->obj->base.size;
    d->ops.unlock(d->ctx); return ret;
}
int gx_file_check(struct gx_device *d, gx_file_id owner, int cleanup) {
    if (!d) return -EINVAL;
    d->ops.lock(d->ctx);
    int ret = (d->detached && !cleanup) ? -ENODEV : !file_find(d, owner) ? -EBADF : 0;
    d->ops.unlock(d->ctx); return ret;
}
int gx_revoke_owner_maps(struct gx_device *d, gx_file_id owner) {
    if (!d || !owner) return -EINVAL;
    d->ops.lock(d->ctx); int ret = 0;
    for (size_t i = 0; i < GX_MAPS; i++) {
        struct map_entry *m = &d->maps[i];
        if (!m->id || m->owner != owner) continue;
        ret = d->ops.unmap_pages(d->ctx, m->mapping, m->length);
        if (ret) break;
        struct drm_i915_gem_object *obj = m->obj;
        memset(m, 0, sizeof(*m)); d->stats.maps--; i915_gem_object_put(obj);
    }
    d->ops.unlock(d->ctx); return ret;
}
int gx_gpu_bind(struct gx_device *d, gx_file_id id, uint32_t handle) {
    (void)d; (void)id; (void)handle; return -EOPNOTSUPP;
}
int gx_exec(struct gx_device *d, gx_file_id id) { (void)d; (void)id; return -EOPNOTSUPP; }
void *gx_meta_alloc(struct gx_device *d, size_t size) {
    if (!d || !size) return NULL;
    d->ops.lock(d->ctx);
    void *p = d->ops.alloc_meta(d->ctx, size);
    d->ops.unlock(d->ctx);
    return p;
}
void gx_meta_free(struct gx_device *d, void *p, size_t size) {
    if (!d || !p) return;
    d->ops.lock(d->ctx); d->ops.free_meta(d->ctx, p, size); d->ops.unlock(d->ctx);
}
int gx_bo_lease_get(struct gx_device *d, gx_file_id owner, uint32_t handle, uint64_t *lease, uint64_t *size) {
    if (!d || !lease || !size) return -EINVAL;
    *lease = *size = 0;
    d->ops.lock(d->ctx);
    struct drm_file *f = file_find(d, owner);
    struct handle_entry *h = f ? handle_find(f, handle) : NULL;
    int ret = d->detached ? -ENODEV : !f ? -EBADF : !h ? -ENOENT : -ENOSPC;
    if (!d->detached && h && d->next_lease != UINT64_MAX) {
        for (unsigned i = 0; i < GX_LEASES; i++) {
            struct lease_entry *l = &d->leases[i];
            if (l->id) continue;
            l->id = d->next_lease++; l->owner = owner; l->obj = h->obj;
            l->obj->refs++;
            *lease = l->id; *size = l->obj->base.size; ret = 0;
            break;
        }
    }
    d->ops.unlock(d->ctx); return ret;
}
int gx_bo_lease_put(struct gx_device *d, gx_file_id owner, uint64_t lease) {
    if (!d || !owner || !lease) return -EINVAL;
    d->ops.lock(d->ctx); int ret = -ENOENT;
    for (unsigned i = 0; i < GX_LEASES; i++) {
        struct lease_entry *l = &d->leases[i];
        if (l->id != lease || l->owner != owner) continue;
        struct drm_i915_gem_object *obj = l->obj;
        memset(l, 0, sizeof(*l)); i915_gem_object_put(obj); ret = 0; break;
    }
    d->ops.unlock(d->ctx); return ret;
}
