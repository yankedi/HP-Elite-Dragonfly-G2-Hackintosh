// Process-local, observation-only tracing of the installed driver's CPU path.
// Field offsets are taken from the recorded native 16.0.32 disassembly.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static IMP originalGet, originalResolve;
static ptrdiff_t infoOffset;
static unsigned calls;
static uint32_t u32(const void *p) { uint32_t v; memcpy(&v,p,4); return v; }
static uint16_t u16(const void *p) { uint16_t v; memcpy(&v,p,2); return v; }
static void state(id t,const char *operation) {
    if (++calls>32) return;
    const uint8_t *info=(const uint8_t*)(__bridge void*)t+infoOffset;
    const uint8_t *resource=NULL; memcpy(&resource,info,sizeof(resource));
    fprintf(stderr,"CPU_TRACE %s texture=%p format=%lu size=%lux%lu storage=%lu pitch108=%u pitch10c=%u bpp=%u tiling=%u flags16a=%04x flags1ac=%04x resource1c=%08x\n",
            operation,(__bridge void*)t,(unsigned long)[t pixelFormat],(unsigned long)[t width],(unsigned long)[t height],(unsigned long)[t storageMode],
            u32(info+0x108),u32(info+0x10c),u32(info+0x114),u32(info+0x134),u16(info+0x16a),u16(info+0x1ac),resource?u32(resource+0x1c):0);
}
static void get(id t,SEL s,void *dst,NSUInteger row,NSUInteger image,MTLRegion region,NSUInteger level,NSUInteger slice) {
    state(t,"getBytes");
    ((void(*)(id,SEL,void*,NSUInteger,NSUInteger,MTLRegion,NSUInteger,NSUInteger))originalGet)(t,s,dst,row,image,region,level,slice);
}
static signed char resolve(id t,SEL s,NSUInteger level,NSUInteger slice,signed char wait) {
    state(t,"resolveCCS");
    signed char result=((signed char(*)(id,SEL,NSUInteger,NSUInteger,signed char))originalResolve)(t,s,level,slice,wait);
    if (calls<=32) fprintf(stderr,"CPU_TRACE resolveCCS_result=%d wait=%d\n",result,wait);
    return result;
}
__attribute__((constructor)) static void install(void) {
    Class c=objc_getClass("MTLIGAccelTexture");
    Ivar ivar=class_getInstanceVariable(c,"m_Info");
    Method g=class_getInstanceMethod(c,sel_registerName("getBytes:bytesPerRow:bytesPerImage:fromRegion:mipmapLevel:slice:"));
    Method r=class_getInstanceMethod(c,sel_registerName("resolveCCS:slice:waitForCompletion:"));
    if (!ivar || !g || !r) { fprintf(stderr,"CPU_TRACE missing ABI\n"); return; }
    infoOffset=ivar_getOffset(ivar);
    originalGet=method_setImplementation(g,(IMP)get);
    originalResolve=method_setImplementation(r,(IMP)resolve);
    fprintf(stderr,"CPU_TRACE installed info_offset=%td get=%s resolve=%s\n",infoOffset,method_getTypeEncoding(g),method_getTypeEncoding(r));
}
