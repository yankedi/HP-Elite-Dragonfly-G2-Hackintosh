/* SPDX-License-Identifier: MIT */
#define _GNU_SOURCE
#include "gem_cpu_backend.h"
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

struct backing { int fd; };
static void lock(void *p) { assert(pthread_mutex_lock(&((struct cpu_context *)p)->lock) == 0); }
static void unlock(void *p) { assert(pthread_mutex_unlock(&((struct cpu_context *)p)->lock) == 0); }
static void *meta(void *p, size_t n) {
    struct cpu_context *c = p;
    if (c->fail_meta) return NULL;
    void *m = calloc(1, n); if (m) c->metas++;
    return m;
}
static void free_meta(void *p, void *m, size_t n) {
    (void)n; struct cpu_context *c = p; assert(c->metas); c->metas--; free(m);
}
static int pages(void *p, uint64_t n, void **out) {
    struct cpu_context *c = p; *out = NULL;
    if (c->fail_pages) return -ENOMEM;
    struct backing *b = calloc(1, sizeof(*b)); if (!b) return -ENOMEM;
    b->fd = memfd_create("ga41-cpu-only-bo", MFD_CLOEXEC);
    if (b->fd < 0) { int ret = -errno; free(b); return ret; }
    if (ftruncate(b->fd, (off_t)n)) { int ret = -errno; close(b->fd); free(b); return ret; }
    /* Linux guarantees new memfd pages read as zero; no GPU access exists. */
    c->pages++; *out = b; return 0;
}
static void free_pages(void *p, void *m, uint64_t n) {
    (void)n; struct cpu_context *c = p; struct backing *b = m;
    assert(c->pages); assert(close(b->fd) == 0); c->pages--; free(b);
}
static int map(void *p, void *m, uintptr_t task, uint64_t off, uint64_t n,
               int writable, void **out, uint64_t *address) {
    struct cpu_context *c = p; *out = NULL; *address = 0;
    if (task != (uintptr_t)getpid()) return -EPERM;
    if (c->fail_map) return -ENOMEM;
    struct backing *b = m;
    void *v = mmap(NULL, (size_t)n, PROT_READ | (writable ? PROT_WRITE : 0), MAP_SHARED, b->fd, (off_t)off);
    if (v == MAP_FAILED) return -errno;
    c->maps++; *out = v; *address = (uintptr_t)v; return 0;
}
static int unmap(void *p, void *m, uint64_t n) {
    struct cpu_context *c = p;
    if (c->fail_unmap) return -EIO;
    if (munmap(m, (size_t)n)) return -errno;
    assert(c->maps); c->maps--; return 0;
}
const struct gx_ops cpu_ops = {lock, unlock, meta, free_meta, pages, free_pages, map, unmap};
