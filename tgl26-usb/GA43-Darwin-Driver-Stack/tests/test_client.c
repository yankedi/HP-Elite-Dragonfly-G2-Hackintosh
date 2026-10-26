/* SPDX-License-Identifier: MIT
 * CPU_TEST: the actual per-open production gate, with the inherited memfd
 * backend and explicit task/copy callbacks. No XNU runtime is simulated. */
#include "gx_client.h"
#include "gem_cpu_backend.h"
#include <assert.h>
#include <errno.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <drm.h>
#include <i915_drm.h>

#define CREATE UINT32_C(0xc010645b)
struct fixture {
    struct cpu_context cpu;
    struct gx_device *d;
    struct gx_client c;
    pthread_mutex_t gate, copy_lock;
    pthread_cond_t cv;
    int task_refs, fail_retain, fail_in, fail_out;
    int pause, entered, resume;
    atomic_int close_started;
};
static void lock(void *p) { assert(!pthread_mutex_lock(&((struct fixture *)p)->gate)); }
static void unlock(void *p) { assert(!pthread_mutex_unlock(&((struct fixture *)p)->gate)); }
static int hold(void *p, uintptr_t task) {
    struct fixture *f = p; assert(task == (uintptr_t)getpid());
    if (f->fail_retain) return -EPERM;
    f->task_refs++; return 0;
}
static void drop(void *p, uintptr_t task) {
    struct fixture *f = p; assert(task == (uintptr_t)getpid());
    assert(f->task_refs > 0 && !f->cpu.maps); f->task_refs--;
}
static const struct gx_client_ops ops = {lock, unlock, hold, drop};
static int copy_in(void *p, uint64_t user, void *dst, size_t n) {
    struct fixture *f = p;
    if (f->fail_in || user <= 1) return -EFAULT;
    memcpy(dst, (const void *)(uintptr_t)user, n); return 0;
}
static int copy_out(void *p, const void *src, uint64_t user, size_t n) {
    struct fixture *f = p;
    assert(!pthread_mutex_lock(&f->copy_lock));
    if (f->pause) {
        f->entered = 1; assert(!pthread_cond_broadcast(&f->cv));
        while (!f->resume) assert(!pthread_cond_wait(&f->cv, &f->copy_lock));
    }
    assert(!pthread_mutex_unlock(&f->copy_lock));
    if (f->fail_out || user <= 1) return -EFAULT;
    memcpy((void *)(uintptr_t)user, src, n); return 0;
}
static const struct gx_copy_ops copy = {copy_in, copy_out};
static void setup(struct fixture *f) {
    memset(f, 0, sizeof(*f)); atomic_init(&f->close_started, 0);
    assert(!pthread_mutex_init(&f->cpu.lock, NULL));
    assert(!pthread_mutex_init(&f->gate, NULL));
    assert(!pthread_mutex_init(&f->copy_lock, NULL));
    assert(!pthread_cond_init(&f->cv, NULL));
    assert(!gx_device_create(&cpu_ops, &f->cpu, &f->d));
}
static void start(struct fixture *f) {
    assert(!gx_client_init(&f->c, f->d, (uintptr_t)getpid(), &ops, f));
    assert(f->task_refs == 1);
}
static int call(struct fixture *f, uint32_t cmd, void *arg) {
    return gx_client_ioctl(&f->c, cmd, (uintptr_t)arg, &copy, f);
}
static uint32_t create(struct fixture *f) {
    struct drm_i915_gem_create a = {.size = 1};
    assert(!call(f, CREATE, &a)); assert(a.size == 4096 && a.handle);
    return a.handle;
}
static void finish(struct fixture *f) {
    assert(!gx_client_close(&f->c)); assert(!gx_client_close(&f->c));
    assert(!f->task_refs);
    assert(!gx_device_destroy(f->d));
    assert(!f->cpu.metas && !f->cpu.pages && !f->cpu.maps);
    assert(!pthread_mutex_destroy(&f->cpu.lock));
    assert(!pthread_mutex_destroy(&f->gate));
    assert(!pthread_mutex_destroy(&f->copy_lock));
    assert(!pthread_cond_destroy(&f->cv));
}
static void rollback_and_death(void) {
    struct fixture f; setup(&f);
    f.fail_retain = 1;
    assert(gx_client_init(&f.c, f.d, (uintptr_t)getpid(), &ops, &f) == -EPERM);
    assert(!f.task_refs); f.fail_retain = 0; start(&f);
    assert(gx_client_init(&f.c, f.d, (uintptr_t)getpid(), &ops, &f) == -EBUSY);
    struct drm_i915_gem_create a = {.size = 4096};
    f.fail_in = 1; assert(call(&f, CREATE, &a) == -EFAULT); f.fail_in = 0;
    f.fail_out = 1; assert(call(&f, CREATE, &a) == -EFAULT); f.fail_out = 0;
    assert(!f.cpu.pages);
    uint32_t h = create(&f);
    struct gx_cpu_map m = {.handle = h, .writable = 1, .length = 4096};
    f.fail_out = 1; assert(call(&f, GX_CPU_MAP, &m) == -EFAULT);
    assert(!f.cpu.maps); f.fail_out = 0;
    m.length = 8192; assert(call(&f, GX_CPU_MAP, &m) == -EINVAL);
    m.length = 4096; m.offset = UINT64_MAX - 4095;
    assert(call(&f, GX_CPU_MAP, &m) == -EINVAL); m.offset = 0;
    assert(!call(&f, GX_CPU_MAP, &m));
    memset((void *)(uintptr_t)m.address, 0x5a, 4096);
    struct gx_cpu_unmap u = {.map_id = m.map_id, .reserved = 1};
    assert(call(&f, GX_CPU_UNMAP, &u) == -EINVAL);
    /* Task-death/close retry must pin task and mapping on failed native unmap. */
    f.cpu.fail_unmap = 1; assert(gx_client_close(&f.c) == -EIO);
    assert(f.task_refs == 1 && f.cpu.maps == 1 && f.cpu.pages == 1);
    assert(call(&f, CREATE, &a) == -EBADF);
    assert(gx_device_destroy(f.d) == -EBUSY);
    f.cpu.fail_unmap = 0; finish(&f);
}
static void detach_and_exhaustion(void) {
    struct fixture f; setup(&f); start(&f);
    uint32_t h = create(&f);
    assert(!gx_device_detach(f.d)); assert(!gx_device_detach(f.d));
    struct drm_i915_gem_create a = {.size = 4096};
    assert(call(&f, CREATE, &a) == -ENODEV);
    struct gx_cpu_map m = {.handle = h, .length = 4096};
    assert(call(&f, GX_CPU_MAP, &m) == -ENODEV);
    gx_file_id owner; assert(gx_open(f.d, &owner) == -ENODEV);
    struct gx_client other = {0};
    assert(gx_client_init(&other, f.d, (uintptr_t)getpid(), &ops, &f) == -ENODEV);
    assert(f.task_refs == 1); finish(&f);
    setup(&f); gx_file_id files[32];
    for (size_t i = 0; i < 32; i++) assert(!gx_open(f.d, &files[i]));
    assert(gx_client_init(&f.c, f.d, (uintptr_t)getpid(), &ops, &f) == -EMFILE);
    assert(!f.task_refs);
    for (size_t i = 0; i < 32; i++) assert(!gx_close(f.d, files[i]));
    start(&f); finish(&f);
}
static void *create_thread(void *p) {
    struct fixture *f = p; struct drm_i915_gem_create a = {.size = 4096};
    int ret = call(f, CREATE, &a);
    assert(ret == (f->fail_out ? -EFAULT : 0)); return NULL;
}
static void *close_thread(void *p) {
    struct fixture *f = p; atomic_store(&f->close_started, 1);
    assert(!gx_client_close(&f->c)); return NULL;
}
static void close_copyout_race(void) {
    for (int fail = 0; fail < 2; fail++) {
        struct fixture f; setup(&f); start(&f); f.pause = 1; f.fail_out = fail;
        pthread_t t, closer; assert(!pthread_create(&t, NULL, create_thread, &f));
        assert(!pthread_mutex_lock(&f.copy_lock));
        while (!f.entered) assert(!pthread_cond_wait(&f.cv, &f.copy_lock));
        assert(!pthread_create(&closer, NULL, close_thread, &f));
        while (!atomic_load(&f.close_started)) { /* close is about to acquire gate */ }
        assert(pthread_mutex_trylock(&f.gate) == EBUSY);
        f.resume = 1; assert(!pthread_cond_broadcast(&f.cv));
        assert(!pthread_mutex_unlock(&f.copy_lock));
        assert(!pthread_join(t, NULL)); assert(!pthread_join(closer, NULL));
        finish(&f);
    }
}
static void trusted_query(void) {
    struct fixture f; setup(&f);
    uint16_t vendor, device;
    assert(gx_device_get_pci_id(f.d, &vendor, &device) == -ENODEV);
    assert(gx_device_set_pci_id(f.d, UINT16_MAX, 0x9a49) == -EINVAL);
    assert(!gx_device_set_pci_id(f.d, 0x8086, 0x9a49));
    assert(gx_device_set_pci_id(f.d, 0x8086, 0x1234) == -EBUSY);
    start(&f);
    int32_t value = -1;
    struct drm_i915_getparam param = {.param = I915_PARAM_CHIPSET_ID, .value = &value};
    assert(!call(&f, UINT32_C(0xc0106446), &param)); assert(value == 0x9a49);
    param.value = (int *)(uintptr_t)1;
    assert(call(&f, UINT32_C(0xc0106446), &param) == -EFAULT);
    param.value = &value; param.param = I915_PARAM_CS_TIMESTAMP_FREQUENCY;
    value = -1; assert(call(&f, UINT32_C(0xc0106446), &param) == -EOPNOTSUPP);
    assert(value == -1);
    param.param = I915_PARAM_HAS_EXEC_SOFTPIN;
    assert(call(&f, UINT32_C(0xc0106446), &param) == -EINVAL);
    struct drm_get_cap cap = {.capability = DRM_CAP_SYNCOBJ_TIMELINE, .value = UINT64_MAX};
    assert(!call(&f, UINT32_C(0xc010640c), &cap)); assert(!cap.value);
    cap.capability = UINT64_MAX;
    assert(call(&f, UINT32_C(0xc010640c), &cap) == -EINVAL);
    struct drm_i915_gem_get_tiling tiling = {.handle = create(&f), .tiling_mode = 99};
    assert(!call(&f, UINT32_C(0xc0106462), &tiling));
    assert(!tiling.tiling_mode && !tiling.swizzle_mode && !tiling.phys_swizzle_mode);
    tiling.handle++;
    assert(call(&f, UINT32_C(0xc0106462), &tiling) == -ENOENT);
    assert(!gx_device_detach(f.d));
    assert(call(&f, UINT32_C(0xc010640c), &cap) == -ENODEV);
    finish(&f);
}
static void exec_rejection(void) {
    struct fixture f; setup(&f); start(&f);
    struct drm_i915_gem_exec_object2 objects[2] = {
        {.handle = create(&f), .offset = 0x10000, .flags = EXEC_OBJECT_PINNED},
        {.handle = create(&f), .offset = 0x20000, .flags = EXEC_OBJECT_PINNED}
    };
    struct drm_i915_gem_execbuffer2 a = {.buffers_ptr = (uintptr_t)objects,
        .buffer_count = 2, .batch_len = 8, .flags = I915_EXEC_NO_RELOC};
    /* Even completely valid input MUST NOT succeed or signal anything. */
    assert(call(&f, UINT32_C(0x80406469), &a) == -EOPNOTSUPP);
    assert(call(&f, UINT32_C(0xc0406469), &a) == -EOPNOTSUPP);
    uint64_t input_fence = UINT64_C(0x1122334455667788);
    a.rsvd2 = input_fence;
    assert(call(&f, UINT32_C(0xc0406469), &a) == -EOPNOTSUPP);
    assert(a.rsvd2 == input_fence); a.rsvd2 = 0;
    a.buffer_count = 17; assert(call(&f, UINT32_C(0x80406469), &a) == -E2BIG);
    a.buffer_count = 0; assert(call(&f, UINT32_C(0x80406469), &a) == -EINVAL);
    a.buffer_count = 2; a.buffers_ptr = UINT64_MAX - 7;
    assert(call(&f, UINT32_C(0x80406469), &a) == -EFAULT);
    a.buffers_ptr = 1; assert(call(&f, UINT32_C(0x80406469), &a) == -EFAULT);
    a.buffers_ptr = (uintptr_t)objects;
    objects[1].handle += 100; assert(call(&f, UINT32_C(0x80406469), &a) == -ENOENT);
    objects[1].handle -= 100;
    objects[1].offset = objects[0].offset;
    assert(call(&f, UINT32_C(0x80406469), &a) == -EINVAL); objects[1].offset = 0x20000;
    objects[1].offset = UINT64_C(0x800000000000);
    assert(call(&f, UINT32_C(0x80406469), &a) == -EINVAL); objects[1].offset = 0x20000;
    objects[1].alignment = 8192; objects[1].offset += 4096;
    assert(call(&f, UINT32_C(0x80406469), &a) == -EINVAL);
    objects[1].offset -= 4096; objects[1].alignment = 0;
    a.batch_start_offset = 4096;
    assert(call(&f, UINT32_C(0x80406469), &a) == -EINVAL); a.batch_start_offset = 0;
    struct drm_i915_gem_exec_fence fence = {.handle = 4, .flags = I915_EXEC_FENCE_SIGNAL};
    a.flags |= I915_EXEC_FENCE_ARRAY; a.num_cliprects = 1; a.cliprects_ptr = (uintptr_t)&fence;
    assert(call(&f, UINT32_C(0xc0406469), &a) == -EOPNOTSUPP);
    fence.flags = 4; assert(call(&f, UINT32_C(0x80406469), &a) == -EINVAL);
    fence.flags = I915_EXEC_FENCE_SIGNAL; a.cliprects_ptr = 1;
    assert(call(&f, UINT32_C(0x80406469), &a) == -EFAULT);
    assert(!f.cpu.maps && f.cpu.pages == 2);
    finish(&f);
}
static void mapped_owner_quota(void) {
    struct fixture f; setup(&f); start(&f);
    struct drm_i915_gem_create a = {.size = UINT64_C(8) << 20};
    assert(!call(&f, CREATE, &a));
    struct gx_cpu_map first = {.handle = a.handle, .length = 4096};
    struct gx_cpu_map second = first;
    assert(!call(&f, GX_CPU_MAP, &first)); assert(!call(&f, GX_CPU_MAP, &second));
    struct drm_gem_close close_arg = {.handle = a.handle};
    assert(!call(&f, UINT32_C(0x80086409), &close_arg));
    /* Two maps of one BO consume its size once, and closing its handle does
     * not release its quota until the last map is gone. */
    a.size = UINT64_C(8) << 20; assert(!call(&f, CREATE, &a));
    struct drm_i915_gem_create extra = {.size = 1};
    assert(call(&f, CREATE, &extra) == -EDQUOT);
    struct gx_cpu_unmap u = {.map_id = first.map_id}; assert(!call(&f, GX_CPU_UNMAP, &u));
    assert(call(&f, CREATE, &extra) == -EDQUOT);
    u.map_id = second.map_id; assert(!call(&f, GX_CPU_UNMAP, &u));
    assert(!call(&f, CREATE, &extra)); finish(&f);
}

struct reaper_fixture {
    struct fixture f;
    struct gx_reap_state state;
    unsigned refs, queued, schedules;
};
static void reaper_hold(void *p) { ((struct reaper_fixture *)p)->refs++; }
static void reaper_schedule(void *p) {
    struct reaper_fixture *r = p;
    assert(r->refs && !r->queued); r->queued++; r->schedules++;
}
static const struct gx_reap_ops reaper_ops = {reaper_hold, reaper_schedule};
static int reap(struct reaper_fixture *r, int callback) {
    /* This deterministic queue is an injected CPU scheduler, not an XNU
     * runtime. Exercise the SAME production reaper used by IOUserClient. */
    assert(!pthread_mutex_lock(&r->f.copy_lock));
    if (callback) { assert(r->queued && r->refs); r->queued--; }
    int ret = gx_client_reap(&r->f.c, &r->state, &reaper_ops, r, callback);
    if (callback) { assert(r->refs); r->refs--; }
    assert(!pthread_mutex_unlock(&r->f.copy_lock));
    return ret;
}
static void deferred_death_cleanup(void) {
    for (int early_close = 0; early_close < 2; early_close++) {
        struct reaper_fixture r = {0}; setup(&r.f); start(&r.f);
        struct gx_cpu_map m = {.handle = create(&r.f), .length = 4096};
        assert(!call(&r.f, GX_CPU_MAP, &m));
        r.f.cpu.fail_unmap = 1;
        assert(reap(&r, 0) == -EIO); /* the single task-death event */
        assert(r.refs == 1 && r.queued == 1 && r.schedules == 1);
        assert(!gx_device_detach(r.f.d));
        for (int i = 0; i < 4; i++) { /* redundant external messages */
            assert(reap(&r, 0) == -EIO);
            assert(r.refs == 1 && r.queued == 1 && r.schedules == 1);
        }
        for (int i = 0; i < 4; i++) { /* persistent error: bounded test only */
            assert(reap(&r, 1) == -EIO);
            assert(r.refs == 1 && r.queued == 1 && r.state.pending);
            assert(r.f.task_refs == 1 && r.f.cpu.maps == 1 && r.f.cpu.pages == 1);
            assert(gx_device_destroy(r.f.d) == -EBUSY);
        }
        r.f.cpu.fail_unmap = 0;
        if (early_close) {
            assert(!reap(&r, 0)); /* callback is pending while close succeeds */
            assert(!r.f.task_refs && !r.f.cpu.maps && r.refs == 1 && r.queued == 1);
        }
        assert(!reap(&r, 1)); /* queue owns eventual progress, no user retry */
        assert(!r.refs && !r.queued && !r.state.pending && !r.f.task_refs);
        finish(&r.f);
    }
}
static void offset_mapping_contract(void) {
    struct fixture f; setup(&f); start(&f);
    const uint32_t getoffset = UINT32_C(0xc0206464);
    struct drm_i915_gem_mmap_offset a = {.handle = create(&f), .flags = I915_MMAP_OFFSET_WB};
    assert(!call(&f, getoffset, &a) && a.offset && !(a.offset & 4095));
    uint64_t cookie = a.offset;
    a.offset = 0; assert(!call(&f, getoffset, &a) && a.offset == cookie);
    a.flags = I915_MMAP_OFFSET_WC; assert(call(&f, getoffset, &a) == -EOPNOTSUPP);
    a.flags = I915_MMAP_OFFSET_WB; a.extensions = 1; assert(call(&f, getoffset, &a) == -EINVAL);
    a.extensions = 0;
    gx_file_id other; assert(!gx_open(f.d, &other));
    struct gx_map_result tmp;
    assert(gx_map_offset(f.d, other, cookie, (uintptr_t)getpid(), 4096, 1, &tmp) == -ENOENT);
    assert(!gx_close(f.d, other));
    struct gx_offset_map w = {.offset = cookie, .length = 4096, .writable = 1};
    struct gx_offset_map r = {.offset = cookie, .length = 4096};
    assert(!call(&f, GX_OFFSET_MAP, &w));
    assert(!call(&f, GX_OFFSET_MAP, &r));
    ((unsigned char *)(uintptr_t)w.address)[23] = 0xa7;
    assert(((const unsigned char *)(uintptr_t)r.address)[23] == 0xa7);
    struct gx_offset_map bad = {.offset = cookie + 4096, .length = 4096};
    assert(call(&f, GX_OFFSET_MAP, &bad) == -ENOENT);
    assert(!gx_handle_close(f.d, f.c.owner, a.handle));
    assert(((const unsigned char *)(uintptr_t)r.address)[23] == 0xa7);
    bad.offset = cookie; assert(call(&f, GX_OFFSET_MAP, &bad) == -ENOENT);
    uint32_t next = create(&f);
    a = (struct drm_i915_gem_mmap_offset){.handle = next, .flags = I915_MMAP_OFFSET_WB};
    f.fail_out = 1; assert(call(&f, getoffset, &a) == -EFAULT);
    f.fail_out = 0; assert(!call(&f, getoffset, &a) && a.offset != cookie);
    /* Failed transport publication and failed rollback retain backing/task;
     * the production close/reaper owns reclamation, never userspace. */
    bad.offset = a.offset; f.fail_out = 1; f.cpu.fail_unmap = 1;
    assert(call(&f, GX_OFFSET_MAP, &bad) == -EFAULT);
    assert(f.cpu.maps == 3);
    f.fail_out = 0;
    assert(gx_client_close(&f.c) == -EIO && f.task_refs == 1);
    f.cpu.fail_unmap = 0; finish(&f);
}
static void alternate_teardown_contract(void) {
    struct fixture f; setup(&f); start(&f);
    struct gx_cpu_map a = {.handle = create(&f), .length = 4096};
    assert(!call(&f, GX_CPU_MAP, &a));
    assert(!gx_close(f.d, f.c.owner)); /* trusted alternate transport */
    f.cpu.fail_unmap = 1;
    assert(gx_client_close(&f.c) == -EIO);
    assert(f.c.file_closed && f.task_refs == 1 && f.cpu.maps == 1);
    f.cpu.fail_unmap = 0;
    finish(&f); /* must reach revoke, drain mapping and release task */
}
int main(void) {
    rollback_and_death(); detach_and_exhaustion(); close_copyout_race(); trusted_query(); exec_rejection();
    mapped_owner_quota();
    deferred_death_cleanup();
    offset_mapping_contract();
    alternate_teardown_contract();
    puts("CPU_TEST: actual client gate/task refs/map rollback/close-copyout/detach PASS");
    return 0;
}
