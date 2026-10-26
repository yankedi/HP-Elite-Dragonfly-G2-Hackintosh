/* Execute the ORIGINAL Mesa intel_get_kmd_type with explicit CPU query stubs.
 * This is not an ioctl or ANV physical-device initialization test.
 */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "util/libdrm.h"
#include "intel_kmd.h"
static drmVersion version;
static int present=1,virtio=0,freed=0;
drmVersionPtr drmGetVersion(int fd) { assert(fd==-1); return present ? &version : NULL; }
void drmFreeVersion(drmVersionPtr v) { assert(v==&version); freed++; }
int is_intel_virtio_fd(int fd) { assert(fd==-1); return virtio; }
int main(void) {
    const char *names[]={"nmdrm","GA40_MOCK_ONLY","i915","xe","unknown"};
    const enum intel_kmd_type expected[]={INTEL_KMD_TYPE_INVALID,INTEL_KMD_TYPE_INVALID,INTEL_KMD_TYPE_I915,INTEL_KMD_TYPE_XE,INTEL_KMD_TYPE_INVALID};
    for (unsigned i=0;i<5;i++) { version.name=(char *)names[i]; assert(intel_get_kmd_type(-1)==expected[i]); }
    present=0; assert(intel_get_kmd_type(-1)==INTEL_KMD_TYPE_INVALID && freed==5);
    present=1; virtio=1; version.name="virtio_gpu";
    assert(intel_get_kmd_type(-1)==INTEL_KMD_TYPE_I915 && freed==6);
    puts("{\"status\":\"PASS\",\"cases\":7,\"original_mesa_function\":true,\"dependency_queries\":\"EXPLICIT_CPU_STUBS\",\"nmdrm_rejected\":true,\"ga40_mock_rejected\":true,\"anv_initialized\":false,\"gpu_access\":false}");
    return 0;
}
