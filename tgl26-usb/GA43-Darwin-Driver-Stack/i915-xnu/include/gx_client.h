/* SPDX-License-Identifier: MIT */
#ifndef GA42_GX_CLIENT_H
#define GA42_GX_CLIENT_H
#include "gx_ioctl.h"
#include "gx_vm.h"
#include "gx_user_abi.h"
#ifdef __cplusplus
extern "C" {
#endif

/* Kernel-owned per-open state, not user ABI. The transport owns storage and
 * its sleepable gate until no entrant can use it. Lock order: client, device.
 * Callbacks must not re-enter this client. task is authenticated by transport. */
struct gx_client_ops {
    void (*lock)(void *);
    void (*unlock)(void *);
    int (*retain_task)(void *, uintptr_t);
    void (*release_task)(void *, uintptr_t);
};
struct gx_client {
    struct gx_device *device;
    struct gx_client_ops ops;
    void *context;
    uintptr_t task;
    gx_file_id owner;
    struct gx_vm_state *vm_plans; /* host ownership only, protected by this gate */
    int initialized, closing, file_closed, task_held;
};

/* init requires fresh zeroed storage and external exclusion. Once initialized,
 * storage remains allocated through close retries and all concurrent callers. */
int gx_client_init(struct gx_client *, struct gx_device *, uintptr_t,
                   const struct gx_client_ops *, void *);
int gx_client_ioctl(struct gx_client *, uint32_t request, uint64_t user,
                    const struct gx_copy_ops *, void *copy_context);
/* close/task death/detach all use this barrier. Idempotent. Unmap failure keeps
 * task, owner, maps and storage alive for retry; no new operations admitted. */
int gx_client_close(struct gx_client *);

/* Deferred close policy, shared by the native transport and CPU fault tests.
 * The transport holds a separate lifecycle lock across each call. schedule
 * MUST enqueue asynchronously, cannot fail, and consumes one retain only when
 * its callback has finished using the client/provider. It must never run inline.
 * A callback calls with from_retry=1 and drops its existing scheduled retain
 * after return; a failed retry can enqueue one replacement retain. External
 * close/death calls use from_retry=0. Do not cancel queued work: even a close
 * that succeeds before its callback must let that callback drain the retain. */
struct gx_reap_state { int pending; };
struct gx_reap_ops {
    void (*retain)(void *);
    void (*schedule)(void *);
};
int gx_client_reap(struct gx_client *, struct gx_reap_state *,
                   const struct gx_reap_ops *, void *, int from_retry);

#ifdef __cplusplus
}
#endif
#endif
