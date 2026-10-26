// GA415: one explicit command buffer, deterministic IOSurface -> render -> readback.
// CPU-only mode never calls MTLCreateSystemDefaultDevice. No kernel modifications.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <IOSurface/IOSurface.h>
#include <CommonCrypto/CommonDigest.h>
#include <fcntl.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <time.h>
#include <unistd.h>

static NSString *directory;
static NSMutableDictionary *files;
static NSUInteger W, H, row;
static uint64_t nowNS(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ULL + t.tv_nsec;
}
static void event(NSString *stage) {
    printf("{\"stage\":\"%s\",\"monotonic_ns\":%llu}\n", stage.UTF8String, (unsigned long long)nowNS()); fflush(stdout);
}
static NSString *hash(NSData *data) {
    unsigned char d[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, (CC_LONG)data.length, d);
    NSMutableString *s = [NSMutableString string];
    for (unsigned i = 0; i < sizeof(d); i++) [s appendFormat:@"%02x", d[i]];
    return s;
}
static void save(NSData *data, NSString *name, NSUInteger bpr) {
    NSError *e = nil;
    if (![data writeToFile:[directory stringByAppendingPathComponent:name]
                  options:NSDataWritingWithoutOverwriting error:&e]) {
        fprintf(stderr, "ARTIFACT_WRITE_FAILED %s %s\n", name.UTF8String, e.description.UTF8String); exit(3);
    }
    NSMutableDictionary *r = [@{@"bytes":@(data.length), @"sha256":hash(data)} mutableCopy];
    if (bpr >= W * 4 && data.length == bpr * H) {
        NSMutableData *active = [NSMutableData dataWithCapacity:W * H * 4];
        for (NSUInteger y = 0; y < H; y++) [active appendBytes:(const uint8_t *)data.bytes + bpr * y length:W * 4];
        r[@"bpr"] = @(bpr); r[@"active_sha256"] = hash(active);
    }
    files[name] = r;
}
static void json(NSString *name, id value) {
    NSError *e = nil;
    NSData *d = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingPrettyPrinted error:&e];
    if (!d) { fprintf(stderr, "JSON_FAILED %s\n", e.description.UTF8String); exit(3); }
    save(d, name, 0);
}
static int fail(NSString *classification, NSString *reason) {
    json(@"result.json", @{@"schema":@"ga415-iosurface-v1", @"RESULT":classification, @"reason":reason,
        @"files":files, @"root_cause":@"ROOT_CAUSE_UNVERIFIED"});
    fprintf(stderr, "%s %s\n", classification.UTF8String, reason.UTF8String); return 3;
}
static void pattern(uint8_t *p, NSUInteger x, NSUInteger y, NSString *name) {
    p[0] = (13*x + 29*y) & 255; p[1] = (7*x + 11*y) & 255; p[2] = (3*x + 17*y) & 255; p[3] = 255;
    if ([name isEqual:@"red"] || [name isEqual:@"green"] || [name isEqual:@"blue"]) {
        p[0] = [name isEqual:@"red"] ? 255 : 0; p[1] = [name isEqual:@"green"] ? 255 : 0; p[2] = [name isEqual:@"blue"] ? 255 : 0;
    } else if ([name isEqual:@"checker"]) {
        p[0] = p[2] = (((x / 8) ^ (y / 8)) & 1) * 255; p[1] = 255 - p[0];
    } else if ([name isEqual:@"rows"]) {
        p[0] = y & 255; p[1] = (y >> 8) & 255; p[2] = (y * 37) & 255;
    } else if ([name isEqual:@"blocks64"]) {
        p[0] = (x / 16) & 255; p[1] = y & 255; p[2] = (x / 16 * 41 + y * 17) & 255;
    } else if ([name isEqual:@"alpha"]) p[3] = (x * 19 + y * 23) & 255;
}
static NSDictionary *texture(id<MTLTexture> t) {
    return @{@"object":[NSString stringWithFormat:@"%p", (__bridge void *)t], @"class":NSStringFromClass([(id)t class]),
        @"width":@(t.width), @"height":@(t.height), @"pixel_format":@(t.pixelFormat), @"storage_mode":@(t.storageMode),
        @"usage":@(t.usage), @"mips":@(t.mipmapLevelCount), @"samples":@(t.sampleCount),
        @"allowGPUOptimizedContents":@(t.allowGPUOptimizedContents), @"internal_pitch":@"NOT_OBSERVED"};
}
static NSArray *driverImages(void) {
    NSMutableArray *images = [NSMutableArray array];
    for (uint32_t i = 0; i < _dyld_image_count(); i++) {
        const char *name = _dyld_get_image_name(i);
        if (!name || (!strstr(name, "AppleIntelTGLGraphicsMTLDriver") && !strstr(name, "libxedrv"))) continue;
        NSString *uuid = @"NOT_OBSERVED";
        const struct mach_header *mh = _dyld_get_image_header(i);
        if (mh && mh->magic == MH_MAGIC_64) {
            const struct mach_header_64 *h = (const struct mach_header_64 *)mh;
            const uint8_t *p = (const uint8_t *)(h + 1), *end = p + h->sizeofcmds;
            for (uint32_t n = 0; n < h->ncmds && p + sizeof(struct load_command) <= end; n++) {
                const struct load_command *c = (const struct load_command *)p;
                if (c->cmdsize < sizeof(*c) || p + c->cmdsize > end) break;
                if (c->cmd == LC_UUID && c->cmdsize >= sizeof(struct uuid_command))
                    uuid = [[NSUUID alloc] initWithUUIDBytes:((const struct uuid_command *)c)->uuid].UUIDString;
                p += c->cmdsize;
            }
        }
        NSData *binary = [NSData dataWithContentsOfFile:@(name)];
        [images addObject:@{@"loaded_path":@(name), @"uuid":uuid, @"on_disk_sha256":binary ? hash(binary) : @"NOT_OBSERVED"}];
    }
    return images;
}
int main(int argc, char **argv) { @autoreleasepool {
    NSString *caseID = nil, *pat = @"affine", *bprMode = @"auto", *claim = nil;
    BOOL cpuOnly = NO, execute = NO, capture = NO;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--case") && i + 1 < argc) caseID = @(argv[++i]);
        else if (!strcmp(argv[i], "--output") && i + 1 < argc) directory = @(argv[++i]);
        else if (!strcmp(argv[i], "--pattern") && i + 1 < argc) pat = @(argv[++i]);
        else if (!strcmp(argv[i], "--bpr") && i + 1 < argc) bprMode = @(argv[++i]);
        else if (!strcmp(argv[i], "--claim-path") && i + 1 < argc) claim = @(argv[++i]);
        else if (!strcmp(argv[i], "--cpu-only")) cpuOnly = YES;
        else if (!strcmp(argv[i], "--execute-once")) execute = YES;
        else if (!strcmp(argv[i], "--metal-capture")) capture = YES;
        else { fprintf(stderr, "INVALID_ARGUMENT\n"); return 2; }
    }
    if (!directory || ![@[@"A",@"B",@"C"] containsObject:caseID] ||
        ![@[@"affine",@"red",@"green",@"blue",@"checker",@"rows",@"blocks64",@"alpha"] containsObject:pat] ||
        ![@[@"auto",@"packed",@"align16"] containsObject:bprMode] || cpuOnly == execute || (execute && !claim) || (cpuOnly && capture)) {
        fprintf(stderr, "usage: iosurface-pixel-probe --case A|B|C --output NEW_DIR (--cpu-only | --execute-once --claim-path NEW_CLAIM) [--pattern affine|red|green|blue|checker|rows|blocks64|alpha] [--bpr auto|packed|align16] [--metal-capture]\n"); return 2;
    }
    W = [caseID isEqual:@"A"] ? 640 : 642; H = [caseID isEqual:@"B"] ? 32 : 100; row = (W * 4 + 255) & ~255UL;
    NSError *error = nil;
    if ([[NSFileManager defaultManager] fileExistsAtPath:directory] ||
        ![[NSFileManager defaultManager] createDirectoryAtPath:directory withIntermediateDirectories:NO attributes:nil error:&error]) return 2;
    files = [NSMutableDictionary dictionary]; setbuf(stdout, NULL); alarm(45);
    if (execute) {
        int fd = open(claim.fileSystemRepresentation, O_WRONLY | O_CREAT | O_EXCL, 0600);
        if (fd < 0) return fail(@"CAPTURE_INVALID", @"ONE_SHOT_CLAIM_ALREADY_EXISTS_OR_CANNOT_BE_CREATED");
        const char *text = "GPU attempt claimed; do not retry, including after timeout or incomplete output.\n";
        if (write(fd, text, strlen(text)) != (ssize_t)strlen(text) || fsync(fd)) { close(fd); return fail(@"CAPTURE_INVALID", @"CLAIM_WRITE_FAILED"); }
        close(fd);
    }
    json(@"intent.json", @{@"case":caseID, @"pattern":pat, @"cpu_only":@(cpuOnly), @"execute_once":@(execute),
        @"requested_surface_bpr":bprMode, @"process_timeout_seconds":@45,
        @"timeout_limit":@"Process deadline does not cancel GPU/driver work. Never retry automatically."});
    NSMutableData *input = [NSMutableData dataWithLength:W * H * 4];
    NSMutableData *expected = [NSMutableData dataWithLength:W * H * 4];
    for (NSUInteger y = 0; y < H; y++) for (NSUInteger x = 0; x < W; x++)
        pattern((uint8_t *)input.mutableBytes + (y * W + x) * 4, x, y, pat);
    // Separate storage; independent Python expected-pattern.py must reconstruct and verify this capture.
    for (NSUInteger y = 0; y < H; y++) for (NSUInteger x = 0; x < W; x++)
        pattern((uint8_t *)expected.mutableBytes + (y * W + x) * 4, x, y, pat);
    save(input, @"input.bin", W * 4); save(expected, @"expected.bin", W * 4);
    NSMutableDictionary *props = [@{(__bridge NSString *)kIOSurfaceWidth:@(W), (__bridge NSString *)kIOSurfaceHeight:@(H),
        (__bridge NSString *)kIOSurfaceBytesPerElement:@4, (__bridge NSString *)kIOSurfacePixelFormat:@(0x52474241)} mutableCopy];
    if ([bprMode isEqual:@"packed"]) props[(__bridge NSString *)kIOSurfaceBytesPerRow] = @(W * 4);
    if ([bprMode isEqual:@"align16"]) props[(__bridge NSString *)kIOSurfaceBytesPerRow] = @((W * 4 + 15) & ~15UL);
    IOSurfaceRef surface = IOSurfaceCreate((__bridge CFDictionaryRef)props);
    if (!surface) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_CREATE_REJECTED_LAYOUT");
    size_t pitch = IOSurfaceGetBytesPerRow(surface), alloc = IOSurfaceGetAllocSize(surface);
    if (pitch < W * 4 || alloc < pitch * H || IOSurfaceGetWidth(surface) != W || IOSurfaceGetHeight(surface) != H || IOSurfaceGetBytesPerElement(surface) != 4)
        return fail(@"CAPTURE_INVALID", @"IOSURFACE_ACTUAL_GEOMETRY_INVALID");
    event(@"iosurface_cpu_upload_begin");
    uint32_t seed = 0; kern_return_t kr = IOSurfaceLock(surface, 0, &seed);
    if (kr != KERN_SUCCESS) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_WRITE_LOCK_FAILED");
    uint8_t *base = IOSurfaceGetBaseAddress(surface);
    if (!base) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_BASE_ADDRESS_NIL");
    memset(base, 0xa5, pitch * H);
    for (NSUInteger y = 0; y < H; y++) memcpy(base + y * pitch, (const uint8_t *)input.bytes + y * W * 4, W * 4);
    NSData *before = [NSData dataWithBytes:base length:pitch * H];
    kr = IOSurfaceUnlock(surface, 0, &seed);
    if (kr != KERN_SUCCESS) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_WRITE_UNLOCK_FAILED");
    save(before, @"iosurface-before.bin", pitch);
    NSMutableDictionary *resource = [@{@"case":caseID, @"width":@(W), @"height":@(H), @"pattern":pat,
        @"pixel_format":@"RGBA8Unorm", @"byte_order":@"R,G,B,A; linear UNORM; no sRGB conversion; straight alpha; blending disabled",
        @"logical_bpr":@(W * 4), @"requested_surface_bpr":bprMode,
        @"iosurface_actual_bpr":@(pitch), @"iosurface_alloc_bytes":@(alloc), @"iosurface_id":@(IOSurfaceGetID(surface)),
        @"iosurface_pixel_format_fourcc":@(IOSurfaceGetPixelFormat(surface)), @"iosurface_seed":@(seed),
        @"actual_surface_bpr_64_aligned":@(pitch % 64 == 0), @"actual_surface_copy_bytes":@(pitch * H),
        @"input_bpr":@(W * 4), @"output_bpr":@(row),
        @"texture_internal_pitch":@"NOT_OBSERVED", @"submitBlit_source_pitch":@"NOT_OBSERVED", @"submitBlit_destination_pitch":@"NOT_OBSERVED",
        @"submitBlit_route":@"NOT_OBSERVED", @"XE_BLITFIX_trigger":@"NOT_OBSERVED",
        @"source_dump_limit":@"upload-proxy.bin is a texture-to-buffer copy proxy, not direct raw GPU storage"} mutableCopy];
    if (cpuOnly) {
        kr = IOSurfaceLock(surface, kIOSurfaceLockReadOnly, &seed);
        if (kr != KERN_SUCCESS) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_READ_LOCK_FAILED");
        NSData *after = [NSData dataWithBytes:IOSurfaceGetBaseAddress(surface) length:pitch * H];
        kr = IOSurfaceUnlock(surface, kIOSurfaceLockReadOnly, &seed);
        if (kr != KERN_SUCCESS) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_READ_UNLOCK_FAILED");
        save(after, @"iosurface-after.bin", pitch); json(@"resource.json", resource);
        json(@"command.json", @{@"submitted":@NO, @"status":@"NOT_OBSERVED", @"reason":@"CPU_ONLY; no MTL device created"});
        json(@"result.json", @{@"schema":@"ga415-iosurface-v1", @"RESULT":@"CPU_CAPTURE_COMPLETE_UNVERIFIED", @"cpu_only":@YES,
            @"case":caseID, @"pattern":pat, @"files":files, @"root_cause":@"ROOT_CAUSE_UNVERIFIED"});
        CFRelease(surface); alarm(0); return 0;
    }
    event(@"metal_device_create_begin");
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) return fail(@"GPU_COMMAND_FAIL", @"NO_METAL_DEVICE");
    resource[@"device"] = dev.name; resource[@"registry_id"] = @(dev.registryID);
    resource[@"unified_memory"] = @(dev.hasUnifiedMemory);
    resource[@"loaded_driver_images"] = driverImages(); resource[@"driver_uuid"] = @"NOT_OBSERVED";
    for (NSDictionary *image in resource[@"loaded_driver_images"])
        if ([image[@"loaded_path"] hasSuffix:@"/AppleIntelTGLGraphicsMTLDriver"]) resource[@"driver_uuid"] = image[@"uuid"];
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "vertex float4 vs(uint i [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(p[i],0,1); }\n"
        "fragment float4 fs(float4 p [[position]], texture2d<float,access::read> t [[texture(0)]]) { return t.read(uint2(p.xy)); }\n";
    save([source dataUsingEncoding:NSUTF8StringEncoding], @"shader.metal", 0);
    id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:&error];
    if (!lib) return fail(@"GPU_COMMAND_FAIL", error.description ?: @"SHADER_COMPILE_FAILED");
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [lib newFunctionWithName:@"vs"]; pd.fragmentFunction = [lib newFunctionWithName:@"fs"];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm; pd.colorAttachments[0].blendingEnabled = NO;
    id<MTLRenderPipelineState> pipeline = [dev newRenderPipelineStateWithDescriptor:pd error:&error];
    if (!pipeline) return fail(@"GPU_COMMAND_FAIL", error.description ?: @"PIPELINE_CREATE_FAILED");
    MTLTextureDescriptor *sd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
    sd.storageMode = MTLStorageModeShared; sd.usage = MTLTextureUsageShaderRead; sd.allowGPUOptimizedContents = NO;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:sd iosurface:surface plane:0];
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
    td.storageMode = MTLStorageModeManaged; td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead; td.allowGPUOptimizedContents = NO;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];
    id<MTLBuffer> proxy = [dev newBufferWithLength:row * H options:MTLResourceStorageModeShared];
    id<MTLBuffer> readback = [dev newBufferWithLength:row * H options:MTLResourceStorageModeShared];
    id<MTLCommandQueue> queue = [dev newCommandQueue];
    if (!tex || !target || !proxy || !readback || !queue || !proxy.contents || !readback.contents ||
        tex.storageMode != MTLStorageModeShared || target.storageMode != MTLStorageModeManaged)
        return fail(@"RESOURCE_READBACK_FAIL", @"RESOURCE_CREATION_OR_STORAGE_MISMATCH");
    memset(proxy.contents, 0xee, row * H); memset(readback.contents, 0xdd, row * H);
    resource[@"source_texture"] = texture(tex); resource[@"target_texture"] = texture(target);
    resource[@"readback_buffer_storage"] = @(readback.storageMode);
    resource[@"Metal_API_route"] = @"IOSurface shared texture -> direct blit proxy; texture.read -> managed RGBA8 render target -> blit shared buffer + managed synchronize -> CPU getBytes";
    resource[@"capture_supported_GPUTraceDocument"] = @([[MTLCaptureManager sharedCaptureManager] supportsDestination:MTLCaptureDestinationGPUTraceDocument]);
    if (capture) {
        MTLCaptureDescriptor *cd = [MTLCaptureDescriptor new]; cd.captureObject = queue;
        cd.destination = MTLCaptureDestinationGPUTraceDocument;
        cd.outputURL = [NSURL fileURLWithPath:[directory stringByAppendingPathComponent:@"capture.gputrace"]];
        if (![[MTLCaptureManager sharedCaptureManager] startCaptureWithDescriptor:cd error:&error])
            return fail(@"CAPTURE_PATH_UNVERIFIED", error.description ?: @"METAL_CAPTURE_FAILED_NO_GPU_SUBMITTED");
    }
    json(@"resource.json", resource);
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    if (!cb) return fail(@"GPU_COMMAND_FAIL", @"COMMAND_BUFFER_NIL");
    cb.label = @"GA415-one-shot-IOSurface-copy-render-sync-readback";
    uint64_t created = nowNS(); event(@"encode_source_proxy");
    id<MTLBlitCommandEncoder> copy = [cb blitCommandEncoder];
    if (!copy) return fail(@"GPU_COMMAND_FAIL", @"SOURCE_PROXY_ENCODER_NIL");
    [copy copyFromTexture:tex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
        toBuffer:proxy destinationOffset:0 destinationBytesPerRow:row destinationBytesPerImage:row * H]; [copy endEncoding];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = target; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].storeAction = MTLStoreActionStore; rp.colorAttachments[0].clearColor = MTLClearColorMake(1,0,1,1);
    id<MTLRenderCommandEncoder> render = [cb renderCommandEncoderWithDescriptor:rp];
    if (!render) return fail(@"GPU_COMMAND_FAIL", @"RENDER_ENCODER_NIL");
    [render setRenderPipelineState:pipeline]; [render setFragmentTexture:tex atIndex:0];
    [render drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; [render endEncoding];
    id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
    if (!blit) return fail(@"GPU_COMMAND_FAIL", @"TARGET_READBACK_ENCODER_NIL");
    [blit copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
        toBuffer:readback destinationOffset:0 destinationBytesPerRow:row destinationBytesPerImage:row * H];
    [blit synchronizeResource:target]; [blit endEncoding];
    uint64_t commitNS = nowNS(); event(@"command_commit"); [cb commit]; [cb waitUntilCompleted];
    uint64_t completeNS = nowNS(); event(@"command_wait_returned");
    NSDictionary *command = @{@"submitted":@YES, @"explicit_command_buffers":@1, @"status":@(cb.status),
        @"error":cb.error.description ?: @"", @"error_domain":cb.error.domain ?: @"", @"error_code":@(cb.error.code),
        @"created_ns":@(created), @"commit_ns":@(commitNS), @"completion_observed_ns":@(completeNS), @"wait_returned":@YES,
        @"operations":@[@"source texture -> shared buffer proxy", @"unfiltered integer-address texture.read -> RGBA8 render target (no blend)",
                        @"target texture -> shared buffer", @"synchronize managed target"],
        @"hidden_driver_operations":@"NOT_OBSERVED", @"timeout":@NO};
    json(@"command.json", command);
    if (capture) [[MTLCaptureManager sharedCaptureManager] stopCapture];
    if (cb.status != MTLCommandBufferStatusCompleted || cb.error) return fail(@"GPU_COMMAND_FAIL", @"COMMAND_NOT_COMPLETED_CLEANLY");
    NSData *upload = [NSData dataWithBytes:proxy.contents length:row * H];
    NSData *gpu = [NSData dataWithBytes:readback.contents length:row * H];
    save(upload, @"upload-proxy.bin", row); save(gpu, @"gpu.bin", row);
    uint64_t freezeNS = nowNS(); event(@"gpu_snapshot_frozen_before_getBytes");
    NSMutableData *cpu = [NSMutableData dataWithLength:row * H]; memset(cpu.mutableBytes, 0xcc, cpu.length);
    uint64_t cpuBegin = nowNS();
    [target getBytes:cpu.mutableBytes bytesPerRow:row fromRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0];
    uint64_t cpuEnd = nowNS(); save(cpu, @"cpu.bin", row);
    kr = IOSurfaceLock(surface, kIOSurfaceLockReadOnly, &seed);
    if (kr != KERN_SUCCESS) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_POST_READ_LOCK_FAILED");
    NSData *after = [NSData dataWithBytes:IOSurfaceGetBaseAddress(surface) length:pitch * H];
    kr = IOSurfaceUnlock(surface, kIOSurfaceLockReadOnly, &seed);
    if (kr != KERN_SUCCESS) return fail(@"RESOURCE_READBACK_FAIL", @"IOSURFACE_POST_READ_UNLOCK_FAILED");
    save(after, @"iosurface-after.bin", pitch);
    json(@"result.json", @{@"schema":@"ga415-iosurface-v1", @"RESULT":@"CAPTURE_COMPLETE_UNVERIFIED", @"cpu_only":@NO,
        @"case":caseID, @"pattern":pat, @"files":files, @"gpu_frozen_ns":@(freezeNS), @"cpu_getBytes_begin_ns":@(cpuBegin),
        @"cpu_getBytes_end_ns":@(cpuEnd), @"snapshots_independent":@YES,
        @"root_cause":@"ROOT_CAUSE_UNVERIFIED", @"verifier_required":@"Python reconstructs expected independently; completed command is not PIXEL_PASS"});
    CFRelease(surface); event(@"capture_complete_unverified"); alarm(0); return 0;
} }
