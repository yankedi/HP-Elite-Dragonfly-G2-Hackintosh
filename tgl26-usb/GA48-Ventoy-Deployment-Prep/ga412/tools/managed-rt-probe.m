// Isolated GA4.12 successor of ga411/tools/managed-rt-probe.m.
// The sole GPU workload is the original R8 legacy render/sync/copy sequence.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static const NSUInteger W = 257, H = 65, ROW = 1280, PITCH = 512;
static pthread_mutex_t logMutex = PTHREAD_MUTEX_INITIALIZER;
static uint64_t nowNS(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}
static void event(NSString *stage, NSDictionary *fields) {
    pthread_mutex_lock(&logMutex);
    @try {
        NSMutableDictionary *r = [fields mutableCopy]; r[@"event"] = stage; r[@"monotonic_ns"] = @(nowNS());
        NSData *data = [NSJSONSerialization dataWithJSONObject:r options:0 error:nil];
        if (data) { fputs("PROBE_EVENT ", stdout); fwrite(data.bytes, 1, data.length, stdout); putchar('\n'); fflush(stdout); }
    } @finally { pthread_mutex_unlock(&logMutex); }
}
static void save(NSData *data, NSString *directory, NSString *name) {
    NSError *error = nil;
    if (![data writeToFile:[directory stringByAppendingPathComponent:name]
                  options:NSDataWritingWithoutOverwriting error:&error]) {
        fprintf(stderr, "ARTIFACT_WRITE_FAILED %s %s\n", name.UTF8String, error.description.UTF8String); exit(3);
    }
}
static NSDictionary *attrs(id<MTLTexture> t) {
    return @{@"class": NSStringFromClass([(id)t class]), @"object": [NSString stringWithFormat:@"%p", (__bridge void *)t],
        @"width": @(t.width), @"height": @(t.height), @"format": @(t.pixelFormat), @"storage": @(t.storageMode),
        @"usage": @(t.usage), @"samples": @(t.sampleCount), @"mips": @(t.mipmapLevelCount), @"array_length": @(t.arrayLength)};
}
static BOOL disjoint(NSData *a, NSData *b) {
    uintptr_t x = (uintptr_t)a.bytes, y = (uintptr_t)b.bytes;
    return x <= y ? a.length <= y - x : b.length <= x - y;
}
@interface CBStamp : NSObject { @public _Atomic(uint64_t) completedNS; }
@end
@implementation CBStamp
@end

int main(int argc, char **argv) { @autoreleasepool {
    setbuf(stdout, NULL);
    if (argc != 4 || strcmp(argv[1], "R8") || strcmp(argv[2], "legacy")) {
        fprintf(stderr, "usage: managed-rt-probe R8 legacy NEW_OUTPUT_DIRECTORY\n"); return 2;
    }
    alarm(30); // Process deadline only; NOT cancellation of GPU/driver work.
    NSString *directory = @(argv[3]); NSError *error = nil;
    if ([[NSFileManager defaultManager] fileExistsAtPath:directory] ||
        ![[NSFileManager defaultManager] createDirectoryAtPath:directory withIntermediateDirectories:NO attributes:nil error:&error]) {
        fprintf(stderr, "NEW_OUTPUT_DIRECTORY_REQUIRED %s\n", error.description.UTF8String); return 2;
    }
    NSMutableData *input = [NSMutableData dataWithLength:PITCH * H];
    NSMutableData *expected = [NSMutableData dataWithLength:ROW * H];
    uint8_t *p = input.mutableBytes, *e = expected.mutableBytes;
    for (NSUInteger y = 0; y < H; y++) for (NSUInteger x = 0; x < W; x++) {
        p[y * PITCH + x] = (x * 13 + y * 29) & 255;
        e[y * ROW + x * 4] = p[y * PITCH + x]; e[y * ROW + x * 4 + 3] = 255;
    }
    save(input, directory, @"input.bin"); save(expected, directory, @"expected.bin");
    event(@"device_create_begin", @{});
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { fprintf(stderr, "DEVICE_MISSING\n"); return 2; }
    const char *trace = getenv("GA411_TRACE_DYLIB");
    void *image = trace ? dlopen(trace, RTLD_NOW | RTLD_LOCAL) : NULL;
    int (*install)(void) = image ? (int (*)(void))dlsym(image, "ga412_trace_install") : NULL;
    char *(*manifest)(void) = image ? (char *(*)(void))dlsym(image, "ga412_trace_manifest") : NULL;
    if (!install || !manifest || !install()) { fprintf(stderr, "TRACER_REQUIRED_OR_ABI_REJECTED\n"); return 2; }
    event(@"device_and_tracer_ready", @{@"device": dev.name, @"registry_id": @(dev.registryID)});
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "vertex float4 vs(uint i [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(p[i],0,1); }\n"
        "fragment float4 fs(float4 p [[position]],texture2d<float> t [[texture(0)]]) { constexpr sampler s(coord::pixel,address::clamp_to_edge,filter::nearest); return t.sample(s,p.xy); }";
    id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:&error];
    if (!lib) { fprintf(stderr, "COMPILE_FAILED %s\n", error.description.UTF8String); return 2; }
    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = [lib newFunctionWithName:@"vs"]; rd.fragmentFunction = [lib newFunctionWithName:@"fs"];
    rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    id<MTLRenderPipelineState> pipeline = [dev newRenderPipelineStateWithDescriptor:rd error:&error];
    if (!pipeline) { fprintf(stderr, "PIPELINE_FAILED %s\n", error.description.UTF8String); return 2; }
    // Preserve historical shared upload buffer and oversized shared GPU output.
    id<MTLBuffer> src = [dev newBufferWithLength:PITCH * H options:MTLResourceStorageModeShared];
    id<MTLBuffer> out = [dev newBufferWithLength:ROW * H * 4 options:MTLResourceStorageModeShared];
    if (!src || !out || !src.contents || !out.contents || out.storageMode != MTLStorageModeShared || out.length < ROW * H) return 2;
    memcpy(src.contents, input.bytes, input.length); memset(out.contents, 0xee, out.length);
    MTLTextureDescriptor *sd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR8Unorm width:W height:H mipmapped:NO];
    sd.storageMode = MTLStorageModeShared; sd.usage = MTLTextureUsageShaderRead; sd.allowGPUOptimizedContents = NO;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
    td.storageMode = MTLStorageModeManaged; td.usage = MTLTextureUsageRenderTarget; td.allowGPUOptimizedContents = NO;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:sd], target = [dev newTextureWithDescriptor:td];
    id<MTLCommandQueue> queue = [dev newCommandQueue];
    if (!tex || !target || !queue || target.storageMode != MTLStorageModeManaged) return 2;
    NSDictionary *resources = @{@"source": attrs(tex), @"target": attrs(target),
        @"readback_buffer": @{@"storage": @(out.storageMode), @"length": @(out.length),
            @"CPU_visibility": @"shared buffer, read after command completion; no managed buffer sync required"}};
    event(@"resources_created", resources);
    [tex replaceRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0 withBytes:src.contents bytesPerRow:PITCH];
    uint64_t createNS = nowNS();
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    if (!cb) return 2;
    NSString *identifier = [NSString stringWithFormat:@"pid-%d-cb-1-%p", getpid(), (__bridge void *)cb];
    cb.label = @"legacy_render_sync_copy";
    event(@"command_created", @{@"id": identifier, @"created_ns": @(createNS), @"resources": resources});
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = target; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore; rp.colorAttachments[0].clearColor = MTLClearColorMake(1, 0, 1, 1);
    id<MTLRenderCommandEncoder> render = [cb renderCommandEncoderWithDescriptor:rp];
    if (!render) return 2;
    [render setRenderPipelineState:pipeline]; [render setFragmentTexture:tex atIndex:0];
    [render drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; [render endEncoding];
    id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder]; if (!blit) return 2;
    [blit synchronizeResource:target];
    [blit copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
        sourceSize:MTLSizeMake(W, H, 1) toBuffer:out destinationOffset:0 destinationBytesPerRow:ROW destinationBytesPerImage:ROW * H];
    [blit endEncoding];
    CBStamp *stamp = [CBStamp new];
    [cb addCompletedHandler:^(id<MTLCommandBuffer> completed) {
        atomic_store_explicit(&stamp->completedNS, nowNS(), memory_order_release);
        event(@"command_completed_callback", @{@"id": identifier, @"status": @(completed.status),
            @"error": completed.error.description ?: @""});
    }];
    uint64_t commitNS = nowNS(); event(@"command_commit", @{@"id": identifier}); [cb commit];
    uint64_t waitNS = nowNS(); event(@"command_wait_begin", @{@"id": identifier}); [cb waitUntilCompleted];
    uint64_t observedNS = nowNS();
    NSDictionary *command = @{@"id": identifier, @"stage": @"legacy_render_sync_copy", @"created_ns": @(createNS),
        @"commit_ns": @(commitNS), @"wait_begin_ns": @(waitNS), @"completion_observed_ns": @(observedNS),
        @"completed_callback_ns": @(atomic_load_explicit(&stamp->completedNS, memory_order_acquire)),
        @"wait_returned": @YES, @"status": @(cb.status), @"error": cb.error.description ?: @"",
        @"error_domain": cb.error.domain ?: @"", @"error_code": @(cb.error.code),
        @"timeout": @NO, @"GPU_reset_observation": @"external health receipt required", @"resources": resources};
    save([NSJSONSerialization dataWithJSONObject:command options:NSJSONWritingPrettyPrinted error:nil], directory, @"command.json");
    event(@"command_wait_returned", command);
    if (cb.status != MTLCommandBufferStatusCompleted || cb.error) return 2;
    NSData *gpu = [NSData dataWithBytes:out.contents length:ROW * H];
    if ((uintptr_t)gpu.bytes == (uintptr_t)out.contents || !disjoint(gpu, expected)) return 2;
    save(gpu, directory, @"gpu.bin");
    uint64_t freezeNS = nowNS(); event(@"gpu_snapshot_frozen", @{@"bytes": @(gpu.length)});
    NSMutableData *cpu = [NSMutableData dataWithLength:ROW * H]; memset(cpu.mutableBytes, 0xdd, cpu.length);
    if (!disjoint(cpu, gpu) || !disjoint(cpu, expected)) return 2;
    uint64_t cpuBeginNS = nowNS(); event(@"cpu_getBytes_begin", @{});
    [target getBytes:cpu.mutableBytes bytesPerRow:ROW fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
    uint64_t cpuEndNS = nowNS(); save(cpu, directory, @"cpu.bin"); event(@"cpu_getBytes_returned", @{});
    char *traceManifest = manifest();
    if (!traceManifest) return 2;
    NSDictionary *traceResult = [NSJSONSerialization JSONObjectWithData:[@(traceManifest) dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
    free(traceManifest); if (!traceResult) return 2;
    // A capture is not self-certified PASS: NixOS reconstructs expected and compares all bytes.
    NSDictionary *result = @{@"schema": @"ga412-managed-rt-v1", @"status": @"CAPTURE_COMPLETE_UNVERIFIED",
        @"case": @"R8", @"mode": @"legacy", @"width": @(W), @"height": @(H), @"input_pitch": @(PITCH),
        @"input_bpp": @1, @"output_pitch": @(ROW), @"device": dev.name, @"registry_id": @(dev.registryID),
        @"unified": @(dev.hasUnifiedMemory), @"source": attrs(tex), @"target": attrs(target),
        @"commands": @[command], @"tracer": traceResult, @"requested_allowGPUOptimizedContents": @NO,
        @"snapshots_disjoint": @YES, @"gpu_frozen_ns": @(freezeNS), @"cpu_getBytes_begin_ns": @(cpuBeginNS),
        @"cpu_getBytes_end_ns": @(cpuEndNS), @"full_snapshot_bytes": @(ROW * H), @"active_pixel_bytes": @(W * H * 4),
        @"kernel_AUX_CCS_and_rc1474": @"NOT_OBSERVED", @"GPU_snapshot_limit": @"copy/readback proxy, not absolute raw GPU truth"};
    save([NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil], directory, @"result.json");
    event(@"capture_complete_unverified", @{}); alarm(0); return 0;
} }
