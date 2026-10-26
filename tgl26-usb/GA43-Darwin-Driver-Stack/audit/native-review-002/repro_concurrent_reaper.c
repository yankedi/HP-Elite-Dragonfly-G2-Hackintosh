/*
 * Bounded CPU-only witness for concurrent external close/death notifications.
 *
 * The included test fixture serializes the lifecycle path with the same
 * injected lock used by its reaper witness.  Two threads issue redundant
 * external calls while unmap is failing; exactly one scheduled retain must be
 * published.  This does not execute XNU thread_call or IOUserClient code.
 */
#define main ga42_existing_client_test_main
#include "../../tests/test_client.c"
#undef main

struct concurrent_reap_arg { struct reaper_fixture *r; };

static void *external_reap(void *p) {
    struct concurrent_reap_arg *a = p;
    assert(reap(a->r, 0) == -EIO);
    return NULL;
}

int main(void) {
    struct reaper_fixture r = {0};
    setup(&r.f);
    start(&r.f);
    struct gx_cpu_map map = {.handle = create(&r.f), .length = 4096};
    assert(!call(&r.f, GX_CPU_MAP, &map));
    r.f.cpu.fail_unmap = 1;

    struct concurrent_reap_arg arg = {.r = &r};
    pthread_t first, second;
    assert(!pthread_create(&first, NULL, external_reap, &arg));
    assert(!pthread_create(&second, NULL, external_reap, &arg));
    assert(!pthread_join(first, NULL));
    assert(!pthread_join(second, NULL));
    assert(r.refs == 1 && r.queued == 1 && r.schedules == 1);

    r.f.cpu.fail_unmap = 0;
    assert(!reap(&r, 1));
    assert(!r.refs && !r.queued && !r.state.pending && !r.f.task_refs);
    finish(&r.f);
    puts("REAPER_WITNESS: concurrent external notifications deduplicate one retained retry PASS");
    return 0;
}
