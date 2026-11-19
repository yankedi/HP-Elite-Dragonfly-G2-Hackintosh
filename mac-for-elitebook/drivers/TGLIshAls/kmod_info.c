// SPDX-License-Identifier: BSD-3-Clause
#include <mach/mach_types.h>

extern kern_return_t TGLIshAls_start(kmod_info_t *ki, void *data);
extern kern_return_t TGLIshAls_stop(kmod_info_t *ki, void *data);

__attribute__((visibility("default")))
KMOD_EXPLICIT_DECL(com.labrouss.TGLIshAls, "0.5.0", TGLIshAls_start, TGLIshAls_stop)

__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t  *_antimain = 0;
__private_extern__ int _kext_apple_cc = __APPLE_CC__;
