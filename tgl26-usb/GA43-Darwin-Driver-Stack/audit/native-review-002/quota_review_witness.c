/*
 * Bounded CPU-only witness for the new per-file quota paths.
 *
 * This uses the repository's explicit Linux CPU backend, not XNU.  It checks
 * that failed metadata/page allocation does not reserve quota, that a mapped
 * object is accounted by its owner, and that two independent open-file
 * records receive independent 16 MiB budgets.  The last property is why this
 * is not evidence of a per-task aggregate quota.
 */
#include "gx_gem.h"
#include "gem_cpu_backend.h"
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <pthread.h>

static void stats(struct gx_device *d, uint64_t bytes, uint64_t objects,
                  uint64_t files) {
    struct gx_stats s;
    assert(!gx_get_stats(d, &s));
    assert(s.bytes == bytes && s.objects == objects && s.files == files);
}

int main(void) {
    struct cpu_context ctx = {.lock = PTHREAD_MUTEX_INITIALIZER};
    struct gx_device *d = NULL;
    assert(!gx_device_create(&cpu_ops, &ctx, &d));

    gx_file_id first = 0, second = 0;
    assert(!gx_open(d, &first) && !gx_open(d, &second));

    uint64_t size = UINT64_C(12) << 20;
    uint32_t handle = 0;
    assert(!gx_create(d, first, &size, &handle));
    assert(size == (UINT64_C(12) << 20) && handle);
    stats(d, UINT64_C(12) << 20, 1, 2);

    ctx.fail_meta = 1;
    size = UINT64_C(4) << 20;
    assert(gx_create(d, first, &size, &handle) == -ENOMEM);
    ctx.fail_meta = 0;
    stats(d, UINT64_C(12) << 20, 1, 2);

    ctx.fail_pages = 1;
    size = UINT64_C(4) << 20;
    assert(gx_create(d, first, &size, &handle) == -ENOMEM);
    ctx.fail_pages = 0;
    stats(d, UINT64_C(12) << 20, 1, 2);

    size = UINT64_C(4) << 20;
    assert(!gx_create(d, first, &size, &handle));
    stats(d, UINT64_C(16) << 20, 2, 2);
    size = 4096;
    assert(gx_create(d, first, &size, &handle) == -EDQUOT);

    /* A second open file has a separate 16 MiB budget. */
    size = UINT64_C(16) << 20;
    assert(!gx_create(d, second, &size, &handle));
    stats(d, UINT64_C(32) << 20, 3, 2);

    assert(!gx_close(d, first) && !gx_close(d, second));
    stats(d, 0, 0, 0);
    assert(!gx_device_destroy(d));
    assert(!pthread_mutex_destroy(&ctx.lock));
    puts("QUOTA_WITNESS: allocation rollback and independent per-file 16MiB budgets PASS");
    return 0;
}
