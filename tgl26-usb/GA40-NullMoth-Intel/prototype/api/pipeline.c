/* Cross-component transport takes CPU bytes, never a DRM/GPU address. */
#include "metal_like.h"
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv) {
    unsigned char input[64]; uint32_t output[16];
    if (fread(input,1,sizeof input,stdin)!=sizeof input || fgetc(stdin)!=EOF) return 2;
    nm_device *d=NULL; nm_handle src=0,dst=0,c=0;
    enum nm_kind kind=argc==2 && !strcmp(argv[1],"lavapipe") ? NM_LAVAPIPE : NM_CPU_MODEL;
    if (nm_open(kind,NM_CAP_TRANSFER,&d)) return 3;
    int rc=nm_buffer_create(d,64,&src);
    if (!rc) rc=nm_buffer_create(d,64,&dst);
    if (!rc) rc=nm_buffer_write(d,src,0,input,64);
    if (!rc) rc=metal_like_copy_and_patch(d,src,dst,64,0x11223344,&c);
    if (!rc) rc=nm_command_wait(d,c,10000000000ull);
    if (c) { int clean=nm_command_destroy(d,c); if (!rc) rc=clean; }
    if (!rc) rc=nm_buffer_read(d,dst,0,output,64);
    nm_info info; nm_info_get(d,&info);
    if (!rc) {
        printf("{\"backend\":\"%s\",\"real_gpu\":false,\"words\":[",kind==NM_LAVAPIPE ? "LAVAPIPE" : "CPU_MODEL");
        for (unsigned i=0;i<16;i++) printf("%s%u",i ? "," : "",output[i]);
        printf("]}\n");
    }
    if (src) { int clean=nm_resource_destroy(d,src); if (!rc) rc=clean; }
    if (dst) { int clean=nm_resource_destroy(d,dst); if (!rc) rc=clean; }
    int clean=nm_close(d); if (!rc) rc=clean;
    if (rc) fprintf(stderr,"pipeline failed: %s\n",nm_result_string(rc));
    return rc ? 4 : 0;
}
