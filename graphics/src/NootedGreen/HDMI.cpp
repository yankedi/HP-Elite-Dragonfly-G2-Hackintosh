//  Copyright © 2022-2023 ChefKiss Inc. Licensed under the Thou Shalt Not Profit License version 1.0. See LICENSE for
//  details.

#include "HDMI.hpp"
#include "kern_green.hpp"
#include "kern_patcherplus.hpp"
#include <Headers/kern_api.hpp>
#include <IOKit/IOLib.h>
#include <libkern/c++/OSArray.h>
#include <libkern/c++/OSBoolean.h>
#include <libkern/c++/OSDictionary.h>
#include <libkern/c++/OSMetaClass.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSSymbol.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>

static const char *pathAppleHDAController =
    "/System/Library/Extensions/AppleHDA.kext/Contents/PlugIns/AppleHDAController.kext/Contents/MacOS/AppleHDAController";
static const char *pathAppleHDA =
    "/System/Library/Extensions/AppleHDA.kext/Contents/MacOS/AppleHDA";

static KernelPatcher::KextInfo kextAppleHDAController {
    "com.apple.driver.AppleHDAController", &pathAppleHDAController, 1, {true}, {},
    KernelPatcher::KextInfo::Unloaded
};
static KernelPatcher::KextInfo kextAppleHDA {
    "com.apple.driver.AppleHDA", &pathAppleHDA, 1, {true}, {},
    KernelPatcher::KextInfo::Unloaded
};

HDMI *HDMI::callback = nullptr;

static mach_vm_address_t gOrgConstructPathMapByDiscovery = 0;
static mach_vm_address_t gOrgPerformWidgetInitialization = 0;
static mach_vm_address_t gOrgPinSetControl = 0;
static mach_vm_address_t gOrgDpInitialiseMCCSControls = 0;
static mach_vm_address_t gOrgDpMccsSetVolume = 0;
static mach_vm_address_t gOrgDpMccsSetMute = 0;
static mach_vm_address_t gOrgEngineClipOutputSamples = 0;

static const char * const kAhdaTargetSymbols[7] = {
    "__ZN30AppleHDAFunctionGroup_8086280727constructPathMapByDiscoveryEPP7OSArray",
    "__ZN23AppleHDAWidget_8086280727performWidgetInitializationEh",
    "__ZN23AppleHDAWidget_8086280713pinSetControlEh",
    "__ZN22AppleHDAEngineOutputDP21intialiseMCCSControlsEv",
    "__ZN22AppleHDAEngineOutputDP27mccsSetCurrentSpeakerVolumeEjh",
    "__ZN22AppleHDAEngineOutputDP25mccsSetCurrentSpeakerMuteEjb",
    "__ZN14AppleHDAEngine17clipOutputSamplesEPKvPvjjPK20_IOAudioStreamFormatP13IOAudioStream"
};

struct PatternSpec {
    const uint8_t *find;
    const uint8_t *replace;
    size_t size;
    size_t expectedCount;
};

struct ShdaModule {
    const char *identifier;
    const char *path;
    const char *plist;
    const uint8_t *executable;
    size_t executableSize;
    const char * const *libraries;
    size_t libraryCount;
};

struct ShdaWriteOp {
    uint8_t *dst;
    const uint8_t *src;
    size_t len;
};

using ShdaValidateFileFn = bool (*)(const void *data, size_t size);

static KernelPatcher *gSavedPatcher = nullptr;
static ShdaValidateFileFn gShdaValidateFile = nullptr;
static volatile uint32_t gShdaFound = 0;
static volatile uint32_t gShdaMod1Patches = 0;
static volatile uint32_t gShdaMod4Patches = 0;
static volatile uint32_t gShdaAhdaRouted = 0;
static volatile uint32_t gShdaPatchAttempted = 0;
static volatile uint32_t gShdaAhdaRoutedOnce = 0;
static volatile uint32_t gPrimeAudioLogs = 0;
static volatile uint32_t gLastPinBufCtl = 0;
static volatile uint32_t gLastFreqCntrl = 0;
static volatile uint32_t gInitFreqCntrlSet = 0;
static volatile uint32_t gInitFreqCntrl = 0;
static volatile uint32_t gLastChickenBit = 0;
static IOMemoryMap *gHdefBar0Map = nullptr;
static volatile uint32_t gHdefSyncBusy = 0;
static volatile uint32_t gHdefLink1Synced = 0;
static volatile uint32_t gHdefGctl = 0;
static volatile uint32_t gHdefWakeen = 0;
static volatile uint32_t gHdefStatests = 0;
static volatile uint32_t gHdefMlcd = 0;
static volatile uint32_t gHdefMl0Lcap = 0;
static volatile uint32_t gHdefMl0Lctl = 0;
static volatile uint32_t gHdefMl0Lsdiid = 0;
static volatile uint32_t gHdefMl1Lcap = 0;
static volatile uint32_t gHdefMl1Lctl = 0;
static volatile uint32_t gHdefMl1Lsdiid = 0;
static volatile uint32_t gHdefEm1 = 0;
static volatile uint32_t gHdefEm4l = 0;
static volatile uint32_t gShdaMod1HookedOnce = 0;
static volatile uint32_t gShdaV7Hooks = 0;
static volatile uint32_t gShdaV7OffClk = 0;
static volatile uint32_t gShdaV7OffCodec = 0;
static volatile uint32_t gLiveSyncCount = 0;
static volatile uint32_t gLiveSyncSrc = 0;
static volatile uint32_t gLiveGctl = 0;
static volatile uint32_t gLiveWakeen = 0;
static volatile uint32_t gLiveStatests = 0;
static volatile uint32_t gLiveMl1Lctl = 0;
static volatile uint32_t gLiveMl1Lsdiid = 0;
static volatile uint32_t gLiveEm1 = 0;
static volatile uint32_t gLiveEm4l = 0;
static volatile uint32_t gLiveAudFreq = 0;
static volatile uint32_t gLiveAudPinVld = 0;
static volatile uintptr_t gDpEngineVtable = 0;
static volatile uint32_t gDpInitMccsCalls = 0;
static volatile uint32_t gDpSetVolumeCalls = 0;
static volatile uint32_t gDpSetMuteCalls = 0;
static volatile uint32_t gDpClipCalls = 0;
static volatile uint32_t gDpLastVolume = 0xFEu;
static volatile uint32_t gDpLastMute = 0u;
static volatile uint32_t gDpVolRoutedMask = 0u;

// Keep AppleHDAController's 0x9d70 device-ID checks intact because AppleALC 1.9.8 already
// patches fDeviceID (0xef4) to 0x9d70 for 8086:a0c8; rewriting 0x9d70->0xa0c8 breaks
// setup80869C20HostInterface() (OutputLowPower=No) and getFIFOSize()/activateAudioStream()
// (bufFrames=0 / 0xe00002d8). Here we patch only the iDisp codec ID (8086:2807 -> 8086:2812),
// framebufferEventGate +0x1e90=1, probe cad 2/3 masking, 9D70 framebufferEventGate selection,
// updateGraphicsClockDividerFromFrameBuffer cad 2 probe, findValidDisplayCodec() bypass,
// integratedCodecAddressIsValid() cad 2 (0x04), and CGCTL.MISCBDCGE clear.
static const uint8_t kFCodecDesc[] = {0x07, 0x28, 0x86, 0x80, 0x01, 0x00, 0x00, 0x00};
static const uint8_t kRCodecDesc[] = {0x12, 0x28, 0x86, 0x80, 0x01, 0x00, 0x00, 0x00};
static const uint8_t kFFbGate1e90[] = {0x81, 0x48, 0x08, 0x00, 0x01, 0x00, 0x00, 0xC6, 0x83, 0x90, 0x1E, 0x00, 0x00, 0x00};
static const uint8_t kRFbGate1e90[] = {0x81, 0x48, 0x08, 0x00, 0x01, 0x00, 0x00, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90};
static const uint8_t kFFindDispCodec[] = {
    0x44, 0x0F, 0xB7, 0xA9, 0xD2, 0x02, 0x00, 0x00, 0x41, 0x21, 0xC5
};
static const uint8_t kRFindDispCodec[] = {
    0x41, 0x89, 0xC5, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90
};
static const uint8_t kFProbeMask9D70[] = {
    0x0F, 0xB7, 0x83, 0xD2, 0x02, 0x00, 0x00
};
static const uint8_t kRProbeMask9D70[] = {
    0xB8, 0x0C, 0x00, 0x00, 0x00, 0x90, 0x90
};
static const uint8_t kFGfxMatchFbGate[] = {
    0x48, 0x8D, 0x35, 0x03, 0x08, 0x00, 0x00
};
static const uint8_t kRGfxMatchFbGate[] = {
    0x48, 0x8D, 0x35, 0x6D, 0xCF, 0xFF, 0xFF
};
static const uint8_t kFUpdateClkProbe[] = {
    0x8A, 0x87, 0x85, 0x1E, 0x00, 0x00, 0x89, 0xC3, 0x80, 0xF3, 0x01, 0x81, 0xBF, 0xF0, 0x0E, 0x00,
    0x00, 0x86, 0x80, 0x00, 0x00, 0x0F, 0x85, 0x55, 0x01, 0x00, 0x00, 0x49, 0x89, 0xF7, 0x49, 0x89,
    0xFE, 0x8B, 0x8F, 0xF4, 0x0E, 0x00, 0x00, 0x81, 0xF9, 0x0C, 0x0A, 0x00, 0x00, 0x74, 0x14, 0x81,
    0xF9, 0x0C, 0x16, 0x00, 0x00
};
static const uint8_t kRUpdateClkProbe[] = {
    0x48, 0x89, 0xFB, 0x48, 0x85, 0xF6, 0x74, 0x24, 0x48, 0x83, 0xBB, 0x80, 0x01, 0x00, 0x00, 0x00,
    0x75, 0x1A, 0xE8, 0x66, 0x44, 0x00, 0x00, 0x48, 0x8B, 0x83, 0x88, 0x00, 0x00, 0x00, 0x81, 0x48,
    0x08, 0x00, 0x01, 0x00, 0x00, 0xC6, 0x83, 0xA4, 0x1E, 0x00, 0x00, 0x00, 0x31, 0xDB, 0xE9, 0x3D,
    0x01, 0x00, 0x00, 0x90, 0x90
};
static const uint8_t kFIntCodecValid[] = {
    0x0F, 0xB7, 0x87, 0xD2, 0x02, 0x00, 0x00
};
static const uint8_t kRIntCodecValid[] = {
    0xB8, 0x04, 0x00, 0x00, 0x00, 0x90, 0x90
};
static const uint8_t kFMiscBdcge[] = {
    0x83, 0xC8, 0x40, 0xBE, 0x48, 0x00, 0x00, 0x00, 0x4C, 0x89, 0xF7, 0x89, 0xC2
};
static const uint8_t kRMiscBdcge[] = {
    0x83, 0xE0, 0xBF, 0xBE, 0x48, 0x00, 0x00, 0x00, 0x4C, 0x89, 0xF7, 0x89, 0xC2
};

static_assert(sizeof(kFCodecDesc) == sizeof(kRCodecDesc), "codec desc patch size mismatch");
static_assert(sizeof(kFFbGate1e90) == sizeof(kRFbGate1e90), "fb gate 1e90 patch size mismatch");
static_assert(sizeof(kFFindDispCodec) == sizeof(kRFindDispCodec), "find disp codec patch size mismatch");
static_assert(sizeof(kFProbeMask9D70) == sizeof(kRProbeMask9D70), "probe mask 9d70 patch size mismatch");
static_assert(sizeof(kFGfxMatchFbGate) == sizeof(kRGfxMatchFbGate), "gfx match fb gate patch size mismatch");
static_assert(sizeof(kFUpdateClkProbe) == sizeof(kRUpdateClkProbe), "update clk probe patch size mismatch");
static_assert(sizeof(kFIntCodecValid) == sizeof(kRIntCodecValid), "int codec valid patch size mismatch");
static_assert(sizeof(kFMiscBdcge) == sizeof(kRMiscBdcge), "misc bdcge patch size mismatch");

static const PatternSpec kCtrlPatterns[] = {
    {kFCodecDesc, kRCodecDesc, sizeof(kFCodecDesc), 1},
    {kFFbGate1e90, kRFbGate1e90, sizeof(kFFbGate1e90), 1},
    {kFFindDispCodec, kRFindDispCodec, sizeof(kFFindDispCodec), 1},
    {kFProbeMask9D70, kRProbeMask9D70, sizeof(kFProbeMask9D70), 1},
    {kFGfxMatchFbGate, kRGfxMatchFbGate, sizeof(kFGfxMatchFbGate), 1},
    {kFUpdateClkProbe, kRUpdateClkProbe, sizeof(kFUpdateClkProbe), 1},
    {kFIntCodecValid, kRIntCodecValid, sizeof(kFIntCodecValid), 1},
    {kFMiscBdcge, kRMiscBdcge, sizeof(kFMiscBdcge), 2},
};

static const uint8_t kFPinRange[] = {
    0x8D, 0x88, 0xFB, 0xD7, 0x79, 0x7F, 0x83, 0xF9, 0x06, 0x0F, 0x87
};
static const uint8_t kRPinRange[] = {
    0x8D, 0x88, 0xFB, 0xD7, 0x79, 0x7F, 0x83, 0xF9, 0x0D, 0x0F, 0x87
};
static const uint8_t kFWidgetMask[] = {
    0xBA, 0x5C, 0x00, 0x00, 0x00, 0x0F, 0xA3, 0xCA
};
static const uint8_t kRWidgetMask[] = {
    0xBA, 0x5C, 0x20, 0x00, 0x00, 0x0F, 0xA3, 0xCA
};
// Critical: nid=0x02, verb=0x781, param=0x01 (non-MST single stream mode).
static const uint8_t kFVendorVerb[] = {
    0xBE, 0x08, 0x00, 0x00, 0x00, 0xBA, 0x81, 0x07, 0x00, 0x00, 0xB9, 0x03, 0x00, 0x00, 0x00
};
static const uint8_t kRVendorVerb[] = {
    0xBE, 0x02, 0x00, 0x00, 0x00, 0xBA, 0x81, 0x07, 0x00, 0x00, 0xB9, 0x01, 0x00, 0x00, 0x00
};

static_assert(sizeof(kFPinRange) == sizeof(kRPinRange), "AppleHDA pin range patch size mismatch");
static_assert(sizeof(kFWidgetMask) == sizeof(kRWidgetMask), "AppleHDA widget mask patch size mismatch");
static_assert(sizeof(kFVendorVerb) == sizeof(kRVendorVerb), "AppleHDA vendor verb patch size mismatch");

static const PatternSpec kAhdaPatterns[] = {
    {kFPinRange, kRPinRange, sizeof(kFPinRange), 2},
    {kFWidgetMask, kRWidgetMask, sizeof(kFWidgetMask), 2},
    {kFVendorVerb, kRVendorVerb, sizeof(kFVendorVerb), 1},
};

bool HDMI::isShdaFound() {
    return gShdaFound != 0u;
}

uint32_t HDMI::getShdaMod1Patches() {
    return gShdaMod1Patches;
}

uint32_t HDMI::getShdaMod4Patches() {
    return gShdaMod4Patches;
}

uint32_t HDMI::getShdaAhdaRouted() {
    return gShdaAhdaRouted;
}

uint32_t HDMI::getPinBufCtl() {
    return gLastPinBufCtl;
}

uint32_t HDMI::getAudFreqCntrl() {
    return gLastFreqCntrl;
}

uint32_t HDMI::getAudFreqCntrlInit() {
    return gInitFreqCntrl;
}

uint32_t HDMI::getAudChickenBit() {
    return gLastChickenBit;
}

uint32_t HDMI::getHdefGctl() { return gHdefGctl; }
uint32_t HDMI::getHdefWakeen() { return gHdefWakeen; }
uint32_t HDMI::getHdefStatests() { return gHdefStatests; }
uint32_t HDMI::getHdefMlcd() { return gHdefMlcd; }
uint32_t HDMI::getHdefMl0Lcap() { return gHdefMl0Lcap; }
uint32_t HDMI::getHdefMl0Lctl() { return gHdefMl0Lctl; }
uint32_t HDMI::getHdefMl0Lsdiid() { return gHdefMl0Lsdiid; }
uint32_t HDMI::getHdefMl1Lcap() { return gHdefMl1Lcap; }
uint32_t HDMI::getHdefMl1Lctl() { return gHdefMl1Lctl; }
uint32_t HDMI::getHdefMl1Lsdiid() { return gHdefMl1Lsdiid; }
uint32_t HDMI::getHdefEm1() { return gHdefEm1; }
uint32_t HDMI::getHdefEm4l() { return gHdefEm4l; }
uint32_t HDMI::getShdaV7Hooks() { return gShdaV7Hooks; }
uint32_t HDMI::getShdaV7OffClk() { return gShdaV7OffClk; }
uint32_t HDMI::getShdaV7OffCodec() { return gShdaV7OffCodec; }
uint32_t HDMI::getLiveSyncCount() { return gLiveSyncCount; }
uint32_t HDMI::getLiveSyncSrc() { return gLiveSyncSrc; }
uint32_t HDMI::getLiveGctl() { return gLiveGctl; }
uint32_t HDMI::getLiveWakeen() { return gLiveWakeen; }
uint32_t HDMI::getLiveStatests() { return gLiveStatests; }
uint32_t HDMI::getLiveMl1Lctl() { return gLiveMl1Lctl; }
uint32_t HDMI::getLiveMl1Lsdiid() { return gLiveMl1Lsdiid; }
uint32_t HDMI::getLiveEm1() { return gLiveEm1; }
uint32_t HDMI::getLiveEm4l() { return gLiveEm4l; }
uint32_t HDMI::getLiveAudFreq() { return gLiveAudFreq; }
uint32_t HDMI::getLiveAudPinVld() { return gLiveAudPinVld; }

void HDMI::publishLiveTelemetry(IORegistryEntry *reg) {
    if (!reg) {
        return;
    }
    reg->setProperty("ngreen-shda-v7-hooks", static_cast<uint32_t>(gShdaV7Hooks), 32);
    reg->setProperty("ngreen-shda-v7-off-clk", static_cast<uint32_t>(gShdaV7OffClk), 32);
    reg->setProperty("ngreen-shda-v7-off-codec", static_cast<uint32_t>(gShdaV7OffCodec), 32);
    reg->setProperty("ngreen-live-sync-count", static_cast<uint32_t>(gLiveSyncCount), 32);
    reg->setProperty("ngreen-live-sync-src", static_cast<uint32_t>(gLiveSyncSrc), 32);
    reg->setProperty("ngreen-live-gctl", static_cast<uint32_t>(gLiveGctl), 32);
    reg->setProperty("ngreen-live-wakeen", static_cast<uint32_t>(gLiveWakeen), 32);
    reg->setProperty("ngreen-live-statests", static_cast<uint32_t>(gLiveStatests), 32);
    reg->setProperty("ngreen-live-ml1-lctl", static_cast<uint32_t>(gLiveMl1Lctl), 32);
    reg->setProperty("ngreen-live-ml1-lsdiid", static_cast<uint32_t>(gLiveMl1Lsdiid), 32);
    reg->setProperty("ngreen-live-em1", static_cast<uint32_t>(gLiveEm1), 32);
    reg->setProperty("ngreen-live-em4l", static_cast<uint32_t>(gLiveEm4l), 32);
    reg->setProperty("ngreen-live-aud-freq", static_cast<uint32_t>(gLiveAudFreq), 32);
    reg->setProperty("ngreen-live-aud-pin-vld", static_cast<uint32_t>(gLiveAudPinVld), 32);
    reg->setProperty("pcfix51-dp-vol-routed",
                     ((gDpVolRoutedMask & 0xFu) == 0xFu) ? kOSBooleanTrue : kOSBooleanFalse);
    reg->setProperty("pcfix51-dp-vol-route-mask", static_cast<uint32_t>(gDpVolRoutedMask), 32);
    reg->setProperty("pcfix51-dp-init-mccs-calls", static_cast<uint32_t>(gDpInitMccsCalls), 32);
    reg->setProperty("pcfix51-dp-set-vol-calls", static_cast<uint32_t>(gDpSetVolumeCalls), 32);
    reg->setProperty("pcfix51-dp-set-mute-calls", static_cast<uint32_t>(gDpSetMuteCalls), 32);
    reg->setProperty("pcfix51-dp-clip-calls", static_cast<uint32_t>(gDpClipCalls), 32);
    reg->setProperty("pcfix51-dp-last-vol", static_cast<uint32_t>(gDpLastVolume), 32);
    reg->setProperty("pcfix51-dp-last-mute", static_cast<uint32_t>(gDpLastMute), 32);
    reg->setProperty("ngreen-pcfix53-audio", kOSBooleanTrue);
}

static constexpr uint32_t kRegHswAudChickenBit = 0x65f10u;

static inline uint32_t hdefRd32(uintptr_t bar0, uint32_t off) {
    return *reinterpret_cast<const volatile uint32_t *>(bar0 + off);
}

static inline void hdefWr32(uintptr_t bar0, uint32_t off, uint32_t val) {
    *reinterpret_cast<volatile uint32_t *>(bar0 + off) = val;
}

static inline uint16_t hdefRd16(uintptr_t bar0, uint32_t off) {
    return *reinterpret_cast<const volatile uint16_t *>(bar0 + off);
}

static inline void hdefWr16(uintptr_t bar0, uint32_t off, uint16_t val) {
    // 16-bit write required for WAKEEN (+0x0c) so W1C STATESTS (+0x0e) is never touched.
    *reinterpret_cast<volatile uint16_t *>(bar0 + off) = val;
}

static bool readPciDataU32(IORegistryEntry *entry, const char *key, uint32_t &out) {
    if (OSData *data = OSDynamicCast(OSData, entry->getProperty(key))) {
        if (data->getLength() >= sizeof(uint32_t)) {
            const uint8_t *b = static_cast<const uint8_t *>(data->getBytesNoCopy());
            out = static_cast<uint32_t>(b[0]) |
                  (static_cast<uint32_t>(b[1]) << 8) |
                  (static_cast<uint32_t>(b[2]) << 16) |
                  (static_cast<uint32_t>(b[3]) << 24);
            return true;
        }
    }
    return false;
}

static bool isHdefPciDevice(IOPCIDevice *dev) {
    uint32_t vid = 0;
    uint32_t did = 0;
    if (readPciDataU32(dev, "vendor-id", vid) && readPciDataU32(dev, "device-id", did)) {
        return vid == 0x8086u && did == 0xa0c8u;
    }
    return dev->getBusNumber() == 0 && dev->getDeviceNumber() == 0x1fu &&
           dev->getFunctionNumber() == 3 && dev->configRead32(0) == 0xa0c88086u;
}

static IOMemoryMap *getHdefBar0Map() {
    if (IOMemoryMap *cached = __atomic_load_n(&gHdefBar0Map, __ATOMIC_ACQUIRE)) {
        return cached;
    }
    OSDictionary *match = IOService::serviceMatching("IOPCIDevice");
    OSIterator *it = match ? IOService::getMatchingServices(match) : nullptr;
    if (!it) {
        return nullptr;
    }
    IOMemoryMap *map = nullptr;
    while (OSObject *obj = it->getNextObject()) {
        if (IOPCIDevice *dev = OSDynamicCast(IOPCIDevice, obj)) {
            if (isHdefPciDevice(dev)) {
                const uint32_t bar0Cfg = dev->configRead32(kIOPCIConfigBaseAddress0);
                if ((bar0Cfg & ~0xfu) != 0u) {
                    map = dev->mapDeviceMemoryWithRegister(kIOPCIConfigBaseAddress0);
                }
                break;
            }
        }
    }
    it->release();
    if (!map) {
        return nullptr;
    }
    if (map->getVirtualAddress() == 0 || map->getLength() < 0x1044u) {
        map->release();
        return nullptr;
    }
    if (!__sync_bool_compare_and_swap(&gHdefBar0Map, nullptr, map)) {
        map->release();
        return __atomic_load_n(&gHdefBar0Map, __ATOMIC_ACQUIRE);
    }
    return map;
}

static void snapshotHdefTelemetry(uintptr_t bar0) {
    gHdefGctl = hdefRd32(bar0, 0x08u);
    gHdefWakeen = hdefRd16(bar0, 0x0cu);
    gHdefStatests = hdefRd16(bar0, 0x0eu);
    gHdefMlcd = hdefRd32(bar0, 0x0c04u);
    gHdefMl0Lcap = hdefRd32(bar0, 0x0c40u);
    gHdefMl0Lctl = hdefRd32(bar0, 0x0c44u);
    gHdefMl0Lsdiid = hdefRd16(bar0, 0x0c4cu);
    gHdefMl1Lcap = hdefRd32(bar0, 0x0c80u);
    gHdefMl1Lctl = hdefRd32(bar0, 0x0c84u);
    gHdefMl1Lsdiid = hdefRd16(bar0, 0x0c8cu);
    gHdefEm1 = hdefRd32(bar0, 0x1000u);
    gHdefEm4l = hdefRd32(bar0, 0x1040u);
}

static void writeAudChickenBit15(bool set) {
    const uint32_t chk = NGreen::callback->readReg32(kRegHswAudChickenBit);
    if (chk == 0xFFFFFFFFu) {
        return;
    }
    const uint32_t next = set ? (chk | 0x8000u) : (chk & ~0x8000u);
    NGreen::callback->writeReg32(kRegHswAudChickenBit, next);
    (void)NGreen::callback->readReg32(kRegHswAudChickenBit);
}

static bool acquireHdefSyncLock() {
    for (uint32_t i = 0; i < 5000u; ++i) {
        if (__sync_lock_test_and_set(&gHdefSyncBusy, 1u) == 0u) {
            return true;
        }
        IODelay(10);
    }
    return false;
}

static inline void releaseHdefSyncLock() {
    __sync_lock_release(&gHdefSyncBusy);
}

static void waitHdefMl1Cpa(uintptr_t bar0, bool wantSet, uint32_t iters, uint32_t delayUs) {
    for (uint32_t i = 0; i < iters; ++i) {
        const uint32_t v = hdefRd32(bar0, 0x0c84u);
        if (v == 0xFFFFFFFFu || ((v & (1u << 23)) != 0u) == wantSet) {
            break;
        }
        IODelay(delayUs);
    }
}

static bool syncHdefLink1(bool earlyBoot) {
    IOMemoryMap *bar0Map = getHdefBar0Map();
    if (!bar0Map) {
        return false;
    }
    const uintptr_t bar0 = static_cast<uintptr_t>(bar0Map->getVirtualAddress());
    if (!acquireHdefSyncLock()) {
        return false;
    }

    const uint32_t gctl = hdefRd32(bar0, 0x08u);
    if (gctl == 0xFFFFFFFFu || (gctl & 1u) == 0u) {
        if (gctl != 0xFFFFFFFFu) {
            gHdefGctl = gctl;
            gHdefLink1Synced = 0u;
        }
        releaseHdefSyncLock();
        return false;
    }

    snapshotHdefTelemetry(bar0);

    bool cycled = false;
    // Never touch Link 0 (ALC285 cad 0); only cycle Link 1 (iDisp) when present and Link 1 does not own SDI0.
    if (!earlyBoot && !gHdefLink1Synced && (gHdefMlcd & 0x7u) >= 1u && (gHdefMl1Lsdiid & 0x1u) == 0u) {
        writeAudChickenBit15(false);
        IODelay(500);

        const uint32_t lctlOff = hdefRd32(bar0, 0x0c84u);
        if (lctlOff != 0xFFFFFFFFu) {
            hdefWr32(bar0, 0x0c84u, lctlOff & ~(1u << 16));
            waitHdefMl1Cpa(bar0, false, 500u, 2u);
        }

        writeAudChickenBit15(true);
        IODelay(1000);

        const uint32_t lctlOn = hdefRd32(bar0, 0x0c84u);
        if (lctlOn != 0xFFFFFFFFu) {
            hdefWr32(bar0, 0x0c84u, lctlOn | (1u << 16));
            waitHdefMl1Cpa(bar0, true, 500u, 2u);
        }
        IODelay(600);

        writeAudChickenBit15(false);
        IODelay(1000);

        gHdefLink1Synced = 1u;
        cycled = true;
    }

    if (!earlyBoot) {
        const uint16_t curWakeen = hdefRd16(bar0, 0x0cu);
        if ((curWakeen & 0x0004u) == 0u) {
            hdefWr16(bar0, 0x0cu, static_cast<uint16_t>(curWakeen | 0x0004u));
        }
        const uint32_t curGctl = hdefRd32(bar0, 0x08u);
        if (curGctl != 0xFFFFFFFFu && (curGctl & 0x100u) == 0u) {
            hdefWr32(bar0, 0x08u, curGctl | 0x100u);
        }
    }

    snapshotHdefTelemetry(bar0);
    const uint32_t rbChicken = NGreen::callback->readReg32(kRegHswAudChickenBit);
    if (rbChicken != 0xFFFFFFFFu) {
        gLastChickenBit = rbChicken;
    }

    releaseHdefSyncLock();
    return cycled;
}

void HDMI::syncLiveHdaAndIgpu(void *hdaCtrl, uint8_t sourceTag) {
    if (!hdaCtrl || !NGreen::callback || !NGreen::callback->getIsRealTGL() || !HDMI::isHdmiAudioFixEnabled()) {
        return;
    }
    const uintptr_t bar0 = *reinterpret_cast<const uintptr_t *>(static_cast<const uint8_t *>(hdaCtrl) + 0x88);
    if (!bar0) {
        return;
    }

    NGreen::callback->setRMMIOIfNecessary();
    if (!acquireHdefSyncLock()) {
        return;
    }

    const uint32_t gctlInit = hdefRd32(bar0, 0x08u);
    if (gctlInit == 0xFFFFFFFFu) {
        releaseHdefSyncLock();
        return;
    }

    static constexpr uint32_t kRegAudPinBufCtl = 0x48414u;
    static constexpr uint32_t kRegAudFreqCntrl = 0x65900u;
    static constexpr uint32_t kRegAudPinVld = 0x650c0u;
    static constexpr uint32_t kAudFreqGen12 = 0x00008010u;

    const uint32_t pinBuf = NGreen::callback->readReg32(kRegAudPinBufCtl);
    if (pinBuf == 0u) {
        NGreen::callback->writeReg32(kRegAudPinBufCtl, 0xb0002077u);
    } else if (pinBuf != 0xFFFFFFFFu && (pinBuf & 0x80000000u) == 0u) {
        NGreen::callback->writeReg32(kRegAudPinBufCtl, pinBuf | 0x80000000u);
    }

    const uint32_t freqCtl = NGreen::callback->readReg32(kRegAudFreqCntrl);
    if (freqCtl != 0xFFFFFFFFu && freqCtl != kAudFreqGen12) {
        NGreen::callback->writeReg32(kRegAudFreqCntrl, kAudFreqGen12);
    }

    const uint32_t pinVld = NGreen::callback->readReg32(kRegAudPinVld);
    if (pinVld != 0xFFFFFFFFu && (pinVld & 0x70u) != 0x70u) {
        NGreen::callback->writeReg32(kRegAudPinVld, pinVld | 0x70u);
    }

    writeAudChickenBit15(false);
    IODelay(200);
    writeAudChickenBit15(true);
    IODelay(500);

    const uint32_t curGctl = hdefRd32(bar0, 0x08u);
    if (curGctl != 0xFFFFFFFFu && (curGctl & 0x0101u) != 0x0101u) {
        hdefWr32(bar0, 0x08u, curGctl | 0x0101u);
        if ((curGctl & 1u) == 0u) {
            for (uint32_t i = 0; i < 50u; ++i) {
                const uint32_t v = hdefRd32(bar0, 0x08u);
                if (v == 0xFFFFFFFFu || (v & 1u) != 0u) {
                    break;
                }
                IODelay(100);
            }
        }
    }

    const uint16_t curWakeen = hdefRd16(bar0, 0x0cu);
    if ((curWakeen & 0x0004u) == 0u) {
        hdefWr16(bar0, 0x0cu, static_cast<uint16_t>(curWakeen | 0x0004u));
    }

    const uint32_t em1 = hdefRd32(bar0, 0x1000u);
    if (em1 != 0xFFFFFFFFu) {
        const uint32_t nextEm1 = (em1 & ~0x0f00u) | 0x0200u;
        if (nextEm1 != em1) {
            hdefWr32(bar0, 0x1000u, nextEm1);
        }
    }

    const uint32_t em2 = hdefRd32(bar0, 0x1030u);
    if (em2 != 0xFFFFFFFFu) {
        const uint32_t nextEm2 = em2 | (1u << 31) | (1u << 13);
        if (nextEm2 != em2) {
            hdefWr32(bar0, 0x1030u, nextEm2);
        }
    }

    const uint32_t em4l = hdefRd32(bar0, 0x1040u);
    if (em4l != 0xFFFFFFFFu) {
        const uint32_t nextEm4l = em4l & ~0xffffu;
        if (nextEm4l != em4l) {
            hdefWr32(bar0, 0x1040u, nextEm4l);
        }
    }

    const uint32_t lctlOff = hdefRd32(bar0, 0x0c84u);
    if (lctlOff != 0xFFFFFFFFu) {
        hdefWr32(bar0, 0x0c84u, lctlOff & ~(1u << 16));
        waitHdefMl1Cpa(bar0, false, 50u, 100u);
        IODelay(200);
        const uint32_t lctlPre = hdefRd32(bar0, 0x0c84u);
        if (lctlPre != 0xFFFFFFFFu) {
            hdefWr32(bar0, 0x0c84u, (lctlPre & ~0xfu) | 0x04u | (1u << 16));
            waitHdefMl1Cpa(bar0, true, 50u, 100u);
            IODelay(1000);
        }
    }

    writeAudChickenBit15(false);
    IODelay(500);

    snapshotHdefTelemetry(bar0);
    const uint32_t rbGctl = hdefRd32(bar0, 0x08u);
    const uint16_t rbWakeen = hdefRd16(bar0, 0x0cu);
    const uint16_t rbStatests = hdefRd16(bar0, 0x0eu);
    const uint32_t rbMl1Lctl = hdefRd32(bar0, 0x0c84u);
    const uint16_t rbMl1Lsdiid = hdefRd16(bar0, 0x0c8cu);
    const uint32_t rbEm1 = hdefRd32(bar0, 0x1000u);
    const uint32_t rbEm4l = hdefRd32(bar0, 0x1040u);
    const uint32_t rbFreq = NGreen::callback->readReg32(kRegAudFreqCntrl);
    const uint32_t rbPinVld = NGreen::callback->readReg32(kRegAudPinVld);
    const uint32_t rbPinBuf = NGreen::callback->readReg32(kRegAudPinBufCtl);
    const uint32_t rbChicken = NGreen::callback->readReg32(kRegHswAudChickenBit);

    gLiveSyncSrc = sourceTag;
    gLiveGctl = rbGctl;
    gLiveWakeen = rbWakeen;
    gLiveStatests = rbStatests;
    gLiveMl1Lctl = rbMl1Lctl;
    gLiveMl1Lsdiid = rbMl1Lsdiid;
    gLiveEm1 = rbEm1;
    gLiveEm4l = rbEm4l;
    gLiveAudFreq = rbFreq;
    gLiveAudPinVld = rbPinVld;
    if (rbFreq != 0xFFFFFFFFu) {
        gLastFreqCntrl = rbFreq;
    }
    if (rbPinBuf != 0xFFFFFFFFu) {
        gLastPinBufCtl = rbPinBuf;
    }
    if (rbChicken != 0xFFFFFFFFu) {
        gLastChickenBit = rbChicken;
    }
    const uint32_t syncCount = __sync_add_and_fetch(&gLiveSyncCount, 1u);
    releaseHdefSyncLock();

    HDMI::publishLiveTelemetry(NGreen::callback->getIGPU());
    if (syncCount <= 16u) {
        IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: liveSync #%u src=%u GCTL=0x%x WAKEEN=0x%x STATESTS=0x%x ML1_LCTL=0x%x ML1_LSDIID=0x%x EM1=0x%x EM4L=0x%x FREQ=0x%x PIN_VLD=0x%x\n",
              syncCount, static_cast<unsigned>(sourceTag),
              rbGctl, static_cast<unsigned>(rbWakeen), static_cast<unsigned>(rbStatests),
              rbMl1Lctl, static_cast<unsigned>(rbMl1Lsdiid), rbEm1, rbEm4l, rbFreq, rbPinVld);
    }
}

static bool isLiveDisplayAudioReady(void *hdaCtrl, uintptr_t &bar0Out) {
    bar0Out = 0;
    if (!hdaCtrl || !NGreen::callback || !NGreen::callback->getIsRealTGL() || !HDMI::isHdmiAudioFixEnabled()) {
        return false;
    }
    const auto *ctrlBytes = static_cast<const uint8_t *>(hdaCtrl);
    const uintptr_t bar0 = *reinterpret_cast<const uintptr_t *>(ctrlBytes + 0x88);
    void * const codec0 = *reinterpret_cast<void * const *>(ctrlBytes + 0x170);
    if (!bar0 || !codec0 || ctrlBytes[0x1e74] != 0u) {
        return false;
    }
    auto *ctrlEntry = reinterpret_cast<IORegistryEntry *>(hdaCtrl);
    if (!ctrlEntry->getProperty("CodecList")) {
        return false;
    }
    const uint32_t gctl = hdefRd32(bar0, 0x08u);
    if (gctl == 0xFFFFFFFFu || (gctl & 1u) == 0u) {
        return false;
    }
    NGreen::callback->setRMMIOIfNecessary();
    const uint32_t pwrWell = NGreen::callback->readReg32(0x45404u);
    const uint32_t pinVld = NGreen::callback->readReg32(0x650c0u);
    const uint32_t transDdiB = NGreen::callback->readReg32(0x61400u);
    if (pwrWell == 0u || pwrWell == 0xFFFFFFFFu) {
        return false;
    }
    const bool hdmiPipeReady =
        (pinVld != 0xFFFFFFFFu && (pinVld & 0x70u) != 0u) ||
        (transDdiB != 0xFFFFFFFFu && (transDdiB & 0x87000000u) == 0x80000000u && ((transDdiB >> 27) & 0xFu) == 2u);
    if (!hdmiPipeReady) {
        return false;
    }
    bar0Out = bar0;
    return true;
}

void HDMI::wrapSetGraphicsClockDivider(void *hdaCtrl) {
    uintptr_t bar0 = 0;
    if (!isLiveDisplayAudioReady(hdaCtrl, bar0)) {
        return;
    }
    (void)bar0;
    syncLiveHdaAndIgpu(hdaCtrl, 1u);
}

uint8_t HDMI::wrapFindValidDisplayCodec(void *hdaCtrl) {
    uintptr_t bar0 = 0;
    if (!isLiveDisplayAudioReady(hdaCtrl, bar0)) {
        return 0xFFu;
    }
    (void)bar0;
    syncLiveHdaAndIgpu(hdaCtrl, 2u);
    return 0x04u;
}

void HDMI::primeTglIDispAudio(bool earlyBoot) {
    if (!NGreen::callback || !NGreen::callback->getIsRealTGL() || !isHdmiAudioFixEnabled()) {
        return;
    }
    NGreen::callback->setRMMIOIfNecessary();

    // TGL Display Engine registers (verified vs Intel PRM and live NootedGreen telemetry):
    // 0x65900 = AUD_FREQ_CNTRL (0x00008010 AUD_FREQ_GEN12: 8T + PULLCLKS=0 + 96M BCLK; avoid 0x9010 TGL_BROKEN),
    // 0x48414 = AUD_PIN_BUF_CTL (bit 31 = PIN_BUF_ENABLE),
    // 0x65010 / 0x65110 = HSW_AUD_MISC_CTRL_{A,B} (bit 2 = sample fabric gate),
    // 0x65f10 = HSW_AUD_CHICKENBIT (bit 15 = codec wake pulse; must rest at 0).
    static constexpr uint32_t kRegAudPinBufCtl = 0x48414u;
    static constexpr uint32_t kRegHswAudMiscCtrlA = 0x65010u;
    static constexpr uint32_t kRegHswAudMiscCtrlB = 0x65110u;
    static constexpr uint32_t kAudPinBufEnable = 0x80000000u;
    static constexpr uint32_t kAudFreqGen12 = 0x00008010u;

    const uint32_t freqCtl = NGreen::callback->readReg32(0x65900u);
    const uint32_t cdclkCtl = NGreen::callback->readReg32(0x46000u);
    const uint32_t pwrWell = NGreen::callback->readReg32(0x45404u);
    const uint32_t pinVld = NGreen::callback->readReg32(0x650c0u);
    const uint32_t audCfgB = NGreen::callback->readReg32(0x65100u);

    if (cdclkCtl == 0u && pwrWell == 0u && freqCtl == 0u) {
        SYSLOG("ngreen", "HP-HDMI-AUDIO [PCFIX53-AUDIO]: iDisp MMIO not active yet (early=%d)", earlyBoot ? 1 : 0);
        return;
    }

    if (freqCtl != 0xFFFFFFFFu && __sync_bool_compare_and_swap(&gInitFreqCntrlSet, 0u, 1u)) {
        gInitFreqCntrl = freqCtl;
    }

    bool repaired = false;
    uint32_t effectiveFreq = freqCtl;
    if (freqCtl != 0xFFFFFFFFu && freqCtl != kAudFreqGen12) {
        NGreen::callback->writeReg32(0x65900u, kAudFreqGen12);
        const uint32_t rbFreq = NGreen::callback->readReg32(0x65900u);
        effectiveFreq = (rbFreq != 0xFFFFFFFFu) ? rbFreq : kAudFreqGen12;
        repaired = true;
        SYSLOG("ngreen", "HP-HDMI-AUDIO [PCFIX53-AUDIO]: repaired AUD_FREQ_CNTRL (early=%d) 0x%x -> 0x%x",
               earlyBoot ? 1 : 0, freqCtl, effectiveFreq);
    }
    gLastFreqCntrl = effectiveFreq;

    const uint32_t pinBuf = NGreen::callback->readReg32(kRegAudPinBufCtl);
    uint32_t effectivePinBuf = pinBuf;
    if (pinBuf != 0xFFFFFFFFu) {
        if ((pinBuf & kAudPinBufEnable) == 0u) {
            repaired = true;
        }
        uint32_t nextPinBuf = pinBuf | kAudPinBufEnable;
        if ((pinBuf & 0xffffu) == 0u) {
            nextPinBuf |= 0x222au;
        }
        if (nextPinBuf != pinBuf) {
            NGreen::callback->writeReg32(kRegAudPinBufCtl, nextPinBuf);
            const uint32_t readBackPinBuf = NGreen::callback->readReg32(kRegAudPinBufCtl);
            effectivePinBuf = (readBackPinBuf != 0xFFFFFFFFu) ? readBackPinBuf : nextPinBuf;
        }
    }
    gLastPinBufCtl = effectivePinBuf;

    const uint32_t miscRegs[2] = {kRegHswAudMiscCtrlA, kRegHswAudMiscCtrlB};
    for (uint32_t reg : miscRegs) {
        const uint32_t misc = NGreen::callback->readReg32(reg);
        if (misc != 0xFFFFFFFFu && (misc & 0x4u) != 0u) {
            NGreen::callback->writeReg32(reg, misc & ~0x4u);
            repaired = true;
        }
    }

    const uint32_t chicken = NGreen::callback->readReg32(kRegHswAudChickenBit);
    uint32_t effectiveChicken = chicken;
    if (chicken != 0xFFFFFFFFu) {
        const uint32_t chickenCleared = chicken & ~0x8000u;
        const uint32_t chickenSet = chickenCleared | 0x8000u;
        NGreen::callback->writeReg32(kRegHswAudChickenBit, chickenCleared);
        (void)NGreen::callback->readReg32(kRegHswAudChickenBit);
        IODelay(1000);
        NGreen::callback->writeReg32(kRegHswAudChickenBit, chickenSet);
        (void)NGreen::callback->readReg32(kRegHswAudChickenBit);
        IODelay(1000);
        NGreen::callback->writeReg32(kRegHswAudChickenBit, chickenCleared);
        (void)NGreen::callback->readReg32(kRegHswAudChickenBit);
        IODelay(1000);
        const uint32_t readBackChicken = NGreen::callback->readReg32(kRegHswAudChickenBit);
        effectiveChicken = (readBackChicken != 0xFFFFFFFFu) ? readBackChicken : chickenCleared;
        repaired = true;
    }
    gLastChickenBit = effectiveChicken;

    if (syncHdefLink1(earlyBoot)) {
        repaired = true;
    }
    effectiveChicken = gLastChickenBit;

    if (earlyBoot || repaired || __sync_add_and_fetch(&gPrimeAudioLogs, 1u) <= 8u) {
        IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: iDisp prime early=%d AUD_FREQ_CNTRL=0x%x(init=0x%x) AUD_PIN_BUF_CTL=0x%x CHICKEN=0x%x CDCLK=0x%x PWR_WELL=0x%x PIN_VLD=0x%x AUD_CFG_B=0x%x HDEF_GCTL=0x%x WAKEEN=0x%x STATESTS=0x%x MLCD=0x%x ML1_LCTL=0x%x ML1_LSDIID=0x%x\n",
              earlyBoot ? 1 : 0, effectiveFreq, gInitFreqCntrl, effectivePinBuf, effectiveChicken,
              cdclkCtl, pwrWell, pinVld, audCfgB, gHdefGctl, gHdefWakeen, gHdefStatests, gHdefMlcd,
              gHdefMl1Lctl, gHdefMl1Lsdiid);
    }
}

bool HDMI::isHdmiAudioFixEnabled() {
    uint32_t eax = 0, ebx = 0, ecx = 0, edx = 0;
    asm volatile("cpuid" : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx) : "a"(1));
    uint32_t family = (eax >> 8) & 0xFU;
    uint32_t extFamily = (eax >> 20) & 0xFFU;
    if (family == 0xFU) {
        family += extFamily;
    }
    uint32_t model = (eax >> 4) & 0xFU;
    uint32_t extModel = (eax >> 16) & 0xFU;
    if (family == 0x6U || family == 0xFU) {
        model |= (extModel << 4);
    }
    return (family == 0x6U && (model == 0x8CU || model == 0x8DU)) &&
           !checkKernelArgument("-ngreennohdmi") &&
           !checkKernelArgument("-ngreennohdahdmi");
}

template <typename Fn>
static inline bool isValidTrampolineOrg(mach_vm_address_t org, Fn wrapper) {
    return org != 0u && org != reinterpret_cast<mach_vm_address_t>(wrapper);
}

static int wrapConstructPathMapByDiscovery(void *that, OSArray **outArray) {
    int rc = isValidTrampolineOrg(gOrgConstructPathMapByDiscovery, wrapConstructPathMapByDiscovery)
        ? FunctionCast(wrapConstructPathMapByDiscovery, gOrgConstructPathMapByDiscovery)(that, outArray)
        : static_cast<int>(kIOReturnError);
    if (rc != 0 || !that || !outArray || !(*outArray)) {
        return rc;
    }

    // Rewrite 8086:2807 discovered NID pairs (5,2),(6,3),(7,4) to TGL 8086:2812 {(4,3),(6,5),(8,7)}.
    static const uint32_t kTglPinConvPairs[3][2] = {
        {4u, 3u},
        {6u, 5u},
        {8u, 7u},
    };
    OSArray *pathMap = *outArray;
    const unsigned int topCount = pathMap->getCount();
    for (unsigned int i = 0; i < 3u && i < topCount; ++i) {
        auto *pathSet = OSDynamicCast(OSArray, pathMap->getObject(i));
        if (!pathSet) {
            continue;
        }
        auto *pathEntry = OSDynamicCast(OSArray, pathSet->getObject(0));
        if (!pathEntry) {
            continue;
        }
        // AppleHDAFunctionGroup_80862807 creates 4 levels: top(3) -> l2(1) -> l3(1) -> l4(2) of dicts.
        OSArray *pathNodes = OSDynamicCast(OSArray, pathEntry->getObject(0));
        if (!pathNodes && OSDynamicCast(OSDictionary, pathEntry->getObject(0)) != nullptr) {
            pathNodes = pathEntry;
        }
        if (!pathNodes) {
            continue;
        }
        for (unsigned int j = 0; j < 2u; ++j) {
            auto *dict = OSDynamicCast(OSDictionary, pathNodes->getObject(j));
            if (!dict) {
                continue;
            }
            auto *nodeId = OSDynamicCast(OSNumber, dict->getObject("NodeID"));
            if (nodeId != nullptr) {
                nodeId->setValue(kTglPinConvPairs[i][j]);
            }
        }
    }

    auto *const *vtable = *reinterpret_cast<void *const *const *>(that);
    using t_set_path_map = void (*)(void *, OSArray *);
    reinterpret_cast<t_set_path_map>(vtable[0x240 / sizeof(void *)])(that, pathMap);
    return 0;
}

static int wrapPerformWidgetInitialization(void *that, uint8_t nid) {
    if (!that) {
        return static_cast<int>(kIOReturnBadArgument);
    }
    if (nid == 2u) {
        return isValidTrampolineOrg(gOrgPerformWidgetInitialization, wrapPerformWidgetInitialization)
            ? FunctionCast(wrapPerformWidgetInitialization, gOrgPerformWidgetInitialization)(that, 8u)
            : static_cast<int>(kIOReturnError);
    }
    if (nid == 3u || nid == 5u || nid == 7u || nid == 9u) {
        return isValidTrampolineOrg(gOrgPerformWidgetInitialization, wrapPerformWidgetInitialization)
            ? FunctionCast(wrapPerformWidgetInitialization, gOrgPerformWidgetInitialization)(that, 2u)
            : static_cast<int>(kIOReturnError);
    }
    if (nid == 4u || nid == 6u || nid == 8u) {
        const uint32_t pinIdx = static_cast<uint32_t>(nid - 4u) >> 1;
        const uint32_t convNid = 3u + 2u * pinIdx;
        auto **connListSlot = reinterpret_cast<OSArray **>(reinterpret_cast<uint8_t *>(that) + 0xf0);
        if (*connListSlot != nullptr) {
            (*connListSlot)->release();
            *connListSlot = nullptr;
        }
        OSArray *newList = OSArray::withCapacity(3);
        if (!newList) {
            return static_cast<int>(kIOReturnNoMemory);
        }
        static const uint32_t kConvNids[3] = {3u, 5u, 7u};
        for (uint32_t n : kConvNids) {
            OSNumber *num = OSNumber::withNumber(static_cast<unsigned long long>(n), 32);
            if (num != nullptr) {
                newList->setObject(num);
                num->release();
            }
        }
        *connListSlot = newList;

        auto *const *vtable = *reinterpret_cast<void *const *const *>(that);
        using t_select_conn = void (*)(void *, uint32_t);
        using t_exec_verb = int (*)(void *, uint32_t);
        reinterpret_cast<t_select_conn>(vtable[0x478 / sizeof(void *)])(that, convNid);
        const int rc = reinterpret_cast<t_exec_verb>(vtable[0x318 / sizeof(void *)])(
            that, 0x18560010u + (pinIdx << 4));
        if (rc == 0) {
            *reinterpret_cast<uint8_t *>(reinterpret_cast<uint8_t *>(that) + 0xe8) &= static_cast<uint8_t>(~0x04u);
            *reinterpret_cast<uint8_t *>(reinterpret_cast<uint8_t *>(that) + 0x37) &= 0x7fu;
        }
        return rc;
    }
    if (nid >= 0x0au && nid <= 0x0fu) {
        auto *const *vtable = *reinterpret_cast<void *const *const *>(that);
        using t_exec_verb = int (*)(void *, uint32_t);
        const int rc = reinterpret_cast<t_exec_verb>(vtable[0x318 / sizeof(void *)])(that, 0x40f000f0u);
        if (rc == 0) {
            *reinterpret_cast<uint8_t *>(reinterpret_cast<uint8_t *>(that) + 0xe8) &= static_cast<uint8_t>(~0x04u);
            *reinterpret_cast<uint8_t *>(reinterpret_cast<uint8_t *>(that) + 0x37) &= 0x7fu;
        }
        return rc;
    }
    return 0;
}

static int wrapPinSetControl(void *that, uint8_t ctrl) {
    int rc = isValidTrampolineOrg(gOrgPinSetControl, wrapPinSetControl)
        ? FunctionCast(wrapPinSetControl, gOrgPinSetControl)(that, ctrl)
        : static_cast<int>(kIOReturnError);
    if (rc == 0 && that != nullptr) {
        const uint32_t mNodeID =
            (*reinterpret_cast<const uint32_t *>(reinterpret_cast<const uint8_t *>(that) + 0x0c)) & 0xffffu;
        if (mNodeID == 4u || mNodeID == 8u) {
            auto *const *vtable = *reinterpret_cast<void *const *const *>(that);
            using t_send_verb = int (*)(void *, uint32_t, uint32_t, uint32_t *);
            uint32_t resp = 0;
            rc = reinterpret_cast<t_send_verb>(vtable[0x120 / sizeof(void *)])(
                that, 0x003u, 0xb000u | ((ctrl != 0x40u) ? 0x80u : 0u), &resp);
        }
    }
    return rc;
}

static const uint32_t kDpVolumeScaleQ16[256] = {
        0,     0,    43,    44,    45,    46,    48,    49,    51,    52,    54,    55,    57,    59,    60,    62,
       64,    66,    68,    70,    72,    74,    76,    78,    81,    83,    86,    88,    91,    93,    96,    99,
      102,   105,   108,   111,   115,   118,   121,   125,   129,   133,   136,   141,   145,   149,   153,   158,
      163,   167,   172,   177,   183,   188,   194,   199,   205,   211,   217,   224,   231,   237,   244,   252,
      259,   267,   275,   283,   291,   300,   308,   318,   327,   337,   347,   357,   367,   378,   389,   401,
      413,   425,   438,   450,   464,   477,   492,   506,   521,   536,   552,   569,   585,   603,   621,   639,
      658,   677,   697,   718,   739,   761,   783,   806,   830,   855,   880,   906,   933,   960,   989,  1018,
     1048,  1079,  1111,  1144,  1178,  1212,  1248,  1285,  1323,  1362,  1403,  1444,  1487,  1531,  1576,  1622,
     1670,  1720,  1771,  1823,  1877,  1932,  1989,  2048,  2109,  2171,  2235,  2301,  2369,  2439,  2511,  2585,
     2662,  2740,  2821,  2905,  2991,  3079,  3170,  3264,  3360,  3459,  3562,  3667,  3775,  3887,  4002,  4120,
     4242,  4367,  4496,  4629,  4766,  4907,  5052,  5201,  5355,  5513,  5676,  5844,  6016,  6194,  6377,  6566,
     6760,  6959,  7165,  7377,  7595,  7819,  8050,  8288,  8533,  8785,  9045,  9312,  9587,  9871, 10162, 10463,
    10772, 11090, 11418, 11755, 12103, 12460, 12829, 13208, 13598, 14000, 14414, 14840, 15278, 15730, 16194, 16673,
    17166, 17673, 18195, 18733, 19287, 19857, 20443, 21047, 21669, 22310, 22969, 23648, 24347, 25066, 25807, 26570,
    27355, 28163, 28995, 29852, 30735, 31643, 32578, 33541, 34532, 35552, 36603, 37685, 38798, 39945, 41125, 42341,
    43592, 44880, 46206, 47572, 48978, 50425, 51915, 53449, 55029, 56655, 58329, 60053, 61828, 63655, 65536, 65536
};

static int wrapDpInitialiseMCCSControls(void *that) {
    if (!isValidTrampolineOrg(gOrgDpInitialiseMCCSControls, wrapDpInitialiseMCCSControls)) {
        return static_cast<int>(kIOReturnError);
    }
    __sync_add_and_fetch(&gDpInitMccsCalls, 1u);
    uintptr_t vt = 0u;
    uint32_t curVol = 0xFEu;
    uint32_t curMute = 0u;
    if (that != nullptr) {
        vt = *reinterpret_cast<const uintptr_t *>(that);
        gDpEngineVtable = vt;
        auto *eb = reinterpret_cast<uint8_t *>(that);
        eb[0x450] = 1u;
        eb[0x451] = 0u;
        eb[0x452] = 0u;
        eb[0x453] = 1u;
        if (eb[0x454] == 0u || eb[0x454] == 0xFFu) {
            eb[0x454] = 0xFEu;
        }
        curVol = eb[0x454];
        curMute = eb[0x455];
        gDpLastVolume = curVol;
        gDpLastMute = curMute;
    }
    int rc = FunctionCast(wrapDpInitialiseMCCSControls, gOrgDpInitialiseMCCSControls)(that);
    if (NGreen::callback) {
        HDMI::publishLiveTelemetry(NGreen::callback->getIGPU());
    }
    IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: DP intialiseMCCSControls vtable=0x%llx vol=%u mute=%u rc=0x%x\n",
          static_cast<unsigned long long>(vt), curVol, curMute, static_cast<unsigned>(rc));
    return rc;
}

static int wrapDpMccsSetVolume(void *that, uint32_t channel, uint8_t volume) {
    (void)channel;
    __sync_add_and_fetch(&gDpSetVolumeCalls, 1u);
    gDpLastVolume = volume;
    if (that != nullptr) {
        *reinterpret_cast<volatile uint8_t *>(reinterpret_cast<uint8_t *>(that) + 0x454) = volume;
    }
    if (NGreen::callback) {
        HDMI::publishLiveTelemetry(NGreen::callback->getIGPU());
    }
    return 0;
}

static int wrapDpMccsSetMute(void *that, uint32_t channel, bool mute) {
    (void)channel;
    __sync_add_and_fetch(&gDpSetMuteCalls, 1u);
    const uint8_t m = mute ? 1u : 0u;
    gDpLastMute = m;
    if (that != nullptr) {
        *reinterpret_cast<volatile uint8_t *>(reinterpret_cast<uint8_t *>(that) + 0x455) = m;
    }
    if (NGreen::callback) {
        HDMI::publishLiveTelemetry(NGreen::callback->getIGPU());
    }
    return 0;
}

__attribute__((target("no-sse,no-sse2,no-mmx,no-avx")))
static int wrapEngineClipOutputSamples(void *that, const void *mixBuf, void *sampleBuf,
                                       uint32_t firstSampleFrame, uint32_t numSampleFrames,
                                       const void *streamFormat, void *audioStream) {
    if (!isValidTrampolineOrg(gOrgEngineClipOutputSamples, wrapEngineClipOutputSamples)) {
        return static_cast<int>(kIOReturnError);
    }
    int ret = FunctionCast(wrapEngineClipOutputSamples, gOrgEngineClipOutputSamples)(
        that, mixBuf, sampleBuf, firstSampleFrame, numSampleFrames, streamFormat, audioStream);
    const uintptr_t dpVt = gDpEngineVtable;
    if (ret == 0 && that != nullptr && dpVt != 0u &&
        *reinterpret_cast<const uintptr_t *>(that) == dpVt &&
        sampleBuf != nullptr && streamFormat != nullptr && numSampleFrames > 0u) {
        const auto *fmtBytes = reinterpret_cast<const uint8_t *>(streamFormat);
        if (*reinterpret_cast<const uint32_t *>(fmtBytes + 0x04) == 0x6c70636du) {
            uint32_t channels = *reinterpret_cast<const uint32_t *>(reinterpret_cast<const uint8_t *>(that) + 0x180);
            if (channels == 0u || channels > 8u) {
                channels = *reinterpret_cast<const uint32_t *>(fmtBytes);
            }
            if (channels >= 1u && channels <= 8u) {
                __sync_add_and_fetch(&gDpClipCalls, 1u);
                const uint8_t bitDepth = fmtBytes[0x0c];
                const uint8_t vol = *reinterpret_cast<volatile const uint8_t *>(
                    reinterpret_cast<const uint8_t *>(that) + 0x454);
                const uint8_t muted = *reinterpret_cast<volatile const uint8_t *>(
                    reinterpret_cast<const uint8_t *>(that) + 0x455);
                gDpLastVolume = vol;
                gDpLastMute = muted;
                const size_t firstSample = static_cast<size_t>(firstSampleFrame) * static_cast<size_t>(channels);
                const size_t sampleCount = static_cast<size_t>(numSampleFrames) * static_cast<size_t>(channels);
                if (muted != 0u || vol <= 1u) {
                    if (bitDepth < 0x11u) {
                        auto *dst16 = reinterpret_cast<int16_t *>(sampleBuf) + firstSample;
                        #pragma clang loop vectorize(disable) unroll(disable)
                        for (size_t i = 0; i < sampleCount; ++i) {
                            dst16[i] = 0;
                        }
                    } else {
                        auto *dst32 = reinterpret_cast<int32_t *>(sampleBuf) + firstSample;
                        #pragma clang loop vectorize(disable) unroll(disable)
                        for (size_t i = 0; i < sampleCount; ++i) {
                            dst32[i] = 0;
                        }
                    }
                } else if (vol < 0xFEu) {
                    const uint32_t scale = kDpVolumeScaleQ16[vol];
                    if (bitDepth < 0x11u) {
                        auto *dst16 = reinterpret_cast<int16_t *>(sampleBuf) + firstSample;
                        #pragma clang loop vectorize(disable) unroll(disable)
                        for (size_t i = 0; i < sampleCount; ++i) {
                            dst16[i] = static_cast<int16_t>(
                                (static_cast<int32_t>(dst16[i]) * static_cast<int32_t>(scale)) >> 16);
                        }
                    } else {
                        auto *dst32 = reinterpret_cast<int32_t *>(sampleBuf) + firstSample;
                        #pragma clang loop vectorize(disable) unroll(disable)
                        for (size_t i = 0; i < sampleCount; ++i) {
                            dst32[i] = static_cast<int32_t>(
                                (static_cast<int64_t>(dst32[i]) * static_cast<int64_t>(scale)) >> 16);
                        }
                    }
                }
            }
        }
    }
    return ret;
}

static size_t boundedStrLen(const char *s, size_t maxLen) {
    if (!s) {
        return 0;
    }
    size_t n = 0;
    while (n < maxLen && s[n] != '\0') {
        ++n;
    }
    return n;
}

static size_t findBytes(const uint8_t *hay, size_t hayLen, const uint8_t *needle, size_t needleLen, size_t start) {
    if (!hay || !needle || needleLen == 0u || hayLen < needleLen || start > hayLen - needleLen) {
        return hayLen;
    }
    const size_t limit = hayLen - needleLen;
    for (size_t i = start; i <= limit; ++i) {
        if (hay[i] == needle[0] && memcmp(hay + i, needle, needleLen) == 0) {
            return i;
        }
    }
    return hayLen;
}

static size_t countBytes(const uint8_t *hay, size_t hayLen, const uint8_t *needle, size_t needleLen) {
    size_t count = 0;
    size_t pos = 0;
    while (pos < hayLen) {
        pos = findBytes(hay, hayLen, needle, needleLen, pos);
        if (pos >= hayLen) {
            break;
        }
        ++count;
        pos += needleLen;
    }
    return count;
}

static uint32_t collectPatternWrites(const uint8_t *buf, size_t bufSize,
                                     const PatternSpec *specs, size_t numSpecs,
                                     ShdaWriteOp *ops, size_t maxOps, size_t *opCount,
                                     const char *label) {
    uint32_t mask = 0;
    for (size_t i = 0; i < numSpecs; ++i) {
        size_t hits[16] {};
        size_t hitCount = 0;
        size_t pos = 0;
        while (pos < bufSize) {
            pos = findBytes(buf, bufSize, specs[i].find, specs[i].size, pos);
            if (pos >= bufSize) {
                break;
            }
            if (hitCount < arrsize(hits)) {
                hits[hitCount] = pos;
            }
            ++hitCount;
            pos += specs[i].size;
        }

        if (hitCount == specs[i].expectedCount && hitCount <= arrsize(hits)) {
            if (*opCount + hitCount <= maxOps) {
                for (size_t h = 0; h < hitCount; ++h) {
                    ops[(*opCount)++] = {
                        const_cast<uint8_t *>(buf + hits[h]),
                        specs[i].replace,
                        specs[i].size
                    };
                }
                mask |= (1u << i);
            } else {
                SYSLOG("ngreen", "hdmi-shda: %s op buffer full at pattern[%zu]", label, i);
            }
        } else if (hitCount == 0u &&
                   countBytes(buf, bufSize, specs[i].replace, specs[i].size) == specs[i].expectedCount) {
            mask |= (1u << i);
        } else {
            SYSLOG("ngreen", "hdmi-shda: %s pattern[%zu] count=%zu expect=%zu",
                   label, i, hitCount, specs[i].expectedCount);
        }
    }
    return mask;
}

static uint32_t collectAhdaPrelinkSymbols(const uint8_t *base, size_t linkedSize, mach_vm_address_t *resolvedOut) {
    const auto *mh = reinterpret_cast<const mach_header_64 *>(base);
    if (mh->magic != MH_MAGIC_64 || mh->sizeofcmds > linkedSize - sizeof(mach_header_64)) {
        return 0;
    }

    const size_t cmdEnd = sizeof(mach_header_64) + mh->sizeofcmds;
    size_t off = sizeof(mach_header_64);
    const symtab_command *symtab = nullptr;
    for (uint32_t i = 0; i < mh->ncmds; ++i) {
        if (off + sizeof(load_command) > cmdEnd) {
            return 0;
        }
        const auto *lc = reinterpret_cast<const load_command *>(base + off);
        if (lc->cmdsize < sizeof(load_command) || lc->cmdsize > cmdEnd - off) {
            return 0;
        }
        if (lc->cmd == LC_SYMTAB) {
            if (lc->cmdsize < sizeof(symtab_command)) {
                return 0;
            }
            symtab = reinterpret_cast<const symtab_command *>(lc);
            break;
        }
        off += lc->cmdsize;
    }
    if (!symtab || symtab->nsyms == 0u) {
        return 0;
    }
    if (symtab->stroff > linkedSize || symtab->strsize > linkedSize - symtab->stroff ||
        symtab->symoff > linkedSize ||
        static_cast<uint64_t>(symtab->nsyms) * sizeof(nlist_64) > linkedSize - symtab->symoff) {
        return 0;
    }

    const char *strtab = reinterpret_cast<const char *>(base + symtab->stroff);
    const auto *syms = reinterpret_cast<const nlist_64 *>(base + symtab->symoff);
    const uint64_t bufStart = reinterpret_cast<uint64_t>(base);
    const uint64_t bufEnd = bufStart + linkedSize;
    uint32_t foundMask = 0;

    for (uint32_t i = 0; i < symtab->nsyms; ++i) {
        const nlist_64 &nl = syms[i];
        if ((nl.n_type & N_STAB) != 0u || (nl.n_type & N_TYPE) != N_SECT ||
            nl.n_un.n_strx >= symtab->strsize) {
            continue;
        }
        const char *symName = strtab + nl.n_un.n_strx;
        const size_t maxRem = symtab->strsize - nl.n_un.n_strx;
        bool hasNul = false;
        for (size_t k = 0; k < maxRem; ++k) {
            if (symName[k] == '\0') {
                hasNul = true;
                break;
            }
        }
        if (!hasNul) {
            continue;
        }
        for (size_t t = 0; t < arrsize(kAhdaTargetSymbols); ++t) {
            if ((foundMask & (1u << t)) != 0u || strcmp(symName, kAhdaTargetSymbols[t]) != 0) {
                continue;
            }
            if (nl.n_value < bufStart || nl.n_value + 16ULL > bufEnd) {
                SYSLOG("ngreen", "hdmi-shda: %s out of range val=0x%llx [%llx..%llx)",
                       kAhdaTargetSymbols[t], static_cast<unsigned long long>(nl.n_value),
                       static_cast<unsigned long long>(bufStart), static_cast<unsigned long long>(bufEnd));
                continue;
            }
            const auto *fn = reinterpret_cast<const uint8_t *>(static_cast<uintptr_t>(nl.n_value));
            if (fn[0] != 0x55u || fn[1] != 0x48u || fn[2] != 0x89u || fn[3] != 0xe5u) {
                SYSLOG("ngreen", "hdmi-shda: %s unexpected prologue %02x %02x %02x %02x",
                       kAhdaTargetSymbols[t], fn[0], fn[1], fn[2], fn[3]);
                continue;
            }
            resolvedOut[t] = static_cast<mach_vm_address_t>(nl.n_value);
            foundMask |= (1u << t);
        }
    }
    return foundMask;
}

static bool applyShdaPrelinkShift(uint8_t *base, size_t linkedSize, uint64_t kcSlide) {
    auto *mh = reinterpret_cast<mach_header_64 *>(base);
    const size_t cmdEnd = sizeof(mach_header_64) + mh->sizeofcmds;
    if (cmdEnd > linkedSize) {
        return false;
    }

    // Matches shda::preparePrelink (clear MH_DYLIB_IN_CACHE bit 31, shift vmaddrs/nlists by -kcSlide).
    base[0x1bu] &= 0x7fu;

    size_t off = sizeof(mach_header_64);
    for (uint32_t i = 0; i < mh->ncmds; ++i) {
        if (off + sizeof(load_command) > cmdEnd) {
            return false;
        }
        auto *lc = reinterpret_cast<load_command *>(base + off);
        if (lc->cmdsize < sizeof(load_command) || lc->cmdsize > cmdEnd - off) {
            return false;
        }
        if (lc->cmd == LC_SEGMENT_64) {
            if (lc->cmdsize < sizeof(segment_command_64)) {
                return false;
            }
            auto *seg = reinterpret_cast<segment_command_64 *>(lc);
            if (seg->vmaddr < kcSlide) {
                return false;
            }
            seg->vmaddr -= kcSlide;
            if (static_cast<uint64_t>(seg->nsects) * sizeof(section_64) > lc->cmdsize - sizeof(segment_command_64)) {
                return false;
            }
            auto *sects = reinterpret_cast<section_64 *>(seg + 1);
            for (uint32_t s = 0; s < seg->nsects; ++s) {
                sects[s].addr -= kcSlide;
            }
        } else if (lc->cmd == LC_DYSYMTAB) {
            if (lc->cmdsize < sizeof(dysymtab_command)) {
                return false;
            }
            const auto *dysym = reinterpret_cast<const dysymtab_command *>(lc);
            if (dysym->nlocrel != 0u || dysym->nextrel != 0u) {
                return false;
            }
        } else if (lc->cmd == LC_SYMTAB) {
            if (lc->cmdsize < sizeof(symtab_command)) {
                return false;
            }
            const auto *symtab = reinterpret_cast<const symtab_command *>(lc);
            if (symtab->symoff > linkedSize ||
                static_cast<uint64_t>(symtab->nsyms) * sizeof(nlist_64) > linkedSize - symtab->symoff) {
                return false;
            }
            auto *syms = reinterpret_cast<nlist_64 *>(base + symtab->symoff);
            for (uint32_t s = 0; s < symtab->nsyms; ++s) {
                if (syms[s].n_type <= 0x1fu) {
                    syms[s].n_value -= kcSlide;
                }
            }
        }
        off += lc->cmdsize;
    }
    return true;
}

static bool machoNameEq(const char field[16], const char *lit) {
    for (size_t i = 0; i < 16u; ++i) {
        if (field[i] != lit[i]) {
            return false;
        }
        if (lit[i] == '\0') {
            return true;
        }
    }
    return lit[16] == '\0';
}

static bool findMachoTextSection(const uint8_t *base, size_t linkedSize, size_t &offOut, size_t &sizeOut) {
    if (linkedSize < sizeof(mach_header_64)) {
        return false;
    }
    const auto *mh = reinterpret_cast<const mach_header_64 *>(base);
    if (mh->magic != MH_MAGIC_64 || mh->sizeofcmds > linkedSize - sizeof(mach_header_64)) {
        return false;
    }
    const size_t cmdEnd = sizeof(mach_header_64) + mh->sizeofcmds;
    size_t off = sizeof(mach_header_64);
    for (uint32_t i = 0; i < mh->ncmds; ++i) {
        if (off + sizeof(load_command) > cmdEnd) {
            return false;
        }
        const auto *lc = reinterpret_cast<const load_command *>(base + off);
        if (lc->cmdsize < sizeof(load_command) || lc->cmdsize > cmdEnd - off) {
            return false;
        }
        if (lc->cmd == LC_SEGMENT_64 && lc->cmdsize >= sizeof(segment_command_64)) {
            const auto *seg = reinterpret_cast<const segment_command_64 *>(lc);
            if (machoNameEq(seg->segname, "__TEXT") &&
                static_cast<uint64_t>(seg->nsects) * sizeof(section_64) <= lc->cmdsize - sizeof(segment_command_64)) {
                const auto *sects = reinterpret_cast<const section_64 *>(seg + 1);
                for (uint32_t s = 0; s < seg->nsects; ++s) {
                    if (machoNameEq(sects[s].sectname, "__text")) {
                        if (sects[s].offset <= linkedSize && sects[s].size <= linkedSize - sects[s].offset) {
                            offOut = static_cast<size_t>(sects[s].offset);
                            sizeOut = static_cast<size_t>(sects[s].size);
                            return true;
                        }
                        return false;
                    }
                }
            }
        }
        off += lc->cmdsize;
    }
    return false;
}

static uint32_t findPatternInText(const uint8_t *text, size_t textSize, const uint8_t *needle, size_t needleLen, size_t &firstOffOut) {
    uint32_t count = 0;
    if (textSize < needleLen) {
        return 0;
    }
    for (size_t i = 0; i <= textSize - needleLen; ++i) {
        if (text[i] == needle[0] && memcmp(text + i, needle, needleLen) == 0) {
            if (count == 0u) {
                firstOffOut = i;
            }
            ++count;
        }
    }
    return count;
}

static void writeAbsJmp(uint8_t *dst, uintptr_t target) {
    dst[0] = 0x48u;
    dst[1] = 0xB8u;
    for (uint32_t i = 0; i < 8u; ++i) {
        dst[2u + i] = static_cast<uint8_t>((static_cast<uint64_t>(target) >> (i * 8u)) & 0xFFu);
    }
    dst[10] = 0xFFu;
    dst[11] = 0xE0u;
}

static void installMod1PrelinkHooks(uint8_t *base, size_t linkedSize) {
    if (gShdaMod1HookedOnce != 0u) {
        return;
    }
    size_t textOff = 0;
    size_t textSize = 0;
    if (!findMachoTextSection(base, linkedSize, textOff, textSize)) {
        return;
    }

    static const uint8_t kFSetGfxClkDiv[18] = {
        0x81, 0xBF, 0xF0, 0x0E, 0x00, 0x00, 0x86, 0x80, 0x00, 0x00, 0x75, 0x48, 0x8B, 0x87, 0xF4, 0x0E, 0x00, 0x00
    };
    static const uint8_t kFFindValidDispCodec[18] = {
        0x55, 0x48, 0x89, 0xE5, 0x41, 0x57, 0x41, 0x56, 0x41, 0x55, 0x41, 0x54, 0x53, 0x50, 0x48, 0x89, 0x7D, 0xD0
    };

    const uint8_t *text = base + textOff;
    size_t clkOff = 0;
    size_t codecOff = 0;
    const uint32_t clkCount = findPatternInText(text, textSize, kFSetGfxClkDiv, sizeof(kFSetGfxClkDiv), clkOff);
    const uint32_t codecCount = findPatternInText(text, textSize, kFFindValidDispCodec, sizeof(kFFindValidDispCodec), codecOff);
    if (clkCount == 0u && codecCount == 0u) {
        return;
    }
    if (clkCount != 1u || codecCount != 1u || clkOff + 12u > textSize || codecOff + 12u > textSize) {
        SYSLOG("ngreen", "HP-HDMI-AUDIO [PCFIX53-AUDIO]: mod1 prelink hook mismatch clk=%u codec=%u", clkCount, codecCount);
        return;
    }
    if (!__sync_bool_compare_and_swap(&gShdaMod1HookedOnce, 0u, 1u)) {
        return;
    }

    writeAbsJmp(base + textOff + clkOff, reinterpret_cast<uintptr_t>(HDMI::wrapSetGraphicsClockDivider));
    writeAbsJmp(base + textOff + codecOff, reinterpret_cast<uintptr_t>(HDMI::wrapFindValidDisplayCodec));
    gShdaV7OffClk = static_cast<uint32_t>(textOff + clkOff);
    gShdaV7OffCodec = static_cast<uint32_t>(textOff + codecOff);
    gShdaV7Hooks = 0x3u;
    if (NGreen::callback) {
        HDMI::publishLiveTelemetry(NGreen::callback->getIGPU());
    }
    IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: SimpleHDA mod1 prelink hooks installed clkOff=0x%x codecOff=0x%x\n",
          static_cast<unsigned>(gShdaV7OffClk), static_cast<unsigned>(gShdaV7OffCodec));
}

static bool wrapShdaPreparePrelink(void *linkedBuf, size_t linkedSize, uint64_t kcSlide) {
    if (!gShdaValidateFile || !gShdaValidateFile(linkedBuf, linkedSize)) {
        return false;
    }
    if (!linkedBuf || linkedSize < sizeof(mach_header_64)) {
        return false;
    }

    auto *base = reinterpret_cast<uint8_t *>(linkedBuf);
    mach_vm_address_t resolved[arrsize(kAhdaTargetSymbols)] {};
    const uint32_t foundMask = collectAhdaPrelinkSymbols(base, linkedSize, resolved);

    if (!applyShdaPrelinkShift(base, linkedSize, kcSlide)) {
        return false;
    }

    installMod1PrelinkHooks(base, linkedSize);

    if (foundMask != 0u && gSavedPatcher && __sync_bool_compare_and_swap(&gShdaAhdaRoutedOnce, 0u, 1u)) {
        static const char * const kNames[7] = {
            "constructPathMapByDiscovery",
            "performWidgetInitialization",
            "pinSetControl",
            "intialiseMCCSControls",
            "mccsSetCurrentSpeakerVolume",
            "mccsSetCurrentSpeakerMute",
            "clipOutputSamples"
        };
        const mach_vm_address_t wrappers[7] = {
            reinterpret_cast<mach_vm_address_t>(wrapConstructPathMapByDiscovery),
            reinterpret_cast<mach_vm_address_t>(wrapPerformWidgetInitialization),
            reinterpret_cast<mach_vm_address_t>(wrapPinSetControl),
            reinterpret_cast<mach_vm_address_t>(wrapDpInitialiseMCCSControls),
            reinterpret_cast<mach_vm_address_t>(wrapDpMccsSetVolume),
            reinterpret_cast<mach_vm_address_t>(wrapDpMccsSetMute),
            reinterpret_cast<mach_vm_address_t>(wrapEngineClipOutputSamples)
        };
        mach_vm_address_t * const orgSlots[7] = {
            &gOrgConstructPathMapByDiscovery,
            &gOrgPerformWidgetInitialization,
            &gOrgPinSetControl,
            &gOrgDpInitialiseMCCSControls,
            &gOrgDpMccsSetVolume,
            &gOrgDpMccsSetMute,
            &gOrgEngineClipOutputSamples
        };

        uint32_t routed = 0;
        for (size_t t = 0; t < arrsize(resolved); ++t) {
            if (resolved[t] == 0u) {
                SYSLOG("ngreen", "hdmi-shda: missing AppleHDA symbol %s", kNames[t]);
                continue;
            }
            gSavedPatcher->clearError();
            #pragma clang diagnostic push
            #pragma clang diagnostic ignored "-Wdeprecated-declarations"
            mach_vm_address_t org = gSavedPatcher->routeFunctionLong(
                resolved[t], wrappers[t], true, true, false);
            #pragma clang diagnostic pop
            if (org != 0u && org != wrappers[t] && gSavedPatcher->getError() == KernelPatcher::Error::NoError) {
                *orgSlots[t] = org;
                ++routed;
                if (t >= 3u) {
                    __sync_or_and_fetch(&gDpVolRoutedMask, 1u << (t - 3u));
                }
            } else {
                SYSLOG("ngreen", "hdmi-shda: routeFunctionLong(%s) invalid org=0x%llx wrapper=0x%llx err=%d",
                       kNames[t], static_cast<unsigned long long>(org),
                       static_cast<unsigned long long>(wrappers[t]),
                       static_cast<int>(gSavedPatcher->getError()));
                gSavedPatcher->clearError();
            }
        }
        gShdaAhdaRouted = routed;
        IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: SimpleHDA AppleHDA linkedBuf=%p size=0x%zx mask=0x%x routed=%u/7\n",
              linkedBuf, linkedSize, foundMask, routed);
    }
    return true;
}

static size_t applyPatternSpecs(KernelPatcher &patcher, KernelPatcher::KextInfo *kext,
                                mach_vm_address_t slide, size_t size,
                                const PatternSpec *specs, size_t numSpecs, const char *label) {
    size_t applied = 0;
    for (size_t i = 0; i < numSpecs; ++i) {
        const LookupPatchPlus patch {
            kext, specs[i].find, specs[i].replace, specs[i].size, specs[i].expectedCount
        };
        if (patch.apply(patcher, slide, size)) {
            ++applied;
        } else {
            SYSLOG("ngreen", "HP-HDMI-AUDIO: %s patch[%zu] failed err=%d",
                   label, i, patcher.getError());
            patcher.clearError();
        }
    }
    return applied;
}

void HDMI::init() {
    callback = this;
    if (!isHdmiAudioFixEnabled()) {
        return;
    }
    lilu.onKextLoadForce(&kextAppleHDAController);
    lilu.onKextLoadForce(&kextAppleHDA);
}

void HDMI::patchSimpleHDA(KernelPatcher &patcher) {
    if (!isHdmiAudioFixEnabled()) {
        return;
    }
    if (!__sync_bool_compare_and_swap(&gShdaPatchAttempted, 0u, 1u)) {
        return;
    }
    gSavedPatcher = &patcher;

    const OSSymbol *sym = OSSymbol::withCStringNoCopy("SimpleHDA");
    if (!sym) {
        return;
    }
    const OSMetaClass *mc = OSMetaClass::getMetaClassWithName(sym);
    sym->release();
    if (!mc) {
        SYSLOG("ngreen", "hdmi-shda: SimpleHDA metaclass not found");
        return;
    }

    const auto mcAddr = reinterpret_cast<mach_vm_address_t>(mc);
    if (mcAddr <= 0x222a8ULL) {
        SYSLOG("ngreen", "hdmi-shda: unexpected SimpleHDA mcAddr=0x%llx",
               static_cast<unsigned long long>(mcAddr));
        return;
    }

    const mach_vm_address_t shdaBase = mcAddr - 0x222a8ULL;
    const uint32_t magic = *reinterpret_cast<const uint32_t *>(static_cast<uintptr_t>(shdaBase));
    const mach_vm_address_t mcVptr = *reinterpret_cast<const mach_vm_address_t *>(static_cast<uintptr_t>(mcAddr));
    if (magic != MH_MAGIC_64 || mcVptr != shdaBase + 0x17978ULL) {
        SYSLOG("ngreen", "hdmi-shda: base validation failed magic=0x%x vptr=0x%llx expect=0x%llx",
               magic, static_cast<unsigned long long>(mcVptr),
               static_cast<unsigned long long>(shdaBase + 0x17978ULL));
        return;
    }

    const auto *mods = reinterpret_cast<const ShdaModule *>(static_cast<uintptr_t>(shdaBase + 0x17b80ULL));
    const ShdaModule &mod1 = mods[1];
    const ShdaModule &mod4 = mods[4];
    if (!mod1.identifier || strcmp(mod1.identifier, "com.apple.driver.AppleHDAController") != 0 ||
        !mod1.plist || !mod1.executable || mod1.executableSize != 0x36eb0u) {
        SYSLOG("ngreen", "hdmi-shda: mod1 validation failed size=0x%zx", mod1.executableSize);
        return;
    }
    if (!mod4.identifier || strcmp(mod4.identifier, "com.apple.driver.AppleHDA") != 0 ||
        !mod4.executable || mod4.executableSize != 0x12aab0u) {
        SYSLOG("ngreen", "hdmi-shda: mod4 validation failed size=0x%zx", mod4.executableSize);
        return;
    }

    gShdaFound = 1u;

    ShdaWriteOp ops[64] {};
    size_t opCount = 0;

    static constexpr char kOldPciStr[] = "<string>pci8086,9d70</string>";
    static constexpr char kNewPciStr[] = "<string>pci8086,a0c8</string>";
    static_assert(sizeof(kOldPciStr) == sizeof(kNewPciStr), "PCI match string length mismatch");
    static constexpr size_t kPciStrLen = sizeof(kOldPciStr) - 1u;

    uint32_t mod1Mask = 0;
    const size_t plistLen = boundedStrLen(mod1.plist, 65536u);
    if (plistLen > 0u && plistLen < 65536u) {
        const auto *plistBytes = reinterpret_cast<const uint8_t *>(mod1.plist);
        const size_t oldCnt = countBytes(plistBytes, plistLen,
                                         reinterpret_cast<const uint8_t *>(kOldPciStr), kPciStrLen);
        if (oldCnt == 1u) {
            const size_t pos = findBytes(plistBytes, plistLen,
                                         reinterpret_cast<const uint8_t *>(kOldPciStr), kPciStrLen, 0u);
            if (pos < plistLen && opCount < arrsize(ops)) {
                ops[opCount++] = {
                    const_cast<uint8_t *>(plistBytes + pos),
                    reinterpret_cast<const uint8_t *>(kNewPciStr),
                    kPciStrLen
                };
                mod1Mask |= (1u << 24);
            }
        } else if (oldCnt == 0u &&
                   countBytes(plistBytes, plistLen,
                              reinterpret_cast<const uint8_t *>(kNewPciStr), kPciStrLen) == 1u) {
            mod1Mask |= (1u << 24);
        } else {
            SYSLOG("ngreen", "hdmi-shda: mod1 plist 9d70 count=%zu len=%zu", oldCnt, plistLen);
        }
    }

    mod1Mask |= collectPatternWrites(mod1.executable, mod1.executableSize,
                                     kCtrlPatterns, arrsize(kCtrlPatterns),
                                     ops, arrsize(ops), &opCount, "mod1");
    const uint32_t mod4Mask = collectPatternWrites(mod4.executable, mod4.executableSize,
                                                   kAhdaPatterns, arrsize(kAhdaPatterns),
                                                   ops, arrsize(ops), &opCount, "mod4");

    bool writesOk = true;
    if (opCount > 0u) {
        const kern_return_t kr = MachInfo::setKernelWriting(true, KernelPatcher::kernelWriteLock);
        if (kr == KERN_SUCCESS) {
            for (size_t i = 0; i < opCount; ++i) {
                lilu_os_memcpy(ops[i].dst, ops[i].src, ops[i].len);
            }
            MachInfo::setKernelWriting(false, KernelPatcher::kernelWriteLock);
        } else {
            writesOk = false;
            SYSLOG("ngreen", "hdmi-shda: setKernelWriting failed kr=%d", kr);
        }
    }
    if (writesOk) {
        gShdaMod1Patches = mod1Mask;
        gShdaMod4Patches = mod4Mask;
    }

    const mach_vm_address_t preparePrelinkAddr = shdaBase + 0x2851ULL;
    const mach_vm_address_t validateFileAddr = shdaBase + 0x1c42ULL;
    static constexpr uint8_t kExpectedPreparePrelink[18] = {
        0x55, 0x48, 0x89, 0xe5, 0x41, 0x56, 0x53,
        0x48, 0x89, 0xd3, 0x49, 0x89, 0xfe,
        0xe8, 0xdf, 0xf3, 0xff, 0xff
    };
    static constexpr uint8_t kExpectedValidateFile[8] = {
        0x55, 0x48, 0x89, 0xe5, 0x41, 0x57, 0x41, 0x56
    };

    bool prelinkHooked = false;
    if (memcmp(reinterpret_cast<const void *>(static_cast<uintptr_t>(preparePrelinkAddr)),
               kExpectedPreparePrelink, sizeof(kExpectedPreparePrelink)) == 0 &&
        memcmp(reinterpret_cast<const void *>(static_cast<uintptr_t>(validateFileAddr)),
               kExpectedValidateFile, sizeof(kExpectedValidateFile)) == 0) {
        gShdaValidateFile = reinterpret_cast<ShdaValidateFileFn>(static_cast<uintptr_t>(validateFileAddr));
        patcher.clearError();
        // Use buildWrapper=false because shda::preparePrelink calls validateFile via relative callq at byte +13.
        #pragma clang diagnostic push
        #pragma clang diagnostic ignored "-Wdeprecated-declarations"
        patcher.routeFunctionLong(preparePrelinkAddr,
                                  reinterpret_cast<mach_vm_address_t>(wrapShdaPreparePrelink),
                                  false, true, false);
        #pragma clang diagnostic pop
        if (patcher.getError() == KernelPatcher::Error::NoError) {
            prelinkHooked = true;
        } else {
            SYSLOG("ngreen", "hdmi-shda: routeFunctionLong(preparePrelink) failed err=%d",
                   static_cast<int>(patcher.getError()));
            patcher.clearError();
        }
    } else {
        SYSLOG("ngreen", "hdmi-shda: preparePrelink/validateFile prologue mismatch");
    }

    IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: SimpleHDA base=0x%llx ops=%zu writesOk=%d mod1=0x%x mod4=0x%x prelinkHooked=%d\n",
          static_cast<unsigned long long>(shdaBase), opCount, writesOk ? 1 : 0,
          gShdaMod1Patches, gShdaMod4Patches, prelinkHooked ? 1 : 0);
}

bool HDMI::processKext(KernelPatcher &patcher, size_t id, mach_vm_address_t slide, size_t size) {
    if (!isHdmiAudioFixEnabled()) {
        return false;
    }

    if (kextAppleHDAController.loadIndex == id) {
        if (gShdaMod1Patches != 0u) {
            IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: AppleHDAController already patched via SimpleHDA mod1=0x%x hooks=0x%x, skipping processKext\n",
                  static_cast<unsigned>(gShdaMod1Patches), static_cast<unsigned>(gShdaV7Hooks));
            return true;
        }
        const size_t applied = applyPatternSpecs(
            patcher, &kextAppleHDAController, slide, size,
            kCtrlPatterns, arrsize(kCtrlPatterns), "AppleHDAController");
        IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: AppleHDAController TGL patches applied %zu/%zu\n",
              applied, arrsize(kCtrlPatterns));
        return true;
    } else if (kextAppleHDA.loadIndex == id) {
        if (gShdaAhdaRoutedOnce != 0u || gShdaMod4Patches != 0u) {
            IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: AppleHDA already patched/routed via SimpleHDA mod4=0x%x routed=%u/7, skipping processKext\n",
                  static_cast<unsigned>(gShdaMod4Patches), static_cast<unsigned>(gShdaAhdaRouted));
            return true;
        }
        const size_t applied = applyPatternSpecs(
            patcher, &kextAppleHDA, slide, size,
            kAhdaPatterns, arrsize(kAhdaPatterns), "AppleHDA");

        mach_vm_address_t tmpOrgs[7] {};
        RouteRequestPlus requests[7] = {
            {kAhdaTargetSymbols[0], wrapConstructPathMapByDiscovery, tmpOrgs[0]},
            {kAhdaTargetSymbols[1], wrapPerformWidgetInitialization, tmpOrgs[1]},
            {kAhdaTargetSymbols[2], wrapPinSetControl, tmpOrgs[2]},
            {kAhdaTargetSymbols[3], wrapDpInitialiseMCCSControls, tmpOrgs[3]},
            {kAhdaTargetSymbols[4], wrapDpMccsSetVolume, tmpOrgs[4]},
            {kAhdaTargetSymbols[5], wrapDpMccsSetMute, tmpOrgs[5]},
            {kAhdaTargetSymbols[6], wrapEngineClipOutputSamples, tmpOrgs[6]},
        };
        const mach_vm_address_t wrappers[7] = {
            reinterpret_cast<mach_vm_address_t>(wrapConstructPathMapByDiscovery),
            reinterpret_cast<mach_vm_address_t>(wrapPerformWidgetInitialization),
            reinterpret_cast<mach_vm_address_t>(wrapPinSetControl),
            reinterpret_cast<mach_vm_address_t>(wrapDpInitialiseMCCSControls),
            reinterpret_cast<mach_vm_address_t>(wrapDpMccsSetVolume),
            reinterpret_cast<mach_vm_address_t>(wrapDpMccsSetMute),
            reinterpret_cast<mach_vm_address_t>(wrapEngineClipOutputSamples),
        };
        mach_vm_address_t * const orgSlots[7] = {
            &gOrgConstructPathMapByDiscovery,
            &gOrgPerformWidgetInitialization,
            &gOrgPinSetControl,
            &gOrgDpInitialiseMCCSControls,
            &gOrgDpMccsSetVolume,
            &gOrgDpMccsSetMute,
            &gOrgEngineClipOutputSamples,
        };
        size_t routed = 0;
        for (size_t i = 0; i < arrsize(requests); ++i) {
            if (requests[i].route(patcher, id, slide, size) &&
                tmpOrgs[i] != 0u && tmpOrgs[i] != wrappers[i]) {
                *orgSlots[i] = tmpOrgs[i];
                ++routed;
                if (i >= 3u) {
                    __sync_or_and_fetch(&gDpVolRoutedMask, 1u << (i - 3u));
                }
            } else {
                SYSLOG("ngreen", "HP-HDMI-AUDIO: AppleHDA route[%zu] (%s) skipped/failed org=0x%llx wrapper=0x%llx err=%d",
                       i, requests[i].symbol,
                       static_cast<unsigned long long>(tmpOrgs[i]),
                       static_cast<unsigned long long>(wrappers[i]),
                       static_cast<int>(patcher.getError()));
                patcher.clearError();
            }
        }
        IOLog("HP-HDMI-AUDIO [PCFIX53-AUDIO]: AppleHDA TGL patches=%zu/%zu routes=%zu/%zu\n",
              applied, arrsize(kAhdaPatterns), routed, arrsize(requests));
        return true;
    }

    return false;
}
