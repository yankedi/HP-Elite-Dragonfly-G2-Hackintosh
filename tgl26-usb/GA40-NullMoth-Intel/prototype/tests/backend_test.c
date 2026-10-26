#include "nm_backend.h"
#include "metal_like.h"
#include "nvmtl_sample_positions.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expr) do { if (!(expr)) { fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#expr); exit(1); } } while (0)
static void *worker(void *ptr) {
    nm_device *d=ptr;
    for (unsigned i=0;i<64;i++) {
        nm_handle b=0; unsigned value=i,readback=0;
        CHECK(nm_buffer_create(d,64,&b)==NM_OK);
        CHECK(nm_buffer_write(d,b,0,&value,4)==NM_OK);
        CHECK(nm_buffer_read(d,b,0,&readback,4)==NM_OK && readback==value);
        CHECK(nm_resource_destroy(d,b)==NM_OK);
    }
    return NULL;
}
int main(int argc,char **argv) {
    enum nm_kind kind=argc>1 && !strcmp(argv[1],"lavapipe") ? NM_LAVAPIPE : NM_CPU_MODEL;
    nm_device *d=(void *)1;
    CHECK(nm_open(NM_INTEL_HARDWARE,0,&d)==NM_UNSUPPORTED && d==NULL);
    CHECK(nm_open(kind,NM_CAP_IOSURFACE,&d)==NM_UNSUPPORTED && d==NULL);
    CHECK(nm_open(kind,NM_CAP_NVIDIA_SASS,&d)==NM_UNSUPPORTED && d==NULL);
    CHECK(nm_open(kind,NM_CAP_METAL_DEVICE,&d)==NM_UNSUPPORTED && d==NULL);
    CHECK(nm_open(kind,NM_CAP_BUFFER|NM_CAP_IMAGE|NM_CAP_TRANSFER,&d)==NM_OK);
    nm_info info; CHECK(nm_info_get(d,&info)==NM_OK && !info.real_gpu && info.kind==kind);
    CHECK(!(info.capabilities&(NM_CAP_INTEL_SUBMIT|NM_CAP_IOSURFACE|NM_CAP_NVIDIA_SASS)));
    nvmtl_sample_pattern samples;
    CHECK(nvmtl_sample_default(4,&samples)==0 && nvmtl_sample_pattern_valid(&samples));
    CHECK(samples.position[0].x==0.375f && samples.position[0].y==0.125f);
    samples.position[0].x=NAN; CHECK(!nvmtl_sample_pattern_valid(&samples));
    nm_handle src=0,dst=0,img=0,c=0;
    CHECK(nm_buffer_create(d,64,&src)==NM_OK && nm_buffer_create(d,64,&dst)==NM_OK);
    CHECK(nm_image_create(d,8,8,&img)==NM_OK);
    CHECK(nm_resource_destroy(d,img)==NM_OK && nm_resource_destroy(d,img)==NM_INVALID);
    CHECK(nm_image_create(d,0,8,&img)==NM_INVALID);
    CHECK(nm_close(d)==NM_BUSY);
    uint32_t data[16],out[16]; for (unsigned i=0;i<16;i++) data[i]=i*17+3;
    CHECK(nm_buffer_write(d,src,0,data,sizeof data)==NM_OK);
    CHECK(nm_buffer_write(d,src,SIZE_MAX,data,4)==NM_INVALID);
    CHECK(nm_buffer_read(d,src,60,out,8)==NM_INVALID);
    CHECK(nm_fault_once(d,NM_FAULT_ALLOCATION)==NM_OK);
    CHECK(nm_buffer_create(d,64,&img)==NM_NOMEM && img==0);
    CHECK(nm_fault_once(d,NM_FAULT_SUBMIT)==NM_OK);
    CHECK(metal_like_copy_and_patch(d,src,dst,64,0x11223344,&c)==NM_BACKEND_FAILED && c==0);
    CHECK(nm_buffer_write(d,src,0,data,sizeof data)==NM_OK); /* references rolled back */
    CHECK(metal_like_copy_and_patch(d,src,dst,64,0x11223344,&c)==NM_OK);
    CHECK(nm_resource_destroy(d,src)==NM_BUSY && nm_resource_destroy(d,dst)==NM_BUSY);
    CHECK(nm_buffer_read(d,dst,0,out,sizeof out)==NM_BUSY);
    CHECK(nm_command_submit(d,c)==NM_BAD_STATE);
    CHECK(nm_command_fill(d,c,dst,0,4,5)==NM_BAD_STATE);
    CHECK(nm_fault_once(d,NM_FAULT_WAIT)==NM_OK);
    CHECK(nm_command_wait(d,c,10000000000ull)==NM_SYNC_FAILED);
    CHECK(nm_command_destroy(d,c)==NM_BUSY && nm_resource_destroy(d,dst)==NM_BUSY);
    CHECK(nm_command_wait(d,c,10000000000ull)==NM_OK);
    CHECK(nm_command_destroy(d,c)==NM_OK && nm_command_destroy(d,c)==NM_INVALID);
    CHECK(nm_buffer_read(d,dst,0,out,sizeof out)==NM_OK);
    data[1]=0x11223344; CHECK(!memcmp(data,out,sizeof data));
    CHECK(nm_resource_destroy(d,src)==NM_OK && nm_resource_destroy(d,dst)==NM_OK);
    CHECK(nm_buffer_read(d,dst,0,out,4)==NM_INVALID); /* stale handle never reused */
    CHECK(nm_buffer_create(d,64,&dst)==NM_OK);
    CHECK(nm_command_create(d,&c)==NM_OK);
    CHECK(nm_command_fill(d,c,dst,1,4,1)==NM_INVALID);
    CHECK(nm_command_fill(d,c,dst,0,4,1)==NM_OK);
    CHECK(nm_command_end(d,c)==NM_OK && nm_command_submit(d,c)==NM_OK);
    nm_handle second=0; CHECK(nm_command_create(d,&second)==NM_OK);
    CHECK(nm_command_fill(d,second,dst,0,4,2)==NM_OK && nm_command_end(d,second)==NM_OK);
    CHECK(nm_command_submit(d,second)==NM_BUSY);
    CHECK(nm_command_wait(d,c,10000000000ull)==NM_OK && nm_command_destroy(d,c)==NM_OK);
    CHECK(nm_command_submit(d,second)==NM_OK && nm_command_wait(d,second,10000000000ull)==NM_OK);
    CHECK(nm_command_destroy(d,second)==NM_OK && nm_buffer_read(d,dst,0,out,4)==NM_OK && out[0]==2);
    CHECK(nm_resource_destroy(d,dst)==NM_OK);
    pthread_t threads[4];
    for (unsigned i=0;i<4;i++) CHECK(!pthread_create(&threads[i],NULL,worker,d));
    for (unsigned i=0;i<4;i++) CHECK(!pthread_join(threads[i],NULL));
    printf("{\"status\":\"PASS\",\"backend\":\"%s\",\"device\":\"%s\",\"real_gpu\":false,\"software_vulkan\":%s,\"metal_abi\":false,\"threaded_lifecycles\":256,\"readback_verified\":true,\"hardware_approval\":\"NO\"}\n",kind==NM_LAVAPIPE ? "LAVAPIPE" : "CPU_MODEL",info.name,kind==NM_LAVAPIPE ? "true" : "false");
    CHECK(nm_close(d)==NM_OK); return 0;
}
