/* SPDX-License-Identifier: MIT */
#include "gx_client.h"
#include <errno.h>
#include <string.h>

_Static_assert(sizeof(struct gx_cpu_map) == 40, "CPU map extension LP64");
_Static_assert(offsetof(struct gx_cpu_map, map_id) == 32, "map token ABI");
_Static_assert(sizeof(struct gx_cpu_unmap) == 16, "CPU unmap extension LP64");
_Static_assert(sizeof(struct gx_offset_map) == 40, "Darwin offset map LP64");

static void *plan_alloc(void *p, size_t n) {
    struct gx_client *c = p; return gx_meta_alloc(c->device, n);
}
static void plan_free(void *p, void *v, size_t n) {
    struct gx_client *c = p; gx_meta_free(c->device, v, n);
}
static int plan_get(void *p, uint32_t handle, uint64_t *lease, uint64_t *size) {
    struct gx_client *c = p; return gx_bo_lease_get(c->device, c->owner, handle, lease, size);
}
static void plan_put(void *p, uint64_t lease) {
    struct gx_client *c = p; (void)gx_bo_lease_put(c->device, c->owner, lease);
}
static int plan_admit(void *p) {
    struct gx_client *c = p; return gx_file_check(c->device, c->owner, 0);
}
static const struct gx_vm_ops vm_ops = {plan_alloc, plan_free, plan_get, plan_put, plan_admit};

int gx_client_init(struct gx_client *c, struct gx_device *d, uintptr_t task,
                   const struct gx_client_ops *ops, void *ctx) {
    if (!c || !d || !task || !ops || !ops->lock || !ops->unlock ||
        !ops->retain_task || !ops->release_task) return -EINVAL;
    if (c->initialized) return -EBUSY;
    int ret = ops->retain_task(ctx, task);
    if (ret) return ret;
    gx_file_id owner = 0;
    ret = gx_open(d, &owner);
    if (ret) { ops->release_task(ctx, task); return ret; }
    memset(c, 0, sizeof(*c));
    c->device = d; c->ops = *ops; c->context = ctx;
    c->task = task; c->owner = owner;
    ret = gx_vm_state_create(&vm_ops, c, &c->vm_plans);
    if (ret) {
        (void)gx_close(d, owner);
        ops->release_task(ctx, task);
        memset(c, 0, sizeof(*c));
        return ret;
    }
    c->initialized = c->task_held = 1;
    return 0;
}

int gx_client_ioctl(struct gx_client *c, uint32_t cmd, uint64_t user,
                    const struct gx_copy_ops *copy, void *ctx) {
    if (!c || !c->initialized || !copy || !copy->in || !copy->out) return -EINVAL;
    c->ops.lock(c->context);
    int ret = -EBADF;
    if (c->closing) goto done;
    if (cmd == GX_OFFSET_MAP) {
        struct gx_offset_map a = {0};
        ret = copy->in(ctx, user, &a, sizeof(a));
        if (ret) goto done;
        if (a.writable > 1 || a.reserved || a.address || a.map_id) { ret = -EINVAL; goto done; }
        struct gx_map_result m = {0};
        ret = gx_map_offset(c->device, c->owner, a.offset, c->task,
                             a.length, (int)a.writable, &m);
        if (ret) goto done;
        a.address = m.address; a.map_id = m.id;
        ret = copy->out(ctx, &a, user, sizeof(a));
        if (ret) (void)gx_unmap(c->device, c->owner, m.id);
    } else if (cmd == GX_CPU_MAP) {
        struct gx_cpu_map a = {0};
        ret = copy->in(ctx, user, &a, sizeof(a));
        if (ret) goto done;
        if (a.writable > 1 || a.address || a.map_id) { ret = -EINVAL; goto done; }
        struct gx_map_result m = {0};
        ret = gx_map(c->device, c->owner, a.handle, c->task, a.offset,
                     a.length, (int)a.writable, &m);
        if (ret) goto done;
        a.address = m.address; a.map_id = m.id;
        ret = copy->out(ctx, &a, user, sizeof(a));
        /* A failed unmap remains owned by this client; close retries it. */
        if (ret) (void)gx_unmap(c->device, c->owner, m.id);
    } else if (cmd == GX_CPU_UNMAP) {
        struct gx_cpu_unmap a = {0};
        ret = copy->in(ctx, user, &a, sizeof(a));
        if (!ret) ret = a.reserved ? -EINVAL : gx_unmap(c->device, c->owner, a.map_id);
    } else {
        /* Gate spans input, object publication, output and failure rollback. */
        ret = gx_user_ioctl(c->device, c->owner, cmd, user, copy, ctx);
    }
done:
    c->ops.unlock(c->context);
    return ret;
}

int gx_client_close(struct gx_client *c) {
    if (!c || !c->initialized) return -EINVAL;
    c->ops.lock(c->context);
    c->closing = 1;
    /* No submit ever enters hardware. Drop contexts before VM names; retained
     * BO leases drain before handles and task, including death/detach paths. */
    if (c->vm_plans) { gx_vm_state_close(c->vm_plans); c->vm_plans = NULL; }
    int ret = 0;
    if (!c->file_closed) {
        ret = gx_close(c->device, c->owner);
        /* Owner tokens never repeat. A trusted alternate teardown may have
         * already consumed the file, but maps/task still belong to this
         * client and must reach revocation rather than retry EBADF forever. */
        if (ret && ret != -EBADF) goto done;
        c->file_closed = 1;
    }
    if (c->task_held) {
        ret = gx_revoke_owner_maps(c->device, c->owner);
        if (ret) goto done;
        /* Last map reference is gone before the trusted task is dropped. */
        c->ops.release_task(c->context, c->task);
        c->task_held = 0;
    }
done:
    c->ops.unlock(c->context);
    return ret;
}

int gx_client_reap(struct gx_client *c, struct gx_reap_state *state,
                   const struct gx_reap_ops *ops, void *ctx, int from_retry) {
    if (!c || !c->initialized || !state || !ops || !ops->retain || !ops->schedule)
        return -EINVAL;
    if (from_retry) {
        if (!state->pending) return -EINVAL;
        state->pending = 0;
    }
    int ret = gx_client_close(c);
    if (ret && !state->pending) {
        /* Publish one lifetime reference before making work runnable. Repeated
         * close/death messages share this scheduled retry, never duplicate it. */
        ops->retain(ctx);
        state->pending = 1;
        ops->schedule(ctx);
    }
    return ret;
}
