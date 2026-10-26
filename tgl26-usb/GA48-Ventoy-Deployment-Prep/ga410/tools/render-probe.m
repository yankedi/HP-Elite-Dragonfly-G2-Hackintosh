// Bounded readback probe: device -> shader compile -> six 256x64 texture reads.
// Compare GPU sampling with CPU-known bytes, independent of desktop scanout.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <IOSurface/IOSurface.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <dlfcn.h>

static int probe(id<MTLDevice> dev, id<MTLComputePipelineState> ps,
                 MTLPixelFormat pf, const char *name, BOOL private,
                 id<MTLRenderPipelineState> render, BOOL surface, BOOL sourceSurface, int managed) {
    const NSUInteger w = managed==3 ? 80 : 257, h = managed==3 ? 80 : 65, bpp = pf == MTLPixelFormatR8Unorm ? 1 : pf==MTLPixelFormatRGBA16Float ? 8 : 4;
    const NSUInteger pitch = managed==3 ? w*bpp : (w*bpp+255)&~255UL, bytes = pitch * h;
    const NSUInteger outPitch = (w*4+255)&~255UL;
    id<MTLBuffer> src = [dev newBufferWithLength:bytes options:MTLResourceStorageModeShared];
    id<MTLBuffer> out = [dev newBufferWithLength:outPitch*h*4 options:MTLResourceStorageModeShared];
    if (!src || !out) return 2;
    uint8_t *p = src.contents;
    for (NSUInteger y=0; y<h; ++y) for (NSUInteger x=0; x<w; ++x)
        for (NSUInteger c=0; c<bpp; ++c) p[y*pitch+x*bpp+c] = (x*13+y*29+c*61) & 255;
    if (bpp==8) {
        const uint16_t halves[4]={0,0x3400,0x3800,0x3c00};
        for (NSUInteger y=0; y<h; ++y) for (NSUInteger x=0; x<w; ++x)
            for(NSUInteger c=0;c<4;++c) ((uint16_t*)(p+y*pitch+x*bpp))[c]=halves[(x+y+c)%4];
    }
    memset(out.contents, 0xEE, out.length);
    MTLTextureDescriptor *d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:pf width:w height:h mipmapped:NO];
    d.storageMode = private ? MTLStorageModePrivate : managed==1 || managed==3 ? MTLStorageModeManaged : MTLStorageModeShared;
    d.usage = MTLTextureUsageShaderRead;
    d.allowGPUOptimizedContents = NO;
    IOSurfaceRef inputIO = NULL;
    id<MTLTexture> tex;
    if (sourceSurface) {
        uint32_t fourcc = bpp==1 ? 0x4c303038 : pf==MTLPixelFormatBGRA8Unorm ? 0x42475241 : 0x52474241;
        inputIO = IOSurfaceCreate((__bridge CFDictionaryRef)@{(id)kIOSurfaceWidth:@(w),(id)kIOSurfaceHeight:@(h),
            (id)kIOSurfaceBytesPerElement:@(bpp),(id)kIOSurfaceBytesPerRow:@(pitch),(id)kIOSurfacePixelFormat:@(fourcc)});
        if (!inputIO) return 2;
        IOSurfaceLock(inputIO,0,NULL);
        for (NSUInteger y=0; y<h; ++y) memcpy((uint8_t*)IOSurfaceGetBaseAddress(inputIO)+y*IOSurfaceGetBytesPerRow(inputIO),p+y*pitch,w*bpp);
        IOSurfaceUnlock(inputIO,0,NULL);
        d.storageMode=MTLStorageModeShared;
        tex=[dev newTextureWithDescriptor:d iosurface:inputIO plane:0];
    } else tex = [dev newTextureWithDescriptor:d];
    id<MTLCommandQueue> q = [dev newCommandQueue];
    if (!tex || !q) return 2;
    id<MTLCommandBuffer> cb = [q commandBuffer];
    if (sourceSurface) {
        // The IOSurface CPU producer above already supplied these pixels.
    } else if (private) {
        id<MTLBlitCommandEncoder> b = [cb blitCommandEncoder];
        [b copyFromBuffer:src sourceOffset:0 sourceBytesPerRow:pitch sourceBytesPerImage:bytes
              sourceSize:MTLSizeMake(w,h,1) toTexture:tex destinationSlice:0 destinationLevel:0 destinationOrigin:MTLOriginMake(0,0,0)];
        [b endEncoding];
    } else [tex replaceRegion:MTLRegionMake2D(0,0,w,h) mipmapLevel:0 withBytes:p bytesPerRow:pitch];
    IOSurfaceRef io = NULL;
    id<MTLTexture> target = nil;
    if (render) {
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:w height:h mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.allowGPUOptimizedContents = NO;
        if (getenv("GA410_PROBE_WRITABLE_TARGET")) td.usage |= MTLTextureUsageShaderWrite;
        td.storageMode = surface ? MTLStorageModeShared : managed==2 ? MTLStorageModeManaged : MTLStorageModePrivate;
        if (surface) {
            io = IOSurfaceCreate((__bridge CFDictionaryRef)@{(id)kIOSurfaceWidth:@(w),(id)kIOSurfaceHeight:@(h),
                (id)kIOSurfaceBytesPerElement:@4,(id)kIOSurfaceBytesPerRow:@(outPitch),(id)kIOSurfacePixelFormat:@(0x52474241)});
            target = [dev newTextureWithDescriptor:td iosurface:io plane:0];
        } else target = [dev newTextureWithDescriptor:td];
        if (!target) { if (io) CFRelease(io); puts("RENDER_TARGET_MISSING"); return 2; }
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture=target;
        rp.colorAttachments[0].loadAction=MTLLoadActionClear;
        rp.colorAttachments[0].storeAction=MTLStoreActionStore;
        rp.colorAttachments[0].clearColor=MTLClearColorMake(1,0,1,1);
        id<MTLRenderCommandEncoder> r = [cb renderCommandEncoderWithDescriptor:rp];
        [r setRenderPipelineState:render]; [r setFragmentTexture:tex atIndex:0];
        [r drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [r endEncoding];
        id<MTLBlitCommandEncoder> b = [cb blitCommandEncoder];
        if (managed==2) [b synchronizeResource:target];
        [b copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(w,h,1)
                   toBuffer:out destinationOffset:0 destinationBytesPerRow:outPitch destinationBytesPerImage:outPitch*h];
        [b endEncoding];
    } else {
        id<MTLComputeCommandEncoder> e = [cb computeCommandEncoder];
        [e setComputePipelineState:ps]; [e setTexture:tex atIndex:0]; [e setBuffer:out offset:0 atIndex:0];
        [e dispatchThreadgroups:MTLSizeMake((w+7)/8,(h+7)/8,1) threadsPerThreadgroup:MTLSizeMake(8,8,1)];
        [e endEncoding];
    }
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status != MTLCommandBufferStatusCompleted) {
        printf("%s %s command_status=%lu error=%s\n",name,private?"private":"shared",(unsigned long)cb.status,cb.error.description.UTF8String); return 2;
    }
    if (managed==2) {
        uint8_t *cpu=malloc(outPitch*h);
        [target getBytes:cpu bytesPerRow:outPitch fromRegion:MTLRegionMake2D(0,0,w,h) mipmapLevel:0];
        NSUInteger differing=0;
        for (NSUInteger y=0;y<h;++y) for (NSUInteger x=0;x<w*4;++x)
            if(cpu[y*outPitch+x]!=((uint8_t*)out.contents)[y*outPitch+x]) ++differing;
        printf("managed_target_CPU_vs_GPU_differing_bytes=%lu\n",(unsigned long)differing);
        memcpy(out.contents,cpu,outPitch*h); free(cpu);
    }
    float *got = out.contents; uint8_t *rgb = out.contents; NSUInteger bad=0;
    for (NSUInteger y=0; y<h; ++y) for (NSUInteger x=0; x<w; ++x) {
        BOOL wrong=NO;
        for (NSUInteger c=0; c<4; ++c) {
            NSUInteger channel = pf == MTLPixelFormatBGRA8Unorm && c<3 ? 2-c : c;
            float expected = bpp == 1 && c>0 ? (c==3 ? 1 : 0) : p[y*pitch+x*bpp+channel]/255.0f;
            if (bpp==8) { const float values[4]={0,0.25,0.5,1}; expected=values[(x+y+c)%4]; }
            float actual = render ? rgb[y*outPitch+x*4+c]/255.0f : got[(y*w+x)*4+c];
            if (!isfinite(actual) || fabsf(actual-expected)>0.002f) wrong=YES;
        }
        if (wrong && bad++<4) printf(" mismatch xy=%lu,%lu raw_input=%u raw_output=%u,%u,%u,%u\n",(unsigned long)x,(unsigned long)y,p[y*pitch+x*bpp],rgb[y*outPitch+x*4],rgb[y*outPitch+x*4+1],rgb[y*outPitch+x*4+2],rgb[y*outPitch+x*4+3]);
    }
    printf("%s %s bad_pixels=%lu/%lu\n",name,private?"private":managed?"managed":"shared",(unsigned long)bad,(unsigned long)(w*h));
    fflush(stdout); if (io) CFRelease(io); if (inputIO) CFRelease(inputIO); return bad ? 1 : 0;
}

int main(int argc, char **argv) { @autoreleasepool {
    alarm(30); setbuf(stdout,NULL);
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { puts("DEVICE_MISSING"); return 2; }
    printf("device=%s registry=%llu unified=%d\n",dev.name.UTF8String,dev.registryID,dev.hasUnifiedMemory);
    const char *trace=getenv("GA410_TRACE_DYLIB");
    if (trace && !dlopen(trace,RTLD_NOW)) { fprintf(stderr,"trace load failed: %s\n",dlerror()); return 3; }
    if (argc != 2 || !strcmp(argv[1],"device")) return 0;
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\nkernel void readtex(texture2d<float,access::read> t [[texture(0)]], device float4* dst [[buffer(0)]], uint2 p [[thread_position_in_grid]]) { if(p.x<t.get_width() && p.y<t.get_height()) dst[p.y*t.get_width()+p.x]=t.read(p); }\nvertex float4 vs(uint i [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(p[i],0,1); }\nfragment float4 fs(float4 p [[position]],texture2d<float> t [[texture(0)]]) { constexpr sampler s(coord::pixel,address::clamp_to_edge,filter::nearest); return t.sample(s,p.xy); }";
    NSError *err=nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:source options:nil error:&err];
    if (!lib) { printf("COMPILE_FAILED %s\n",err.description.UTF8String); return 2; }
    id<MTLFunction> f = [lib newFunctionWithName:@"readtex"];
    id<MTLComputePipelineState> ps = [dev newComputePipelineStateWithFunction:f error:&err];
    if (!ps || ps.maxTotalThreadsPerThreadgroup<64) { printf("PIPELINE_FAILED %s\n",err.description.UTF8String); return 2; }
    puts("SHADER_COMPILE_PIPELINE_OK");
    if (!strcmp(argv[1],"compile")) return 0;
    int managed = !strcmp(argv[1],"managed") ? 1 : !strcmp(argv[1],"managed-target") ? 2 : (!strcmp(argv[1],"tight") || !strcmp(argv[1],"half")) ? 3 : 0;
    BOOL render = managed || !strcmp(argv[1],"render") || !strcmp(argv[1],"surface") || !strcmp(argv[1],"source");
    id<MTLRenderPipelineState> rps=nil;
    if (render) {
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction=[lib newFunctionWithName:@"vs"]; rd.fragmentFunction=[lib newFunctionWithName:@"fs"];
        rd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
        rps=[dev newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!rps) { printf("RENDER_PIPELINE_FAILED %s\n",err.description.UTF8String); return 2; }
    } else if (strcmp(argv[1],"run")) return 2;
    int status=0;
    if (!strcmp(argv[1],"half")) return probe(dev,ps,MTLPixelFormatRGBA16Float,"RGBA16Float",NO,rps,NO,NO,managed);
    for (int priv=0; priv<(!strcmp(argv[1],"source") || managed ?1:2); ++priv) {
        status |= probe(dev,ps,MTLPixelFormatR8Unorm,"R8",priv,rps,!strcmp(argv[1],"surface"),!strcmp(argv[1],"source"),managed);
        status |= probe(dev,ps,MTLPixelFormatRGBA8Unorm,"RGBA8",priv,rps,!strcmp(argv[1],"surface"),!strcmp(argv[1],"source"),managed);
        status |= probe(dev,ps,MTLPixelFormatBGRA8Unorm,"BGRA8",priv,rps,!strcmp(argv[1],"surface"),!strcmp(argv[1],"source"),managed);
    }
    return status;
} }
