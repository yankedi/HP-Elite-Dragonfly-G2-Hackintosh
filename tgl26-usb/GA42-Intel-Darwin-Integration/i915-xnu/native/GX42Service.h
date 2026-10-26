/* SPDX-License-Identifier: MIT */
#ifndef GA42_SERVICE_H
#define GA42_SERVICE_H
#include <IOKit/IOService.h>
#include <IOKit/IOUserClient.h>
#include <IOKit/IOLocks.h>
#include <kern/thread_call.h>
#include "gx_client.h"
#include "gx_xnu.h"

/* CPU-memory diagnostic service only. No Metal accelerator, PCI resource
 * claim, BAR map, DMA preparation, GPU VM or execution capability. */
class GX42Service : public IOService {
    OSDeclareDefaultStructors(GX42Service)
    IOLock *gate;
    gx_device *device;
    void *context;
    bool stopping;
    bool counted;
public:
    bool start(IOService *) override;
    void stop(IOService *) override;
    void free() override;
    IOReturn newUserClient(task_t, void *, UInt32, OSDictionary *, IOUserClient **) override;
    int openClient(gx_client *, task_t, const gx_client_ops *, void *);
};

class GX42UserClient : public IOUserClient {
    OSDeclareDefaultStructors(GX42UserClient)
    GX42Service *service;
    IOLock *gate;
    IOLock *lifecycle;
    task_t owner;
    gx_client client;
    bool provisionalTask, terminationStarted;
    /* Regular calls may overlap after resubmission; lifecycle serializes the
     * reaper and every scheduled/running callback owns one client retain. */
    thread_call_t cleanupCall;
    gx_reap_state reaper;
    static void queueCleanup(void *);
    static void retryCleanup(thread_call_param_t, thread_call_param_t);
    IOReturn revoke(bool fromRetry = false);
public:
    bool initWithTask(task_t, void *, UInt32, OSDictionary *) override;
    bool start(IOService *) override;
    IOReturn clientClose() override;
    IOReturn clientDied() override;
    IOReturn message(UInt32, IOService *, void *) override;
    IOReturn externalMethod(uint32_t, IOExternalMethodArguments *,
                            IOExternalMethodDispatch *, OSObject *, void *) override;
    void free() override;
};
#endif
