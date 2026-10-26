// Observation-only successor to ga411/tools/trace-managed-cpu.m.
// No resolve, lock, flag write, or resource mutation is initiated by this image.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static IMP originals[4];
static Method methods[4];
static const char *names[] = {
    "getBytes:bytesPerRow:bytesPerImage:fromRegion:mipmapLevel:slice:",
    "lockForCPUAccess:readOnly:level:slice:",
    "resolveCCS:slice:waitForCompletion:", "unlockForCPUAccess:readOnly:"
};
// Exact metadata captured CPU-only from the installed 16.0.32 user-mode image.
static const char *encodings[] = {
    "v104@0:8^v16Q24Q32{?={?=QQQ}{?=QQQ}}40Q88Q96",
    "Q36@0:8^I16c24I28I32", "c36@0:8Q16Q24c32", "c24@0:8I16c20"
};
static pthread_mutex_t installMutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t logMutex = PTHREAD_MUTEX_INITIALIZER;
static _Atomic unsigned long counts[4];
static unsigned long sequence;
static _Thread_local unsigned active;
static _Thread_local int logging;
static ptrdiff_t infoOffset;
static size_t instanceSize;
static int installed;

static uint64_t nowNS(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}

static BOOL readOwn(uintptr_t address, void *out, size_t length) {
    mach_vm_size_t copied = 0;
    return mach_vm_read_overwrite(mach_task_self(), address, length,
        (mach_vm_address_t)out, &copied) == KERN_SUCCESS && copied == length;
}

static NSDictionary *state(id<MTLTexture> object) {
    NSMutableDictionary *r = [@{@"texture": [NSString stringWithFormat:@"%p", (__bridge void *)object],
        @"class": NSStringFromClass([object class]), @"width": @([object width]),
        @"height": @([object height]), @"format": @([object pixelFormat]),
        @"storage": @([object storageMode])} mutableCopy];
    unsigned char info[0x1b0];
    if (infoOffset >= 0 && (size_t)infoOffset + sizeof(info) <= instanceSize &&
        readOwn((uintptr_t)(__bridge void *)object + infoOffset, info, sizeof(info))) {
        NSMutableDictionary *raw = [NSMutableDictionary dictionary];
        for (NSNumber *offset in @[@0x108, @0x10c, @0x114, @0x134]) {
            uint32_t value; memcpy(&value, info + offset.unsignedLongValue, sizeof(value));
            raw[[NSString stringWithFormat:@"0x%lx", offset.unsignedLongValue]] = @(value);
        }
        for (NSNumber *offset in @[@0x16a, @0x1ac]) {
            uint16_t value; memcpy(&value, info + offset.unsignedLongValue, sizeof(value));
            raw[[NSString stringWithFormat:@"0x%lx", offset.unsignedLongValue]] = @(value);
        }
        uintptr_t resource = 0; memcpy(&resource, info, sizeof(resource));
        uint32_t value = 0;
        raw[@"resource"] = [NSString stringWithFormat:@"0x%lx", (unsigned long)resource];
        raw[@"resource_0x1c"] = resource && readOwn(resource + 0x1c, &value, sizeof(value)) ? @(value) : (id)NSNull.null;
        r[@"raw_m_Info_offsets_not_compression_verdict"] = raw;
    } else r[@"raw_m_Info_offsets_not_compression_verdict"] = @"UNAVAILABLE";
    return r;
}

static void event(unsigned index, NSString *phase, id object, NSDictionary *arguments) {
    if (logging) return;
    logging = 1;
    @try {
        @autoreleasepool {
            uint64_t tid = 0; pthread_threadid_np(NULL, &tid);
            pthread_mutex_lock(&logMutex);
            @try {
            NSMutableDictionary *r = [@{@"sequence": @(++sequence), @"monotonic_ns": @(nowNS()),
                @"thread": @(tid), @"method": @(names[index]), @"phase": phase,
                @"arguments": arguments, @"resource": state(object)} mutableCopy];
            NSData *data = [NSJSONSerialization dataWithJSONObject:r options:0 error:nil];
            if (data) {
                fputs("CPU_TRACE_JSON ", stderr); fwrite(data.bytes, 1, data.length, stderr);
                fputc('\n', stderr); fflush(stderr);
            }
            } @finally { pthread_mutex_unlock(&logMutex); }
        }
    } @catch (NSException *exception) {
        fprintf(stderr, "CPU_TRACE_LOG_EXCEPTION %s\n", exception.name.UTF8String);
    } @finally { logging = 0; }
}

static BOOL begin(unsigned index, id object, NSDictionary *arguments) {
    atomic_fetch_add_explicit(&counts[index], 1, memory_order_relaxed);
    if (logging || (active & (1U << index))) return NO;
    active |= 1U << index;
    event(index, @"enter", object, arguments);
    return YES;
}
static void end(unsigned index, BOOL observed, id object, NSDictionary *arguments) {
    if (observed) { event(index, @"exit", object, arguments); active &= ~(1U << index); }
}

static void getObserved(id t, SEL s, void *dst, NSUInteger row, NSUInteger image,
                        MTLRegion region, NSUInteger level, NSUInteger slice) {
    BOOL observed = begin(0, t, @{@"destination": [NSString stringWithFormat:@"%p", dst],
        @"bytes_per_row": @(row), @"bytes_per_image": @(image), @"level": @(level),
        @"slice": @(slice), @"origin": @[@(region.origin.x), @(region.origin.y), @(region.origin.z)],
        @"size": @[@(region.size.width), @(region.size.height), @(region.size.depth)]});
    @try { ((void (*)(id, SEL, void *, NSUInteger, NSUInteger, MTLRegion, NSUInteger, NSUInteger))originals[0])
        (t, s, dst, row, image, region, level, slice); }
    @finally { end(0, observed, t, @{}); }
}
static uint64_t lockObserved(id t, SEL s, unsigned *seed, signed char readOnly, unsigned level, unsigned slice) {
    BOOL observed = begin(1, t, @{@"seed_pointer": [NSString stringWithFormat:@"%p", seed],
        @"read_only": @(readOnly), @"level": @(level), @"slice": @(slice)});
    uint64_t result = 0;
    @try { result = ((uint64_t (*)(id, SEL, unsigned *, signed char, unsigned, unsigned))originals[1])
        (t, s, seed, readOnly, level, slice); }
    @finally { end(1, observed, t, @{@"return_u64": @(result)}); }
    return result;
}
static signed char resolveObserved(id t, SEL s, NSUInteger level, NSUInteger slice, signed char wait) {
    BOOL observed = begin(2, t, @{@"level": @(level), @"slice": @(slice), @"wait": @(wait)});
    signed char result = 0;
    @try { result = ((signed char (*)(id, SEL, NSUInteger, NSUInteger, signed char))originals[2])
        (t, s, level, slice, wait); }
    @finally { end(2, observed, t, @{@"return_i8": @(result)}); }
    return result;
}
static signed char unlockObserved(id t, SEL s, unsigned seed, signed char readOnly) {
    BOOL observed = begin(3, t, @{@"seed": @(seed), @"read_only": @(readOnly)});
    signed char result = 0;
    @try { result = ((signed char (*)(id, SEL, unsigned, signed char))originals[3])(t, s, seed, readOnly); }
    @finally { end(3, observed, t, @{@"return_i8": @(result)}); }
    return result;
}

int ga412_trace_install(void) {
    pthread_mutex_lock(&installMutex);
    if (installed) { pthread_mutex_unlock(&installMutex); return 1; }
    Class c = objc_getClass("MTLIGAccelTexture");
    Ivar info = c ? class_getInstanceVariable(c, "m_Info") : NULL;
    // Validate every ABI before changing any IMP. A rejected installation is inert.
    for (unsigned i = 0; i < 4; i++) {
        methods[i] = c ? class_getInstanceMethod(c, sel_registerName(names[i])) : NULL;
        if (!methods[i] || strcmp(method_getTypeEncoding(methods[i]), encodings[i])) {
            fprintf(stderr, "CPU_TRACE_ABI_REJECT %s actual=%s expected=%s\n", names[i],
                methods[i] ? method_getTypeEncoding(methods[i]) : "MISSING", encodings[i]);
            pthread_mutex_unlock(&installMutex); return 0;
        }
        originals[i] = method_getImplementation(methods[i]);
    }
    infoOffset = info ? ivar_getOffset(info) : -1;
    instanceSize = c ? class_getInstanceSize(c) : 0;
    IMP replacements[] = {(IMP)getObserved, (IMP)lockObserved, (IMP)resolveObserved, (IMP)unlockObserved};
    for (unsigned i = 0; i < 4; i++) method_setImplementation(methods[i], replacements[i]);
    installed = 1;
    fprintf(stderr, "CPU_TRACE_ABI_VERIFIED installed=4 info_offset=%td instance_size=%zu\n", infoOffset, instanceSize);
    pthread_mutex_unlock(&installMutex); return 1;
}

char *ga412_trace_manifest(void) {
    NSMutableArray *entries = [NSMutableArray array];
    for (unsigned i = 0; i < 4; i++) {
        Dl_info origin = {0};
        BOOL known = originals[i] && dladdr((const void *)originals[i], &origin);
        [entries addObject:@{@"method": @(names[i]), @"encoding": @(encodings[i]),
            @"original_IMP_image": known && origin.dli_fname ? @(origin.dli_fname) : @"UNKNOWN",
            @"calls": @(atomic_load_explicit(&counts[i], memory_order_relaxed))}];
    }
    NSData *data = [NSJSONSerialization dataWithJSONObject:@{@"installed": @(installed), @"methods": entries,
        @"private_state": @"bounded own-process reads only; no kernel AUX/CCS verdict"} options:0 error:nil];
    NSString *manifest = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    return manifest ? strdup(manifest.UTF8String) : NULL; // caller owns the copy
}
