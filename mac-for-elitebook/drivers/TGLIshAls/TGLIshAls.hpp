// SPDX-License-Identifier: BSD-3-Clause
// Clean-room Intel 500-Series ISH (8086:a0fc) ALS VirtualSMC Driver

#ifndef TGL_ISH_ALS_HPP
#define TGL_ISH_ALS_HPP

#include <IOKit/IOService.h>
#include <IOKit/IOWorkLoop.h>
#include <IOKit/IOCommandGate.h>
#include <IOKit/IOTimerEventSource.h>
#include <IOKit/IOInterruptEventSource.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <IOKit/IOMessage.h>
#include <IOKit/acpi/IOACPIPlatformDevice.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/pwr_mgt/IOPM.h>
#include <IOKit/pwr_mgt/RootDomain.h>
#include <libkern/OSByteOrder.h>
#include <stdatomic.h>

#include <VirtualSMCSDK/kern_vsmcapi.hpp>

#include "IshProtocol.hpp"

class IshAlsForceBits : public VirtualSMCValue {
public:
    uint8_t bits() const {
        return static_cast<uint8_t>(data[0] | data[1]);
    }
};

class IshAlsLightValue : public VirtualSMCValue {
public:
    struct __attribute__((packed)) Value {
        uint8_t  valid;
        uint8_t  highGain;
        uint16_t chan0;
        uint16_t chan1;
        uint32_t roomLux;
    };
    static_assert(sizeof(Value) == 10, "ALV0 Value size");

    IshAlsLightValue(_Atomic(uint32_t) *luxPtr, IshAlsForceBits *bitsPtr)
        : currentLux(luxPtr), forceBits(bitsPtr) {}

protected:
    SMC_RESULT readAccess() APPLE_KEXT_OVERRIDE;

private:
    _Atomic(uint32_t) *currentLux;
    IshAlsForceBits   *forceBits;
};

class TGLIshAls : public IOService {
    OSDeclareDefaultStructors(TGLIshAls)

public:
    bool init(OSDictionary *dict = nullptr) APPLE_KEXT_OVERRIDE;
    IOService *probe(IOService *provider, SInt32 *score) APPLE_KEXT_OVERRIDE;
    bool start(IOService *provider) APPLE_KEXT_OVERRIDE;
    void stop(IOService *provider) APPLE_KEXT_OVERRIDE;
    void free() APPLE_KEXT_OVERRIDE;
    IOWorkLoop *getWorkLoop() const APPLE_KEXT_OVERRIDE;
    IOReturn setPowerState(unsigned long powerStateOrdinal, IOService *whatDevice) APPLE_KEXT_OVERRIDE;

private:
    static constexpr uint32_t kInitTickMs              = 10u;
    static constexpr uint32_t kStreamingTickMs         = 1000u;
    static constexpr uint32_t kFallbackPollTickMs      = 100u;
    static constexpr uint32_t kMaxConsecutiveEmptyIrqs = 500u;

    struct __attribute__((packed)) AlsSensorInfo {
        uint8_t sensorType;
        uint8_t validWhenLidClosed;
        uint8_t unknown;
        uint8_t controlSIL;
    };
    static_assert(sizeof(AlsSensorInfo) == 4, "AlsSensorInfo size");

    struct __attribute__((packed)) LkbStub {
        uint8_t unknown0;
        uint8_t unknown1;
    };
    static_assert(sizeof(LkbStub) == 2, "LkbStub size");

    struct __attribute__((packed)) LksStub {
        uint8_t unknown0;
        uint8_t unknown1;
    };
    static_assert(sizeof(LksStub) == 2, "LksStub size");

    IOPCIDevice             *pci         {nullptr};
    IOACPIPlatformDevice    *ishdAcpi    {nullptr};
    IOMemoryMap             *bar0        {nullptr};
    volatile uint8_t        *mmioBase    {nullptr};
    bool                     pciOpen     {false};
    bool                     pmRegistered {false};
    bool                     debugEnabled {false};
    bool                     disableDsm   {false};
    bool                     disableClock {false};
    bool                     disableNub   {false};
    IONotifier              *pmNotifier  {nullptr};
    IOService               *alsNub      {nullptr};
    uint32_t                 dsmEvalCount {0};

    IOWorkLoop              *workLoop    {nullptr};
    IOCommandGate           *gate        {nullptr};
    IOTimerEventSource      *timer       {nullptr};
    IOInterruptEventSource  *irqSource   {nullptr};
    bool                     irqModeMsi  {false};
    int                      irqIndex    {0};
    bool                     irqEnabled  {false};

    uint16_t                 savedPciCmd {0};
    uint32_t                 savedPimr   {0};
    uint32_t                 savedHostComm {0};
    uint32_t                 savedRmp2   {0};

    _Atomic(bool)            suspended       = ATOMIC_VAR_INIT(false);
    _Atomic(bool)            transportActive = ATOMIC_VAR_INIT(false);
    _Atomic(bool)            stopping        = ATOMIC_VAR_INIT(false);
    unsigned long            powerState      {1};
    uint32_t                 wakeCount       {0};

    IONotifier              *vsmcNotifier {nullptr};
    _Atomic(bool)            smcSubmitted = ATOMIC_VAR_INIT(false);
    _Atomic(uint32_t)        smcLux       = ATOMIC_VAR_INIT(ish::kSmcLuxInvalid);
    IshAlsForceBits         *forceBits    {nullptr};
    IshAlsLightValue        *lightValue   {nullptr};
    VirtualSMCAPI::Plugin    vsmcPlugin {
        "TGLIshAls",
        0x052,
        VirtualSMCAPI::Version,
        {},
        {}
    };

    ish::IshTransport             transport {};
    ish::IshTransport::Stage      lastStage {ish::IshTransport::Stage::Idle};
    ish::WakeAlsNotifyState       wakeAlsNotify {};
    bool                          lastPostedValid {false};
    uint64_t                      lastPostedMilliLux {0};
    uint32_t                      wakeAlsRefreshCount {0};
    uint32_t                      lastClockSyncCount {0};
    uint32_t                      lastSysStateCount {0};
    uint32_t                      lastSysStateInitCount {0};
    uint32_t                      lastDsmProxyCount {0};
    uint32_t                      lastFixedClients {0};
    uint32_t                      lastSampleCountPublished {0};
    uint32_t                      rxFrameCount {0};
    uint32_t                      txFrameCount {0};
    uint32_t                      irqActionCount {0};
    uint32_t                      spuriousIrqCount {0};
    uint32_t                      consecutiveEmptyIrqs {0};
    uint32_t                      timerDrainRxCount {0};
    uint32_t                      mngRxCmplCount {0};
    uint32_t                      host2IshStallTicks {0};
    uint32_t                      telemetryTickDiv {0};
    bool                          irqFallbackPolling {false};
    _Atomic(uint32_t)             smcNotifyCount = ATOMIC_VAR_INIT(0);
    _Atomic(bool)                 smcNotifyPosted = ATOMIC_VAR_INIT(false);
    bool                          origFeatPublished {false};
    bool                          reqFeatPublished {false};
    bool                          curFeatPublished {false};
    bool                          hidDevListPublished {false};
    bool                          alsDescSlicePublished {false};

    uint32_t mmioRead32(uint32_t offset) const;
    void     mmioWrite32(uint32_t offset, uint32_t val) const;
    void     quiesceHardwareDma();
    void     restartTransport(bool isWake = false);
    uint32_t drainRx(uint64_t nowNs);
    void     pumpTx();
    void     processPendingDsmWork();
    void     discoverIshdAcpiDevice();
    uint32_t queryDsmSupportedMask();
    bool     evaluateIshdDsm(uint32_t funcIndex, const uint8_t *args, uint8_t argLen, uint32_t *outFirstWord = nullptr);
    void     handleTransportUpdates(uint64_t nowNs);
    void     enterFailed(const char *reason);
    void     publishTelemetry(bool sampleChanged);
    void     scheduleNextTick();
    bool     setupVirtualSmcKeys();
    bool     createInterruptSource();
    void     publishAlsNub();
    void     cleanupResources();

    static void     irqOccurred(OSObject *owner, IOInterruptEventSource *sender, int count);
    static void     timerFired(OSObject *owner, IOTimerEventSource *sender);
    static bool     vsmcNotificationHandler(void *target, void *refCon, IOService *newService, IONotifier *notifier);
    static IOReturn pmInterestHandler(void *target, void *refCon, UInt32 messageType,
                                      IOService *provider, void *messageArgument, vm_size_t argSize);
    static IOReturn gatedStartTransport(OSObject *owner, void *, void *, void *, void *);
    static IOReturn gatedPublishAlsNub(OSObject *owner, void *, void *, void *, void *);
    static IOReturn gatedDisplayState(OSObject *owner, void *arg0, void *arg1, void *arg2, void *);
    static IOReturn gatedPowerSleep(OSObject *owner, void *, void *, void *, void *);
    static IOReturn gatedPowerWake(OSObject *owner, void *, void *, void *, void *);
    static IOReturn gatedStop(OSObject *owner, void *, void *, void *, void *);
};

#endif // TGL_ISH_ALS_HPP
