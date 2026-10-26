// GA46 native TGL boundary. No RPL memory/display/compression workarounds.
// Unverified private Metal conversions cannot be enabled by an environment var.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <syslog.h>
#include "../metal/runtime-preflight.h"

static pthread_once_t install_once=PTHREAD_ONCE_INIT;
static int device_gate_installed;

__attribute__((visibility("default"))) const char *XEAdapterABIStatus(void) {
    return "ABI_UNVERIFIED: no approved 25G83 field/ownership/logicOp schema";
}

// Objective-C init has a known nil failure contract. No reference to the
// original IMP is needed: an unverified device is never exposed to a caller.
static id reject_device(id self, SEL cmd, unsigned int port) {
    (void)cmd;(void)port;
    syslog(LOG_ERR,"xedrv-ga46: refusing donor device: %s",XEAdapterABIStatus());
    [self release];
    return nil;
}

static void install_gate(void) {
    Class c=objc_getClass("MTLIGAccelDevice");
    SEL s=sel_registerName("initWithAcceleratorPort:");
    Method m=c ? class_getInstanceMethod(c,s) : NULL;
    if (!m || method_getNumberOfArguments(m)!=3) return;
    // Guard only the actual donor implementation. Never change an inherited
    // framework method in place or change another vendor's global class.
    Dl_info di={0};
    if (!dladdr((void *)method_getImplementation(m),&di) || !di.dli_fname ||
        !strstr(di.dli_fname,"AppleIntelTGLGraphicsMTLDriver")) return;
    char *ret=method_copyReturnType(m),*arg=method_copyArgumentType(m,2);
    int signature_ok=ret && !strcmp(ret,"@") && arg && !strcmp(arg,"I");
    free(ret);free(arg);
    if (!signature_ok) return;
    unsigned n=0;Method *own=class_copyMethodList(c,&n);int declared=0;
    for(unsigned i=0;i<n;i++) if(method_getName(own[i])==s) declared=1;
    free(own);
    if (declared) method_setImplementation(m,(IMP)reject_device);
    else if (!class_addMethod(c,s,(IMP)reject_device,method_getTypeEncoding(m))) return;
    device_gate_installed=1;
}

__attribute__((constructor)) static void xe_initialize(void) {
    pthread_once(&install_once,install_gate);
    syslog(LOG_ERR,"xedrv-ga46: %s",XEAdapterABIStatus());
    // No deferred polling/swizzle or silent pass-through if image/class init
    // order differs. Loading this quarantine build into a host is unsupported.
    if (!device_gate_installed) abort();
}
