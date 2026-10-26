// CPU descriptor observations only. Matching observations are NOT an ABI approval.
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include "../src/xe_abi.h"
#include <string.h>
#include <stdlib.h>

typedef struct {
    size_t pipeline_size, attachment_size;
    ptrdiff_t pipeline_offset, attachment_offset;
    size_t pipeline_storage, attachment_storage;
    size_t pipeline_alignment, attachment_alignment;
    int selector_ok, encoding_ok, storage_ok, inline_pointer_ok, values_ok;
} XeMetalObservation;

static int xe_private_selector_ok(Class c) {
    Method m=c ? class_getInstanceMethod(c,sel_registerName("_descriptorPrivate")) : NULL;
    if (!m || method_getNumberOfArguments(m)!=2) return 0;
    char *type=method_copyReturnType(m);
    int ok=type && type[0]=='^';
    free(type);
    return ok;
}

static XeMetalObservation xe_observe_metal(void) {
    XeMetalObservation o={0};
    o.pipeline_offset=o.attachment_offset=-1;
    Class pc=objc_getClass("MTLRenderPipelineDescriptorInternal");
    Class ac=objc_getClass("MTLRenderPipelineColorAttachmentDescriptorInternal");
    Ivar pi=pc ? class_getInstanceVariable(pc,"_private") : NULL;
    Ivar ai=ac ? class_getInstanceVariable(ac,"_private") : NULL;
    if (!pi || !ai) return o;
    o.pipeline_size=class_getInstanceSize(pc);o.attachment_size=class_getInstanceSize(ac);
    o.pipeline_offset=ivar_getOffset(pi);o.attachment_offset=ivar_getOffset(ai);
    const char *pe=ivar_getTypeEncoding(pi),*ae=ivar_getTypeEncoding(ai);
    if (!pe || !ae || pe[0]=='^' || ae[0]=='^') return o;
    // NSGetSizeAndAlignment interprets the actual encoding; never infer a
    // struct extent from the total class size or an arbitrary readable page.
    @try {
        NSGetSizeAndAlignment(pe,&o.pipeline_storage,&o.pipeline_alignment);
        NSGetSizeAndAlignment(ae,&o.attachment_storage,&o.attachment_alignment);
    } @catch (NSException *e) { (void)e; return o; }
    o.encoding_ok=strstr(pe,"\"shaderValidation\"q\"shaderValidationState\"q\"textureWriteRoundingMode\"q") &&
                  strstr(ae,"\"writeMask\"b5\"logicOpEnabled\"b1\"logicOp\"b4\"pixelFormat\"b22");
    o.storage_ok=xe_abi_layout_ok(o.pipeline_size,o.pipeline_offset,o.attachment_size,o.attachment_offset) &&
        xe_abi_storage_ok(o.pipeline_size,o.pipeline_offset,o.pipeline_storage,o.pipeline_alignment,XE_RPD_PRIVATE_SIZE) &&
        xe_abi_storage_ok(o.attachment_size,o.attachment_offset,o.attachment_storage,o.attachment_alignment,8);
    o.selector_ok=xe_private_selector_ok(pc) && xe_private_selector_ok(ac);
    if (!o.storage_ok || !o.selector_ok || !o.encoding_ok) return o;
    MTLRenderPipelineDescriptor *d=[MTLRenderPipelineDescriptor new];
    MTLRenderPipelineColorAttachmentDescriptor *a=[MTLRenderPipelineColorAttachmentDescriptor new];
    @try {
        if (object_getClass(d)==pc && object_getClass(a)==ac) {
            SEL sel=sel_registerName("_descriptorPrivate");
            const uint8_t *raw=((const void *(*)(id,SEL))objc_msgSend)(d,sel);
            const void *araw=((const void *(*)(id,SEL))objc_msgSend)(a,sel);
            o.inline_pointer_ok=raw==(const uint8_t *)(void *)d+o.pipeline_offset &&
                                araw==(const uint8_t *)(void *)a+o.attachment_offset;
            if (o.inline_pointer_ok) {
                d.rasterSampleCount=4;d.vertexDescriptor=[MTLVertexDescriptor vertexDescriptor];
                uint64_t sample=0;void *vertex=NULL;
                memcpy(&sample,raw+XE_RASTER_SAMPLE_COUNT_OFF,sizeof sample);
                memcpy(&vertex,raw+XE_VERTEX_DESCRIPTOR_OFF,sizeof vertex);
                o.values_ok=sample==d.rasterSampleCount && vertex==(void *)d.vertexDescriptor;
            }
        }
    } @catch (NSException *e) { (void)e; o.values_ok=0; }
    [a release];[d release];
    return o;
}
