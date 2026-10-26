// Derived from ga410/tools/render-probe.m's managed-target workload.
// Diagnostic only: no installed driver/KC modifications. One case per process.
// Preserve GPU and CPU results independently; never overwrite GPU bytes with CPU bytes.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dlfcn.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static const NSUInteger W=257, H=65, ROW=1280;
static NSMutableArray *commands;

static void save(NSData *data, NSString *directory, NSString *name) {
    NSError *error=nil;
    if (![data writeToFile:[directory stringByAppendingPathComponent:name] options:NSDataWritingWithoutOverwriting error:&error]) {
        fprintf(stderr,"ARTIFACT_WRITE_FAILED %s: %s\n",name.UTF8String,error.description.UTF8String);
        exit(3);
    }
}

static BOOL finish(id<MTLCommandBuffer> cb, NSString *stage) {
    if (!cb) return NO;
    cb.label=stage;
    printf("STAGE %s commit\n",stage.UTF8String);
    [cb commit]; [cb waitUntilCompleted];
    [commands addObject:@{@"stage":stage,@"status":@(cb.status),@"error":cb.error.description ?: @""}];
    printf("STAGE %s completed status=%lu error=%s\n",stage.UTF8String,(unsigned long)cb.status,
           (cb.error.description ?: @"").UTF8String);
    return cb.status==MTLCommandBufferStatusCompleted && cb.error==nil;
}

static NSDictionary *diff(NSData *a, NSData *b) {
    const uint8_t *x=a.bytes,*y=b.bytes;
    NSUInteger bytes=0,pixels=0;
    NSMutableArray *first=[NSMutableArray array];
    for (NSUInteger r=0;r<H;r++) for (NSUInteger c=0;c<W;c++) {
        BOOL bad=NO;
        for (NSUInteger k=0;k<4;k++) {
            NSUInteger i=r*ROW+c*4+k;
            if (x[i]!=y[i]) {
                bytes++; bad=YES;
                if (first.count<32) [first addObject:@{@"offset":@(i),@"x":@(c),@"y":@(r),
                    @"channel":@(k),@"a":@(x[i]),@"b":@(y[i])}];
            }
        }
        if (bad) pixels++;
    }
    return @{@"differing_bytes":@(bytes),@"bad_pixels":@(pixels),@"total_pixels":@(W*H),
             @"padding_excluded":@YES,@"first_differences":first};
}

static NSDictionary *attrs(id<MTLTexture> t) {
    return @{@"class":NSStringFromClass([(id)t class]),@"width":@(t.width),@"height":@(t.height),
             @"format":@(t.pixelFormat),@"storage":@(t.storageMode),@"usage":@(t.usage),
             @"samples":@(t.sampleCount),@"mips":@(t.mipmapLevelCount),@"array_length":@(t.arrayLength)};
}

static BOOL copyTarget(id<MTLCommandQueue> q,id<MTLTexture> t,id<MTLBuffer> out,NSString *stage) {
    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLBlitCommandEncoder> b=[cb blitCommandEncoder];
    if (!b) return NO;
    [b copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
           sourceSize:MTLSizeMake(W,H,1) toBuffer:out destinationOffset:0
           destinationBytesPerRow:ROW destinationBytesPerImage:ROW*H];
    [b endEncoding]; return finish(cb,stage);
}

int main(int argc,char **argv) { @autoreleasepool {
    setbuf(stdout,NULL); alarm(30);
    if (argc!=4 || (strcmp(argv[1],"R8") && strcmp(argv[1],"RGBA8") && strcmp(argv[1],"BGRA8")) ||
        (strcmp(argv[2],"legacy") && strcmp(argv[2],"staged"))) {
        fprintf(stderr,"usage: managed-rt-probe R8|RGBA8|BGRA8 legacy|staged NEW_OUTPUT_DIRECTORY\n"); return 2;
    }
    NSString *directory=[NSString stringWithUTF8String:argv[3]];
    NSError *error=nil;
    if ([[NSFileManager defaultManager] fileExistsAtPath:directory] ||
        ![[NSFileManager defaultManager] createDirectoryAtPath:directory withIntermediateDirectories:NO attributes:nil error:&error]) {
        fprintf(stderr,"NEW_OUTPUT_DIRECTORY_REQUIRED %s\n",error.description.UTF8String); return 2;
    }
    commands=[NSMutableArray array];
    BOOL staged=!strcmp(argv[2],"staged"),r8=!strcmp(argv[1],"R8"),bgra=!strcmp(argv[1],"BGRA8");
    NSUInteger bpp=r8?1:4,pitch=(W*bpp+255)&~255UL;
    MTLPixelFormat pf=r8?MTLPixelFormatR8Unorm:bgra?MTLPixelFormatBGRA8Unorm:MTLPixelFormatRGBA8Unorm;
    NSMutableData *input=[NSMutableData dataWithLength:pitch*H];
    NSMutableData *expected=[NSMutableData dataWithLength:ROW*H];
    uint8_t *p=input.mutableBytes,*e=expected.mutableBytes;
    for (NSUInteger y=0;y<H;y++) for (NSUInteger x=0;x<W;x++) {
        for (NSUInteger c=0;c<bpp;c++) p[y*pitch+x*bpp+c]=(x*13+y*29+c*61)&255;
        for (NSUInteger c=0;c<4;c++) e[y*ROW+x*4+c]=r8 && c>0 ? (c==3?255:0) :
            p[y*pitch+x*bpp+(bgra && c<3?2-c:c)];
    }
    save(input,directory,@"input.bin"); save(expected,directory,@"expected.bin");
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    if (!dev) { puts("DEVICE_MISSING"); return 2; }
    printf("DEVICE %s registry=%llu unified=%d\n",dev.name.UTF8String,dev.registryID,dev.hasUnifiedMemory);
    const char *trace=getenv("GA411_TRACE_DYLIB");
    if (trace && !dlopen(trace,RTLD_NOW)) { fprintf(stderr,"TRACE_LOAD_FAILED %s\n",dlerror()); return 2; }
    // Shader, dimensions, pattern, clear colour and formats match the historical workload.
    NSString *source=@"#include <metal_stdlib>\nusing namespace metal;\n"
        "vertex float4 vs(uint i [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(p[i],0,1); }\n"
        "fragment float4 fs(float4 p [[position]],texture2d<float> t [[texture(0)]]) { constexpr sampler s(coord::pixel,address::clamp_to_edge,filter::nearest); return t.sample(s,p.xy); }";
    id<MTLLibrary> lib=[dev newLibraryWithSource:source options:nil error:&error];
    if (!lib) { fprintf(stderr,"COMPILE_FAILED %s\n",error.description.UTF8String); return 2; }
    MTLRenderPipelineDescriptor *rd=[MTLRenderPipelineDescriptor new];
    rd.vertexFunction=[lib newFunctionWithName:@"vs"]; rd.fragmentFunction=[lib newFunctionWithName:@"fs"];
    rd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
    id<MTLRenderPipelineState> ps=[dev newRenderPipelineStateWithDescriptor:rd error:&error];
    if (!ps) { fprintf(stderr,"PIPELINE_FAILED %s\n",error.description.UTF8String); return 2; }
    // Retain the historical shared upload buffer and oversized output allocation.
    id<MTLBuffer> src=[dev newBufferWithLength:pitch*H options:MTLResourceStorageModeShared];
    id<MTLBuffer> out=[dev newBufferWithLength:ROW*H*4 options:MTLResourceStorageModeShared];
    if (!src || !out) return 2;
    memcpy(src.contents,p,input.length); memset(out.contents,0xee,out.length);
    MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pf width:W height:H mipmapped:NO];
    d.storageMode=MTLStorageModeShared; d.usage=MTLTextureUsageShaderRead; d.allowGPUOptimizedContents=NO;
    id<MTLTexture> tex=[dev newTextureWithDescriptor:d];
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
    td.storageMode=MTLStorageModeManaged; td.usage=MTLTextureUsageRenderTarget; td.allowGPUOptimizedContents=NO;
    id<MTLTexture> target=[dev newTextureWithDescriptor:td];
    id<MTLCommandQueue> q=[dev newCommandQueue];
    if (!tex || !target || !out || !q || target.storageMode!=MTLStorageModeManaged) { puts("RESOURCE_MISSING_OR_MODE_MISMATCH"); return 2; }
    [tex replaceRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0 withBytes:src.contents bytesPerRow:pitch];
    id<MTLCommandBuffer> cb=[q commandBuffer];
    MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].storeAction=MTLStoreActionStore; rp.colorAttachments[0].clearColor=MTLClearColorMake(1,0,1,1);
    id<MTLRenderCommandEncoder> r=[cb renderCommandEncoderWithDescriptor:rp];
    if (!r) return 2;
    [r setRenderPipelineState:ps]; [r setFragmentTexture:tex atIndex:0];
    [r drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; [r endEncoding];
    NSData *gpuBefore=nil;
    if (staged) {
        if (!finish(cb,@"render") || !copyTarget(q,target,out,@"gpu_copy_before_explicit_sync")) return 2;
        gpuBefore=[NSData dataWithBytes:out.contents length:ROW*H];
        save(gpuBefore,directory,@"gpu-before-sync.bin");
        cb=[q commandBuffer];
    }
    id<MTLBlitCommandEncoder> b=[cb blitCommandEncoder];
    if (!b) return 2;
    [b synchronizeResource:target];
    if (!staged) [b copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
        sourceSize:MTLSizeMake(W,H,1) toBuffer:out destinationOffset:0 destinationBytesPerRow:ROW destinationBytesPerImage:ROW*H];
    [b endEncoding];
    if (!finish(cb,staged?@"explicit_sync":@"legacy_render_sync_copy")) return 2;
    if (staged && !copyTarget(q,target,out,@"gpu_copy_after_explicit_sync")) return 2;
    NSData *gpu=[NSData dataWithBytes:out.contents length:ROW*H];
    save(gpu,directory,@"gpu.bin");
    // Save and validate the GPU snapshot before any CPU getBytes/resolve/lock operation.
    NSDictionary *gpuDiff=diff(gpu,expected);
    printf("GPU_EXPECTED %s\n",gpuDiff.description.UTF8String);
    NSMutableData *cpu=[NSMutableData dataWithLength:ROW*H]; memset(cpu.mutableBytes,0xdd,cpu.length);
    puts("STAGE cpu_getBytes begin (automatic lock/resolve observed only if tracer loaded)");
    [target getBytes:cpu.mutableBytes bytesPerRow:ROW fromRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0];
    puts("STAGE cpu_getBytes returned"); save(cpu,directory,@"cpu.bin");
    NSDictionary *cpuDiff=diff(cpu,expected),*paths=diff(cpu,gpu);
    NSDictionary *beforeDiff=gpuBefore?diff(gpuBefore,expected):nil;
    BOOL pass=[gpuDiff[@"bad_pixels"] unsignedLongValue]==0 && [cpuDiff[@"bad_pixels"] unsignedLongValue]==0 &&
              (!beforeDiff || [beforeDiff[@"bad_pixels"] unsignedLongValue]==0);
    NSMutableDictionary *result=[@{@"status":pass?@"PIXEL_PASS":@"PIXEL_FAIL",@"case":[NSString stringWithUTF8String:argv[1]],
        @"mode":[NSString stringWithUTF8String:argv[2]],@"width":@(W),@"height":@(H),@"input_pitch":@(pitch),@"output_pitch":@(ROW),
        @"input_bpp":@(bpp),@"device":dev.name,@"registry_id":@(dev.registryID),@"unified":@(dev.hasUnifiedMemory),
        @"source":attrs(tex),@"target":attrs(target),@"requested_allowGPUOptimizedContents":@NO,
        @"commands":commands,@"gpu_vs_expected":gpuDiff,@"cpu_vs_expected":cpuDiff,@"cpu_vs_gpu":paths,
        @"resolve_observation":trace?@"see stderr; entry/return are not proof of conversion":@"NOT_OBSERVED",
        @"kernel_AUX_CCS_and_rc1474":@"NOT_OBSERVED",@"comparison":@"exact active RGBA8 bytes; row padding excluded"} mutableCopy];
    if (beforeDiff) result[@"gpu_before_vs_expected"]=beforeDiff;
    NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:&error];
    if (!json) return 3;
    save(json,directory,@"result.json"); puts(pass?"PIXEL_PASS":"PIXEL_FAIL");
    return pass?0:1;
} }
