/*
 * Bounded CPU-only witness for a regular (non-ONCE) deferred reaper.
 *
 * This drives the production gx_client_reap() state machine with an injected
 * asynchronous scheduler.  A failed callback reschedules while its original
 * callback is still running; the lifecycle lock blocks the replacement from
 * entering gx_client_reap until the original leaves.  Each scheduled callback
 * owns one retain, and the final callback release is allowed only when no
 * other callback remains active.  No XNU thread_call, IOUserClient, or
 * IOMemoryMap runtime is simulated.
 */
#include "gx_client.h"
#include "gem_cpu_backend.h"
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

struct reaper_fixture;
static void callback_release(struct reaper_fixture *);
static const struct gx_reap_ops reaper_ops;

struct reaper_fixture {
    struct cpu_context cpu;
    struct gx_device *device;
    struct gx_client client;
    pthread_mutex_t gate;
    pthread_mutex_t lifecycle;
    pthread_mutex_t state_lock;
    pthread_cond_t state_cv;
    struct gx_reap_state state;
    unsigned refs, schedules, active;
    int freed;
    pthread_t callbacks[4];
    unsigned callback_count;
};

static void client_lock(void *p) {
    struct reaper_fixture *r = p;
    assert(!pthread_mutex_lock(&r->gate));
}
static void client_unlock(void *p) {
    struct reaper_fixture *r = p;
    assert(!pthread_mutex_unlock(&r->gate));
}
static int retain_task(void *p, uintptr_t task) {
    struct reaper_fixture *r = p;
    assert(task == (uintptr_t)getpid());
    (void)r;
    return 0;
}
static void release_task(void *p, uintptr_t task) {
    struct reaper_fixture *r = p;
    assert(task == (uintptr_t)getpid());
    (void)r;
}
static const struct gx_client_ops client_ops = {
    client_lock, client_unlock, retain_task, release_task
};

static void retain_callback(void *p) {
    struct reaper_fixture *r = p;
    assert(!pthread_mutex_lock(&r->state_lock));
    assert(!r->freed);
    r->refs++;
    assert(!pthread_mutex_unlock(&r->state_lock));
}

static void *callback_thread(void *p) {
    struct reaper_fixture *r = p;
    assert(!pthread_mutex_lock(&r->state_lock));
    r->active++;
    assert(!pthread_cond_broadcast(&r->state_cv));
    assert(!pthread_mutex_unlock(&r->state_lock));

    assert(!pthread_mutex_lock(&r->lifecycle));
    int ret = gx_client_reap(&r->client, &r->state, &reaper_ops, r, 1);
    assert(ret == -EIO || ret == 0);
    assert(!pthread_mutex_unlock(&r->lifecycle));
    callback_release(r);
    return NULL;
}

static void schedule_callback(void *p) {
    struct reaper_fixture *r = p;
    assert(!pthread_mutex_lock(&r->state_lock));
    assert(r->callback_count < sizeof(r->callbacks) / sizeof(r->callbacks[0]));
    unsigned index = r->callback_count++;
    r->schedules++;
    if (r->schedules == 2) r->cpu.fail_unmap = 0;
    assert(!pthread_mutex_unlock(&r->state_lock));
    assert(!pthread_create(&r->callbacks[index], NULL, callback_thread, r));
}

static const struct gx_reap_ops reaper_ops = {retain_callback, schedule_callback};

static void callback_release(struct reaper_fixture *r) {
    assert(!pthread_mutex_lock(&r->state_lock));
    assert(r->active > 0 && r->refs > 0);
    r->active--;
    r->refs--;
    if (!r->refs) {
        /* The current callback is the last use; no other callback may live. */
        assert(!r->active);
        r->freed = 1;
        assert(!pthread_cond_broadcast(&r->state_cv));
    }
    assert(!pthread_mutex_unlock(&r->state_lock));
}

static int external_reap(struct reaper_fixture *r) {
    assert(!pthread_mutex_lock(&r->lifecycle));
    int ret = gx_client_reap(&r->client, &r->state, &reaper_ops, r, 0);
    assert(!pthread_mutex_unlock(&r->lifecycle));
    return ret;
}

int main(void) {
    struct reaper_fixture r = {0};
    assert(!pthread_mutex_init(&r.cpu.lock, NULL));
    assert(!pthread_mutex_init(&r.gate, NULL));
    assert(!pthread_mutex_init(&r.lifecycle, NULL));
    assert(!pthread_mutex_init(&r.state_lock, NULL));
    assert(!pthread_cond_init(&r.state_cv, NULL));
    assert(!gx_device_create(&cpu_ops, &r.cpu, &r.device));
    assert(!gx_client_init(&r.client, r.device, (uintptr_t)getpid(),
                           &client_ops, &r));

    gx_file_id owner = r.client.owner;
    uint64_t size = 4096;
    uint32_t handle = 0;
    assert(!gx_create(r.device, owner, &size, &handle));
    struct gx_map_result map = {0};
    assert(!gx_map(r.device, owner, handle, (uintptr_t)getpid(), 0, 4096, 1,
                   &map));
    r.cpu.fail_unmap = 1;

    assert(external_reap(&r) == -EIO);
    assert(!pthread_mutex_lock(&r.state_lock));
    while (!r.freed)
        assert(!pthread_cond_wait(&r.state_cv, &r.state_lock));
    assert(r.schedules == 2 && r.callback_count == 2);
    assert(!pthread_mutex_unlock(&r.state_lock));

    for (unsigned i = 0; i < r.callback_count; i++)
        assert(!pthread_join(r.callbacks[i], NULL));
    assert(!r.refs && !r.active && !r.state.pending);
    assert(!r.client.task_held);
    assert(!gx_device_destroy(r.device));
    assert(!pthread_cond_destroy(&r.state_cv));
    assert(!pthread_mutex_destroy(&r.state_lock));
    assert(!pthread_mutex_destroy(&r.lifecycle));
    assert(!pthread_mutex_destroy(&r.gate));
    assert(!pthread_mutex_destroy(&r.cpu.lock));
    puts("OVERLAP_WITNESS: rescheduled callback overlap serialized and final retain drained PASS");
    return 0;
}
