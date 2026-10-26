/* GA4.5: read-only 25G83 Metal descriptor ABI probe.
 * It only reads class/ivar metadata and a private descriptor buffer returned
 * by Metal.  It does not create an MTLDevice, command queue, or GPU work.
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include "xe_abi.h"

static void emit(const char *k, long long v) { printf("\"%s\": %lld,\n", k, v); }

int main(void) {
  @autoreleasepool {
    Class c = objc_getClass("MTLRenderPipelineDescriptorInternal");
    Class ac = objc_getClass("MTLRenderPipelineColorAttachmentDescriptorInternal");
    Ivar p = c ? class_getInstanceVariable(c, "_private") : NULL;
    Ivar ap = ac ? class_getInstanceVariable(ac, "_private") : NULL;
    size_t rpd_size = c ? class_getInstanceSize(c) : 0;
    ptrdiff_t rpd_priv = p ? ivar_getOffset(p) : -1;
    size_t att_size = ac ? class_getInstanceSize(ac) : 0;
    ptrdiff_t att_priv = ap ? ivar_getOffset(ap) : -1;
    printf("{\n");
    emit("rpd_size", (long long)rpd_size);
    emit("rpd_private_offset", (long long)rpd_priv);
    emit("att_size", (long long)att_size);
    emit("att_private_offset", (long long)att_priv);
    emit("layout_ok", xe_abi_layout_ok(rpd_size, rpd_priv, att_size, att_priv));
    emit("logicop_old_bit", XE_LOGICOP_OLD_BIT);
    emit("logicop_new_bit", XE_LOGICOP_NEW_BIT);
    if (c) {
      MTLRenderPipelineDescriptor *d = [MTLRenderPipelineDescriptor new];
      SEL s = sel_registerName("_descriptorPrivate");
      if ([d respondsToSelector:s]) {
        const uint8_t *raw = ((const void *(*)(id, SEL))objc_msgSend)(d, s);
        if (raw) {
          uint64_t sample = 0; void *vd = NULL;
          memcpy(&sample, raw + XE_RASTER_SAMPLE_COUNT_OFF, 8);
          memcpy(&vd, raw + XE_VERTEX_DESCRIPTOR_OFF, 8);
          emit("sample_offset_value", (long long)sample);
          emit("vertex_descriptor_nonnull", vd != NULL);
        }
      }
      [d release];
    }
    printf("\"status\": \"ABI_PROBE_READ_ONLY\"\n}\n");
  }
  return 0;
}
