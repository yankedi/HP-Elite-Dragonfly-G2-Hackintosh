/* SPDX-License-Identifier: MIT */
#ifndef GA43_GX_VM_H
#define GA43_GX_VM_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Host-side ownership / GPU-VA planning only. NO PPGTT, page tables, residency
 * or engine state is created. Do not advertise I915 VM/context capabilities.
 * All calls, including close, require the owning client's sleepable gate.
 * Each BO lease must hold real GEM backing and remain charged to that owner
 * until put_bo. Metadata allocator returns zeroed storage. No callbacks reenter.
 */
struct gx_vm_state;
struct gx_vm_ops {
    void *(*alloc)(void *, size_t);
    void (*free)(void *, void *, size_t);
    int (*get_bo)(void *, uint32_t handle, uint64_t *lease, uint64_t *size);
    void (*put_bo)(void *, uint64_t lease);
    /* Linearization point for new host-side work. Work admitted before a
     * concurrent detach may finish; work checked after detach must fail. */
    int (*admit)(void *);
};
struct gx_vm_counts { uint32_t names, contexts, objects, bindings, requests; };
int gx_vm_state_create(const struct gx_vm_ops *, void *, struct gx_vm_state **);
void gx_vm_state_close(struct gx_vm_state *);
int gx_vm_plan_create(struct gx_vm_state *, uint32_t *);
int gx_vm_plan_destroy(struct gx_vm_state *, uint32_t, uint32_t flags, uint64_t extensions);
int gx_context_plan_create(struct gx_vm_state *, uint32_t vm, uint32_t *);
int gx_context_plan_destroy(struct gx_vm_state *, uint32_t);
int gx_vm_plan_bind(struct gx_vm_state *, uint32_t vm, uint32_t handle,
                    uint64_t va, uint64_t length);
int gx_vm_plan_unbind(struct gx_vm_state *, uint32_t vm, uint64_t va);
int gx_vm_plan_counts(struct gx_vm_state *, struct gx_vm_counts *);
/* Internal request-ownership/error foundation, NOT a GPU fence or DRM
 * syncobj. prepare snapshots one validated bound batch range and retains its
 * VM/BO until release. No success/signal operation exists; status is pending
 * (-EINPROGRESS) or a first negative error. Context close cancels pending
 * records; client close releases all. Caller must hold the client gate and
 * must not retain IDs/pointers beyond client lifetime. */
int gx_request_plan_prepare(struct gx_vm_state *, uint32_t context,
                            uint64_t batch_va, uint64_t length, uint64_t *request);
int gx_request_plan_fail(struct gx_vm_state *, uint64_t request, int error);
int gx_request_plan_status(struct gx_vm_state *, uint64_t request);
int gx_request_plan_release(struct gx_vm_state *, uint64_t request);
/* Validate an existing context's retained VM range. No submit/fence output.
 * A valid retained range returns EOPNOTSUPP, never completion. */
int gx_context_plan_submit(struct gx_vm_state *, uint32_t context,
                          uint64_t batch_va, uint64_t length);
#ifdef __cplusplus
}
#endif
#endif
