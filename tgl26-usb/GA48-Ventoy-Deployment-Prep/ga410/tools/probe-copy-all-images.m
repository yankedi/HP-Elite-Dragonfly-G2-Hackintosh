// Process-only diagnostic of upstream v15's predicate: copy aligned offsets too.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <stdio.h>

@interface GA410ImageOwner : NSObject
@property(copy) void (^callback)(void*, NSUInteger);
@property void *pointer;
@property NSUInteger length;
@end
@implementation GA410ImageOwner
- (void)dealloc { if (_callback) _callback(_pointer,_length); }
@end

static IMP prior3,prior4;
static char ownerKey;
static id copyImage(id dev, void *ptr, NSUInteger len, MTLTextureDescriptor *d, NSUInteger off, NSUInteger bpr) {
    if (!ptr || off>=len || !bpr || d.textureType!=MTLTextureType2D || d.mipmapLevelCount!=1 || d.arrayLength!=1) return nil;
    MTLTextureDescriptor *c=[d copy]; c.storageMode=MTLStorageModeManaged;
    id<MTLTexture> t=[dev newTextureWithDescriptor:c];
    if (!t) return nil;
    [t replaceRegion:MTLRegionMake2D(0,0,d.width,d.height) mipmapLevel:0 withBytes:(uint8_t*)ptr+off bytesPerRow:bpr];
    fprintf(stderr,"COPY_ALL_IMAGE %lux%lu fmt=%lu off=%lu bpr=%lu\n",d.width,d.height,d.pixelFormat,off,bpr);
    return t;
}
static id __attribute__((ns_returns_retained)) wrap3(id s,SEL c,void *p,NSUInteger len,MTLTextureDescriptor *d,NSUInteger off,NSUInteger bpr) {
    id t=copyImage(s,p,len,d,off,bpr);
    return t ?: ((id(*)(id,SEL,void*,NSUInteger,id,NSUInteger,NSUInteger))prior3)(s,c,p,len,d,off,bpr);
}
static id __attribute__((ns_returns_retained)) wrap4(id s,SEL c,void *p,NSUInteger len,id dealloc,MTLTextureDescriptor *d,NSUInteger off,NSUInteger bpr) {
    id t=copyImage(s,p,len,d,off,bpr);
    if (!t) return ((id(*)(id,SEL,void*,NSUInteger,id,id,NSUInteger,NSUInteger))prior4)(s,c,p,len,dealloc,d,off,bpr);
    if (dealloc) {
        GA410ImageOwner *owner=[GA410ImageOwner new];
        owner.callback=dealloc; owner.pointer=p; owner.length=len;
        objc_setAssociatedObject(t,&ownerKey,owner,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
    return t;
}
__attribute__((constructor)) static void install(void) {
    Class c=objc_getClass("MTLIOAccelDevice");
    Method m3=class_getInstanceMethod(c,sel_registerName("newTiledTextureWithBytesNoCopy:length:descriptor:offset:bytesPerRow:"));
    Method m4=class_getInstanceMethod(c,sel_registerName("newTiledTextureWithBytesNoCopy:length:deallocator:descriptor:offset:bytesPerRow:"));
    if (!m3 || !m4) { fprintf(stderr,"COPY_ALL_IMAGE missing methods\n"); return; }
    prior3=method_setImplementation(m3,(IMP)wrap3); prior4=method_setImplementation(m4,(IMP)wrap4);
    fprintf(stderr,"COPY_ALL_IMAGE diagnostic installed in this process\n");
}
