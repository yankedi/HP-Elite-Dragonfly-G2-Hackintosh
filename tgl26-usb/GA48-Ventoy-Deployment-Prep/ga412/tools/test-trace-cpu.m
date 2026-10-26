// Native CPU-only regression. Fake texture methods; no Metal device or commands.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

static _Atomic unsigned calls[4];
@interface MTLIGAccelTexture : NSObject
- (NSUInteger)width;
- (NSUInteger)height;
- (MTLPixelFormat)pixelFormat;
- (MTLStorageMode)storageMode;
- (void)getBytes:(void *)dst bytesPerRow:(NSUInteger)row bytesPerImage:(NSUInteger)image
     fromRegion:(MTLRegion)region mipmapLevel:(NSUInteger)level slice:(NSUInteger)slice;
#ifdef BAD_ABI
- (void *)lockForCPUAccess:(unsigned *)seed readOnly:(signed char)readOnly level:(unsigned)level slice:(unsigned)slice;
#else
- (uint64_t)lockForCPUAccess:(unsigned *)seed readOnly:(signed char)readOnly level:(unsigned)level slice:(unsigned)slice;
#endif
- (signed char)resolveCCS:(NSUInteger)level slice:(NSUInteger)slice waitForCompletion:(signed char)wait;
- (signed char)unlockForCPUAccess:(unsigned)seed readOnly:(signed char)readOnly;
@end
@implementation MTLIGAccelTexture
- (NSUInteger)width { return 257; }
- (NSUInteger)height { return 65; }
- (MTLPixelFormat)pixelFormat { return MTLPixelFormatRGBA8Unorm; }
- (MTLStorageMode)storageMode { return MTLStorageModeManaged; }
- (signed char)resolveCCS:(NSUInteger)level slice:(NSUInteger)slice waitForCompletion:(signed char)wait {
    NSCAssert(level == 7 && slice == 9 && wait == 1, @"resolve args changed");
    atomic_fetch_add(&calls[2], 1); return -7;
}
#ifdef BAD_ABI
- (void *)lockForCPUAccess:(unsigned *)seed readOnly:(signed char)readOnly level:(unsigned)level slice:(unsigned)slice {
#else
- (uint64_t)lockForCPUAccess:(unsigned *)seed readOnly:(signed char)readOnly level:(unsigned)level slice:(unsigned)slice {
#endif
    NSCAssert(readOnly == 1 && level == 7 && slice == 9, @"lock args changed");
    atomic_fetch_add(&calls[1], 1); *seed = 0x12345678;
    NSCAssert([self resolveCCS:level slice:slice waitForCompletion:1] == -7, @"resolve return changed");
#ifdef BAD_ABI
    return (void *)(uintptr_t)0xfedcba9876543210ULL;
#else
    return 0xfedcba9876543210ULL;
#endif
}
- (signed char)unlockForCPUAccess:(unsigned)seed readOnly:(signed char)readOnly {
    NSCAssert(seed == 0x12345678 && readOnly == 1, @"unlock args changed");
    atomic_fetch_add(&calls[3], 1); return -3;
}
- (void)getBytes:(void *)dst bytesPerRow:(NSUInteger)row bytesPerImage:(NSUInteger)image
     fromRegion:(MTLRegion)region mipmapLevel:(NSUInteger)level slice:(NSUInteger)slice {
    NSCAssert(row == 1280 && image == 83200 && region.origin.x == 2 && region.size.height == 3 &&
              level == 7 && slice == 9, @"getBytes args changed");
    atomic_fetch_add(&calls[0], 1); unsigned seed = 0;
    uint64_t locked = (uint64_t)[self lockForCPUAccess:&seed readOnly:1 level:7 slice:9];
    NSCAssert(locked == 0xfedcba9876543210ULL, @"64-bit lock return truncated");
    memset(dst, 0x7b, 16);
    NSCAssert([self unlockForCPUAccess:seed readOnly:1] == -3, @"unlock return changed");
}
@end
static __attribute__((unused)) void *worker(void *ignored) {
    (void)ignored;
    @autoreleasepool {
        MTLIGAccelTexture *texture = [MTLIGAccelTexture new];
        for (unsigned i = 0; i < 4; i++) {
            unsigned char bytes[16] = {0};
            [texture getBytes:bytes bytesPerRow:1280 bytesPerImage:83200
                fromRegion:MTLRegionMake2D(2, 1, 4, 3) mipmapLevel:7 slice:9];
            for (unsigned j = 0; j < sizeof(bytes); j++) NSCAssert(bytes[j] == 0x7b, @"copy changed");
        }
    }
    return NULL;
}
int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 2) return 2;
    void *trace = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    int (*install)(void) = trace ? (int (*)(void))dlsym(trace, "ga412_trace_install") : NULL;
    char *(*manifest)(void) = trace ? (char *(*)(void))dlsym(trace, "ga412_trace_manifest") : NULL;
    if (!install || !manifest) return 2;
#ifdef BAD_ABI
    Method get = class_getInstanceMethod([MTLIGAccelTexture class], @selector(getBytes:bytesPerRow:bytesPerImage:fromRegion:mipmapLevel:slice:));
    IMP before = method_getImplementation(get);
    if (install() || before != method_getImplementation(get)) return 1;
    puts("CPU_TEST_PASS ABI rejected without partial installation"); return 0;
#else
    if (!install() || !install()) return 1;
    pthread_t threads[4];
    for (unsigned i = 0; i < 4; i++) if (pthread_create(&threads[i], NULL, worker, NULL)) return 1;
    for (unsigned i = 0; i < 4; i++) if (pthread_join(threads[i], NULL)) return 1;
    for (unsigned i = 0; i < 4; i++) if (atomic_load(&calls[i]) != 16) return 1;
    char *raw = manifest(); if (!raw) return 1;
    NSDictionary *report = [NSJSONSerialization JSONObjectWithData:[@(raw) dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
    free(raw);
    for (NSDictionary *entry in report[@"methods"]) if ([entry[@"calls"] unsignedLongValue] != 16) return 1;
    puts("CPU_TEST_PASS nested call forwarding, 64-bit return, signed return, concurrent hooks and idempotent install");
    return 0;
#endif
} }
