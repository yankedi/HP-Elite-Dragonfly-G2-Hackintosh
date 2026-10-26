// Known-pixel reproduction of CoreAnimation's private image-upload path.
// Bounded process only: 80x80 pixels, six cases; no WindowServer injection.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/message.h>
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int run(id<MTLDevice> dev,id<MTLComputePipelineState> pipeline,NSUInteger off,BOOL half) {
    NSUInteger w=80,h=80,bpp=half?8:4,pitch=w*bpp;
    NSUInteger length=(off+pitch*h+4095)&~4095UL;
    void *memory=NULL;
    if(posix_memalign(&memory,4096,length)) return 2;
    memset(memory,0xCD,length);
    uint8_t *pixels=(uint8_t*)memory+off;
    const uint16_t halves[]={0,0x3400,0x3800,0x3c00};
    for(NSUInteger y=0;y<h;++y) for(NSUInteger x=0;x<w;++x) for(NSUInteger c=0;c<4;++c) {
        if(half) ((uint16_t*)(pixels+y*pitch+x*bpp))[c]=halves[(x+y+c)%4];
        else pixels[y*pitch+x*bpp+c]=(x*13+y*29+c*61)&255;
    }
    MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:half?MTLPixelFormatRGBA16Float:MTLPixelFormatBGRA8Unorm width:w height:h mipmapped:NO];
    d.storageMode=MTLStorageModeShared; d.usage=MTLTextureUsageShaderRead; d.allowGPUOptimizedContents=NO;
    SEL selector=sel_registerName("newTiledTextureWithBytesNoCopy:length:descriptor:offset:bytesPerRow:");
    if(![dev respondsToSelector:selector]) { puts("NOCOPY_SELECTOR_MISSING"); free(memory); return 2; }
    id<MTLTexture> texture=((id(*)(id,SEL,void*,NSUInteger,id,NSUInteger,NSUInteger))objc_msgSend)(dev,selector,memory,length,d,off,pitch);
    if(!texture) { printf("NOCOPY_NIL half=%d offset=%lu\n",half,off); free(memory); return 2; }
    id<MTLBuffer> output=[dev newBufferWithLength:w*h*16 options:MTLResourceStorageModeShared];
    id<MTLCommandQueue> queue=[dev newCommandQueue];
    if(!output || !queue) return 2;
    memset(output.contents,0xEE,output.length);
    id<MTLCommandBuffer> cb=[queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder=[cb computeCommandEncoder];
    [encoder setComputePipelineState:pipeline]; [encoder setTexture:texture atIndex:0];
    [encoder setBuffer:output offset:0 atIndex:0];
    [encoder dispatchThreadgroups:MTLSizeMake(10,10,1) threadsPerThreadgroup:MTLSizeMake(8,8,1)];
    [encoder endEncoding]; [cb commit]; [cb waitUntilCompleted];
    if(cb.status!=MTLCommandBufferStatusCompleted) { printf("NOCOPY_COMMAND_FAILED status=%lu %s\n",cb.status,cb.error.description.UTF8String); return 2; }
    NSUInteger bad=0;
    for(NSUInteger y=0;y<h;++y) for(NSUInteger x=0;x<w;++x) {
        BOOL wrong=NO;
        for(NSUInteger c=0;c<4;++c) {
            const float expectedHalf[]={0,0.25,0.5,1};
            NSUInteger channel=c<3?2-c:c;
            float expected=half?expectedHalf[(x+y+c)%4]:pixels[y*pitch+x*bpp+channel]/255.f;
            float actual=((float*)output.contents)[(y*w+x)*4+c];
            if(!isfinite(actual) || fabsf(expected-actual)>0.002f) wrong=YES;
        }
        if(wrong) ++bad;
    }
    printf("NOCOPY_RESULT half=%d offset=%lu row=%lu format=%lu storage=%lu bad_pixels=%lu/%lu\n",half,off,pitch,texture.pixelFormat,texture.storageMode,bad,w*h);
    [texture release]; [queue release]; [output release]; free(memory);
    return bad?1:0;
}

int main(void) { @autoreleasepool {
    alarm(25); setbuf(stdout,NULL);
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    if(!dev) return 2;
    const char *inject=getenv("GA410_PROBE_DYLIB");
    if(inject && !dlopen(inject,RTLD_NOW)) { fprintf(stderr,"%s\n",dlerror()); return 2; }
    NSError *error=nil;
    NSString *source=@"#include <metal_stdlib>\nusing namespace metal; kernel void copyPixels(texture2d<float> t [[texture(0)]],device float4 *dst [[buffer(0)]],uint2 p [[thread_position_in_grid]]) { constexpr sampler s(coord::pixel,filter::nearest,address::clamp_to_edge); dst[p.y*80+p.x]=t.sample(s,float2(p)+0.5f); }";
    id<MTLLibrary> lib=[dev newLibraryWithSource:source options:nil error:&error];
    id<MTLFunction> fn=[lib newFunctionWithName:@"copyPixels"];
    id<MTLComputePipelineState> pipeline=fn?[dev newComputePipelineStateWithFunction:fn error:&error]:nil;
    if(!pipeline || pipeline.maxTotalThreadsPerThreadgroup<64) { fprintf(stderr,"%s\n",error.description.UTF8String); return 2; }
    int result=0;
    for(int half=0;half<2;++half) for(int i=0;i<3;++i) {
        const NSUInteger offsets[]={0,32,256};
        result|=run(dev,pipeline,offsets[i],half);
    }
    return result;
} }
