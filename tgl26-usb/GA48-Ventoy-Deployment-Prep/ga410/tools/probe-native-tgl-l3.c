// Diagnostic only: undo the upstream RPL-specific L3 immediate in this process.
// Does not modify any file or another process. Exact instruction guarded.
#include <mach-o/dyld.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static void image_added(const struct mach_header *header, intptr_t slide) {
    (void)slide;
    const char *name = NULL;
    for (uint32_t i=0; i<_dyld_image_count(); ++i)
        if (_dyld_get_image_header(i)==header) { name=_dyld_get_image_name(i); break; }
    if (!name || !strstr(name,"/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver")) return;
    uint8_t *p=(uint8_t*)header+0x65f0c;
    const uint8_t expected[]={0xc7,0x41,0x14,0x20,0x00,0x00,0xd0};
    if (memcmp(p,expected,sizeof expected)) { fprintf(stderr,"L3_PROBE instruction mismatch\n"); _exit(90); }
    mach_vm_address_t page=(mach_vm_address_t)p & ~((mach_vm_address_t)vm_page_size-1);
    kern_return_t kr=mach_vm_protect(mach_task_self(),page,vm_page_size,FALSE,VM_PROT_READ|VM_PROT_WRITE|VM_PROT_COPY);
    if (kr) { fprintf(stderr,"L3_PROBE protect failed %x\n",kr); _exit(91); }
    p[6]=0x88;
    kr=mach_vm_protect(mach_task_self(),page,vm_page_size,FALSE,VM_PROT_READ|VM_PROT_EXECUTE);
    if (kr) _exit(92);
    fprintf(stderr,"L3_PROBE process-local immediate 0xd0000020 -> stock TGL 0x88000020\n");
}

__attribute__((constructor)) static void install(void) {
    _dyld_register_func_for_add_image(image_added);
}
