/* GA40 private research glue; uses unchanged NullMoth upload lifetime policy.
 * Original helper license is PolyForm Noncommercial (see source LICENSE).
 * CPU model operations and Lavapipe operations are distinctly identified.
 */
#include "nm_backend.h"
#include "nvmtl_tex_upload.h"
#include <vulkan/vulkan.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

#ifndef NM_LVP_PATH
#define NM_LVP_PATH "LAVAPIPE_NOT_CONFIGURED"
#endif
#define NR 32
#define NC 16
#define NO 16
#define CAPS (NM_CAP_BUFFER | NM_CAP_IMAGE | NM_CAP_TRANSFER)
#define VKFUNCS(X) \
 X(DestroyInstance) X(GetPhysicalDeviceProperties) X(GetPhysicalDeviceMemoryProperties) \
 X(GetPhysicalDeviceQueueFamilyProperties) X(EnumeratePhysicalDevices) X(CreateDevice) \
 X(DestroyDevice) X(GetDeviceQueue) X(CreateBuffer) X(DestroyBuffer) \
 X(GetBufferMemoryRequirements) X(AllocateMemory) X(FreeMemory) X(BindBufferMemory) \
 X(MapMemory) X(UnmapMemory) X(CreateImage) X(DestroyImage) X(GetImageMemoryRequirements) \
 X(BindImageMemory) X(CreateCommandPool) X(DestroyCommandPool) X(AllocateCommandBuffers) \
 X(FreeCommandBuffers) X(BeginCommandBuffer) X(EndCommandBuffer) X(CmdFillBuffer) \
 X(CmdCopyBuffer) X(CmdPipelineBarrier) X(CreateFence) X(DestroyFence) X(QueueSubmit) \
 X(WaitForFences) X(DeviceWaitIdle)
struct resource {
    nm_handle id; size_t size; unsigned refs; int image;
    void *map; VkBuffer buffer; VkImage img; VkDeviceMemory memory;
    nvmtl_up_state upload;
};
struct operation { int copy; nm_handle src, dst; size_t offset, size; uint32_t value; };
enum command_state { RECORDING, ENDED, PENDING, DONE };
struct command {
    nm_handle id; enum command_state state; unsigned n;
    struct operation op[NO]; VkCommandBuffer vk; VkFence fence;
};
struct nm_device {
    enum nm_kind kind; enum nm_fault fault; pthread_mutex_t lock; nm_handle next;
    struct resource resources[NR]; struct command commands[NC];
    char name[VK_MAX_PHYSICAL_DEVICE_NAME_SIZE];
    void *lib; VkInstance instance; VkPhysicalDevice physical; VkDevice device;
    VkQueue queue; VkCommandPool pool; uint32_t family;
    VkPhysicalDeviceMemoryProperties memory;
#define DECLARE(name) PFN_vk##name name;
    VKFUNCS(DECLARE)
#undef DECLARE
};

static struct resource *resource(nm_device *d, nm_handle id) {
    if (id) for (unsigned i=0;i<NR;i++) if (d->resources[i].id==id) return &d->resources[i];
    return NULL;
}
static struct command *command(nm_device *d, nm_handle id) {
    if (id) for (unsigned i=0;i<NC;i++) if (d->commands[i].id==id) return &d->commands[i];
    return NULL;
}
static int fault(nm_device *d, enum nm_fault f) {
    if (d->fault!=f) return 0;
    d->fault=NM_FAULT_NONE; return 1;
}
static int range(size_t total, size_t offset, size_t size) {
    return size && offset<=total && size<=total-offset;
}
static int memory_type(nm_device *d, uint32_t bits, VkMemoryPropertyFlags flags) {
    for (unsigned i=0;i<d->memory.memoryTypeCount;i++)
        if ((bits&(1u<<i)) && (d->memory.memoryTypes[i].propertyFlags&flags)==flags) return (int)i;
    return -1;
}
static void vk_finish(nm_device *d) {
    if (d->device && d->DestroyDevice) {
        if (d->pool && d->DestroyCommandPool) d->DestroyCommandPool(d->device,d->pool,NULL);
        d->DestroyDevice(d->device,NULL);
    }
    if (d->instance && d->DestroyInstance) d->DestroyInstance(d->instance,NULL);
    if (d->lib) dlclose(d->lib);
}
static int vk_start(nm_device *d) {
    /* Direct fixed software ICD: no loader, auto-discovery, or hardware ICD. */
    d->lib=dlopen(NM_LVP_PATH,RTLD_NOW|RTLD_LOCAL);
    if (!d->lib) return NM_BACKEND_FAILED;
    PFN_vkGetInstanceProcAddr get=(PFN_vkGetInstanceProcAddr)dlsym(d->lib,"vk_icdGetInstanceProcAddr");
    if (!get) return NM_BACKEND_FAILED;
    PFN_vkCreateInstance create=(PFN_vkCreateInstance)get(VK_NULL_HANDLE,"vkCreateInstance");
    if (!create) return NM_BACKEND_FAILED;
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="GA40 software research",.apiVersion=VK_API_VERSION_1_1};
    VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};
    if (create(&ici,NULL,&d->instance)!=VK_SUCCESS) return NM_BACKEND_FAILED;
#define LOAD(name) d->name=(PFN_vk##name)get(d->instance,"vk" #name);
    VKFUNCS(LOAD)
#undef LOAD
    if (!d->DestroyInstance || !d->EnumeratePhysicalDevices || !d->CreateDevice) return NM_BACKEND_FAILED;
    uint32_t n=0;
    if (d->EnumeratePhysicalDevices(d->instance,&n,NULL)!=VK_SUCCESS || n!=1) return NM_UNSUPPORTED;
    if (d->EnumeratePhysicalDevices(d->instance,&n,&d->physical)!=VK_SUCCESS) return NM_BACKEND_FAILED;
    VkPhysicalDeviceProperties props;
    d->GetPhysicalDeviceProperties(d->physical,&props);
    if (props.deviceType!=VK_PHYSICAL_DEVICE_TYPE_CPU || !strstr(props.deviceName,"llvmpipe")) return NM_UNSUPPORTED;
    memcpy(d->name,props.deviceName,sizeof d->name); d->name[sizeof d->name-1]=0;
    d->GetPhysicalDeviceMemoryProperties(d->physical,&d->memory);
    uint32_t nq=0; d->GetPhysicalDeviceQueueFamilyProperties(d->physical,&nq,NULL);
    if (!nq || nq>64) return NM_UNSUPPORTED;
    VkQueueFamilyProperties q[64]; d->GetPhysicalDeviceQueueFamilyProperties(d->physical,&nq,q);
    d->family=UINT32_MAX;
    for (uint32_t i=0;i<nq;i++) if (q[i].queueCount && (q[i].queueFlags&VK_QUEUE_TRANSFER_BIT)) { d->family=i; break; }
    if (d->family==UINT32_MAX) return NM_UNSUPPORTED;
    float priority=1;
    VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=d->family,.queueCount=1,.pQueuePriorities=&priority};
    VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi};
    if (d->CreateDevice(d->physical,&di,NULL,&d->device)!=VK_SUCCESS) return NM_BACKEND_FAILED;
    PFN_vkGetDeviceProcAddr gd=(PFN_vkGetDeviceProcAddr)get(d->instance,"vkGetDeviceProcAddr");
    if (!gd) return NM_BACKEND_FAILED;
    /* Device entries may not be exported by an ICD's instance resolver. */
#define RELOAD(name) if (!d->name) d->name=(PFN_vk##name)gd(d->device,"vk" #name); if (!d->name) return NM_BACKEND_FAILED;
    VKFUNCS(RELOAD)
#undef RELOAD
    d->GetDeviceQueue(d->device,d->family,0,&d->queue);
    VkCommandPoolCreateInfo pi={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=d->family};
    return d->CreateCommandPool(d->device,&pi,NULL,&d->pool)==VK_SUCCESS ? NM_OK : NM_BACKEND_FAILED;
}

int nm_open(enum nm_kind kind, uint32_t required, nm_device **out) {
    if (!out) return NM_INVALID;
    *out=NULL;
    if ((required&~CAPS) || (kind!=NM_CPU_MODEL && kind!=NM_LAVAPIPE)) return NM_UNSUPPORTED;
    nm_device *d=calloc(1,sizeof *d); if (!d) return NM_NOMEM;
    d->kind=kind; d->next=1;
    if (pthread_mutex_init(&d->lock,NULL)) { free(d); return NM_BACKEND_FAILED; }
    strcpy(d->name,"GA40 explicitly simulated CPU model");
    int rc=kind==NM_LAVAPIPE ? vk_start(d) : NM_OK;
    if (rc) { vk_finish(d); pthread_mutex_destroy(&d->lock); free(d); return rc; }
    *out=d; return NM_OK;
}
int nm_info_get(nm_device *d,nm_info *out) {
    if (!d||!out) return NM_INVALID;
    *out=(nm_info){d->kind,CAPS,d->name,0}; return NM_OK;
}
int nm_close(nm_device *d) {
    if (!d) return NM_INVALID;
    pthread_mutex_lock(&d->lock);
    for (unsigned i=0;i<NR;i++) if (d->resources[i].id) { pthread_mutex_unlock(&d->lock); return NM_BUSY; }
    for (unsigned i=0;i<NC;i++) if (d->commands[i].id) { pthread_mutex_unlock(&d->lock); return NM_BUSY; }
    vk_finish(d); pthread_mutex_unlock(&d->lock); pthread_mutex_destroy(&d->lock); free(d); return NM_OK;
}
int nm_fault_once(nm_device *d,enum nm_fault f) {
    if (!d || f<NM_FAULT_NONE || f>NM_FAULT_WAIT) return NM_INVALID;
    pthread_mutex_lock(&d->lock); d->fault=f; pthread_mutex_unlock(&d->lock); return NM_OK;
}
static void resource_free(nm_device *d,struct resource *r) {
    if (d->kind==NM_CPU_MODEL) free(r->map);
    else {
        if (r->map) d->UnmapMemory(d->device,r->memory);
        if (r->buffer) d->DestroyBuffer(d->device,r->buffer,NULL);
        if (r->img) d->DestroyImage(d->device,r->img,NULL);
        if (r->memory) d->FreeMemory(d->device,r->memory,NULL);
    }
    memset(r,0,sizeof *r);
}
static int make_resource(nm_device *d,size_t size,uint32_t w,uint32_t h,nm_handle *out) {
    if (!out) return NM_INVALID;
    *out=0;
    if (!d||!size||size>16*1024*1024) return NM_INVALID;
    pthread_mutex_lock(&d->lock); int rc=NM_NOMEM;
    struct resource *r=NULL;
    for (unsigned i=0;i<NR;i++) if (!d->resources[i].id) { r=&d->resources[i]; break; }
    if (!r || fault(d,NM_FAULT_ALLOCATION)) goto end;
    r->size=size; r->image=w!=0;
    if (d->kind==NM_CPU_MODEL) { r->map=calloc(1,size); if (!r->map) goto fail; }
    else {
        VkMemoryRequirements req;
        if (w) {
            VkImageCreateInfo info={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=VK_FORMAT_R8G8B8A8_UNORM,.extent={w,h,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,.usage=VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED};
            if (d->CreateImage(d->device,&info,NULL,&r->img)!=VK_SUCCESS) goto fail;
            d->GetImageMemoryRequirements(d->device,r->img,&req);
        } else {
            VkBufferCreateInfo info={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=size,.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
            if (d->CreateBuffer(d->device,&info,NULL,&r->buffer)!=VK_SUCCESS) goto fail;
            d->GetBufferMemoryRequirements(d->device,r->buffer,&req);
        }
        int type=memory_type(d,req.memoryTypeBits,w ? 0 : VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
        if (type<0) { rc=NM_UNSUPPORTED; goto fail; }
        VkMemoryAllocateInfo alloc={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=req.size,.memoryTypeIndex=(uint32_t)type};
        if (d->AllocateMemory(d->device,&alloc,NULL,&r->memory)!=VK_SUCCESS) goto fail;
        if (w) { if (d->BindImageMemory(d->device,r->img,r->memory,0)!=VK_SUCCESS) goto fail; }
        else if (d->BindBufferMemory(d->device,r->buffer,r->memory,0)!=VK_SUCCESS || d->MapMemory(d->device,r->memory,0,size,0,&r->map)!=VK_SUCCESS) goto fail;
    }
    if (d->next==UINT64_MAX) { rc=NM_BAD_STATE; goto fail; }
    r->id=d->next++; *out=r->id; rc=NM_OK; goto end;
fail: resource_free(d,r);
end: pthread_mutex_unlock(&d->lock); return rc;
}
int nm_buffer_create(nm_device *d,size_t size,nm_handle *out) { return make_resource(d,size,0,0,out); }
int nm_image_create(nm_device *d,uint32_t w,uint32_t h,nm_handle *out) {
    if (!w||!h||w>2048||h>2048) return NM_INVALID;
    return make_resource(d,(size_t)w*h*4,w,h,out);
}
int nm_resource_destroy(nm_device *d,nm_handle id) {
    if (!d) return NM_INVALID;
    pthread_mutex_lock(&d->lock); struct resource *r=resource(d,id); int rc=NM_INVALID;
    if (r) { rc=(r->refs || nvmtl_up_before_consume(&r->upload)) ? NM_BUSY : NM_OK; if (!rc) resource_free(d,r); }
    pthread_mutex_unlock(&d->lock); return rc;
}
static int access_buffer(nm_device *d,nm_handle id,size_t offset,void *data,size_t size,int write) {
    if (!d||!data) return NM_INVALID;
    pthread_mutex_lock(&d->lock); struct resource *r=resource(d,id); int rc=NM_INVALID;
    if (r && !r->image && range(r->size,offset,size)) {
        rc=(r->refs || nvmtl_up_before_consume(&r->upload)) ? NM_BUSY : NM_OK;
        if (!rc) { if (write) memcpy((char *)r->map+offset,data,size); else memcpy(data,(char *)r->map+offset,size); }
    }
    pthread_mutex_unlock(&d->lock); return rc;
}
int nm_buffer_write(nm_device *d,nm_handle id,size_t off,const void *data,size_t n) { return access_buffer(d,id,off,(void *)data,n,1); }
int nm_buffer_read(nm_device *d,nm_handle id,size_t off,void *data,size_t n) { return access_buffer(d,id,off,data,n,0); }
int nm_command_create(nm_device *d,nm_handle *out) {
    if (!d||!out) return NM_INVALID;
    *out=0; pthread_mutex_lock(&d->lock); int rc=NM_NOMEM;
    if (d->next!=UINT64_MAX) for (unsigned i=0;i<NC;i++) if (!d->commands[i].id) { d->commands[i].id=d->next++; *out=d->commands[i].id; rc=NM_OK; break; }
    pthread_mutex_unlock(&d->lock); return rc;
}
static int encode(nm_device *d,nm_handle id,struct operation op) {
    if (!d) return NM_INVALID;
    pthread_mutex_lock(&d->lock); struct command *c=command(d,id);
    struct resource *dst=resource(d,op.dst),*src=op.copy ? resource(d,op.src) : NULL;
    int rc=NM_INVALID;
    if (!c||!dst||dst->image||!range(dst->size,op.offset,op.size)) goto end;
    if (c->state!=RECORDING) { rc=NM_BAD_STATE; goto end; }
    if (c->n==NO) { rc=NM_NOMEM; goto end; }
    if (op.copy && (!src||src->image||src==dst||!range(src->size,0,op.size))) goto end;
    if (!op.copy && (op.offset%4||op.size%4)) goto end;
    c->op[c->n++]=op; dst->refs++; if (src) src->refs++; rc=NM_OK;
end: pthread_mutex_unlock(&d->lock); return rc;
}
int nm_command_fill(nm_device *d,nm_handle c,nm_handle dst,size_t off,size_t n,uint32_t v) { return encode(d,c,(struct operation){0,0,dst,off,n,v}); }
int nm_command_copy(nm_device *d,nm_handle c,nm_handle src,nm_handle dst,size_t n) { return encode(d,c,(struct operation){1,src,dst,0,n,0}); }
int nm_command_end(nm_device *d,nm_handle id) {
    if (!d) return NM_INVALID;
    pthread_mutex_lock(&d->lock); struct command *c=command(d,id); int rc=NM_INVALID;
    if (c) { rc=(c->state==RECORDING && c->n) ? NM_OK : NM_BAD_STATE; if (!rc) c->state=ENDED; }
    pthread_mutex_unlock(&d->lock); return rc;
}
static void vk_command_free(nm_device *d,struct command *c) {
    if (c->fence) d->DestroyFence(d->device,c->fence,NULL);
    if (c->vk) d->FreeCommandBuffers(d->device,d->pool,1,&c->vk);
    c->fence=VK_NULL_HANDLE; c->vk=VK_NULL_HANDLE;
}
static int vk_submit(nm_device *d,struct command *c) {
    VkCommandBufferAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=d->pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
    if (d->AllocateCommandBuffers(d->device,&ai,&c->vk)!=VK_SUCCESS) return NM_BACKEND_FAILED;
    VkCommandBufferBeginInfo bi={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    if (d->BeginCommandBuffer(c->vk,&bi)!=VK_SUCCESS) goto fail;
    for (unsigned i=0;i<c->n;i++) {
        struct operation *op=&c->op[i]; struct resource *dst=resource(d,op->dst);
        if (op->copy) { VkBufferCopy copy={.size=op->size}; d->CmdCopyBuffer(c->vk,resource(d,op->src)->buffer,dst->buffer,1,&copy); }
        else d->CmdFillBuffer(c->vk,dst->buffer,op->offset,op->size,op->value);
        VkMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT|VK_ACCESS_TRANSFER_WRITE_BIT|VK_ACCESS_HOST_READ_BIT};
        d->CmdPipelineBarrier(c->vk,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_HOST_BIT,0,1,&barrier,0,NULL,0,NULL);
    }
    if (d->EndCommandBuffer(c->vk)!=VK_SUCCESS) goto fail;
    VkFenceCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
    if (d->CreateFence(d->device,&fi,NULL,&c->fence)!=VK_SUCCESS) goto fail;
    VkSubmitInfo si={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&c->vk};
    if (d->QueueSubmit(d->queue,1,&si,c->fence)==VK_SUCCESS) return NM_OK;
fail: vk_command_free(d,c); return NM_BACKEND_FAILED;
}
int nm_command_submit(nm_device *d,nm_handle id) {
    if (!d) return NM_INVALID;
    pthread_mutex_lock(&d->lock); struct command *c=command(d,id); int rc=NM_INVALID;
    if (!c) goto end;
    if (c->state!=ENDED) { rc=NM_BAD_STATE; goto end; }
    /* This research interface deliberately exposes a single in-flight slot.
     * In particular the CPU model never executes submissions out of queue order. */
    for (unsigned i=0;i<NC;i++) if (d->commands[i].state==PENDING && d->commands[i].id) { rc=NM_BUSY; goto end; }
    for (unsigned i=0;i<c->n;i++) if (nvmtl_up_before_consume(&resource(d,c->op[i].dst)->upload) || (c->op[i].copy && nvmtl_up_before_consume(&resource(d,c->op[i].src)->upload))) { rc=NM_BUSY; goto end; }
    if (fault(d,NM_FAULT_SUBMIT)) { rc=NM_BACKEND_FAILED; goto end; }
    rc=d->kind==NM_LAVAPIPE ? vk_submit(d,c) : NM_OK;
    if (!rc) { c->state=PENDING; for (unsigned i=0;i<c->n;i++) nvmtl_up_set(&resource(d,c->op[i].dst)->upload,id); }
end: pthread_mutex_unlock(&d->lock); return rc;
}
int nm_command_wait(nm_device *d,nm_handle id,uint64_t timeout_ns) {
    if (!d) return NM_INVALID;
    pthread_mutex_lock(&d->lock); struct command *c=command(d,id); int rc=NM_INVALID;
    if (!c) goto end;
    if (c->state==DONE) { rc=NM_OK; goto end; }
    if (c->state!=PENDING) { rc=NM_BAD_STATE; goto end; }
    if (!timeout_ns || fault(d,NM_FAULT_WAIT)) { rc=NM_SYNC_FAILED; goto end; }
    if (d->kind==NM_LAVAPIPE) { if (d->WaitForFences(d->device,1,&c->fence,VK_TRUE,timeout_ns)!=VK_SUCCESS) { rc=NM_SYNC_FAILED; goto end; } }
    else for (unsigned i=0;i<c->n;i++) {
        struct operation *op=&c->op[i]; struct resource *dst=resource(d,op->dst);
        if (op->copy) memcpy(dst->map,resource(d,op->src)->map,op->size);
        else for (size_t j=0;j<op->size;j+=4) memcpy((char *)dst->map+op->offset+j,&op->value,4);
    }
    for (unsigned i=0;i<c->n;i++) nvmtl_up_clear(&resource(d,c->op[i].dst)->upload);
    c->state=DONE; rc=NM_OK;
end: pthread_mutex_unlock(&d->lock); return rc;
}
int nm_command_destroy(nm_device *d,nm_handle id) {
    if (!d) return NM_INVALID;
    pthread_mutex_lock(&d->lock); struct command *c=command(d,id); int rc=NM_INVALID;
    if (c) {
        if (c->state==PENDING) { rc=NM_BUSY; goto end; }
        for (unsigned i=0;i<c->n;i++) { resource(d,c->op[i].dst)->refs--; if (c->op[i].copy) resource(d,c->op[i].src)->refs--; }
        if (d->kind==NM_LAVAPIPE) vk_command_free(d,c);
        memset(c,0,sizeof *c); rc=NM_OK;
    }
end: pthread_mutex_unlock(&d->lock); return rc;
}
const char *nm_result_string(int r) {
    static const char *names[]={"OK","INVALID","UNSUPPORTED","NOMEM","BUSY","SYNC_FAILED","BAD_STATE","BACKEND_FAILED"};
    return r>=0 && r<=NM_BACKEND_FAILED ? names[r] : "UNKNOWN_ERROR";
}
