/* SPDX-License-Identifier: MIT */
#include <mach/kmod.h>
#include <libkern/OSAtomic.h>

volatile SInt32 gx42_live_services;
static kern_return_t module_start(kmod_info_t *info, void *data) {
    (void)info; (void)data;
    return KERN_SUCCESS;
}
static kern_return_t module_stop(kmod_info_t *info, void *data) {
    (void)info; (void)data;
    /* Live/quarantined native clients retain their provider; refuse unload.
     * This does not claim teardown has succeeded when unmap returned failure. */
    return OSAddAtomic(0, &gx42_live_services) ? KERN_FAILURE : KERN_SUCCESS;
}
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL(local.ga42.IntelGEMDiagnostics, "0.0.1", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = module_start;
__private_extern__ kmod_stop_func_t *_antimain = module_stop;
