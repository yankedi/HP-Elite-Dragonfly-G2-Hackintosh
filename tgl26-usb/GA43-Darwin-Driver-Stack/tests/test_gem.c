/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include "gem_cpu_backend.h"
#include "gx_ioctl.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <drm.h>
#include <i915_drm.h>

static int groups;
#define GROUP(name) do { printf("PASS %s\n", name); groups++; } while (0)
static struct cpu_context ctx = {.lock = PTHREAD_MUTEX_INITIALIZER};
static struct gx_device *dev;
static void empty(uint64_t files, uint64_t objects, uint64_t maps) {
    struct gx_stats s; assert(gx_get_stats(dev, &s) == 0);
    assert(s.files == files && s.objects == objects && s.maps == maps);
    assert(ctx.pages == objects && ctx.maps == maps);
}
static void life(void) {
    gx_file_id f; assert(gx_open(dev, &f) == 0);
    uint64_t size = 4097; uint32_t h;
    assert(gx_create(dev, f, &size, &h) == 0 && size == 8192 && h);
    struct gx_map_result a,b;
    assert(gx_map(dev, f, h, getpid(), 0, size, 1, &a) == 0);
    assert(gx_map(dev, f, h, getpid(), 4096, 4096, 0, &b) == 0);
    unsigned char *v = (void *)(uintptr_t)a.address;
    const unsigned char *r = (void *)(uintptr_t)b.address;
    for (size_t i = 0; i < size; i++) assert(v[i] == 0);
    v[4096] = 91; v[8191] = 37;
    assert(r[0] == 91 && r[4095] == 37);
    assert(gx_handle_close(dev, f, h) == 0);
    assert(gx_handle_close(dev, f, h) == -ENOENT);
    assert(gx_close(dev, f) == 0);
    empty(0, 1, 2);
    assert(gx_device_destroy(dev) == -EBUSY);
    assert(v[4096] == 91); /* Mapping holds backing after both closes. */
    assert(gx_unmap(dev, f + 1000, a.id) == -ENOENT);
    assert(gx_unmap(dev, f, a.id) == 0); empty(0, 1, 1);
    assert(r[4095] == 37);
    assert(gx_unmap(dev, f, b.id) == 0); empty(0, 0, 0);
    assert(gx_unmap(dev, f, b.id) == -ENOENT);
    assert(gx_close(dev, f) == -EBADF);
    GROUP("rounded-zeroed-shared-pages-map-ref-outlives-file");
}
static void invalid(void) {
    gx_file_id f,g; assert(gx_open(dev, &f) == 0 && gx_open(dev, &g) == 0);
    uint32_t h; uint64_t size = 0;
    assert(gx_create(dev, f, &size, &h) == -EINVAL && h == 0);
    size = UINT64_MAX; assert(gx_create(dev, f, &size, &h) == -E2BIG);
    size = 8192; assert(gx_create(dev, f, &size, &h) == 0);
    struct gx_map_result m;
    assert(gx_map(dev, g, h, getpid(), 0, 4096, 1, &m) == -ENOENT);
    assert(gx_handle_close(dev, g, h) == -ENOENT);
    assert(gx_map(dev, f, h, getpid(), 8192, 4096, 1, &m) == -EINVAL);
    assert(gx_map(dev, f, h, getpid(), UINT64_MAX - 4095, 8192, 1, &m) == -EINVAL);
    assert(gx_map(dev, f, h, getpid(), 1, 4096, 1, &m) == -EINVAL);
    assert(gx_map(dev, f, h, getpid(), 0, 0, 1, &m) == -EINVAL);
    assert(gx_map(dev, f, h, getpid(), 0, 4096, 2, &m) == -EINVAL);
    assert(gx_map(dev, f, h, getpid()+1, 0, 4096, 1, &m) == -EPERM);
    assert(gx_gpu_bind(dev, f, h) == -EOPNOTSUPP && gx_exec(dev, f) == -EOPNOTSUPP);
    assert(gx_close(dev, f) == 0 && gx_close(dev, g) == 0); empty(0,0,0);
    GROUP("bad-size-overflow-offset-permission-cross-open-hardware-refusal");
}
static void failure(void) {
    gx_file_id f; assert(gx_open(dev, &f) == 0);
    uint64_t size = 4096; uint32_t h;
    ctx.fail_meta = 1; assert(gx_create(dev,f,&size,&h) == -ENOMEM); ctx.fail_meta = 0; empty(1,0,0);
    ctx.fail_pages = 1; assert(gx_create(dev,f,&size,&h) == -ENOMEM); ctx.fail_pages = 0; empty(1,0,0);
    assert(gx_create(dev,f,&size,&h) == 0);
    struct gx_map_result m;
    ctx.fail_map = 1; assert(gx_map(dev,f,h,getpid(),0,4096,1,&m) == -ENOMEM); ctx.fail_map = 0; empty(1,1,0);
    assert(gx_map(dev,f,h,getpid(),0,4096,1,&m) == 0);
    assert(gx_handle_close(dev,f,h) == 0);
    ctx.fail_unmap = 1; assert(gx_unmap(dev,f,m.id) == -EIO); ctx.fail_unmap = 0; empty(1,1,1);
    assert(gx_unmap(dev,f,m.id) == 0);
    assert(gx_close(dev,f) == 0); empty(0,0,0);
    GROUP("allocation-map-unmap-failure-reference-rollback-and-retry");
}
static void capacity(void) {
    gx_file_id f; assert(gx_open(dev, &f) == 0);
    uint32_t handles[128];
    for (size_t i=0;i<128;i++) { uint64_t n=4096; assert(gx_create(dev,f,&n,&handles[i]) == 0); }
    uint64_t n=4096; uint32_t h; assert(gx_create(dev,f,&n,&h) == -EMFILE); empty(1,128,0);
    assert(gx_handle_close(dev,f,handles[0]) == 0);
    assert(gx_create(dev,f,&n,&h) == 0 && h != handles[0]);
    assert(gx_handle_close(dev,f,handles[0]) == -ENOENT);
    assert(gx_close(dev,f) == 0); empty(0,0,0);
    gx_file_id files[32];
    for (size_t i=0;i<32;i++) assert(gx_open(dev,&files[i]) == 0);
    assert(gx_open(dev,&f) == -EMFILE);
    for (size_t i=0;i<32;i++) assert(gx_close(dev,files[i]) == 0);
    empty(0,0,0);
    GROUP("bounded-tables-handle-exhaustion-no-stale-reuse");
}
struct user_copy { unsigned char bytes[32]; int fail_in, fail_out; };
static int copy_in(void *p, uint64_t address, void *out, size_t n) {
    struct user_copy *c=p;
    if (c->fail_in || address != 0x10000 || n > sizeof(c->bytes)) return -EFAULT;
    memcpy(out,c->bytes,n); return 0;
}
static int copy_out(void *p,const void *in,uint64_t address,size_t n) {
    struct user_copy *c=p;
    if (c->fail_out || address != 0x10000 || n > sizeof(c->bytes)) return -EFAULT;
    memcpy(c->bytes,in,n); return 0;
}
static void boundary(void) {
    const struct gx_copy_ops ops={copy_in,copy_out}; struct user_copy c={0};
    gx_file_id f; assert(gx_open(dev,&f) == 0);
    struct drm_i915_gem_create a={.size=4097}; memcpy(c.bytes,&a,sizeof(a));
    c.fail_in=1; assert(gx_user_ioctl(dev,f,0xc010645b,0x10000,&ops,&c) == -EFAULT); c.fail_in=0;
    c.fail_out=1; assert(gx_user_ioctl(dev,f,0xc010645b,0x10000,&ops,&c) == -EFAULT); c.fail_out=0; empty(1,0,0);
    assert(gx_user_ioctl(dev,f,0xc010645b,UINT64_MAX,&ops,&c) == -EFAULT);
    a.pad=1; memcpy(c.bytes,&a,sizeof(a)); assert(gx_user_ioctl(dev,f,0xc010645b,0x10000,&ops,&c) == -EINVAL);
    a.pad=0; memcpy(c.bytes,&a,sizeof(a)); assert(gx_user_ioctl(dev,f,0xc010645b,0x10000,&ops,&c) == 0);
    memcpy(&a,c.bytes,sizeof(a)); assert(a.size == 8192 && a.handle);
    struct drm_gem_close close_arg={.handle=a.handle}; memcpy(c.bytes,&close_arg,sizeof(close_arg));
    assert(gx_user_ioctl(dev,f,0x40086409,0x10000,&ops,&c) == -ENOTTY); /* Linux direction. */
    assert(gx_user_ioctl(dev,f,0x80086409,0x10000,&ops,&c) == 0); empty(1,0,0);
    assert(gx_user_ioctl(dev,f,0xc0106479,0x10000,&ops,&c) == -ENOTTY);
    /* Exec preflight recognizes BSD ABI but this 32B copy region cannot hold
     * its 64B header. Linux input-direction encoding remains unsupported. */
    assert(gx_user_ioctl(dev,f,0x80406469,0x10000,&ops,&c) == -EFAULT);
    assert(gx_user_ioctl(dev,f,0x40406469,0x10000,&ops,&c) == -ENOTTY);
    assert(gx_close(dev,f) == 0); empty(0,0,0);
    GROUP("BSD-wire-copyin-copyout-invalid-pointer-create-rollback");
}
static void *thread(void *arg) {
    (void)arg;
    for (int i=0;i<500;i++) {
        gx_file_id f; assert(gx_open(dev,&f) == 0);
        uint64_t n=4096; uint32_t h; assert(gx_create(dev,f,&n,&h) == 0);
        struct gx_map_result m; assert(gx_map(dev,f,h,getpid(),0,n,1,&m) == 0);
        unsigned char *v=(void *)(uintptr_t)m.address;
        assert(v[0] == 0 && v[4095] == 0); v[0]=0x7b; v[4095]=0x3a;
        assert(gx_handle_close(dev,f,h) == 0); assert(gx_close(dev,f) == 0);
        assert(v[0] == 0x7b && v[4095] == 0x3a); assert(gx_unmap(dev,f,m.id) == 0);
    }
    return NULL;
}
static void concurrent(void) {
    pthread_t threads[8];
    for (int i=0;i<8;i++) assert(pthread_create(&threads[i],NULL,thread,NULL) == 0);
    for (int i=0;i<8;i++) assert(pthread_join(threads[i],NULL) == 0);
    empty(0,0,0); GROUP("8-thread-4000-real-host-mapping-lifecycles");
}
struct race_args { gx_file_id f; uint32_t h; struct gx_map_result map; pthread_barrier_t barrier; int ret; };
static void *race_map(void *p) {
    struct race_args *a = p;
    int ret = pthread_barrier_wait(&a->barrier); assert(ret == 0 || ret == PTHREAD_BARRIER_SERIAL_THREAD);
    a->ret = gx_map(dev,a->f,a->h,getpid(),0,4096,1,&a->map);
    return NULL;
}
static void *race_close(void *p) {
    struct race_args *a = p;
    int ret = pthread_barrier_wait(&a->barrier); assert(ret == 0 || ret == PTHREAD_BARRIER_SERIAL_THREAD);
    assert(gx_close(dev,a->f) == 0); return NULL;
}
static void shared_race_and_revoke(void) {
    for (int i=0;i<100;i++) {
        struct race_args a = {0};
        assert(gx_open(dev,&a.f) == 0); uint64_t n=4096;
        assert(gx_create(dev,a.f,&n,&a.h) == 0);
        assert(pthread_barrier_init(&a.barrier,NULL,2) == 0);
        pthread_t t1,t2; assert(pthread_create(&t1,NULL,race_map,&a) == 0);
        assert(pthread_create(&t2,NULL,race_close,&a) == 0);
        assert(pthread_join(t1,NULL) == 0 && pthread_join(t2,NULL) == 0);
        assert(a.ret == 0 || a.ret == -EBADF);
        if (a.ret == 0) {
            unsigned char *v=(void *)(uintptr_t)a.map.address; assert(v[0] == 0); v[0]=12;
            ctx.fail_unmap=1; assert(gx_revoke_owner_maps(dev,a.f) == -EIO); ctx.fail_unmap=0;
            empty(0,1,1); assert(v[0] == 12);
        }
        assert(gx_revoke_owner_maps(dev,a.f) == 0); empty(0,0,0);
        assert(pthread_barrier_destroy(&a.barrier) == 0);
    }
    GROUP("same-file-map-close-race-and-task-owner-drain-retry");
}
int main(void) {
    assert(gx_device_create(&cpu_ops,&ctx,&dev) == 0);
    life(); invalid(); failure(); capacity(); boundary(); concurrent(); shared_race_and_revoke();
    assert(gx_device_destroy(dev) == 0 && ctx.metas == 0 && ctx.pages == 0 && ctx.maps == 0);
    assert(pthread_mutex_destroy(&ctx.lock) == 0);
    printf("PASS groups=%d backend=LINUX_CPU_MEMFD GPU_VISIBLE=NO XNU_TESTED=NO\n",groups);
    return 0;
}
