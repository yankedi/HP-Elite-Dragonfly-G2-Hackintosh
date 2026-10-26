/* SPDX-License-Identifier: MIT */
#include "GX42Service.h"
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/IOMessage.h>
#include <IOKit/IOLib.h>
#include <kern/task.h>
#include <kern/clock.h>
#include <sys/errno.h>
#include <sys/systm.h>
#include <libkern/libkern.h>
#include <libkern/OSAtomic.h>
#include <libkern/c++/OSData.h>

extern "C" volatile SInt32 gx42_live_services;

OSDefineMetaClassAndStructors(GX42Service, IOService)
OSDefineMetaClassAndStructors(GX42UserClient, IOUserClient)

static void client_lock(void *p) { IOLockLock(static_cast<IOLock *>(p)); }
static void client_unlock(void *p) { IOLockUnlock(static_cast<IOLock *>(p)); }
static int task_hold(void *, uintptr_t t) {
    task_t task = reinterpret_cast<task_t>(t);
    if (!task || task == kernel_task) return -EPERM;
    task_reference(task); return 0;
}
static void task_drop(void *, uintptr_t t) { task_deallocate(reinterpret_cast<task_t>(t)); }
static void reap_hold(void *p) { static_cast<GX42UserClient *>(p)->retain(); }
static int copy_from(void *, uint64_t addr, void *dst, size_t n) {
    int ret = copyin(static_cast<user_addr_t>(addr), dst, n);
    return ret ? -ret : 0;
}
static int copy_to(void *, const void *src, uint64_t addr, size_t n) {
    int ret = copyout(src, static_cast<user_addr_t>(addr), n);
    return ret ? -ret : 0;
}

bool GX42Service::start(IOService *provider) {
    gate = nullptr; device = nullptr; context = nullptr; stopping = counted = false;
    if (!OSDynamicCast(IOPCIDevice, provider) || !IOService::start(provider)) return false;
    gate = IOLockAlloc();
    if (!gate || gx_xnu_create(&device, &context)) {
        if (gate) { IOLockFree(gate); gate = nullptr; }
        IOService::stop(provider); return false;
    }
    /* Cached IOPCIDevice properties, not config-space/MMIO reads. */
    OSData *v = OSDynamicCast(OSData, provider->getProperty("vendor-id"));
    OSData *p = OSDynamicCast(OSData, provider->getProperty("device-id"));
    uint32_t vendor = 0, product = 0;
    if (v && v->getLength() == 4) bcopy(v->getBytesNoCopy(), &vendor, 4);
    if (p && p->getLength() == 4) bcopy(p->getBytesNoCopy(), &product, 4);
    if (vendor != 0x8086 || product != 0x9a49 ||
        gx_device_set_pci_id(device, static_cast<uint16_t>(vendor), static_cast<uint16_t>(product))) {
        (void)gx_xnu_destroy(device, context); device = nullptr; context = nullptr;
        IOLockFree(gate); gate = nullptr;
        IOService::stop(provider); return false;
    }
    /* Personality matches PCI identity only. It does not grant ownership of
     * the GT, and we deliberately publish no accelerator/Metal properties. */
    OSIncrementAtomic(&gx42_live_services); counted = true;
    registerService();
    return true;
}
int GX42Service::openClient(gx_client *c, task_t task, const gx_client_ops *ops, void *ctx) {
    IOLockLock(gate);
    int ret = stopping ? -ENODEV : gx_client_init(c, device, reinterpret_cast<uintptr_t>(task), ops, ctx);
    IOLockUnlock(gate); return ret;
}
IOReturn GX42Service::newUserClient(task_t task, void *security, UInt32 type,
                                   OSDictionary *properties, IOUserClient **out) {
    if (!out) return kIOReturnBadArgument;
    *out = nullptr;
    if (type != 0 || !task || task == kernel_task) return kIOReturnBadArgument;
    /* This interface allocates pinned CPU kernel backing for diagnostics; it
     * is not the eventual ordinary-process GPU render-node access policy.
     * The supplied security token is the only authorization input accepted by
     * clientHasPrivilege; a null token is never treated as administrator. */
    if (!security ||
        IOUserClient::clientHasPrivilege(security, kIOClientPrivilegeAdministrator) != kIOReturnSuccess)
        return kIOReturnNotPrivileged;
    GX42UserClient *c = new GX42UserClient;
    if (!c) return kIOReturnNoMemory;
    if (!c->initWithTask(task, security, type, properties)) { c->release(); return kIOReturnNoMemory; }
    if (!c->attach(this)) { c->release(); return kIOReturnNotAttached; }
    if (!c->start(this)) { c->detach(this); c->release(); return kIOReturnNotReady; }
    *out = c; return kIOReturnSuccess;
}
void GX42Service::stop(IOService *provider) {
    IOLockLock(gate);
    stopping = true;
    (void)gx_device_detach(device);
    IOLockUnlock(gate);
    /* Synchronous client gates drain operations through explicit copyout.
     * Failed unmap work retains its UserClient and this service for retry. */
    messageClients(kIOMessageServiceIsTerminated);
    IOService::stop(provider);
}
void GX42Service::free() {
    if (device) {
        int ret = gx_xnu_destroy(device, context);
        /* A live client retains the provider; reaching free with resources
         * would violate that contract. Never free pages/locks underneath it. */
        if (ret) panic("GA42: provider freed before GEM client quiescence");
        device = nullptr; context = nullptr;
    }
    if (gate) { IOLockFree(gate); gate = nullptr; }
    if (counted) { OSDecrementAtomic(&gx42_live_services); counted = false; }
    IOService::free();
}

bool GX42UserClient::initWithTask(task_t task, void *security, UInt32 type, OSDictionary *properties) {
    service = nullptr; gate = lifecycle = nullptr; owner = TASK_NULL;
    provisionalTask = terminationStarted = false; cleanupCall = nullptr;
    bzero(&client, sizeof(client)); bzero(&reaper, sizeof(reaper));
    if (!task || task == kernel_task || type != 0 ||
        !IOUserClient::initWithTask(task, security, type, properties)) return false;
    gate = IOLockAlloc();
    lifecycle = IOLockAlloc();
    if (!gate || !lifecycle) return false;
    /* Preallocate before admitting the client: scheduling after task death
     * must not depend on a fresh allocation. This pairing is documented for
     * thread_call_free. A rescheduled regular call may overlap its prior
     * callback; lifecycle serializes gx_client_reap, and each scheduled or
     * running callback owns its own retained UserClient reference. */
    /* Exact 25G83 KDK exposes this through our declared Mach KPI. The priority
     * variant exists in the kernel but is exported only by kpi.private. */
    cleanupCall = thread_call_allocate(retryCleanup, this);
    if (!cleanupCall) return false;
    owner = task; task_reference(owner); provisionalTask = true;
    return true;
}
bool GX42UserClient::start(IOService *provider) {
    service = OSDynamicCast(GX42Service, provider);
    if (!service) return false;
    service->retain();
    if (!IOUserClient::start(provider)) { service->release(); service = nullptr; return false; }
    const gx_client_ops ops = {client_lock, client_unlock, task_hold, task_drop};
    if (service->openClient(&client, owner, &ops, gate)) {
        IOUserClient::stop(provider); service->release(); service = nullptr; return false;
    }
    task_deallocate(owner); provisionalTask = false; /* client now owns the task */
    return true;
}
IOReturn GX42UserClient::externalMethod(uint32_t selector, IOExternalMethodArguments *args,
                                       IOExternalMethodDispatch *, OSObject *, void *) {
    /* selector 0: scalar {BSD request, user address}; scalar errno output.
     * No automatic structure copyout can hide a GEM publication failure.
     * Inherited/transferred connection ports cannot map into another task. */
    if (!args || selector != GX_IOCONNECT_IOCTL_SELECTOR || args->scalarInputCount != 2 ||
        args->scalarOutputCount != 1 || args->structureInputSize ||
        args->structureOutputSize || args->structureInputDescriptor ||
        args->structureOutputDescriptor || args->asyncWakePort ||
        args->scalarInput[0] > UINT32_MAX) return kIOReturnBadArgument;
    if (current_task() != owner) return kIOReturnNotPermitted;
    const gx_copy_ops copy = {copy_from, copy_to};
    int ret = gx_client_ioctl(&client, static_cast<uint32_t>(args->scalarInput[0]),
                              args->scalarInput[1], &copy, nullptr);
    args->scalarOutput[0] = static_cast<uint64_t>(ret ? -ret : 0);
    return kIOReturnSuccess; /* transport success, errno is never fabricated */
}
void GX42UserClient::queueCleanup(void *p) {
    GX42UserClient *c = static_cast<GX42UserClient *>(p);
    uint64_t deadline;
    clock_interval_to_deadline(100, kMillisecondScale, &deadline);
    (void)thread_call_enter_delayed(c->cleanupCall, deadline);
}
void GX42UserClient::retryCleanup(thread_call_param_t p, thread_call_param_t) {
    GX42UserClient *c = static_cast<GX42UserClient *>(p);
    (void)c->revoke(true);
    /* Drop this callback's retain only after revoke has released lifecycle.
     * An overlapping rescheduled callback has a separate retain. If this is
     * the final release, free() is allowed to free the current thread call. */
    c->release();
}
IOReturn GX42UserClient::revoke(bool fromRetry) {
    if (!client.initialized) return kIOReturnSuccess;
    retain(); /* protect this invocation through termination and ref changes */
    IOLockLock(lifecycle);
    const gx_reap_ops ops = {reap_hold, queueCleanup};
    int ret = gx_client_reap(&client, &reaper, &ops, this, fromRetry);
    /* lifecycle -> client gate -> device. The queued callback, not the dead
     * process, owns retry progress and keeps both client and provider alive. */
    bool finish = !ret && !terminationStarted;
    if (finish) terminationStarted = true;
    IOLockUnlock(lifecycle);
    if (finish) terminate();
    release();
    return ret ? kIOReturnBusy : kIOReturnSuccess;
}
IOReturn GX42UserClient::clientClose() { return revoke(); }
IOReturn GX42UserClient::clientDied() { return revoke(); }
IOReturn GX42UserClient::message(UInt32 type, IOService *provider, void *arg) {
    if (type == kIOMessageServiceIsTerminated || type == kIOMessageServiceIsRequestingClose)
        return revoke();
    return IOUserClient::message(type, provider, arg);
}
void GX42UserClient::free() {
    /* Every scheduled/running callback owns a retain. Thus free cannot race
     * queued or overlapping work; it may be entered by the final release at
     * the end of the current callback. Never cancel_wait here: waiting on
     * one's own callback would deadlock, and pending work must not be canceled. */
    if (reaper.pending) panic("GA42: pending cleanup lost its client reference");
    if (cleanupCall) {
        if (!thread_call_free(cleanupCall)) panic("GA42: cleanup still pending at free");
        cleanupCall = nullptr;
    }
    if (client.initialized && gx_client_close(&client))
        panic("GA42: quarantined user client freed before unmap retry");
    if (provisionalTask) { task_deallocate(owner); provisionalTask = false; }
    if (gate) { IOLockFree(gate); gate = nullptr; }
    if (lifecycle) { IOLockFree(lifecycle); lifecycle = nullptr; }
    if (service) { service->release(); service = nullptr; }
    IOUserClient::free();
}
