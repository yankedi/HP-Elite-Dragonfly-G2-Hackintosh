/* SPDX-License-Identifier: MIT */
#ifndef GA41_CPU_BACKEND_H
#define GA41_CPU_BACKEND_H
#include "gx_gem.h"
#include <pthread.h>
/* Explicit Linux-only test backend. memfd pages are real host CPU pages and
 * mmap permissions are enforced by the host VM. Not XNU or GPU memory. */
struct cpu_context {
    pthread_mutex_t lock;
    int fail_meta, fail_pages, fail_map, fail_unmap;
    uint64_t metas, pages, maps;
};
extern const struct gx_ops cpu_ops;
#endif
