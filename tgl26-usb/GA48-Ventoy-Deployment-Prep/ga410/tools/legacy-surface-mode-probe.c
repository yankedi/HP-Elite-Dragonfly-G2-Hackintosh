// Bounded IOAF2 control-plane check: open, set legacy surface ID/mode, close.
// No backing store, texture, command buffer, flush, or GPU work is created.
#include <IOKit/IOKitLib.h>
#include <IOKit/graphics/IOAccelSurfaceConnect.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static kern_return_t check_mode(io_service_t service, uint32_t identifier, uint32_t mode) {
    io_connect_t connection = IO_OBJECT_NULL;
    kern_return_t result = IOServiceOpen(service, mach_task_self(), kIOAccelSurfaceClientType, &connection);
    printf("SURFACE_OPEN mode=0x%x result=0x%x\n", mode, result);
    if (result != KERN_SUCCESS) return result;
    uint64_t arguments[] = {identifier, mode};
    result = IOConnectCallScalarMethod(connection, kIOAccelSurfaceSetIDMode, arguments, 2, NULL, NULL);
    printf("SURFACE_SET_ID_MODE id=0x%x mode=0x%x result=0x%x\n", identifier, mode, result);
    kern_return_t close_result = IOServiceClose(connection);
    printf("SURFACE_CLOSE result=0x%x\n", close_result);
    return close_result == KERN_SUCCESS ? result : close_result;
}

int main(int argc, char **argv) {
    int expect_fixed = argc == 2 && strcmp(argv[1], "--expect-fixed") == 0;
    if (argc != 1 && !expect_fixed) return 2;
    alarm(15);
    setbuf(stdout, NULL);
    io_service_t service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("IntelAccelerator"));
    if (!service) return 2;
    uint64_t registry_id = 0;
    kern_return_t result = IORegistryEntryGetRegistryEntryID(service, &registry_id);
    printf("SURFACE_REGISTRY result=0x%x id=%llu\n", result, registry_id);
    if (result != KERN_SUCCESS) { IOObjectRelease(service); return 2; }
    kern_return_t original = check_mode(service, 0x7a410001, 0x224);
    kern_return_t normalized = check_mode(service, 0x7a410002, 0x24);
    IOObjectRelease(service);
    if (expect_fixed && original == kIOReturnSuccess && normalized == kIOReturnSuccess) {
        puts("SURFACE_MODE_R7_BOTH_CALLS_ACCEPTED");
        return 0;
    }
    if (expect_fixed) { puts("SURFACE_MODE_R7_UNEXPECTED_RESULTS"); return 1; }
    if (original == kIOReturnBadArgument && normalized == kIOReturnSuccess) {
        puts("SURFACE_MODE_SOFTWARE_VALIDATION_MISMATCH_CONFIRMED");
        return 0;
    }
    puts("SURFACE_MODE_UNEXPECTED_RESULTS");
    return 1;
}
