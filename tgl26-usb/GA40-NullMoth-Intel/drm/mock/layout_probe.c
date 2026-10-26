/* Layout evidence from the selected unmodified Mesa Linux UAPI headers. */
#include <stdio.h>
#include <stddef.h>
#include <drm.h>
#include <i915_drm.h>
#define TYPE(tag) printf("\"" #tag "\":{\"size\":%zu,\"align\":%zu,\"fields\":{",sizeof(struct tag),_Alignof(struct tag))
#define FIELD(tag,f,last) printf("\"" #f "\":{\"offset\":%zu,\"size\":%zu}" last,offsetof(struct tag,f),sizeof(((struct tag*)0)->f))
#define END(last) printf("}}" last)
#define REQUEST(name,tag,last) printf("\"" #name "\":{\"value\":%lu,\"struct\":\"" #tag "\"}" last,(unsigned long)DRM_IOCTL_##name)
int main(void) {
    printf("{\"pointer_size\":%zu,\"structs\":{",sizeof(void*));
    TYPE(drm_version); FIELD(drm_version,version_major,","); FIELD(drm_version,version_minor,","); FIELD(drm_version,version_patchlevel,","); FIELD(drm_version,name_len,","); FIELD(drm_version,name,","); FIELD(drm_version,date_len,","); FIELD(drm_version,date,","); FIELD(drm_version,desc_len,","); FIELD(drm_version,desc,""); END(",");
    TYPE(drm_get_cap); FIELD(drm_get_cap,capability,","); FIELD(drm_get_cap,value,""); END(",");
    TYPE(drm_i915_getparam); FIELD(drm_i915_getparam,param,","); FIELD(drm_i915_getparam,value,""); END(",");
    TYPE(drm_i915_query); FIELD(drm_i915_query,num_items,","); FIELD(drm_i915_query,flags,","); FIELD(drm_i915_query,items_ptr,""); END(",");
    TYPE(drm_i915_gem_create); FIELD(drm_i915_gem_create,size,","); FIELD(drm_i915_gem_create,handle,","); FIELD(drm_i915_gem_create,pad,""); END(",");
    TYPE(drm_gem_close); FIELD(drm_gem_close,handle,","); FIELD(drm_gem_close,pad,""); END(",");
    TYPE(drm_i915_gem_mmap_offset); FIELD(drm_i915_gem_mmap_offset,handle,","); FIELD(drm_i915_gem_mmap_offset,pad,","); FIELD(drm_i915_gem_mmap_offset,offset,","); FIELD(drm_i915_gem_mmap_offset,flags,","); FIELD(drm_i915_gem_mmap_offset,extensions,""); END(",");
    TYPE(drm_i915_gem_context_create_ext); FIELD(drm_i915_gem_context_create_ext,ctx_id,","); FIELD(drm_i915_gem_context_create_ext,flags,","); FIELD(drm_i915_gem_context_create_ext,extensions,""); END(",");
    TYPE(drm_i915_gem_context_destroy); FIELD(drm_i915_gem_context_destroy,ctx_id,","); FIELD(drm_i915_gem_context_destroy,pad,""); END(",");
    TYPE(drm_i915_gem_vm_control); FIELD(drm_i915_gem_vm_control,extensions,","); FIELD(drm_i915_gem_vm_control,flags,","); FIELD(drm_i915_gem_vm_control,vm_id,""); END(",");
    TYPE(drm_syncobj_create); FIELD(drm_syncobj_create,handle,","); FIELD(drm_syncobj_create,flags,""); END(",");
    TYPE(drm_syncobj_destroy); FIELD(drm_syncobj_destroy,handle,","); FIELD(drm_syncobj_destroy,pad,""); END(",");
    TYPE(drm_syncobj_array); FIELD(drm_syncobj_array,handles,","); FIELD(drm_syncobj_array,count_handles,","); FIELD(drm_syncobj_array,pad,""); END(",");
    TYPE(drm_syncobj_wait); FIELD(drm_syncobj_wait,handles,","); FIELD(drm_syncobj_wait,timeout_nsec,","); FIELD(drm_syncobj_wait,count_handles,","); FIELD(drm_syncobj_wait,flags,","); FIELD(drm_syncobj_wait,first_signaled,","); FIELD(drm_syncobj_wait,pad,","); FIELD(drm_syncobj_wait,deadline_nsec,""); END(",");
    TYPE(drm_i915_gem_execbuffer2); FIELD(drm_i915_gem_execbuffer2,buffers_ptr,","); FIELD(drm_i915_gem_execbuffer2,buffer_count,","); FIELD(drm_i915_gem_execbuffer2,batch_start_offset,","); FIELD(drm_i915_gem_execbuffer2,batch_len,","); FIELD(drm_i915_gem_execbuffer2,flags,""); END("");
    printf("},\"requests\":{");
    REQUEST(VERSION,drm_version,","); REQUEST(GET_CAP,drm_get_cap,","); REQUEST(I915_GETPARAM,drm_i915_getparam,","); REQUEST(I915_QUERY,drm_i915_query,","); REQUEST(I915_GEM_CREATE,drm_i915_gem_create,","); REQUEST(GEM_CLOSE,drm_gem_close,","); REQUEST(I915_GEM_MMAP_OFFSET,drm_i915_gem_mmap_offset,","); REQUEST(I915_GEM_CONTEXT_CREATE_EXT,drm_i915_gem_context_create_ext,","); REQUEST(I915_GEM_CONTEXT_DESTROY,drm_i915_gem_context_destroy,","); REQUEST(I915_GEM_VM_CREATE,drm_i915_gem_vm_control,","); REQUEST(I915_GEM_VM_DESTROY,drm_i915_gem_vm_control,","); REQUEST(SYNCOBJ_CREATE,drm_syncobj_create,","); REQUEST(SYNCOBJ_DESTROY,drm_syncobj_destroy,","); REQUEST(SYNCOBJ_SIGNAL,drm_syncobj_array,","); REQUEST(SYNCOBJ_RESET,drm_syncobj_array,","); REQUEST(SYNCOBJ_WAIT,drm_syncobj_wait,","); REQUEST(I915_GEM_EXECBUFFER2,drm_i915_gem_execbuffer2,"");
    printf("},\"constants\":{\"DRM_CAP_PRIME\":%u,\"SYNCOBJ_SIGNALED\":%u,\"WAIT_ALL\":%u}}\n",DRM_CAP_PRIME,DRM_SYNCOBJ_CREATE_SIGNALED,DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL);
    return 0;
}
