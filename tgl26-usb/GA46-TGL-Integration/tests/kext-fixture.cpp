// Offline linker fixture. These are real KPI references, never mock definitions.
#include <mach/mach_types.h>
#include <mach/kmod.h>
#include <IOKit/IOLib.h>

static void *allocation;
static volatile unsigned lifecycle;
struct Lifecycle {
    Lifecycle() { lifecycle = 1; }
    ~Lifecycle() { lifecycle = 0; }
};
static Lifecycle instance;

extern "C" kern_return_t fixture_start(kmod_info_t *, void *) {
    if (lifecycle != 1 || allocation) return KERN_FAILURE;
    allocation = IOMalloc(64);
    return allocation ? KERN_SUCCESS : KERN_RESOURCE_SHORTAGE;
}
extern "C" kern_return_t fixture_stop(kmod_info_t *, void *) {
    if (allocation) { IOFree(allocation, 64); allocation = nullptr; }
    return KERN_SUCCESS;
}
extern "C" {
KMOD_EXPLICIT_DECL(org.example.GA46Fixture, "1.0.0", fixture_start, fixture_stop)
}
