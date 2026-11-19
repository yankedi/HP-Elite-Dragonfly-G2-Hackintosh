// SPDX-License-Identifier: BSD-3-Clause
// Clean-room Intel 500-Series ISH (8086:a0fc) ALS VirtualSMC Driver

#include "TGLIshAls.hpp"
#include <kern/clock.h>
#include <pexpert/pexpert.h>

#define super IOService
OSDefineMetaClassAndStructors(TGLIshAls, IOService)

static _Atomic(bool) gSmcSubmitted = ATOMIC_VAR_INIT(false);

extern "C" kern_return_t TGLIshAls_start(kmod_info_t *, void *) {
    return KERN_SUCCESS;
}

extern "C" kern_return_t TGLIshAls_stop(kmod_info_t *, void *) {
    if (atomic_load_explicit(&gSmcSubmitted, memory_order_acquire)) {
        return KERN_FAILURE;
    }
    return KERN_SUCCESS;
}

#define LOG(fmt, ...)  IOLog("TGLIshAls: " fmt "\n", ##__VA_ARGS__)
#define DBG(fmt, ...)  do { if (debugEnabled) IOLog("TGLIshAls: " fmt "\n", ##__VA_ARGS__); } while (0)

static IOPMPowerState gPowerStates[2] = {
    { kIOPMPowerStateVersion1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { kIOPMPowerStateVersion1, kIOPMPowerOn | kIOPMDeviceUsable, kIOPMPowerOn, kIOPMPowerOn, 0, 0, 0, 0, 0, 0, 0, 0 },
};

static inline uint64_t currentTimeNs() {
    uint64_t abstime = 0;
    uint64_t ns = 0;
    clock_get_uptime(&abstime);
    absolutetime_to_nanoseconds(abstime, &ns);
    return ns;
}

static inline uint64_t currentMonoUs() {
    return currentTimeNs() / 1000ULL;
}

static inline uint64_t currentUtcUs() {
    clock_sec_t secs = 0;
    clock_usec_t usecs = 0;
    clock_get_calendar_microtime(&secs, &usecs);
    return static_cast<uint64_t>(secs) * 1000000ULL + static_cast<uint64_t>(usecs);
}

static bool strEqual(const char *a, const char *b) {
    if (!a || !b) {
        return false;
    }
    while (*a != '\0' && *b != '\0') {
        if (*a != *b) {
            return false;
        }
        ++a;
        ++b;
    }
    return *a == *b;
}

static bool setDataProperty(IOService *target, const char *key, const void *bytes, uint32_t len) {
    if (!target || !key || !bytes || len == 0u) {
        return false;
    }
    OSData *dataObj = OSData::withBytes(bytes, len);
    if (!dataObj) {
        return false;
    }
    const bool ok = target->setProperty(key, dataObj);
    dataObj->release();
    return ok;
}

static bool hasBootArg(const char *name) {
    char buf[16] {};
    return PE_parse_boot_argn(name, buf, sizeof(buf));
}

SMC_RESULT IshAlsLightValue::readAccess() {
    auto *v = reinterpret_cast<Value *>(data);
    const uint32_t fixedLux = atomic_load_explicit(currentLux, memory_order_acquire);
    const uint8_t bits = forceBits ? forceBits->bits() : 0u;

    if (fixedLux == ish::kSmcLuxInvalid) {
        v->valid = 0u;
    } else {
        v->valid = 1u;
        if ((bits & ish::kForceHighGain) == 0u) {
            v->highGain = 1u;
        }
        if ((bits & ish::kForceChan) == 0u) {
            uint32_t intLux = fixedLux >> 14;
            if (intLux > 0xFFFFu) {
                intLux = 0xFFFFu;
            }
            OSWriteBigInt16(data, 2, static_cast<uint16_t>(intLux));
        }
        if ((bits & ish::kForceLux) == 0u) {
            OSWriteBigInt32(data, 6, fixedLux);
        }
    }
    return SmcSuccess;
}

bool TGLIshAls::init(OSDictionary *dict) {
    if (!super::init(dict)) {
        return false;
    }
    atomic_init(&suspended, false);
    atomic_init(&transportActive, false);
    atomic_init(&stopping, false);
    atomic_init(&smcSubmitted, false);
    atomic_init(&smcLux, ish::kSmcLuxInvalid);
    atomic_init(&smcNotifyCount, 0u);
    atomic_init(&smcNotifyPosted, false);
    return true;
}

IOService *TGLIshAls::probe(IOService *provider, SInt32 *score) {
    if (hasBootArg("-tglishoff")) {
        LOG("disabled via -tglishoff boot-arg");
        return nullptr;
    }
    auto *dev = OSDynamicCast(IOPCIDevice, provider);
    if (!dev) {
        return nullptr;
    }
    const uint32_t id = dev->configRead32(kIOPCIConfigVendorID);
    const uint16_t vendor = static_cast<uint16_t>(id & 0xFFFFu);
    const uint16_t device = static_cast<uint16_t>((id >> 16) & 0xFFFFu);
    if (vendor != ish::kPciVendorIntel || device != ish::kPciDeviceIshTglLp) {
        return nullptr;
    }
    const uint32_t revReg = dev->configRead32(kIOPCIConfigRevisionID);
    const uint8_t rev = static_cast<uint8_t>(revReg & 0xFFu);
    const uint32_t subsys = dev->configRead32(kIOPCIConfigSubSystemVendorID);
    if (subsys != ish::kPciSubsystemHp8716) {
        LOG("probe warning: unexpected subsystem 0x%08x (expected 0x%08x), rev 0x%02x",
            subsys, ish::kPciSubsystemHp8716, rev);
    }
    return super::probe(provider, score);
}

uint32_t TGLIshAls::mmioRead32(uint32_t offset) const {
    if (!mmioBase) {
        return 0xFFFFFFFFu;
    }
    return *reinterpret_cast<const volatile uint32_t *>(mmioBase + offset);
}

void TGLIshAls::mmioWrite32(uint32_t offset, uint32_t val) const {
    if (!mmioBase) {
        return;
    }
    *reinterpret_cast<volatile uint32_t *>(mmioBase + offset) = val;
}

void TGLIshAls::quiesceHardwareDma() {
    if (!mmioBase) {
        return;
    }
    const uint16_t cmd = pci ? pci->configRead16(kIOPCIConfigCommand) : 0u;
    if ((cmd & kIOPCICommandMemorySpace) == 0u) {
        return;
    }
    const uint32_t curPimr = mmioRead32(ish::kRegPimrBxt);
    if (curPimr != 0xFFFFFFFFu) {
        mmioWrite32(ish::kRegPimrBxt, curPimr & ~ish::kPimrIntEnBit);
        (void)mmioRead32(ish::kRegFwsts);
    }
    const uint32_t hc = mmioRead32(ish::kRegHostComm);
    if (hc != 0xFFFFFFFFu) {
        mmioWrite32(ish::kRegHostComm, hc & ~ish::kHostCommReadyBit);
    }
    mmioWrite32(ish::kRegIshRmp2, 0u);
    for (int step = 0; step < 4; ++step) {
        const uint32_t fwsts = mmioRead32(ish::kRegFwsts);
        if (fwsts == 0xFFFFFFFFu || (fwsts & ish::kFwstsInDmaMask) == 0u) {
            break;
        }
        IOSleep(5);
    }
}

bool TGLIshAls::setupVirtualSmcKeys() {
    static constexpr SMC_KEY kKeyAL   = SMC_MAKE_IDENTIFIER('A', 'L', '!', ' ');
    static constexpr SMC_KEY kKeyALI0 = SMC_MAKE_IDENTIFIER('A', 'L', 'I', '0');
    static constexpr SMC_KEY kKeyALI1 = SMC_MAKE_IDENTIFIER('A', 'L', 'I', '1');
    static constexpr SMC_KEY kKeyALRV = SMC_MAKE_IDENTIFIER('A', 'L', 'R', 'V');
    static constexpr SMC_KEY kKeyALV0 = SMC_MAKE_IDENTIFIER('A', 'L', 'V', '0');
    static constexpr SMC_KEY kKeyALV1 = SMC_MAKE_IDENTIFIER('A', 'L', 'V', '1');
    static constexpr SMC_KEY kKeyLKSB = SMC_MAKE_IDENTIFIER('L', 'K', 'S', 'B');
    static constexpr SMC_KEY kKeyLKSS = SMC_MAKE_IDENTIFIER('L', 'K', 'S', 'S');
    static constexpr SMC_KEY kKeyMSLD = SMC_MAKE_IDENTIFIER('M', 'S', 'L', 'D');

    forceBits = new IshAlsForceBits();
    if (!forceBits) {
        return false;
    }
    lightValue = new IshAlsLightValue(&smcLux, forceBits);
    if (!lightValue) {
        delete forceBits;
        forceBits = nullptr;
        return false;
    }

    const AlsSensorInfo sensorPrimary { 7u, 1u, 6u, 0u };
    const AlsSensorInfo sensorAbsent  { 0u, 0u, 0u, 0u };
    const uint8_t emptyAlv[10] {};
    const LkbStub lkb { 0u, 1u };
    const LksStub lks { 0u, 1u };

    bool ok = true;
    ok &= VirtualSMCAPI::addKey(kKeyAL, vsmcPlugin.data,
        VirtualSMCAPI::valueWithUint16(0u, forceBits, SMC_KEY_ATTRIBUTE_READ | SMC_KEY_ATTRIBUTE_WRITE));
    if (!ok) {
        // valueWithUint16 deletes forceBits on failure; avoid dangling pointer
        forceBits = nullptr;
        delete lightValue;
        lightValue = nullptr;
        vsmcPlugin.data.deinit();
        return false;
    }

    ok &= VirtualSMCAPI::addKey(kKeyALI0, vsmcPlugin.data,
        VirtualSMCAPI::valueWithData(reinterpret_cast<const SMC_DATA *>(&sensorPrimary), sizeof(sensorPrimary),
            SmcKeyTypeAli, nullptr, SMC_KEY_ATTRIBUTE_CONST | SMC_KEY_ATTRIBUTE_READ));
    ok &= VirtualSMCAPI::addKey(kKeyALI1, vsmcPlugin.data,
        VirtualSMCAPI::valueWithData(reinterpret_cast<const SMC_DATA *>(&sensorAbsent), sizeof(sensorAbsent),
            SmcKeyTypeAli, nullptr, SMC_KEY_ATTRIBUTE_CONST | SMC_KEY_ATTRIBUTE_READ));
    ok &= VirtualSMCAPI::addKey(kKeyALRV, vsmcPlugin.data,
        VirtualSMCAPI::valueWithUint16(1u, nullptr, SMC_KEY_ATTRIBUTE_CONST | SMC_KEY_ATTRIBUTE_READ));
    ok &= VirtualSMCAPI::addKey(kKeyALV0, vsmcPlugin.data,
        VirtualSMCAPI::valueWithData(emptyAlv, sizeof(emptyAlv),
            SmcKeyTypeAlv, lightValue, SMC_KEY_ATTRIBUTE_READ | SMC_KEY_ATTRIBUTE_WRITE));
    ok &= VirtualSMCAPI::addKey(kKeyALV1, vsmcPlugin.data,
        VirtualSMCAPI::valueWithData(emptyAlv, sizeof(emptyAlv),
            SmcKeyTypeAlv, nullptr, SMC_KEY_ATTRIBUTE_READ | SMC_KEY_ATTRIBUTE_WRITE));
    ok &= VirtualSMCAPI::addKey(kKeyLKSB, vsmcPlugin.data,
        VirtualSMCAPI::valueWithData(reinterpret_cast<const SMC_DATA *>(&lkb), sizeof(lkb),
            SmcKeyTypeLkb, nullptr, SMC_KEY_ATTRIBUTE_READ | SMC_KEY_ATTRIBUTE_WRITE));
    ok &= VirtualSMCAPI::addKey(kKeyLKSS, vsmcPlugin.data,
        VirtualSMCAPI::valueWithData(reinterpret_cast<const SMC_DATA *>(&lks), sizeof(lks),
            SmcKeyTypeLks, nullptr, SMC_KEY_ATTRIBUTE_READ | SMC_KEY_ATTRIBUTE_WRITE));
    ok &= VirtualSMCAPI::addKey(kKeyMSLD, vsmcPlugin.data,
        VirtualSMCAPI::valueWithUint8(0u));

    if (!ok) {
        vsmcPlugin.data.deinit();
        forceBits = nullptr;
        lightValue = nullptr;
        return false;
    }

    // Inline insertion sort by SMC_KEY (zero Lilu qsort dependency).
    const size_t n = vsmcPlugin.data.size();
    for (size_t i = 1; i < n; ++i) {
        VirtualSMCKeyValue cur = vsmcPlugin.data[i];
        size_t j = i;
        while (j > 0 && VirtualSMCKeyValue::compare(cur.key, vsmcPlugin.data[j - 1].key) < 0) {
            vsmcPlugin.data[j] = vsmcPlugin.data[j - 1];
            --j;
        }
        vsmcPlugin.data[j] = cur;
    }

    return true;
}

bool TGLIshAls::createInterruptSource() {
    int msiIndex = -1;
    int fallbackIndex = -1;
    for (int idx = 0; idx < 4; ++idx) {
        int intType = 0;
        if (pci->getInterruptType(idx, &intType) == kIOReturnSuccess) {
            if ((intType & kIOInterruptTypePCIMessaged) != 0) {
                msiIndex = idx;
                break;
            }
            if (fallbackIndex < 0) {
                fallbackIndex = idx;
            }
        }
    }

    if (msiIndex >= 0) {
        irqModeMsi = true;
        irqIndex = msiIndex;
        irqSource = IOInterruptEventSource::interruptEventSource(this, &TGLIshAls::irqOccurred, pci, irqIndex);
    } else if (fallbackIndex >= 0) {
        irqModeMsi = false;
        irqIndex = fallbackIndex;
        // Exclusive level-triggered INTx on ISHD: XNU auto-masks IOAPIC line in hard-IRQ and unmasks after workLoop runs.
        irqSource = IOInterruptEventSource::interruptEventSource(this, &TGLIshAls::irqOccurred, pci, irqIndex);
    } else {
        LOG("no usable interrupt source on PCI device");
        return false;
    }

    if (!irqSource) {
        LOG("failed to allocate interrupt event source (mode=%s, idx=%d)",
            irqModeMsi ? "MSI" : "INTx-AutoDisable", irqIndex);
        return false;
    }
    return true;
}

bool TGLIshAls::start(IOService *provider) {
    if (!super::start(provider)) {
        return false;
    }

    pci = OSDynamicCast(IOPCIDevice, provider);
    if (!pci) {
        return false;
    }
    pci->retain();

    debugEnabled = hasBootArg("-tglishdbg");
    disableDsm   = hasBootArg("-tglnodsm");
    disableClock = hasBootArg("-tglnoclock");
    disableNub   = hasBootArg("-tglnonub");

    transport.setClockSyncEnabled(!disableClock);
    discoverIshdAcpiDevice();
    const uint32_t dsmMask = queryDsmSupportedMask();
    transport.setDsmConfig(!disableDsm, dsmMask);

    if (!pci->open(this)) {
        LOG("failed to open IOPCIDevice");
        cleanupResources();
        return false;
    }
    pciOpen = true;

    savedPciCmd = pci->configRead16(kIOPCIConfigCommand);
    pci->setMemoryEnable(true);
    pci->setBusMasterEnable(true);

    bar0 = pci->mapDeviceMemoryWithRegister(kIOPCIConfigBaseAddress0);
    if (!bar0 || bar0->getLength() < ish::kMinBar0Size) {
        LOG("failed to map BAR0 (len=0x%llx)", bar0 ? static_cast<unsigned long long>(bar0->getLength()) : 0ULL);
        cleanupResources();
        return false;
    }
    mmioBase = reinterpret_cast<volatile uint8_t *>(bar0->getVirtualAddress());
    if (!mmioBase) {
        LOG("BAR0 virtual address is null");
        cleanupResources();
        return false;
    }

    savedPimr = mmioRead32(ish::kRegPimrBxt);
    savedHostComm = mmioRead32(ish::kRegHostComm);
    savedRmp2 = mmioRead32(ish::kRegIshRmp2);
    setProperty("SavedPIMR", static_cast<unsigned long long>(savedPimr), 32);

    workLoop = IOWorkLoop::workLoop();
    gate = IOCommandGate::commandGate(this);
    timer = IOTimerEventSource::timerEventSource(this, &TGLIshAls::timerFired);
    if (!workLoop || !gate || !timer || !createInterruptSource()) {
        LOG("failed to create workLoop/gate/timer/irqSource");
        cleanupResources();
        return false;
    }

    if (workLoop->addEventSource(gate) != kIOReturnSuccess ||
        workLoop->addEventSource(timer) != kIOReturnSuccess ||
        workLoop->addEventSource(irqSource) != kIOReturnSuccess) {
        LOG("failed to add event sources to workLoop");
        cleanupResources();
        return false;
    }

    if (!setupVirtualSmcKeys()) {
        LOG("failed to prepare VirtualSMC keys");
        cleanupResources();
        return false;
    }

    setProperty("IRQMode", irqModeMsi ? "MSI" : "INTx-AutoDisable");
    setProperty("IRQFallbackPolling", false);
    setProperty("SMCSubmitted", false);
    setProperty("ALSNubPublished", false);
    setProperty("WakeCount", 0ULL, 32);
    setProperty("Suspended", false);
    setProperty("ClockSyncEnabled", !disableClock);
    setProperty("ClockSyncCount", 0ULL, 32);
    setProperty("SystemStateCount", 0ULL, 32);
    setProperty("SystemStateStatus", 0ULL, 32);
    setProperty("DsmEnabled", !disableDsm);
    setProperty("DsmSupportedMask", static_cast<unsigned long long>(dsmMask), 32);
    setProperty("DsmProxyCount", 0ULL, 32);
    setProperty("DsmEvalCount", 0ULL, 32);
    setProperty("FixedClientsSeen", 0ULL, 32);
    setProperty("ALSDarkPermissive", false);
    setProperty("SMCALSNotifyCount", 0ULL, 32);
    setProperty("SMCALSNotifyPosted", false);

    PMinit();
    provider->joinPMtree(this);
    if (registerPowerDriver(this, gPowerStates, 2) != kIOReturnSuccess) {
        LOG("registerPowerDriver failed");
        PMstop();
        cleanupResources();
        return false;
    }
    pmRegistered = true;

    if (IOPMrootDomain *rd = IOService::getPMRootDomain()) {
        pmNotifier = rd->registerInterest(gIOPriorityPowerStateInterest,
                                          &TGLIshAls::pmInterestHandler, this, nullptr);
    }

    vsmcNotifier = VirtualSMCAPI::registerHandler(vsmcNotificationHandler, this);
    if (!vsmcNotifier) {
        LOG("failed to register VirtualSMC notification handler");
        cleanupResources();
        return false;
    }

    gate->runAction(gatedStartTransport);
    registerService();
    LOG("started (irq=%s idx=%d savedPimr=0x%08x clock=%d dsm=%d mask=0x%x nub=%d)",
        irqModeMsi ? "MSI" : "INTx-AutoDisable", irqIndex, savedPimr,
        disableClock ? 0 : 1, disableDsm ? 0 : 1, dsmMask, disableNub ? 0 : 1);
    return true;
}

void TGLIshAls::cleanupResources() {
    atomic_store_explicit(&stopping, true, memory_order_release);

    if (pmNotifier) {
        pmNotifier->remove();
        pmNotifier = nullptr;
    }

    if (vsmcNotifier) {
        vsmcNotifier->remove();
        vsmcNotifier = nullptr;
    }

    if (gate) {
        gate->runAction(gatedStop);
    } else {
        if (timer) {
            timer->cancelTimeout();
        }
        if (irqSource && irqEnabled) {
            irqSource->disable();
            irqEnabled = false;
        }
        quiesceHardwareDma();
    }

    if (alsNub) {
        alsNub->terminate(kIOServiceRequired | kIOServiceSynchronous);
        alsNub->PMstop();
        alsNub->detach(this);
        OSSafeReleaseNULL(alsNub);
    }

    if (pmRegistered) {
        PMstop();
        pmRegistered = false;
    }

    if (timer) {
        timer->cancelTimeout();
        if (workLoop) {
            workLoop->removeEventSource(timer);
        }
        OSSafeReleaseNULL(timer);
    }
    if (irqSource) {
        if (workLoop) {
            workLoop->removeEventSource(irqSource);
        }
        OSSafeReleaseNULL(irqSource);
    }
    if (gate) {
        if (workLoop) {
            workLoop->removeEventSource(gate);
        }
        OSSafeReleaseNULL(gate);
    }
    OSSafeReleaseNULL(workLoop);

    if (mmioBase && !atomic_load_explicit(&smcSubmitted, memory_order_acquire)) {
        const uint16_t cmd = pci ? pci->configRead16(kIOPCIConfigCommand) : 0u;
        if ((cmd & kIOPCICommandMemorySpace) != 0u) {
            mmioWrite32(ish::kRegPimrBxt, savedPimr);
            mmioWrite32(ish::kRegHostComm, savedHostComm);
            mmioWrite32(ish::kRegIshRmp2, savedRmp2);
        }
    }
    mmioBase = nullptr;
    OSSafeReleaseNULL(bar0);

    if (!atomic_load_explicit(&smcSubmitted, memory_order_acquire)) {
        vsmcPlugin.data.deinit();
        vsmcPlugin.dataHidden.deinit();
        forceBits = nullptr;
        lightValue = nullptr;
    }

    if (pci && pciOpen) {
        pci->close(this);
        pciOpen = false;
    }
}

void TGLIshAls::stop(IOService *provider) {
    cleanupResources();
    super::stop(provider);
}

void TGLIshAls::free() {
    OSSafeReleaseNULL(ishdAcpi);
    OSSafeReleaseNULL(pci);
    super::free();
}

void TGLIshAls::discoverIshdAcpiDevice() {
    if (disableDsm || !pci) {
        return;
    }
    if (OSString *path = OSDynamicCast(OSString, pci->getProperty("acpi-path"))) {
        IORegistryEntry *entry = IORegistryEntry::fromPath(path->getCStringNoCopy());
        ishdAcpi = OSDynamicCast(IOACPIPlatformDevice, entry);
        if (ishdAcpi) {
            return;
        }
        OSSafeReleaseNULL(entry);
    }
    IORegistryIterator *it = IORegistryIterator::iterateOver(gIOACPIPlane, kIORegistryIterateRecursively);
    if (!it) {
        return;
    }
    while (IORegistryEntry *entry = it->getNextObject()) {
        auto *cand = OSDynamicCast(IOACPIPlatformDevice, entry);
        if (!cand) {
            continue;
        }
        UInt32 adr = 0;
        const bool adrMatch = (cand->evaluateInteger("_ADR", &adr) == kIOReturnSuccess && adr == 0x00120000u);
        const bool nameMatch = strEqual(cand->getName(), "ISHD");
        if (nameMatch || adrMatch) {
            cand->retain();
            ishdAcpi = cand;
            break;
        }
    }
    it->release();
}

uint32_t TGLIshAls::queryDsmSupportedMask() {
    if (disableDsm || !ishdAcpi) {
        return 0u;
    }
    if (ishdAcpi->validateObject("_DSM") != kIOReturnSuccess) {
        return 0u;
    }
    uint32_t mask = 0u;
    if (evaluateIshdDsm(0u, nullptr, 0u, &mask)) {
        return mask;
    }
    return 0u;
}

bool TGLIshAls::evaluateIshdDsm(uint32_t funcIndex, const uint8_t *args, uint8_t argLen, uint32_t *outFirstWord) {
    if (disableDsm || !ishdAcpi) {
        return false;
    }
    OSData *guid = OSData::withBytes(ish::kIshDsmGuidBytes, sizeof(ish::kIshDsmGuidBytes));
    OSNumber *rev = OSNumber::withNumber(static_cast<unsigned long long>(0u), 32);
    OSNumber *fn = OSNumber::withNumber(static_cast<unsigned long long>(funcIndex), 32);
    OSArray *pkg = OSArray::withCapacity(argLen > 0u ? argLen : 1u);
    if (!guid || !rev || !fn || !pkg) {
        OSSafeReleaseNULL(guid);
        OSSafeReleaseNULL(rev);
        OSSafeReleaseNULL(fn);
        OSSafeReleaseNULL(pkg);
        return false;
    }
    bool pkgOk = true;
    for (uint8_t i = 0; i < argLen && args != nullptr; ++i) {
        OSNumber *elem = OSNumber::withNumber(static_cast<unsigned long long>(args[i]), 8);
        if (!elem || !pkg->setObject(elem)) {
            pkgOk = false;
        }
        OSSafeReleaseNULL(elem);
        if (!pkgOk) {
            break;
        }
    }

    OSObject *params[4] = { guid, rev, fn, pkg };
    OSObject *result = nullptr;
    const IOReturn ret = pkgOk ? ishdAcpi->evaluateObject("_DSM", &result, params, 4) : kIOReturnNoMemory;
    for (OSObject *p : params) {
        OSSafeReleaseNULL(p);
    }

    if (ret == kIOReturnSuccess) {
        ++dsmEvalCount;
        if (outFirstWord != nullptr) {
            *outFirstWord = 0u;
            if (OSData *dataObj = OSDynamicCast(OSData, result)) {
                const uint32_t len = dataObj->getLength();
                const auto *bytes = static_cast<const uint8_t *>(dataObj->getBytesNoCopy());
                if (bytes != nullptr) {
                    const uint32_t copyLen = (len < 4u) ? len : 4u;
                    uint32_t w = 0u;
                    for (uint32_t b = 0; b < copyLen; ++b) {
                        w |= static_cast<uint32_t>(bytes[b]) << (b * 8u);
                    }
                    *outFirstWord = w;
                }
            } else if (OSNumber *numObj = OSDynamicCast(OSNumber, result)) {
                *outFirstWord = numObj->unsigned32BitValue();
            }
        }
    }
    OSSafeReleaseNULL(result);
    return ret == kIOReturnSuccess;
}

void TGLIshAls::processPendingDsmWork() {
    ish::DsmWorkItem item {};
    while (transport.popPendingDsm(item)) {
        if (disableDsm || !ishdAcpi) {
            DBG("DSM proxy ignored (disabled=%d acpi=%d func=%u)",
                disableDsm ? 1 : 0, ishdAcpi ? 1 : 0, item.funcIndex);
            continue;
        }
        uint32_t outVal = 0u;
        const bool ok = evaluateIshdDsm(item.funcIndex, item.args, item.argLen, &outVal);
        DBG("DSM proxy func=%u argLen=%u ok=%d out=0x%x",
            item.funcIndex, item.argLen, ok ? 1 : 0, outVal);
    }
}

IOWorkLoop *TGLIshAls::getWorkLoop() const {
    return workLoop;
}

IOReturn TGLIshAls::setPowerState(unsigned long powerStateOrdinal, IOService *) {
    if (atomic_load_explicit(&stopping, memory_order_acquire) || !gate) {
        return kIOPMAckImplied;
    }
    if (powerStateOrdinal == 0 && powerState != 0) {
        powerState = 0;
        gate->runAction(gatedPowerSleep);
    } else if (powerStateOrdinal == 1 && powerState == 0) {
        powerState = 1;
        gate->runAction(gatedPowerWake);
    }
    return kIOPMAckImplied;
}

bool TGLIshAls::vsmcNotificationHandler(void *target, void *, IOService *newService, IONotifier *) {
    auto *self = static_cast<TGLIshAls *>(target);
    if (!self || !newService || atomic_load_explicit(&self->stopping, memory_order_acquire)) {
        return false;
    }
    if (atomic_load_explicit(&self->smcSubmitted, memory_order_acquire)) {
        return true;
    }

    const IOReturn ret = newService->callPlatformFunction(
        VirtualSMCAPI::SubmitPlugin, true, self, &self->vsmcPlugin, nullptr, nullptr);
    if (ret == kIOReturnSuccess) {
        atomic_store_explicit(&self->smcSubmitted, true, memory_order_release);
        atomic_store_explicit(&gSmcSubmitted, true, memory_order_release);
        self->setProperty("SMCSubmitted", true);
        if (atomic_load_explicit(&self->smcLux, memory_order_acquire) != ish::kSmcLuxInvalid) {
            const bool posted = VirtualSMCAPI::postInterrupt(SmcEventALSChange);
            atomic_store_explicit(&self->smcNotifyPosted, posted, memory_order_release);
            if (posted) {
                atomic_fetch_add_explicit(&self->smcNotifyCount, 1u, memory_order_acq_rel);
            }
        }
        if (!self->disableNub && self->gate) {
            self->gate->runAction(gatedPublishAlsNub);
        }
        return true;
    }
    if (ret != kIOReturnUnsupported) {
        IOLog("TGLIshAls: SubmitPlugin failed (0x%x)\n", ret);
    }
    return false;
}

IOReturn TGLIshAls::pmInterestHandler(void *target, void *, UInt32 messageType,
                                      IOService *, void *messageArgument, vm_size_t) {
    auto *self = static_cast<TGLIshAls *>(target);
    if (!self || atomic_load_explicit(&self->stopping, memory_order_acquire) || !self->gate) {
        return kIOReturnSuccess;
    }
    if (messageType == kIOMessageSystemCapabilityChange && messageArgument != nullptr) {
        const auto *caps = static_cast<const IOPMSystemCapabilityChangeParameters *>(messageArgument);
        if ((caps->changeFlags & (kIOPMSystemCapabilityWillChange | kIOPMSystemCapabilityDidChange)) != 0u) {
            const bool cpuOn = (caps->toCapabilities & kIOPMSystemCapabilityCPU) != 0u;
            const bool gfxOn = (caps->toCapabilities & kIOPMSystemCapabilityGraphics) != 0u;
            if (!atomic_load_explicit(&self->suspended, memory_order_acquire)) {
                self->gate->runAction(gatedDisplayState,
                                      reinterpret_cast<void *>(static_cast<uintptr_t>(cpuOn ? 1u : 0u)),
                                      reinterpret_cast<void *>(static_cast<uintptr_t>(gfxOn ? 1u : 0u)));
            }
        }
    }
    return kIOReturnSuccess;
}

void TGLIshAls::publishAlsNub() {
    if (alsNub != nullptr || disableNub || atomic_load_explicit(&stopping, memory_order_acquire)) {
        return;
    }
    IOService *nub = OSTypeAlloc(IOService);
    if (!nub) {
        LOG("failed to allocate ACPI0008 ALS nub");
        return;
    }
    if (!nub->init()) {
        nub->release();
        LOG("failed to init ACPI0008 ALS nub");
        return;
    }
    static constexpr char kAcpiAlsName[] = "ACPI0008";
    nub->setName(kAcpiAlsName);
    setDataProperty(nub, "name", kAcpiAlsName, sizeof(kAcpiAlsName));
    setDataProperty(nub, "compatible", kAcpiAlsName, sizeof(kAcpiAlsName));
    if (!nub->attach(this)) {
        nub->release();
        LOG("failed to attach ACPI0008 ALS nub");
        return;
    }
    nub->PMinit();
    this->joinPMtree(nub);
    alsNub = nub;
    alsNub->registerService();
    setProperty("ALSNubPublished", true);
    LOG("published ACPI0008 nub for AppleSMCLMU");
}

IOReturn TGLIshAls::gatedPublishAlsNub(OSObject *owner, void *, void *, void *, void *) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self) {
        return kIOReturnBadArgument;
    }
    self->publishAlsNub();
    return kIOReturnSuccess;
}

IOReturn TGLIshAls::gatedStartTransport(OSObject *owner, void *, void *, void *, void *) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self) {
        return kIOReturnBadArgument;
    }
    self->restartTransport();
    return kIOReturnSuccess;
}

IOReturn TGLIshAls::gatedDisplayState(OSObject *owner, void *arg0, void *arg1, void *, void *) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self || atomic_load_explicit(&self->stopping, memory_order_acquire) ||
        atomic_load_explicit(&self->suspended, memory_order_acquire) ||
        !atomic_load_explicit(&self->transportActive, memory_order_acquire)) {
        return kIOReturnSuccess;
    }
    const bool awake = (arg0 != nullptr);
    const bool displayOn = (arg1 != nullptr);
    const uint64_t nowNs = currentTimeNs();
    if (self->transport.setHostPowerState(awake, displayOn, nowNs, currentUtcUs(), currentMonoUs())) {
        self->pumpTx();
        self->handleTransportUpdates(nowNs);
    }
    return kIOReturnSuccess;
}

IOReturn TGLIshAls::gatedPowerSleep(OSObject *owner, void *, void *, void *, void *) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self) {
        return kIOReturnBadArgument;
    }
    if (atomic_load_explicit(&self->transportActive, memory_order_acquire)) {
        const uint64_t nowNs = currentTimeNs();
        self->transport.setHostPowerState(false, false, nowNs, currentUtcUs(), currentMonoUs());
        self->pumpTx();
    }
    atomic_store_explicit(&self->suspended, true, memory_order_release);
    atomic_store_explicit(&self->transportActive, false, memory_order_release);
    atomic_store_explicit(&self->smcLux, ish::kSmcLuxInvalid, memory_order_release);

    if (self->lastPostedValid && atomic_load_explicit(&self->smcSubmitted, memory_order_acquire)) {
        VirtualSMCAPI::postInterrupt(SmcEventALSChange);
    }
    self->lastPostedValid = false;

    if (self->timer) {
        self->timer->cancelTimeout();
    }
    if (self->irqSource && self->irqEnabled) {
        self->irqSource->disable();
        self->irqEnabled = false;
    }

    self->quiesceHardwareDma();
    self->setProperty("Suspended", true);
    self->setProperty("TransportState", "Suspended");
    self->setProperty("SystemStateStatus", static_cast<unsigned long long>(self->transport.sysStateStatus()), 32);
    self->setProperty("SystemStateCount", static_cast<unsigned long long>(self->transport.sysStateCount()), 32);
    self->setProperty("ALSDarkPermissive", false);
    return kIOReturnSuccess;
}

IOReturn TGLIshAls::gatedPowerWake(OSObject *owner, void *, void *, void *, void *) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self) {
        return kIOReturnBadArgument;
    }
    atomic_store_explicit(&self->suspended, false, memory_order_release);
    ++self->wakeCount;
    if (self->pci) {
        self->pci->setMemoryEnable(true);
        self->pci->setBusMasterEnable(true);
    }
    self->setProperty("Suspended", false);
    self->setProperty("WakeCount", static_cast<unsigned long long>(self->wakeCount), 32);
    self->restartTransport();
    return kIOReturnSuccess;
}

IOReturn TGLIshAls::gatedStop(OSObject *owner, void *, void *, void *, void *) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self) {
        return kIOReturnBadArgument;
    }
    atomic_store_explicit(&self->transportActive, false, memory_order_release);
    atomic_store_explicit(&self->smcLux, ish::kSmcLuxInvalid, memory_order_release);
    if (self->timer) {
        self->timer->cancelTimeout();
    }
    if (self->irqSource && self->irqEnabled) {
        self->irqSource->disable();
        self->irqEnabled = false;
    }
    self->quiesceHardwareDma();
    return kIOReturnSuccess;
}

void TGLIshAls::restartTransport() {
    if (!mmioBase || atomic_load_explicit(&stopping, memory_order_acquire)) {
        return;
    }
    if (timer) {
        timer->cancelTimeout();
    }

    // Drain any stale RX doorbell or PISR bits before starting fresh reset.
    const uint32_t staleDrbl = mmioRead32(ish::kRegIsh2HostDrbl);
    if (staleDrbl != 0xFFFFFFFFu && ish::drblBusy(staleDrbl)) {
        mmioWrite32(ish::kRegIsh2HostDrbl, 0u);
        (void)mmioRead32(ish::kRegFwsts);
    }
    const uint32_t stalePisr = mmioRead32(ish::kRegPisrBxt);
    if (stalePisr != 0u && stalePisr != 0xFFFFFFFFu) {
        mmioWrite32(ish::kRegPisrBxt, stalePisr);
    }

    // Assert HOST_COMM ready bit 7 and enable RMP2 DMA flag (used by FW handshake; host stays inline MMIO).
    const uint32_t hc = mmioRead32(ish::kRegHostComm);
    if (hc != 0xFFFFFFFFu) {
        mmioWrite32(ish::kRegHostComm, hc | ish::kHostCommReadyBit);
    }
    mmioWrite32(ish::kRegIshRmp2, ish::kRmp2DmaEnabledBit);

    const uint64_t nowNs = currentTimeNs();
    transport.setHostPowerState(true, true, nowNs, currentUtcUs(), currentMonoUs());
    transport.startInit(nowNs);
    lastStage = ish::IshTransport::Stage::Idle;
    lastPostedValid = false;
    lastPostedMilliLux = 0;
    lastClockSyncCount = 0;
    lastSysStateCount = 0;
    lastDsmProxyCount = 0;
    lastFixedClients = 0;
    lastSampleCountPublished = 0;
    rxFrameCount = 0;
    txFrameCount = 0;
    irqActionCount = 0;
    spuriousIrqCount = 0;
    consecutiveEmptyIrqs = 0;
    timerDrainRxCount = 0;
    mngRxCmplCount = 0;
    host2IshStallTicks = 0;
    telemetryTickDiv = 0;
    irqFallbackPolling = false;
    setProperty("IRQFallbackPolling", false);
    atomic_store_explicit(&smcNotifyCount, 0u, memory_order_release);
    atomic_store_explicit(&smcNotifyPosted, false, memory_order_release);
    origFeatPublished = false;
    reqFeatPublished = false;
    curFeatPublished = false;
    hidDevListPublished = false;
    alsDescSlicePublished = false;
    removeProperty("ALSFeatureOriginal");
    removeProperty("ALSFeatureRequested");
    removeProperty("ALSFeatureCurrent");
    removeProperty("ALSFeatGetHdr");
    removeProperty("ALSReportDescSlice");
    removeProperty("HIDDeviceList");
    atomic_store_explicit(&smcLux, ish::kSmcLuxInvalid, memory_order_release);
    atomic_store_explicit(&transportActive, true, memory_order_release);

    const uint32_t curPimr = mmioRead32(ish::kRegPimrBxt);
    if (curPimr != 0xFFFFFFFFu) {
        mmioWrite32(ish::kRegPimrBxt, ish::computeInitPimr(curPimr));
        (void)mmioRead32(ish::kRegFwsts);
    }
    if (irqSource && !irqEnabled) {
        irqSource->enable();
        irqEnabled = true;
    }

    pumpTx();
    handleTransportUpdates(nowNs);
    scheduleNextTick();
}

void TGLIshAls::pumpTx() {
    if (!mmioBase || atomic_load_explicit(&suspended, memory_order_acquire) ||
        !atomic_load_explicit(&transportActive, memory_order_acquire)) {
        return;
    }
    if (transport.consumeNeedHostReady()) {
        const uint32_t hc = mmioRead32(ish::kRegHostComm);
        if (hc != 0xFFFFFFFFu && (hc & ish::kHostCommReadyBit) == 0u) {
            mmioWrite32(ish::kRegHostComm, hc | ish::kHostCommReadyBit);
            (void)mmioRead32(ish::kRegFwsts);
        }
    }
    while (transport.hasTxPending()) {
        const uint32_t drbl = mmioRead32(ish::kRegHost2IshDrbl);
        if (drbl == 0xFFFFFFFFu || ish::drblBusy(drbl)) {
            break;
        }
        ish::TxFrame frame {};
        if (!transport.popTxFrame(frame)) {
            break;
        }
        const size_t dwords = (static_cast<size_t>(frame.len) + 3u) / 4u;
        for (size_t i = 0; i < dwords; ++i) {
            uint8_t chunk[4] {};
            for (size_t b = 0; b < 4u; ++b) {
                const size_t idx = i * 4u + b;
                if (idx < frame.len) {
                    chunk[b] = frame.data[idx];
                }
            }
            mmioWrite32(ish::kRegHost2IshMsg + static_cast<uint32_t>(i * 4u), ish::readLe32(chunk));
        }
        const uint32_t outDrbl = ish::makeDrbl(frame.proto, frame.mngCmd, frame.len);
        mmioWrite32(ish::kRegHost2IshDrbl, outDrbl);
        (void)mmioRead32(ish::kRegFwsts);
        ++txFrameCount;
        DBG("TX proto=%u mng=%u len=%u drbl=0x%08x", frame.proto, frame.mngCmd, frame.len, outDrbl);
    }
}

void TGLIshAls::enterFailed(const char *reason) {
    atomic_store_explicit(&transportActive, false, memory_order_release);
    atomic_store_explicit(&smcLux, ish::kSmcLuxInvalid, memory_order_release);
    if (lastPostedValid && atomic_load_explicit(&smcSubmitted, memory_order_acquire)) {
        VirtualSMCAPI::postInterrupt(SmcEventALSChange);
    }
    lastPostedValid = false;

    if (timer) {
        timer->cancelTimeout();
    }
    if (irqSource && irqEnabled) {
        irqSource->disable();
        irqEnabled = false;
    }
    quiesceHardwareDma();

    const char *msg = (reason && reason[0]) ? reason : "transport failure";
    setProperty("TransportState", "Failed");
    setProperty("TransportError", msg);
    LOG("transport entered Failed state: %s", msg);
}

void TGLIshAls::publishTelemetry(bool sampleChanged) {
    const uint32_t fwsts = mmioBase ? mmioRead32(ish::kRegFwsts) : 0xFFFFFFFFu;
    const auto st = transport.stage();
    const uint32_t sCnt = transport.sampleCount();
    lastSampleCountPublished = sCnt;

    setProperty("TransportState", transport.stageName());
    setProperty("SMCSubmitted", atomic_load_explicit(&smcSubmitted, memory_order_acquire));
    setProperty("ALSNubPublished", alsNub != nullptr);
    if (fwsts != 0xFFFFFFFFu) {
        setProperty("FirmwareStatus", static_cast<unsigned long long>(fwsts), 32);
        setProperty("FirmwareState",
                    static_cast<unsigned long long>((fwsts & ish::kFwstsStateMask) >> ish::kFwstsStateShift), 8);
    }
    if (mmioBase) {
        setProperty("MMIOPimr", static_cast<unsigned long long>(mmioRead32(ish::kRegPimrBxt)), 32);
        setProperty("MMIOPisr", static_cast<unsigned long long>(mmioRead32(ish::kRegPisrBxt)), 32);
        setProperty("MMIOHostComm", static_cast<unsigned long long>(mmioRead32(ish::kRegHostComm)), 32);
        setProperty("MMIOHost2IshDrbl", static_cast<unsigned long long>(mmioRead32(ish::kRegHost2IshDrbl)), 32);
        setProperty("MMIOIsh2HostDrbl", static_cast<unsigned long long>(mmioRead32(ish::kRegIsh2HostDrbl)), 32);
        setProperty("MMIORmp2", static_cast<unsigned long long>(mmioRead32(ish::kRegIshRmp2)), 32);
    }
    setProperty("TxRingCount", static_cast<unsigned long long>(transport.txPendingCount()), 32);
    setProperty("RxFrameCount", static_cast<unsigned long long>(rxFrameCount), 32);
    setProperty("TxFrameCount", static_cast<unsigned long long>(txFrameCount), 32);
    setProperty("IrqActionCount", static_cast<unsigned long long>(irqActionCount), 32);
    setProperty("SpuriousIrqCount", static_cast<unsigned long long>(spuriousIrqCount), 32);
    setProperty("TimerDrainRxCount", static_cast<unsigned long long>(timerDrainRxCount), 32);
    setProperty("MngRxCmplCount", static_cast<unsigned long long>(mngRxCmplCount), 32);
    setProperty("Host2IshStallTicks", static_cast<unsigned long long>(host2IshStallTicks), 32);
    setProperty("IRQFallbackPolling", irqFallbackPolling);
    setProperty("HIDClientAddress", static_cast<unsigned long long>(transport.hidFwAddr()), 8);
    setProperty("HIDMaxMsgLen", static_cast<unsigned long long>(transport.hidMaxMsg()), 32);
    setProperty("HIDConnected", transport.hidConnected());
    setProperty("HIDDevCount", static_cast<unsigned long long>(transport.hidDevCount()), 8);
    setProperty("HIDTxCredits", static_cast<unsigned long long>(transport.hidTxCredits()), 32);
    setProperty("HIDTxPending", transport.hidTxPending());
    setProperty("HIDFlowCtrlRxCount", static_cast<unsigned long long>(transport.hidFlowCtrlRxCount()), 32);
    setProperty("RXFlowControlPending", transport.rxFlowControlPending());
    setProperty("FlowCreditsSent", static_cast<unsigned long long>(transport.flowCreditsSent()), 32);
    setProperty("OverflowDrops", static_cast<unsigned long long>(transport.overflowDrops()), 32);
    setProperty("ALSPublishCount", static_cast<unsigned long long>(transport.publishReportCount()), 32);
    setProperty("ALSGetInputRespCount", static_cast<unsigned long long>(transport.getInputRespCount()), 32);
    setProperty("ALSDeviceID", static_cast<unsigned long long>(transport.alsDevId()), 8);
    setProperty("ALSLastHostifCmd", static_cast<unsigned long long>(transport.lastHostifCmd()), 8);
    setProperty("ALSLastHostifStatus", static_cast<unsigned long long>(transport.lastHostifStatus()), 8);
    setProperty("ALSLastHostifLen", static_cast<unsigned long long>(transport.lastHostifLen()), 16);
    setProperty("ALSFeatGetStatus", static_cast<unsigned long long>(transport.featGetStatus()), 8);
    setProperty("ALSFeatGetFlags", static_cast<unsigned long long>(transport.featGetFlags()), 8);
    setProperty("ALSFeatGetDeclaredSize", static_cast<unsigned long long>(transport.featGetDeclaredSize()), 16);
    setProperty("ALSFeatGetAvailLen", static_cast<unsigned long long>(transport.featGetAvailLen()), 16);
    setProperty("ALSFeatGetAttempts", static_cast<unsigned long long>(transport.featGetAttempts()), 8);
    setProperty("ALSFeatZeroHdrSize", transport.featUseZeroHdrSize());
    setProperty("ALSFeatSetStatus", static_cast<unsigned long long>(transport.featSetStatus()), 8);
    setProperty("ALSFeatVerifyStatus", static_cast<unsigned long long>(transport.featVerifyStatus()), 8);
    setProperty("ClockSyncCount", static_cast<unsigned long long>(transport.clockSyncCount()), 32);
    setProperty("SystemStateCount", static_cast<unsigned long long>(transport.sysStateCount()), 32);
    setProperty("SystemStateStatus", static_cast<unsigned long long>(transport.sysStateStatus()), 32);
    setProperty("DsmProxyCount", static_cast<unsigned long long>(transport.dsmProxyCount()), 32);
    setProperty("DsmEvalCount", static_cast<unsigned long long>(dsmEvalCount), 32);
    setProperty("FixedClientsSeen", static_cast<unsigned long long>(transport.fixedClientsSeen()), 32);
    setProperty("ALSDarkPermissive", transport.isAlsDarkPermissive());
    setProperty("SMCALSNotifyCount",
                static_cast<unsigned long long>(atomic_load_explicit(&smcNotifyCount, memory_order_acquire)), 32);
    setProperty("SMCALSNotifyPosted", atomic_load_explicit(&smcNotifyPosted, memory_order_acquire));
    setProperty("ALSSampleCount", static_cast<unsigned long long>(sCnt), 32);
    setProperty("ALSRawIlluminance", static_cast<unsigned long long>(transport.rawIllum()), 32);
    setProperty("ALSMilliLux", static_cast<unsigned long long>(transport.milliLux()), 64);
    setProperty("SMCLuxFixed", static_cast<unsigned long long>(transport.fixedLux()), 32);
    setProperty("ALSLastRxNS", static_cast<unsigned long long>(transport.lastSampleRxNs()), 64);

    if (transport.alsIntervalMs() != 0u) {
        setProperty("ALSIntervalMs", static_cast<unsigned long long>(transport.alsIntervalMs()), 32);
    }
    if (transport.alsSensitivity() != 0u) {
        setProperty("ALSSensitivity", static_cast<unsigned long long>(transport.alsSensitivity()), 32);
    }
    if (transport.hidDevListLen() > 0u && !hidDevListPublished) {
        hidDevListPublished = setDataProperty(this, "HIDDeviceList",
                                              transport.hidDevListData(), transport.hidDevListLen());
    }
    if (transport.alsDesc().found) {
        const int32_t expo = static_cast<int32_t>(ish::decodeUnitExponent(transport.alsDesc().unitExpoRaw));
        setProperty("ALSReportID", static_cast<unsigned long long>(transport.alsDesc().inputReportId), 8);
        setProperty("ALSUnitExponent", static_cast<unsigned long long>(static_cast<uint32_t>(expo)), 32);
        setProperty("ALSFeatureReportID", static_cast<unsigned long long>(transport.alsDesc().featureReportId), 8);
        setProperty("ALSFeatureByteLen", static_cast<unsigned long long>(transport.alsDesc().featureByteLen), 32);
        setProperty("ALSInputByteLen", static_cast<unsigned long long>(transport.alsDesc().inputByteLen), 32);
        setProperty("ALSControlsVerified", transport.alsControlsVerified());
    }
    if (transport.origFeatLen() > 0u && !origFeatPublished) {
        origFeatPublished = setDataProperty(this, "ALSFeatureOriginal", transport.origFeatData(), transport.origFeatLen());
    }
    if (transport.reqFeatLen() > 0u && (!reqFeatPublished || st == ish::IshTransport::Stage::AlsFeatSet)) {
        reqFeatPublished = setDataProperty(this, "ALSFeatureRequested", transport.reqFeatData(), transport.reqFeatLen());
    }
    if (transport.curFeatLen() > 0u && !curFeatPublished) {
        curFeatPublished = setDataProperty(this, "ALSFeatureCurrent", transport.curFeatData(), transport.curFeatLen());
    }
    if (st == ish::IshTransport::Stage::Streaming && !transport.alsControlsVerified()) {
        if (transport.featGetHdrValid()) {
            (void)setDataProperty(this, "ALSFeatGetHdr", transport.featGetHdr(), 6u);
        }
        if (transport.alsDescSliceLen() > 0u && !alsDescSlicePublished) {
            alsDescSlicePublished = setDataProperty(this, "ALSReportDescSlice",
                                                    transport.alsDescSliceData(), transport.alsDescSliceLen());
        }
    }
    if (transport.featureError()[0] != '\0') {
        setProperty("ALSFeatureError", transport.featureError());
    } else {
        removeProperty("ALSFeatureError");
    }
    if (sampleChanged) {
        setProperty("ALSLastUpdateNS", static_cast<unsigned long long>(currentTimeNs()), 64);
    }
}

void TGLIshAls::handleTransportUpdates(uint64_t nowNs) {
    // Evaluate any queued Client 13/14 _DSM requests safely on IOWorkLoop (outside irqFilter/locks).
    processPendingDsmWork();

    bool sampleChanged = false;
    bool telemetryDirty = false;
    if (transport.consumeSampleUpdated()) {
        const uint32_t newFixed = transport.fixedLux();
        const uint64_t newMilli = transport.milliLux();
        const bool nowValid = (newFixed != ish::kSmcLuxInvalid);
        const bool firstValid = nowValid && !lastPostedValid;

        atomic_store_explicit(&smcLux, newFixed, memory_order_release);

        if (ish::shouldPostAlsChange(lastPostedValid, lastPostedMilliLux, nowValid, newMilli)) {
            lastPostedValid = nowValid;
            lastPostedMilliLux = newMilli;
            sampleChanged = true;
            if (atomic_load_explicit(&smcSubmitted, memory_order_acquire)) {
                const bool posted = VirtualSMCAPI::postInterrupt(SmcEventALSChange);
                atomic_store_explicit(&smcNotifyPosted, posted, memory_order_release);
                if (posted) {
                    atomic_fetch_add_explicit(&smcNotifyCount, 1u, memory_order_acq_rel);
                }
            }
        }
        const uint32_t sCnt = transport.sampleCount();
        if (sCnt != lastSampleCountPublished && sCnt <= 5u) {
            telemetryDirty = true;
        }
        if (debugEnabled || firstValid || sampleChanged) {
            telemetryDirty = true;
            DBG("ALS raw=%u milliLux=%llu fixed=0x%08x dark=%d (samples=%u)",
                transport.rawIllum(), static_cast<unsigned long long>(newMilli), newFixed,
                transport.isAlsDarkPermissive() ? 1 : 0, sCnt);
        }
    }

    const uint32_t cCount = transport.clockSyncCount();
    const uint32_t sCount = transport.sysStateCount();
    const uint32_t dCount = transport.dsmProxyCount();
    const uint32_t fSeen  = transport.fixedClientsSeen();
    if (cCount != lastClockSyncCount || sCount != lastSysStateCount ||
        dCount != lastDsmProxyCount || fSeen != lastFixedClients) {
        lastClockSyncCount = cCount;
        lastSysStateCount = sCount;
        lastDsmProxyCount = dCount;
        lastFixedClients = fSeen;
        telemetryDirty = true;
    }

    const auto st = transport.stage();
    if (st != lastStage) {
        lastStage = st;
        if (st == ish::IshTransport::Stage::Failed) {
            enterFailed(transport.errorMsg());
            return;
        }
        if (st == ish::IshTransport::Stage::Streaming || st == ish::IshTransport::Stage::NoAlsSensor) {
            removeProperty("TransportError");
            if (st == ish::IshTransport::Stage::Streaming) {
                LOG("streaming ALS (devId=%u, rptId=%u, expo=%d, verified=%d, intvl=%u, sens=%u, fgetSt=%u, fgetSz=%u, fgetTry=%u)",
                    transport.alsDevId(), transport.alsDesc().inputReportId,
                    ish::decodeUnitExponent(transport.alsDesc().unitExpoRaw),
                    transport.alsControlsVerified() ? 1 : 0,
                    transport.alsIntervalMs(), transport.alsSensitivity(),
                    transport.featGetStatus(), transport.featGetDeclaredSize(), transport.featGetAttempts());
            } else {
                LOG("HID discovery complete (%u devices), no ALS sensor present", transport.hidDevCount());
            }
        }
        publishTelemetry(sampleChanged);
    } else if (telemetryDirty) {
        publishTelemetry(sampleChanged);
    }
    (void)nowNs;
}

void TGLIshAls::scheduleNextTick() {
    if (!timer || atomic_load_explicit(&stopping, memory_order_acquire) ||
        atomic_load_explicit(&suspended, memory_order_acquire)) {
        return;
    }
    const auto st = transport.stage();
    if (st == ish::IshTransport::Stage::Idle ||
        st == ish::IshTransport::Stage::Failed ||
        st == ish::IshTransport::Stage::NoAlsSensor) {
        return;
    }
    const uint32_t ms = (st == ish::IshTransport::Stage::Streaming)
        ? (irqFallbackPolling ? kFallbackPollTickMs : kStreamingTickMs)
        : kInitTickMs;
    timer->setTimeoutMS(ms);
}

uint32_t TGLIshAls::drainRx(uint64_t nowNs) {
    if (!mmioBase) {
        return 0u;
    }

    const uint32_t pisr = mmioRead32(ish::kRegPisrBxt);
    if (pisr != 0u && pisr != 0xFFFFFFFFu) {
        mmioWrite32(ish::kRegPisrBxt, pisr);
        if ((pisr & ish::kPisrHost2IshBusyClrBit) != 0u) {
            const uint32_t pimr = mmioRead32(ish::kRegPimrBxt);
            if (pimr != 0xFFFFFFFFu && (pimr & ish::kPimrHost2IshBusyClrMaskBit) != 0u) {
                mmioWrite32(ish::kRegPimrBxt, pimr & ~ish::kPimrHost2IshBusyClrMaskBit);
            }
        }
        (void)mmioRead32(ish::kRegFwsts);
    }

    uint32_t drained = 0u;
    for (int iter = 0; iter < 32; ++iter) {
        const uint32_t drbl = mmioRead32(ish::kRegIsh2HostDrbl);
        if (drbl == 0xFFFFFFFFu || !ish::drblBusy(drbl)) {
            break;
        }
        uint8_t rxBuf[ish::kIpcMaxFrameBytes] {};
        uint16_t len = ish::drblLength(drbl);
        if (len > ish::kIpcMaxFrameBytes) {
            len = static_cast<uint16_t>(ish::kIpcMaxFrameBytes);
        }
        const size_t dwords = (static_cast<size_t>(len) + 3u) / 4u;
        for (size_t i = 0; i < dwords; ++i) {
            const uint32_t w = mmioRead32(ish::kRegIsh2HostMsg + static_cast<uint32_t>(i * 4u));
            ish::writeLe32(&rxBuf[i * 4u], w);
        }
        mmioWrite32(ish::kRegIsh2HostDrbl, 0u);
        (void)mmioRead32(ish::kRegFwsts);

        ++rxFrameCount;
        ++drained;
        if (ish::drblProto(drbl) == ish::kProtoMng &&
            ish::drblMngCmd(drbl) == ish::kMngRxCmplIndication) {
            ++mngRxCmplCount;
        }
        if (debugEnabled) {
            IOLog("TGLIshAls: RX proto=%u mng=%u len=%u drbl=0x%08x\n",
                  ish::drblProto(drbl), ish::drblMngCmd(drbl), len, drbl);
        }
        transport.onRxFrame(drbl, rxBuf, len, nowNs);
        pumpTx();
    }
    return drained;
}

void TGLIshAls::irqOccurred(OSObject *owner, IOInterruptEventSource *, int) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self || !self->mmioBase || atomic_load_explicit(&self->stopping, memory_order_acquire) ||
        atomic_load_explicit(&self->suspended, memory_order_acquire)) {
        return;
    }

    ++self->irqActionCount;
    const uint64_t nowNs = currentTimeNs();
    const uint32_t drained = self->drainRx(nowNs);
    if (drained == 0u) {
        ++self->spuriousIrqCount;
        ++self->consecutiveEmptyIrqs;
        if (!self->irqFallbackPolling && self->consecutiveEmptyIrqs >= kMaxConsecutiveEmptyIrqs) {
            self->irqFallbackPolling = true;
            if (self->irqSource && self->irqEnabled) {
                self->irqSource->disable();
                self->irqEnabled = false;
            }
            LOG("IRQ storm circuit-breaker tripped (%u empty IRQs); switching to %u ms polling "
                "(PIMR=0x%08x PISR=0x%08x FWSTS=0x%08x H2I=0x%08x I2H=0x%08x)",
                self->consecutiveEmptyIrqs, kFallbackPollTickMs,
                self->mmioRead32(ish::kRegPimrBxt), self->mmioRead32(ish::kRegPisrBxt),
                self->mmioRead32(ish::kRegFwsts), self->mmioRead32(ish::kRegHost2IshDrbl),
                self->mmioRead32(ish::kRegIsh2HostDrbl));
            self->publishTelemetry(false);
            self->scheduleNextTick();
        }
    } else {
        self->consecutiveEmptyIrqs = 0u;
    }

    if (atomic_load_explicit(&self->transportActive, memory_order_acquire)) {
        const uint32_t fwsts = self->mmioRead32(ish::kRegFwsts);
        const uint32_t h2iDrbl = self->mmioRead32(ish::kRegHost2IshDrbl);
        const bool txBusy = (h2iDrbl != 0xFFFFFFFFu) && ish::drblBusy(h2iDrbl);
        self->transport.onTick(nowNs, fwsts, txBusy, currentUtcUs(), currentMonoUs());
        self->pumpTx();
        self->handleTransportUpdates(nowNs);
    }
}

void TGLIshAls::timerFired(OSObject *owner, IOTimerEventSource *) {
    auto *self = OSDynamicCast(TGLIshAls, owner);
    if (!self || !self->mmioBase || atomic_load_explicit(&self->stopping, memory_order_acquire) ||
        atomic_load_explicit(&self->suspended, memory_order_acquire)) {
        return;
    }
    if (!atomic_load_explicit(&self->transportActive, memory_order_acquire)) {
        return;
    }

    const uint64_t nowNs = currentTimeNs();
    const uint32_t drained = self->drainRx(nowNs);
    if (drained > 0u) {
        self->timerDrainRxCount += drained;
    }
    const uint32_t fwsts = self->mmioRead32(ish::kRegFwsts);
    const uint32_t h2iDrbl = self->mmioRead32(ish::kRegHost2IshDrbl);
    const bool txBusy = (h2iDrbl != 0xFFFFFFFFu) && ish::drblBusy(h2iDrbl);

    self->transport.onTick(nowNs, fwsts, txBusy, currentUtcUs(), currentMonoUs());
    self->pumpTx();
    self->handleTransportUpdates(nowNs);

    const uint32_t postH2i = self->mmioRead32(ish::kRegHost2IshDrbl);
    const bool postTxBusy = (postH2i != 0xFFFFFFFFu) && ish::drblBusy(postH2i);
    if (postTxBusy && self->transport.hasTxPending()) {
        ++self->host2IshStallTicks;
        if (self->host2IshStallTicks == 10u) {
            LOG("HOST2ISH_DRBL stalled busy (txQ=%zu PIMR=0x%08x PISR=0x%08x FWSTS=0x%08x H2I=0x%08x I2H=0x%08x)",
                self->transport.txPendingCount(), self->mmioRead32(ish::kRegPimrBxt),
                self->mmioRead32(ish::kRegPisrBxt), self->mmioRead32(ish::kRegFwsts),
                postH2i, self->mmioRead32(ish::kRegIsh2HostDrbl));
        }
    } else {
        self->host2IshStallTicks = 0u;
    }

    if (atomic_load_explicit(&self->transportActive, memory_order_acquire) &&
        (drained > 0u || ++self->telemetryTickDiv >= 5u)) {
        self->telemetryTickDiv = 0u;
        self->publishTelemetry(false);
    }
    self->scheduleNextTick();
}
