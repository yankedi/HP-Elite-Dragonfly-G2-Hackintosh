/* SPDX-License-Identifier: MIT
 * CPU_SANITIZER: production VM planning and real GEM memfd backing leases.
 * No PPGTT/context hardware, residency, completion or GPU fence is simulated. */
#include "gx_client.h"
#include "gem_cpu_backend.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

struct fixture {
    struct cpu_context cpu;
    pthread_mutex_t gate;
    struct gx_device *d;
    struct gx_client c;
    unsigned refs;
};
static void lock(void *p) { assert(!pthread_mutex_lock(&((struct fixture *)p)->gate)); }
static void unlock(void *p) { assert(!pthread_mutex_unlock(&((struct fixture *)p)->gate)); }
static int retain(void *p, uintptr_t task) {
    assert(task == (uintptr_t)getpid()); ((struct fixture *)p)->refs++; return 0;
}
static void release(void *p, uintptr_t task) {
    struct fixture *f = p; assert(task == (uintptr_t)getpid() && f->refs); f->refs--;
}
static const struct gx_client_ops ops = {lock, unlock, retain, release};
static void setup(struct fixture *f) {
    memset(f, 0, sizeof(*f));
    assert(!pthread_mutex_init(&f->cpu.lock, NULL));
    assert(!pthread_mutex_init(&f->gate, NULL));
    assert(!gx_device_create(&cpu_ops, &f->cpu, &f->d));
    f->cpu.fail_meta = 1;
    assert(gx_client_init(&f->c, f->d, (uintptr_t)getpid(), &ops, f) == -ENOMEM);
    assert(!f->refs && !f->c.initialized);
    f->cpu.fail_meta = 0;
    assert(!gx_client_init(&f->c, f->d, (uintptr_t)getpid(), &ops, f));
}
static void finish(struct fixture *f) {
    assert(!gx_client_close(&f->c));
    assert(!gx_client_close(&f->c));
    assert(!f->refs && !f->c.vm_plans);
    assert(!gx_device_destroy(f->d));
    assert(!f->cpu.metas && !f->cpu.pages && !f->cpu.maps);
    assert(!pthread_mutex_destroy(&f->gate));
    assert(!pthread_mutex_destroy(&f->cpu.lock));
}
static uint32_t create(struct fixture *f, uint64_t n) {
    uint32_t h; assert(!gx_create(f->d, f->c.owner, &n, &h)); return h;
}
static void lifetime_and_quota(void) {
    struct fixture f; setup(&f);
    lock(&f);
    struct gx_vm_state *s = f.c.vm_plans;
    uint32_t vm, ctx, h = create(&f, UINT64_C(16) << 20);
    f.cpu.fail_meta = 1;
    assert(gx_vm_plan_create(s, &vm) == -ENOMEM && !vm);
    f.cpu.fail_meta = 0;
    assert(!gx_vm_plan_create(s, &vm) && vm);
    assert(!gx_context_plan_create(s, vm, &ctx));
    assert(!gx_vm_plan_bind(s, vm, h, 0x10000, UINT64_C(16) << 20));
    assert(gx_vm_plan_bind(s, vm, h, 0x10000, 4096) == -EEXIST);
    assert(gx_vm_plan_bind(s, vm, h, UINT64_MAX-4095, 4096) == -EINVAL);
    assert(gx_vm_plan_bind(s, vm, h, 0x4000000, UINT64_C(32) << 20) == -EINVAL);
    gx_file_id other; assert(!gx_open(f.d, &other));
    uint64_t lease, size;
    assert(gx_bo_lease_get(f.d, other, h, &lease, &size) == -ENOENT);
    assert(!gx_close(f.d, other));
    assert(!gx_handle_close(f.d, f.c.owner, h));
    uint32_t unused; size = 4096;
    assert(gx_create(f.d, f.c.owner, &size, &unused) == -EDQUOT);
    assert(gx_vm_plan_destroy(s, vm, 1, 0) == -EINVAL);
    assert(gx_vm_plan_destroy(s, vm, 0, 1) == -EINVAL);
    assert(!gx_vm_plan_destroy(s, vm, 0, 0));
    assert(gx_vm_plan_destroy(s, vm, 0, 0) == -ENOENT);
    assert(gx_vm_plan_unbind(s, vm, 0x10000) == -ENOENT);
    assert(gx_context_plan_submit(s, ctx, 0x10000, 8) == -EOPNOTSUPP);
    assert(gx_context_plan_submit(s, ctx, 0x10000-8, 8) == -ENOENT);
    struct gx_vm_counts counts; assert(!gx_vm_plan_counts(s, &counts));
    assert(!counts.names && counts.contexts == 1 && counts.objects == 1 && counts.bindings == 1);
    assert(f.cpu.pages == 1);
    assert(!gx_context_plan_destroy(s, ctx));
    assert(!f.cpu.pages);
    h = create(&f, 4096);
    assert(!gx_handle_close(f.d, f.c.owner, h));
    unlock(&f); finish(&f);
}
static void limits_and_teardown(void) {
    struct fixture f; setup(&f);
    lock(&f);
    struct gx_vm_state *s = f.c.vm_plans;
    uint32_t vm, ctx[32], h = create(&f, 4096);
    assert(!gx_vm_plan_create(s, &vm));
    for (unsigned i = 0; i < 32; i++) assert(!gx_context_plan_create(s, vm, &ctx[i]));
    uint32_t extra; assert(gx_context_plan_create(s, vm, &extra) == -ENOSPC && !extra);
    assert(!gx_vm_plan_bind(s, vm, h, 0x10000, 4096));
    assert(!gx_vm_plan_unbind(s, vm, 0x10000));
    assert(!gx_vm_plan_bind(s, vm, h, 0x20000, 4096));
    assert(!gx_vm_plan_destroy(s, vm, 0, 0));
    /* Orphan VMs still count against VM limit, preventing name-recreate leak. */
    uint32_t names[15];
    for (unsigned i = 0; i < 15; i++) assert(!gx_vm_plan_create(s, &names[i]));
    assert(gx_vm_plan_create(s, &extra) == -ENOSPC && !extra);
    assert(!gx_device_detach(f.d));
    assert(gx_vm_plan_bind(s, names[0], h, 0x10000, 4096) == -ENODEV);
    /* Client death/close drains contexts, orphan VM and BO leases after detach. */
    unlock(&f); finish(&f);
}
static void request_error_ownership(void) {
    struct fixture f; setup(&f); lock(&f);
    struct gx_vm_state *s = f.c.vm_plans;
    uint32_t vm, ctx, h = create(&f, 4096);
    assert(!gx_vm_plan_create(s, &vm));
    assert(!gx_context_plan_create(s, vm, &ctx));
    assert(!gx_vm_plan_bind(s, vm, h, 0x10000, 4096));
    uint64_t request, other;
    assert(!gx_request_plan_prepare(s, ctx, 0x10000, 8, &request));
    assert(gx_request_plan_status(s, request) == -EINPROGRESS);
    assert(gx_request_plan_fail(s, request, 0) == -EINVAL); /* no fake success */
    assert(gx_request_plan_fail(s, request, -EINPROGRESS) == -EINVAL);
    assert(gx_vm_plan_unbind(s, vm, 0x10000) == -EBUSY);
    assert(!gx_request_plan_fail(s, request, -EIO));
    assert(!gx_request_plan_fail(s, request, -ETIMEDOUT));
    assert(gx_request_plan_status(s, request) == -EIO); /* first error wins */
    assert(!gx_request_plan_prepare(s, ctx, 0x10008, 8, &other));
    assert(!gx_handle_close(f.d, f.c.owner, h));
    assert(!gx_vm_plan_destroy(s, vm, 0, 0));
    assert(!gx_context_plan_destroy(s, ctx));
    assert(gx_request_plan_status(s, request) == -EIO);
    assert(gx_request_plan_status(s, other) == -ECANCELED);
    struct gx_vm_counts counts; assert(!gx_vm_plan_counts(s, &counts));
    assert(!counts.names && !counts.contexts && counts.objects == 1 &&
           counts.bindings == 1 && counts.requests == 2 && f.cpu.pages == 1);
    assert(!gx_request_plan_release(s, request));
    assert(gx_request_plan_release(s, request) == -ENOENT && f.cpu.pages == 1);
    assert(!gx_request_plan_release(s, other) && !f.cpu.pages);
    assert(!gx_vm_plan_create(s, &vm));
    assert(!gx_context_plan_create(s, vm, &ctx));
    h = create(&f, 4096);
    assert(!gx_vm_plan_bind(s, vm, h, 0x20000, 4096));
    for (unsigned i = 0; i < 32; i++)
        assert(!gx_request_plan_prepare(s, ctx, 0x20000, 8, &request));
    assert(gx_request_plan_prepare(s, ctx, 0x20000, 8, &other) == -ENOSPC && !other);
    assert(!gx_device_detach(f.d));
    unlock(&f); finish(&f); /* abort/release all plans, backing and metadata */
}
static void orphan_vm_bound_and_detach_admission(void) {
    struct fixture f; setup(&f); lock(&f);
    struct gx_vm_state *s = f.c.vm_plans;
    uint32_t h = create(&f, 4096), vm, ctx;
    uint64_t requests[16];
    for (unsigned i = 0; i < 16; i++) {
        assert(!gx_vm_plan_create(s, &vm));
        assert(!gx_context_plan_create(s, vm, &ctx));
        assert(!gx_vm_plan_bind(s, vm, h, 0x10000, 4096));
        assert(!gx_request_plan_prepare(s, ctx, 0x10000, 8, &requests[i]));
        assert(!gx_vm_plan_destroy(s, vm, 0, 0));
        assert(!gx_context_plan_destroy(s, ctx));
    }
    uint32_t extra;
    assert(gx_vm_plan_create(s, &extra) == -ENOSPC && !extra);
    struct gx_vm_counts counts;
    assert(!gx_vm_plan_counts(s, &counts) && counts.objects == 16 &&
           counts.requests == 16 && counts.bindings == 16 && !counts.names && !counts.contexts);
    for (unsigned i = 0; i < 16; i++) assert(!gx_request_plan_release(s, requests[i]));
    assert(!gx_vm_plan_create(s, &vm));
    assert(!gx_context_plan_create(s, vm, &ctx));
    assert(!gx_vm_plan_bind(s, vm, h, 0x20000, 4096));
    uint64_t req, other;
    assert(!gx_request_plan_prepare(s, ctx, 0x20000, 8, &req));
    assert(!gx_device_detach(f.d));
    assert(gx_vm_plan_create(s, &extra) == -ENODEV && !extra);
    assert(gx_context_plan_create(s, vm, &extra) == -ENODEV && !extra);
    assert(gx_request_plan_prepare(s, ctx, 0x20000, 8, &other) == -ENODEV && !other);
    assert(gx_context_plan_submit(s, ctx, 0x20000, 8) == -ENODEV);
    assert(gx_vm_plan_bind(s, vm, h, 0x30000, 4096) == -ENODEV);
    assert(gx_request_plan_status(s, req) == -EINPROGRESS);
    assert(!gx_request_plan_fail(s, req, -EIO));
    assert(gx_request_plan_status(s, req) == -EIO);
    assert(!gx_request_plan_release(s, req));
    assert(!gx_vm_plan_unbind(s, vm, 0x20000));
    assert(!gx_context_plan_destroy(s, ctx));
    assert(!gx_vm_plan_destroy(s, vm, 0, 0));
    unlock(&f); finish(&f);
}
int main(void) {
    lifetime_and_quota(); limits_and_teardown(); request_error_ownership();
    orphan_vm_bound_and_detach_admission();
    puts("VM/context ownership, orphan VM limit, real GEM lease quota and death/detach cleanup PASS; no GPU execution");
    return 0;
}
