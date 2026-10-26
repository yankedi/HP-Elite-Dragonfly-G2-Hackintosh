#include "metal_like.h"

int metal_like_copy_and_patch(nm_device *d,nm_handle src,nm_handle dst,
                             size_t n,uint32_t patch,nm_handle *out) {
    if (!out) return NM_INVALID;
    *out=0;
    nm_handle c=0; int rc=nm_command_create(d,&c);
    if (rc) return rc;
    if (!(rc=nm_command_copy(d,c,src,dst,n)) &&
        !(rc=nm_command_fill(d,c,dst,4,4,patch)) &&
        !(rc=nm_command_end(d,c))) rc=nm_command_submit(d,c);
    if (rc) { nm_command_destroy(d,c); return rc; }
    *out=c; return NM_OK;
}
