#import <Foundation/Foundation.h>
#import <CoreWLAN/CoreWLAN.h>
#import <CoreAudio/CoreAudio.h>
#import <CoreGraphics/CoreGraphics.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOMessage.h>
#include <IOKit/pwr_mgt/IOPMLib.h>
#include <IOKit/graphics/IOGraphicsLib.h>
#include <spawn.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char **environ;

static io_connect_t gRootPort = MACH_PORT_NULL;
static IONotificationPortRef gNotifyPort = NULL;
static io_object_t gNotifier = MACH_PORT_NULL;
static io_iterator_t gWranglerMatchIter = MACH_PORT_NULL;
static io_object_t gWranglerNotifier = MACH_PORT_NULL;
static dispatch_queue_t gAudioQueue = NULL;
static dispatch_queue_t gWifiQueue = NULL;
static dispatch_queue_t gDisplayQueue = NULL;
static volatile uint64_t gWakeSeq = 0;
static volatile uint64_t gDisplayWakeSeq = 0;
static volatile int gDisplayIsAwake = 1;
static volatile int gPreSleepCaptured = 0;
static volatile int gPreSleepBkltNonZero = 1;
static volatile SInt32 gSavedBklt = 24951;
static uint64_t gLastAmpQuickNs = 0;
static AudioDeviceID gWatchedSpeakerId = 0;

static const char *kWakeBlankFlagPath = "/private/var/run/hp-wake-blank";
static const char *kSavedBkltPath = "/private/var/run/hp-saved-bklt";

static void hpLog(NSString *fmt, ...) NS_FORMAT_FUNCTION(1, 2);
static void hpLog(NSString *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    NSString *msg = [[NSString alloc] initWithFormat:fmt arguments:ap];
    va_end(ap);

    time_t now = time(NULL);
    struct tm tmv;
    localtime_r(&now, &tmv);
    char ts[32];
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", &tmv);
    fprintf(stdout, "[%s] [hp-wake-helper] %s\n", ts, [msg UTF8String]);
    fflush(stdout);
}

static int getServiceCurrentPowerState(io_service_t service) {
    if (service == MACH_PORT_NULL) return -1;
    int ps = -1;
    CFTypeRef pmProp = IORegistryEntryCreateCFProperty(service, CFSTR("IOPowerManagement"), kCFAllocatorDefault, 0);
    if (pmProp != NULL) {
        if (CFGetTypeID(pmProp) == CFDictionaryGetTypeID()) {
            CFNumberRef num = (CFNumberRef)CFDictionaryGetValue((CFDictionaryRef)pmProp, CFSTR("CurrentPowerState"));
            if (num != NULL && CFGetTypeID(num) == CFNumberGetTypeID()) {
                int val = -1;
                if (CFNumberGetValue(num, kCFNumberIntType, &val)) {
                    ps = val;
                }
            }
        }
        CFRelease(pmProp);
    }
    return ps;
}

static int getDisplayWranglerPowerState(void) {
    io_service_t wrangler = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IODisplayWrangler"));
    if (wrangler == MACH_PORT_NULL) return -1;
    int ps = getServiceCurrentPowerState(wrangler);
    IOObjectRelease(wrangler);
    return ps;
}

static int getFramebufferPowerState(void) {
    io_service_t fb = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleIntelFramebuffer"));
    if (fb == MACH_PORT_NULL) return -1;
    int ps = getServiceCurrentPowerState(fb);
    IOObjectRelease(fb);
    return ps;
}

static io_service_t findBacklightDisplayService(void) {
    const char *classes[] = { "AppleBacklightDisplay", "IODisplayConnect" };
    for (size_t c = 0; c < sizeof(classes) / sizeof(classes[0]); c++) {
        io_iterator_t iter = MACH_PORT_NULL;
        if (IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching(classes[c]), &iter) != KERN_SUCCESS || iter == MACH_PORT_NULL) {
            continue;
        }
        io_service_t svc = MACH_PORT_NULL;
        while ((svc = IOIteratorNext(iter)) != MACH_PORT_NULL) {
            SInt32 val = 0, min = 0, max = 0;
            if (IODisplayGetIntegerRangeParameter(svc, kNilOptions, CFSTR("bklt"), &val, &min, &max) == kIOReturnSuccess && max > 0) {
                IOObjectRelease(iter);
                return svc;
            }
            IOObjectRelease(svc);
        }
        IOObjectRelease(iter);
    }
    return MACH_PORT_NULL;
}

static SInt32 readHardwareBklt(void) {
    io_service_t svc = findBacklightDisplayService();
    if (svc == MACH_PORT_NULL) {
        return -1;
    }
    SInt32 val = -1, min = 0, max = 0;
    if (IODisplayGetIntegerRangeParameter(svc, kNilOptions, CFSTR("bklt"), &val, &min, &max) != kIOReturnSuccess) {
        val = -1;
    }
    IOObjectRelease(svc);
    return val;
}

static void writeHardwareBkltAndNeutralRGBScale(SInt32 bkltVal, bool resetRGBScale) {
    io_service_t svc = findBacklightDisplayService();
    if (svc == MACH_PORT_NULL) {
        return;
    }
    if (bkltVal >= 0) {
        IODisplaySetIntegerParameter(svc, kNilOptions, CFSTR("bklt"), bkltVal);
    }
    if (resetRGBScale) {
        IODisplaySetIntegerParameter(svc, kNilOptions, CFSTR("rgsc"), 65536);
        IODisplaySetIntegerParameter(svc, kNilOptions, CFSTR("ggsc"), 65536);
        IODisplaySetIntegerParameter(svc, kNilOptions, CFSTR("bgsc"), 65536);
    }
    IOObjectRelease(svc);
}

static void saveBkltToDisk(SInt32 val) {
    if (val <= 600 || val > 65535) return;
    FILE *fp = fopen(kSavedBkltPath, "w");
    if (fp) {
        fprintf(fp, "%d\n", (int)val);
        fclose(fp);
    }
}

static SInt32 loadSavedBkltFromDisk(void) {
    FILE *fp = fopen(kSavedBkltPath, "r");
    if (!fp) return 24951;
    int v = 24951;
    if (fscanf(fp, "%d", &v) != 1 || v <= 600 || v > 65535) {
        v = 24951;
    }
    fclose(fp);
    return (SInt32)v;
}

static void verifyAndRefreshPostWakeDisplay(const char *tag, int guardZero) {
    SInt32 cur = readHardwareBklt();
    if (guardZero && cur >= 0 && cur <= 600) {
        SInt32 target = __atomic_load_n(&gSavedBklt, __ATOMIC_SEQ_CST);
        if (target <= 600 || target > 65535) {
            target = loadSavedBkltFromDisk();
        }
        writeHardwareBkltAndNeutralRGBScale(target, true);
        CGDisplayRestoreColorSyncSettings();
        hpLog(@"Restored zeroed post-wake bklt (%s): cur=%d -> target=%d", tag, (int)cur, (int)target);
    } else {
        writeHardwareBkltAndNeutralRGBScale(-1, true);
        CGDisplayRestoreColorSyncSettings();
        hpLog(@"Post-wake display ok (%s): bklt=%d (preserved)", tag, (int)cur);
    }
}

static void handleDisplayWillSleep(const char *reason) {
    __atomic_add_fetch(&gDisplayWakeSeq, 1, __ATOMIC_SEQ_CST);
    __atomic_store_n(&gDisplayIsAwake, 0, __ATOMIC_SEQ_CST);
    unlink(kWakeBlankFlagPath);

    if (__atomic_exchange_n(&gPreSleepCaptured, 1, __ATOMIC_SEQ_CST) == 0) {
        SInt32 cur = readHardwareBklt();
        if (cur > 600 && cur <= 65535) {
            __atomic_store_n(&gSavedBklt, cur, __ATOMIC_SEQ_CST);
            saveBkltToDisk(cur);
            __atomic_store_n(&gPreSleepBkltNonZero, 1, __ATOMIC_SEQ_CST);
            hpLog(@"Pre-sleep recorded bklt=%d (%s, no-blank)", (int)cur, reason);
        } else if (cur >= 0 && cur <= 600) {
            __atomic_store_n(&gPreSleepBkltNonZero, 0, __ATOMIC_SEQ_CST);
            hpLog(@"Pre-sleep bklt=%d already off/min (%s, no-blank)", (int)cur, reason);
        } else {
            __atomic_store_n(&gPreSleepBkltNonZero, 1, __ATOMIC_SEQ_CST);
            hpLog(@"Pre-sleep bklt unreadable (%s, keeping savedBklt=%d)",
                  reason, (int)__atomic_load_n(&gSavedBklt, __ATOMIC_SEQ_CST));
        }
    }
}

static void scheduleDisplayWakeRestore(const char *reason) {
    uint64_t dseq = __atomic_add_fetch(&gDisplayWakeSeq, 1, __ATOMIC_SEQ_CST);
    __atomic_store_n(&gDisplayIsAwake, 1, __ATOMIC_SEQ_CST);
    int shouldGuardZero = __atomic_load_n(&gPreSleepBkltNonZero, __ATOMIC_SEQ_CST);
    __atomic_store_n(&gPreSleepCaptured, 0, __ATOMIC_SEQ_CST);
    unlink(kWakeBlankFlagPath);

    hpLog(@"Scheduling post-wake display check (%s, seq=%llu, guardZero=%d)",
          reason, (unsigned long long)dseq, shouldGuardZero);

    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.15 * NSEC_PER_SEC)), gDisplayQueue, ^{
        if (dseq != __atomic_load_n(&gDisplayWakeSeq, __ATOMIC_SEQ_CST)) return;
        if (getDisplayWranglerPowerState() < 3) return;
        verifyAndRefreshPostWakeDisplay("wake+0.15s", shouldGuardZero);
    });

    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.60 * NSEC_PER_SEC)), gDisplayQueue, ^{
        if (dseq != __atomic_load_n(&gDisplayWakeSeq, __ATOMIC_SEQ_CST)) return;
        if (getDisplayWranglerPowerState() < 3) return;
        verifyAndRefreshPostWakeDisplay("wake+0.60s", shouldGuardZero);
    });
}

static int runCommand(const char *path, const char *arg1, const char *arg2, const char *arg3) {
    pid_t pid = 0;
    const char *argv[5];
    argv[0] = path;
    argv[1] = arg1;
    argv[2] = arg2;
    argv[3] = arg3;
    argv[4] = NULL;

    int rc = posix_spawn(&pid, path, NULL, NULL, (char * const *)argv, environ);
    if (rc != 0) {
        hpLog(@"posix_spawn(%s) failed: %d", path, rc);
        return -1;
    }
    int status = 0;
    if (waitpid(pid, &status, 0) < 0) {
        return -1;
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : -1;
}

static void applyQuickAmpVerbs(void) {
    runCommand("/usr/local/bin/alc-verb", "0x20", "SET_COEF_INDEX", "0x65");
    runCommand("/usr/local/bin/alc-verb", "0x20", "SET_PROC_COEF", "0x0000");
    runCommand("/usr/local/bin/alc-verb", "0x14", "SET_EAPD_BTLENABLE", "0x02");
    runCommand("/usr/local/bin/alc-verb", "0x17", "SET_EAPD_BTLENABLE", "0x02");
    runCommand("/usr/local/bin/alc-verb", "0x17", "SET_PIN_WIDGET_CONTROL", "0x40");
    runCommand("/usr/local/bin/alc-verb", "0x17", "SET_AMP_GAIN_MUTE", "0xb000");
}

static void quickAmpUnlockForActiveStream(const char *reason) {
    uint64_t nowNs = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
    if (gLastAmpQuickNs != 0 && (nowNs - gLastAmpQuickNs) < 2000000000ULL) {
        return;
    }
    gLastAmpQuickNs = nowNs;
    applyQuickAmpVerbs();
    usleep(100000); // 100ms settle follow-up after AFG D0 transition
    applyQuickAmpVerbs();
    hpLog(@"ALC285 amp quick-unlock applied (%s)", reason);
}

static AudioDeviceID findBuiltInSpeakerDevice(void) {
    AudioObjectPropertyAddress devsAddr = {
        kAudioHardwarePropertyDevices,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    UInt32 dataSize = 0;
    if (AudioObjectGetPropertyDataSize(kAudioObjectSystemObject, &devsAddr, 0, NULL, &dataSize) != noErr || dataSize == 0) {
        return 0;
    }
    UInt32 count = dataSize / sizeof(AudioDeviceID);
    if (count > 64) count = 64;
    AudioDeviceID devs[64];
    dataSize = count * sizeof(AudioDeviceID);
    if (AudioObjectGetPropertyData(kAudioObjectSystemObject, &devsAddr, 0, NULL, &dataSize, devs) != noErr) {
        return 0;
    }
    for (UInt32 i = 0; i < count; i++) {
        CFStringRef uid = NULL;
        UInt32 uidSize = sizeof(uid);
        AudioObjectPropertyAddress uidAddr = {
            kAudioDevicePropertyDeviceUID,
            kAudioObjectPropertyScopeGlobal,
            kAudioObjectPropertyElementMain
        };
        if (AudioObjectGetPropertyData(devs[i], &uidAddr, 0, NULL, &uidSize, &uid) == noErr && uid != NULL) {
            char buf[256] = {0};
            CFStringGetCString(uid, buf, sizeof(buf), kCFStringEncodingUTF8);
            CFRelease(uid);
            if (strstr(buf, "1F,3,0,1,3") != NULL) {
                return devs[i];
            }
        }
    }
    return 0;
}

static OSStatus speakerRunningListener(AudioObjectID inObjectID,
                                       UInt32 inNumberAddresses,
                                       const AudioObjectPropertyAddress *inAddresses,
                                       void *inClientData) {
    (void)inNumberAddresses;
    (void)inAddresses;
    (void)inClientData;
    UInt32 isRunning = 0;
    UInt32 sz = sizeof(isRunning);
    AudioObjectPropertyAddress runAddr = {
        kAudioDevicePropertyDeviceIsRunningSomewhere,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    if (AudioObjectGetPropertyData(inObjectID, &runAddr, 0, NULL, &sz, &isRunning) == noErr && isRunning != 0) {
        dispatch_async(gAudioQueue, ^{
            quickAmpUnlockForActiveStream("Built-in Speaker stream start");
        });
    }
    return noErr;
}

static void registerSpeakerStreamListener(void) {
    AudioDeviceID spk = findBuiltInSpeakerDevice();
    if (spk == 0 || spk == gWatchedSpeakerId) {
        return;
    }
    AudioObjectPropertyAddress runAddr = {
        kAudioDevicePropertyDeviceIsRunningSomewhere,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    if (gWatchedSpeakerId != 0) {
        AudioObjectRemovePropertyListener(gWatchedSpeakerId, &runAddr, speakerRunningListener, NULL);
    }
    if (AudioObjectAddPropertyListener(spk, &runAddr, speakerRunningListener, NULL) == noErr) {
        gWatchedSpeakerId = spk;
        hpLog(@"Registered stream-start listener on Built-in Speaker (AudioDeviceID=%u)", spk);
    }
}

static void runAudioReinit(const char *tag, const char *modeArg) {
    hpLog(@"Running ALC285 amp & route init (%s, mode=%s)...", tag, modeArg);
    int rc = runCommand("/usr/local/bin/hp-alc285-ampinit.sh", modeArg, NULL, NULL);
    registerSpeakerStreamListener();
    hpLog(@"ALC285 amp & route init (%s) finished with rc=%d", tag, rc);
}

static void runWiFiFastScan(const char *tag) {
    @autoreleasepool {
        CWWiFiClient *client = [CWWiFiClient sharedWiFiClient];
        CWInterface *iface = [client interface];
        if (!iface) {
            hpLog(@"Wi-Fi fast-scan (%s): no CWInterface found", tag);
            return;
        }
        NSString *ssid = [iface ssid];
        if (ssid && [ssid length] > 0) {
            hpLog(@"Wi-Fi fast-scan (%s): already associated to SSID '%@', skipping scan", tag, ssid);
            return;
        }
        NSError *err = nil;
        NSSet<CWNetwork *> *nets = [iface scanForNetworksWithName:nil error:&err];
        hpLog(@"Wi-Fi fast-scan (%s): triggered active SET_SCAN_REQ (found=%lu err=%@)",
              tag, (unsigned long)(nets ? [nets count] : 0), err ? [err localizedDescription] : @"none");
    }
}

static void scheduleWakeSequence(const char *sourceMsg) {
    uint64_t seq = __atomic_add_fetch(&gWakeSeq, 1, __ATOMIC_SEQ_CST);
    hpLog(@"Scheduling post-wake recovery sequence #%llu (%s)", (unsigned long long)seq, sourceMsg);

    // +0.3s: early ALC285 amp unlock & speaker route (fast path on dedicated audio queue)
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.3 * NSEC_PER_SEC)), gAudioQueue, ^{
        if (seq != __atomic_load_n(&gWakeSeq, __ATOMIC_SEQ_CST)) return;
        runAudioReinit("wake+0.3s", "--wake-fast");
    });

    // +1.0s: early Wi-Fi active scan kickstart (on dedicated Wi-Fi queue right after ItlIwx firmware reload at ~0.85s)
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.0 * NSEC_PER_SEC)), gWifiQueue, ^{
        if (seq != __atomic_load_n(&gWakeSeq, __ATOMIC_SEQ_CST)) return;
        runWiFiFastScan("wake+1.0s");
    });

    // +1.5s: second ALC285 amp unlock & speaker route (after AppleHDADriver protectedCompletePowerStateChange at ~0.6s)
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.5 * NSEC_PER_SEC)), gAudioQueue, ^{
        if (seq != __atomic_load_n(&gWakeSeq, __ATOMIC_SEQ_CST)) return;
        runAudioReinit("wake+1.5s", "--wake-fast");
    });

    // +2.8s: second Wi-Fi active scan kickstart if not yet associated
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2.8 * NSEC_PER_SEC)), gWifiQueue, ^{
        if (seq != __atomic_load_n(&gWakeSeq, __ATOMIC_SEQ_CST)) return;
        runWiFiFastScan("wake+2.8s");
    });

    // +3.5s: final full ALC285 amp, DMIC & speaker route verification pass
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(3.5 * NSEC_PER_SEC)), gAudioQueue, ^{
        if (seq != __atomic_load_n(&gWakeSeq, __ATOMIC_SEQ_CST)) return;
        runAudioReinit("wake+3.5s", "--wake");
    });
}

static void wranglerInterestCallback(void *refCon, io_service_t service, natural_t messageType, void *messageArgument) {
    (void)refCon;
    (void)service;
    (void)messageArgument;
    if (messageType == kIOMessageDeviceWillPowerOff) {
        int wps = getDisplayWranglerPowerState();
        int fbps = getFramebufferPowerState();
        // wps == 3 is normal macOS half-dim before display sleep; do not treat as display-off.
        if (wps == 3) {
            SInt32 cur = readHardwareBklt();
            if (cur > 600 && cur <= 65535) {
                __atomic_store_n(&gSavedBklt, cur, __ATOMIC_SEQ_CST);
                saveBkltToDisk(cur);
            }
            return;
        }
        // Always cancel any active wake check immediately
        __atomic_add_fetch(&gDisplayWakeSeq, 1, __ATOMIC_SEQ_CST);
        int wasAwake = __atomic_exchange_n(&gDisplayIsAwake, 0, __ATOMIC_SEQ_CST);
        // Ignore PMRD RootDomainPower (ps 0, 0->1->0) dark maintenance ticks when display is already asleep
        if (wasAwake == 0 && wps >= 0 && wps < 2 && fbps < 2) {
            return;
        }
        hpLog(@"IODisplayWrangler kIOMessageDeviceWillPowerOff (wps=%d fbps=%d wasAwake=%d)", wps, fbps, wasAwake);
        handleDisplayWillSleep("IODisplayWranglerWillPowerOff");
    } else if (messageType == kIOMessageDeviceHasPoweredOn) {
        int wps = getDisplayWranglerPowerState();
        if (wps >= 3) {
            hpLog(@"IODisplayWrangler kIOMessageDeviceHasPoweredOn (wps=%d)", wps);
            scheduleDisplayWakeRestore("IODisplayWranglerHasPoweredOn");
        } else {
            // Re-check after 15ms in case IODisplayWrangler stepped through ps 1 on the way to ps 4;
            // if still < 3, it was a 0->1->0 dark maintenance tick and must be ignored.
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.015 * NSEC_PER_SEC)), gDisplayQueue, ^{
                int laterWps = getDisplayWranglerPowerState();
                if (laterWps >= 3 && __atomic_load_n(&gDisplayIsAwake, __ATOMIC_SEQ_CST) == 0) {
                    hpLog(@"IODisplayWrangler kIOMessageDeviceHasPoweredOn confirmed after 15ms (wps=%d)", laterWps);
                    scheduleDisplayWakeRestore("IODisplayWranglerHasPoweredOn+15ms");
                }
            });
        }
    }
}

static void wranglerMatchedCallback(void *refCon, io_iterator_t iterator) {
    (void)refCon;
    io_service_t wrangler = MACH_PORT_NULL;
    while ((wrangler = IOIteratorNext(iterator)) != MACH_PORT_NULL) {
        if (gWranglerNotifier == MACH_PORT_NULL && gNotifyPort != NULL) {
            kern_return_t kr = IOServiceAddInterestNotification(
                gNotifyPort,
                wrangler,
                kIOGeneralInterest,
                wranglerInterestCallback,
                NULL,
                &gWranglerNotifier
            );
            hpLog(@"Registered IODisplayWrangler power interest notification (kr=0x%x)", kr);
        }
        IOObjectRelease(wrangler);
    }
}

static void powerCallback(void *refCon, io_service_t service, natural_t messageType, void *messageArgument) {
    (void)refCon;
    (void)service;
    switch (messageType) {
        case kIOMessageCanSystemSleep:
            IOAllowPowerChange(gRootPort, (long)messageArgument);
            break;
        case kIOMessageSystemWillSleep:
            hpLog(@"SystemWillSleep: recording pre-sleep state & acknowledging immediately");
            handleDisplayWillSleep("kIOMessageSystemWillSleep");
            IOAllowPowerChange(gRootPort, (long)messageArgument);
            break;
        case kIOMessageSystemWillPowerOn:
            hpLog(@"SystemWillPowerOn received");
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.2 * NSEC_PER_SEC)), gAudioQueue, ^{
                runAudioReinit("willPowerOn+0.2s", "--wake-fast");
            });
            break;
        case kIOMessageSystemHasPoweredOn:
            hpLog(@"SystemHasPoweredOn received");
            if (getDisplayWranglerPowerState() >= 3) {
                scheduleDisplayWakeRestore("kIOMessageSystemHasPoweredOn");
            }
            scheduleWakeSequence("kIOMessageSystemHasPoweredOn");
            break;
        default:
            break;
    }
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        (void)argc;
        (void)argv;
        gAudioQueue = dispatch_queue_create("com.hp.wake-helper.audio", DISPATCH_QUEUE_SERIAL);
        gWifiQueue = dispatch_queue_create("com.hp.wake-helper.wifi", DISPATCH_QUEUE_SERIAL);
        gDisplayQueue = dispatch_queue_create("com.hp.wake-helper.display", DISPATCH_QUEUE_SERIAL);

        bool hadStaleBlank = (access(kWakeBlankFlagPath, F_OK) == 0);

        int initWps = getDisplayWranglerPowerState();
        int initFbps = getFramebufferPowerState();
        SInt32 initialBklt = readHardwareBklt();
        if (initialBklt > 600 && initialBklt <= 65535) {
            __atomic_store_n(&gSavedBklt, initialBklt, __ATOMIC_SEQ_CST);
            saveBkltToDisk(initialBklt);
        } else {
            __atomic_store_n(&gSavedBklt, loadSavedBkltFromDisk(), __ATOMIC_SEQ_CST);
        }

        if (initWps >= 0 && initWps < 3) {
            __atomic_store_n(&gDisplayIsAwake, 0, __ATOMIC_SEQ_CST);
        } else {
            __atomic_store_n(&gDisplayIsAwake, 1, __ATOMIC_SEQ_CST);
        }

        if (hadStaleBlank && (initWps < 0 || initWps >= 3) && initialBklt >= 0 && initialBklt <= 600) {
            SInt32 targetBklt = __atomic_load_n(&gSavedBklt, __ATOMIC_SEQ_CST);
            writeHardwareBkltAndNeutralRGBScale(targetBklt, true);
        }
        unlink(kWakeBlankFlagPath);

        hpLog(@"hp-wake-helper v20261123-no-blank starting (pid=%d, wps=%d, fbps=%d, initialBklt=%d, savedBklt=%d, hadStaleBlank=%d)",
              getpid(), initWps, initFbps, (int)initialBklt,
              (int)__atomic_load_n(&gSavedBklt, __ATOMIC_SEQ_CST),
              hadStaleBlank ? 1 : 0);

        gRootPort = IORegisterForSystemPower(NULL, &gNotifyPort, powerCallback, &gNotifier);
        if (gRootPort == MACH_PORT_NULL || gNotifyPort == NULL) {
            hpLog(@"FATAL: IORegisterForSystemPower failed");
            return 1;
        }
        CFRunLoopAddSource(CFRunLoopGetCurrent(),
                           IONotificationPortGetRunLoopSource(gNotifyPort),
                           kCFRunLoopDefaultMode);

        kern_return_t matchKr = IOServiceAddMatchingNotification(
            gNotifyPort,
            kIOFirstMatchNotification,
            IOServiceMatching("IODisplayWrangler"),
            wranglerMatchedCallback,
            NULL,
            &gWranglerMatchIter
        );
        if (matchKr == KERN_SUCCESS && gWranglerMatchIter != MACH_PORT_NULL) {
            wranglerMatchedCallback(NULL, gWranglerMatchIter);
        } else {
            hpLog(@"WARN: IOServiceAddMatchingNotification(IODisplayWrangler) failed (kr=0x%x)", matchKr);
        }

        if (hadStaleBlank && (initWps < 0 || initWps >= 3) && initialBklt >= 0 && initialBklt <= 600) {
            SInt32 targetBklt = __atomic_load_n(&gSavedBklt, __ATOMIC_SEQ_CST);
            dispatch_async(gDisplayQueue, ^{
                writeHardwareBkltAndNeutralRGBScale(targetBklt, true);
                CGDisplayRestoreColorSyncSettings();
                hpLog(@"Recovered stale wake-blank at startup: bklt %d -> %d", (int)initialBklt, (int)targetBklt);
            });
        } else if (initWps < 0 || initWps >= 3) {
            dispatch_async(gDisplayQueue, ^{
                writeHardwareBkltAndNeutralRGBScale(-1, true);
                CGDisplayRestoreColorSyncSettings();
                hpLog(@"Display ColorSync & RGB scale refreshed (startup-color-check, bklt preserved)");
            });
        }

        dispatch_async(gAudioQueue, ^{
            runAudioReinit("startup", "--boot");
        });

        CFRunLoopRun();
    }
    return 0;
}
