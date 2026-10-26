/* SPDX-License-Identifier: MIT
 * Native XNU adapter, compiled with public kernel headers only.
 * No exact-target KDK link, kext load or native runtime validation.
 * See sources/xnu reference headers and reports/GEM-LIFECYCLE.md.
 */
#include "gx_xnu.h"
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOLocks.h>
#include <kern/task.h>
#include <libkern/libkern.h>
#include <sys/errno.h>

struct gx_xnu_context { IOLock *lock; };
static void lock(void *p) { IOLockLock(static_cast<gx_xnu_context *>(p)->lock); }
static void unlock(void *p) { IOLockUnlock(static_cast<gx_xnu_context *>(p)->lock); }
static void *meta(void *, size_t n) { return IOMallocZero(n); }
static void free_meta(void *, void *p, size_t n) { IOFree(p, n); }
static int pages(void *, uint64_t n, void **out) {
    *out = nullptr;
    /* CPU-sharing descriptor only. No physical contiguity, IODMACommand,
     * prepare(), GPU PTE, or GPU-visible/DMA address is promised. */
    IOBufferMemoryDescriptor *md = IOBufferMemoryDescriptor::inTaskWithOptions(
        kernel_task, kIODirectionInOut | kIOMemoryKernelUserShared, n, 4096);
    if (!md) return -ENOMEM;
    void *bytes = md->getBytesNoCopy();
    if (!bytes || md->getLength() != n) { md->release(); return -ENOMEM; }
    bzero(bytes, n); /* Explicitly zero all rounded pages before publishing. */
    *out = md;
    return 0;
}
static void free_pages(void *, void *p, uint64_t) {
    static_cast<IOBufferMemoryDescriptor *>(p)->release();
}
static int map_pages(void *, void *p, uintptr_t task_value, uint64_t off,
                     uint64_t len, int writable, void **out, uint64_t *address) {
    *out = nullptr; *address = 0;
    /* This task MUST come from a retained, authenticated IOUserClient owner,
     * never from a user supplied integer or a public ioctl task field. */
    task_t task = reinterpret_cast<task_t>(task_value);
    if (task == TASK_NULL || task == kernel_task) return -EPERM;
    IOOptionBits options = kIOMapAnywhere | kIOMapUnique;
    if (!writable) options |= kIOMapReadOnly;
    IOMemoryMap *m = static_cast<IOBufferMemoryDescriptor *>(p)->createMappingInTask(
        task, 0, options, off, len);
    if (!m) return -ENOMEM;
    if (m->getLength() != len) { m->release(); return -EIO; }
    *address = m->getAddress(); *out = m;
    return 0;
}
static int unmap_pages(void *, void *p, uint64_t) {
    IOMemoryMap *m = static_cast<IOMemoryMap *>(p);
    IOReturn ret = m->unmap();
    if (ret != kIOReturnSuccess) return -EIO; /* Keep reference for retry. */
    m->release();
    return 0;
}

extern "C" int gx_xnu_create(struct gx_device **out, void **context) {
    if (!out || !context) return -EINVAL;
    *out = nullptr; *context = nullptr;
    gx_xnu_context *ctx = static_cast<gx_xnu_context *>(IOMallocZero(sizeof(*ctx)));
    if (!ctx) return -ENOMEM;
    ctx->lock = IOLockAlloc();
    if (!ctx->lock) { IOFree(ctx, sizeof(*ctx)); return -ENOMEM; }
    const gx_ops ops = {lock, unlock, meta, free_meta, pages, free_pages, map_pages, unmap_pages};
    int ret = gx_device_create(&ops, ctx, out);
    if (ret) { IOLockFree(ctx->lock); IOFree(ctx, sizeof(*ctx)); return ret; }
    *context = ctx;
    return 0;
}
/* Driver must first quiesce concurrent calls and revoke/drain mappings; EBUSY
 * keeps context/lock alive. GX42UserClient supplies task-death retry through
 * its retained native reaper before this destroy path can succeed. */
extern "C" int gx_xnu_destroy(struct gx_device *d, void *context) {
    if (!context) return -EINVAL;
    int ret = gx_device_destroy(d);
    if (ret) return ret;
    gx_xnu_context *ctx = static_cast<gx_xnu_context *>(context);
    IOLockFree(ctx->lock); IOFree(ctx, sizeof(*ctx)); return 0;
}
