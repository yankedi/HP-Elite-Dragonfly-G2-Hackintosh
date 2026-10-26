// Reproduce Xcode's MODULE_NAME / MODULE_START / MODULE_STOP metadata.
// The SDK libkmod.a supplies the real _start/_stop trampolines; XNU owns
// __mod_init_func/__mod_term_func execution on modern x86_64.
#include <mach/mach_types.h>
#include <mach/kmod.h>

extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
extern kern_return_t NootedGreen_kern_start(kmod_info_t *, void *);
extern kern_return_t NootedGreen_kern_stop(kmod_info_t *, void *);
__attribute__((visibility("hidden"))) kmod_start_func_t *_realmain = NootedGreen_kern_start;
__attribute__((visibility("hidden"))) kmod_stop_func_t *_antimain = NootedGreen_kern_stop;
KMOD_EXPLICIT_DECL(com.StezzaPilot.NootedGreen, "1.0.0", _start, _stop)
