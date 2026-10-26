/* SPDX-License-Identifier: MIT
 * Native host-side VM/context ownership, not hardware PPGTT initialization.
 */
#include "gx_vm.h"
#include <errno.h>
#include <string.h>
#include <drm.h>
#include <i915_drm.h>

#define VM_LIMIT 16
#define CTX_LIMIT 32
#define BIND_LIMIT 64
#define REQUEST_LIMIT 32
#define PAGE UINT64_C(4096)
#define VA_END (UINT64_C(1) << 48)
struct gx_binding { uint64_t va, length, lease; uint32_t requests; };
struct i915_address_space {
    struct gx_vm_state *state;
    uint32_t refs;
    struct gx_binding bindings[BIND_LIMIT];
};
struct vm_name { uint32_t id; struct i915_address_space *vm; };
struct context_name { uint32_t id; struct i915_address_space *vm; };
struct request_plan {
    uint64_t id, batch_va, length;
    uint32_t context, binding;
    int error;
    struct i915_address_space *vm;
};
struct gx_vm_state {
    struct gx_vm_ops ops;
    void *ctx;
    uint64_t next_vm, next_context;
    struct vm_name names[VM_LIMIT];
    struct context_name contexts[CTX_LIMIT];
    struct request_plan requests[REQUEST_LIMIT];
    uint64_t next_request;
    uint32_t vm_objects;
};
/* Narrow source-port hooks. xa_erase is an owned ID table operation under
 * the caller's client lock, NOT an emulation of Linux RCU/xarray generally. */
struct drm_device { int unused; };
struct drm_i915_file_private { struct gx_vm_state vm_xa; };
struct drm_file { struct drm_i915_file_private *driver_priv; };
static struct i915_address_space *xa_erase(struct gx_vm_state *s, uint32_t id)
{
    for (unsigned i = 0; id && i < VM_LIMIT; i++) {
        if (s->names[i].id != id) continue;
        struct i915_address_space *vm = s->names[i].vm;
        memset(&s->names[i], 0, sizeof(s->names[i]));
        return vm;
    }
    return NULL;
}
static void i915_vm_put(struct i915_address_space *vm)
{
    if (--vm->refs) return;
    struct gx_vm_state *s = vm->state;
    for (unsigned i = 0; i < BIND_LIMIT; i++)
        if (vm->bindings[i].lease) s->ops.put_bo(s->ctx, vm->bindings[i].lease);
    s->vm_objects--;
    s->ops.free(s->ctx, vm, sizeof(*vm));
}
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
#endif
#include "upstream_vm_destroy.inc"
#if defined(__clang__)
#pragma clang diagnostic pop
#endif

static struct i915_address_space *find_vm(struct gx_vm_state *s, uint32_t id)
{
    for (unsigned i = 0; id && i < VM_LIMIT; i++)
        if (s->names[i].id == id) return s->names[i].vm;
    return NULL;
}
int gx_vm_state_create(const struct gx_vm_ops *ops, void *ctx, struct gx_vm_state **out)
{
    if (!out) return -EINVAL;
    *out = NULL;
    if (!ops || !ops->alloc || !ops->free || !ops->get_bo || !ops->put_bo || !ops->admit) return -EINVAL;
    int admitted = ops->admit(ctx);
    if (admitted) return admitted;
    /* Allocate the enclosing private type, never cast between unrelated layouts. */
    struct drm_i915_file_private *f = ops->alloc(ctx, sizeof(*f));
    if (!f) return -ENOMEM;
    f->vm_xa.ops = *ops; f->vm_xa.ctx = ctx;
    f->vm_xa.next_vm = f->vm_xa.next_context = 1;
    f->vm_xa.next_request = 1;
    *out = &f->vm_xa;
    return 0;
}
int gx_vm_plan_create(struct gx_vm_state *s, uint32_t *out)
{
    if (!s || !out) return -EINVAL;
    *out = 0;
    int admitted = s->ops.admit(s->ctx);
    if (admitted) return admitted;
    if (s->next_vm > UINT32_MAX || s->vm_objects >= VM_LIMIT) return -ENOSPC;
    unsigned i;
    for (i = 0; i < VM_LIMIT && s->names[i].id; i++) {}
    if (i == VM_LIMIT) return -ENOSPC;
    struct i915_address_space *vm = s->ops.alloc(s->ctx, sizeof(*vm));
    if (!vm) return -ENOMEM;
    vm->state = s; vm->refs = 1; s->vm_objects++;
    s->names[i].id = (uint32_t)s->next_vm++; s->names[i].vm = vm;
    *out = s->names[i].id;
    return 0;
}
int gx_vm_plan_destroy(struct gx_vm_state *s, uint32_t id, uint32_t flags, uint64_t extensions)
{
    if (!s) return -EINVAL;
    struct drm_file f = { .driver_priv = (struct drm_i915_file_private *)s };
    struct drm_i915_gem_vm_control args = { .vm_id = id, .flags = flags, .extensions = extensions };
    return i915_gem_vm_destroy_ioctl(NULL, &args, &f);
}
int gx_context_plan_create(struct gx_vm_state *s, uint32_t id, uint32_t *out)
{
    if (!s || !out) return -EINVAL;
    *out = 0;
    int admitted = s->ops.admit(s->ctx);
    if (admitted) return admitted;
    struct i915_address_space *vm = find_vm(s, id);
    if (!vm) return -ENOENT;
    if (s->next_context > UINT32_MAX) return -ENOSPC;
    for (unsigned i = 0; i < CTX_LIMIT; i++) {
        if (s->contexts[i].id) continue;
        vm->refs++; s->contexts[i].vm = vm;
        *out = s->contexts[i].id = (uint32_t)s->next_context++;
        return 0;
    }
    return -ENOSPC;
}
int gx_context_plan_destroy(struct gx_vm_state *s, uint32_t id)
{
    if (!s) return -EINVAL;
    for (unsigned i = 0; id && i < CTX_LIMIT; i++) {
        if (s->contexts[i].id != id) continue;
        struct i915_address_space *vm = s->contexts[i].vm;
        for (unsigned j = 0; j < REQUEST_LIMIT; j++)
            if (s->requests[j].id && s->requests[j].context == id && !s->requests[j].error)
                s->requests[j].error = -ECANCELED;
        memset(&s->contexts[i], 0, sizeof(s->contexts[i]));
        i915_vm_put(vm);
        return 0;
    }
    return -ENOENT;
}
int gx_vm_plan_bind(struct gx_vm_state *s, uint32_t id, uint32_t handle, uint64_t va, uint64_t len)
{
    if (!s || !len || ((va | len) & (PAGE - 1)) || va >= VA_END || len > VA_END - va) return -EINVAL;
    int admitted = s->ops.admit(s->ctx);
    if (admitted) return admitted;
    struct i915_address_space *vm = find_vm(s, id);
    if (!vm) return -ENOENT;
    unsigned slot = BIND_LIMIT;
    for (unsigned i = 0; i < BIND_LIMIT; i++) {
        struct gx_binding *b = &vm->bindings[i];
        if (!b->lease) { if (slot == BIND_LIMIT) slot = i; continue; }
        if (va < b->va + b->length && b->va < va + len) return -EEXIST;
    }
    if (slot == BIND_LIMIT) return -ENOSPC;
    uint64_t lease = 0, size = 0;
    int ret = s->ops.get_bo(s->ctx, handle, &lease, &size);
    if (ret) return ret;
    if (!lease || len > size) {
        if (lease) s->ops.put_bo(s->ctx, lease);
        return -EINVAL;
    }
    vm->bindings[slot] = (struct gx_binding){.va = va, .length = len, .lease = lease};
    return 0;
}
int gx_vm_plan_unbind(struct gx_vm_state *s, uint32_t id, uint64_t va)
{
    if (!s) return -EINVAL;
    struct i915_address_space *vm = find_vm(s, id);
    if (!vm) return -ENOENT;
    for (unsigned i = 0; i < BIND_LIMIT; i++) {
        struct gx_binding *b = &vm->bindings[i];
        if (!b->lease || b->va != va) continue;
        if (b->requests) return -EBUSY;
        s->ops.put_bo(s->ctx, b->lease);
        memset(b, 0, sizeof(*b));
        return 0;
    }
    return -ENOENT;
}
int gx_request_plan_prepare(struct gx_vm_state *s, uint32_t id, uint64_t va, uint64_t len, uint64_t *out)
{
    if (!out) return -EINVAL;
    *out = 0;
    if (!s || !len || ((va | len) & 7) || va >= VA_END || len > VA_END - va) return -EINVAL;
    int admitted = s->ops.admit(s->ctx);
    if (admitted) return admitted;
    for (unsigned i = 0; id && i < CTX_LIMIT; i++) {
        if (s->contexts[i].id != id) continue;
        struct i915_address_space *vm = s->contexts[i].vm;
        for (unsigned j = 0; j < BIND_LIMIT; j++) {
            struct gx_binding *b = &vm->bindings[j];
            if (b->lease && va >= b->va && va - b->va < b->length && len <= b->length - (va - b->va)) {
                if (s->next_request == UINT64_MAX) return -ENOSPC;
                for (unsigned k = 0; k < REQUEST_LIMIT; k++) {
                    if (s->requests[k].id) continue;
                    s->requests[k] = (struct request_plan){.id = s->next_request++,
                        .batch_va = va, .length = len, .context = id, .binding = j, .vm = vm};
                    vm->refs++; b->requests++;
                    *out = s->requests[k].id;
                    return 0; /* ownership snapshot only: not submitted */
                }
                return -ENOSPC;
            }
        }
        return -ENOENT;
    }
    return -ENOENT;
}
static struct request_plan *find_request(struct gx_vm_state *s, uint64_t id)
{
    for (unsigned i = 0; id && i < REQUEST_LIMIT; i++)
        if (s->requests[i].id == id) return &s->requests[i];
    return NULL;
}
int gx_request_plan_fail(struct gx_vm_state *s, uint64_t id, int error)
{
    if (!s || error >= 0 || error < -4095 || error == -EINPROGRESS) return -EINVAL;
    struct request_plan *r = find_request(s, id);
    if (!r) return -ENOENT;
    if (!r->error) r->error = error;
    return 0;
}
int gx_request_plan_status(struct gx_vm_state *s, uint64_t id)
{
    if (!s) return -EINVAL;
    struct request_plan *r = find_request(s, id);
    return !r ? -ENOENT : r->error ? r->error : -EINPROGRESS;
}
int gx_request_plan_release(struct gx_vm_state *s, uint64_t id)
{
    if (!s) return -EINVAL;
    struct request_plan *r = find_request(s, id);
    if (!r) return -ENOENT;
    struct i915_address_space *vm = r->vm;
    vm->bindings[r->binding].requests--;
    memset(r, 0, sizeof(*r));
    i915_vm_put(vm);
    return 0;
}
int gx_context_plan_submit(struct gx_vm_state *s, uint32_t id, uint64_t va, uint64_t len)
{
    uint64_t request = 0;
    int ret = gx_request_plan_prepare(s, id, va, len, &request);
    if (ret) return ret;
    /* Real hardware admission is absent. Preserve the failure, never publish
     * a success fence, and release all retained planning resources. */
    (void)gx_request_plan_fail(s, request, -EOPNOTSUPP);
    ret = gx_request_plan_status(s, request);
    (void)gx_request_plan_release(s, request);
    return ret;
}
int gx_vm_plan_counts(struct gx_vm_state *s, struct gx_vm_counts *out)
{
    if (!s || !out) return -EINVAL;
    memset(out, 0, sizeof(*out));
    out->objects = s->vm_objects;
    for (unsigned i = 0; i < VM_LIMIT; i++) if (s->names[i].id) out->names++;
    for (unsigned i = 0; i < CTX_LIMIT; i++) if (s->contexts[i].id) out->contexts++;
    for (unsigned i = 0; i < REQUEST_LIMIT; i++) if (s->requests[i].id) out->requests++;
    /* Each VM can appear under name and many contexts; count it only once. */
    struct i915_address_space *seen[VM_LIMIT];
    unsigned count = 0;
    for (unsigned i = 0; i < VM_LIMIT + CTX_LIMIT; i++) {
        struct i915_address_space *vm = i < VM_LIMIT ? s->names[i].vm : s->contexts[i-VM_LIMIT].vm;
        if (!vm) continue;
        unsigned j; for (j = 0; j < count && seen[j] != vm; j++) {}
        if (j < count) continue;
        /* Creation counts every live VM, including request-held orphans, so
         * count cannot exceed VM_LIMIT. Fail closed if that invariant ever
         * changes, rather than allowing a future table expansion to overflow. */
        if (count == VM_LIMIT) return -EOVERFLOW;
        seen[count++] = vm;
        for (j = 0; j < BIND_LIMIT; j++) if (vm->bindings[j].lease) out->bindings++;
    }
    /* Request-held orphan VMs can outlive both their name and context. */
    for (unsigned i = 0; i < REQUEST_LIMIT; i++) {
        struct i915_address_space *vm = s->requests[i].vm;
        if (!vm) continue;
        unsigned j; for (j = 0; j < count && seen[j] != vm; j++) {}
        if (j < count) continue;
        if (count == VM_LIMIT) return -EOVERFLOW;
        seen[count++] = vm;
        for (j = 0; j < BIND_LIMIT; j++) if (vm->bindings[j].lease) out->bindings++;
    }
    return 0;
}
void gx_vm_state_close(struct gx_vm_state *s)
{
    if (!s) return;
    for (unsigned i = 0; i < REQUEST_LIMIT; i++)
        if (s->requests[i].id) (void)gx_request_plan_release(s, s->requests[i].id);
    for (unsigned i = 0; i < CTX_LIMIT; i++)
        if (s->contexts[i].id) (void)gx_context_plan_destroy(s, s->contexts[i].id);
    for (unsigned i = 0; i < VM_LIMIT; i++)
        if (s->names[i].id) (void)gx_vm_plan_destroy(s, s->names[i].id, 0, 0);
    struct gx_vm_ops ops = s->ops; void *ctx = s->ctx;
    ops.free(ctx, (struct drm_i915_file_private *)s, sizeof(struct drm_i915_file_private));
}
