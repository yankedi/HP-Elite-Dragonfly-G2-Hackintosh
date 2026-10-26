/*
 * Bounded CPU-only witness for native task-death cleanup review.
 *
 * This is not an XNU simulation.  One gx_client_close() call stands in for
 * the only clientDied()/termination callback that XNU supplies.  The test
 * injects one failed unmap and verifies that the contract leaves the task,
 * map and backing object pinned.  There is deliberately no second close:
 * the native code has no deferred retry path to invoke it.
 */
#include "gx_client.h"
#include "gem_cpu_backend.h"
#include <i915_drm.h>
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

struct fixture {
    struct cpu_context cpu;
    struct gx_device *device;
    struct gx_client client;
    pthread_mutex_t gate;
    int task_refs;
};

static void gate_lock(void *p) {
    assert(!pthread_mutex_lock(&((struct fixture *)p)->gate));
}
static void gate_unlock(void *p) {
    assert(!pthread_mutex_unlock(&((struct fixture *)p)->gate));
}
static int retain_task(void *p, uintptr_t task) {
    struct fixture *f = p;
    assert(task == (uintptr_t)getpid());
    f->task_refs++;
    return 0;
}
static void release_task(void *p, uintptr_t task) {
    struct fixture *f = p;
    assert(task == (uintptr_t)getpid());
    assert(f->task_refs == 1);
    f->task_refs--;
}
static const struct gx_client_ops client_ops = {
    gate_lock, gate_unlock, retain_task, release_task
};

static int copy_in(void *unused, uint64_t user, void *dst, size_t n) {
    (void)unused;
    if (user <= 1) return -EFAULT;
    memcpy(dst, (const void *)(uintptr_t)user, n);
    return 0;
}
static int copy_out(void *unused, const void *src, uint64_t user, size_t n) {
    (void)unused;
    if (user <= 1) return -EFAULT;
    memcpy((void *)(uintptr_t)user, src, n);
    return 0;
}
static const struct gx_copy_ops copy_ops = {copy_in, copy_out};

int main(void) {
    struct fixture f;
    memset(&f, 0, sizeof(f));
    assert(!pthread_mutex_init(&f.cpu.lock, NULL));
    assert(!pthread_mutex_init(&f.gate, NULL));
    assert(!gx_device_create(&cpu_ops, &f.cpu, &f.device));
    assert(!gx_client_init(&f.client, f.device, (uintptr_t)getpid(),
                           &client_ops, &f));

    struct drm_i915_gem_create create = {.size = 4096};
    assert(!gx_client_ioctl(&f.client, UINT32_C(0xc010645b),
                            (uintptr_t)&create, &copy_ops, &f));
    struct gx_cpu_map map = {
        .handle = create.handle, .writable = 1, .length = 4096
    };
    assert(!gx_client_ioctl(&f.client, GX_CPU_MAP, (uintptr_t)&map,
                            &copy_ops, &f));

    /* Sole process-death callback: native unmap fails and cleanup quarantines. */
    f.cpu.fail_unmap = 1;
    assert(gx_client_close(&f.client) == -EIO);
    assert(f.client.closing && f.client.file_closed && f.client.task_held);
    assert(f.task_refs == 1 && f.cpu.maps == 1 && f.cpu.pages == 1);
    assert(gx_device_destroy(f.device) == -EBUSY);

    puts("REPRO: one death/termination cleanup callback leaves task+map pinned on unmap failure");

    f.cpu.fail_unmap = 0;
    assert(!gx_client_close(&f.client));
    assert(!f.client.task_held && !f.task_refs && !f.cpu.maps && !f.cpu.pages);
    assert(!gx_device_destroy(f.device));
    assert(!pthread_mutex_destroy(&f.cpu.lock));
    assert(!pthread_mutex_destroy(&f.gate));
    return 0;
}
