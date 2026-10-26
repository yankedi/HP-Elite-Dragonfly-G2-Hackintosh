/* SPDX-License-Identifier: MIT
 * Real IOConnect client for the existing GX42UserClient and XNU GEM backend.
 * Compile/link evidence is not target runtime or fd/pager validation. */
#include "drm-darwin-native.h"
#include "gx_user_abi.h"
#include <IOKit/IOKitLib.h>
#include <errno.h>
#include <stddef.h>
#include <mach/mach.h>

_Static_assert(sizeof(struct gx_offset_map) == 40, "map-offset LP64 ABI");
_Static_assert(offsetof(struct gx_offset_map, writable) == 32, "map permissions ABI");
_Static_assert(sizeof(struct gx_cpu_unmap) == 16, "unmap LP64 ABI");
_Static_assert(sizeof(io_connect_t) == sizeof(uint32_t), "connection port ABI");

static int transport_errno(kern_return_t ret)
{
    switch (ret) {
    case KERN_SUCCESS: return 0;
    case kIOReturnNoDevice: case kIOReturnNotAttached: return -ENODEV;
    case kIOReturnNotPrivileged: return -EACCES;
    case kIOReturnNotPermitted: return -EPERM;
    case kIOReturnBadArgument: return -EINVAL;
    case kIOReturnNoMemory: return -ENOMEM;
    case kIOReturnBusy: return -EBUSY;
    default: return -EIO;
    }
}

int drmDarwinNativeOpen(uint32_t *connection)
{
    if (!connection) return -EINVAL;
    CFMutableDictionaryRef match = IOServiceMatching("GX42Service");
    if (!match) return -ENOMEM;
    io_service_t service = IOServiceGetMatchingService(kIOMainPortDefault, match);
    if (!service) return -ENODEV;
    io_connect_t port = IO_OBJECT_NULL;
    kern_return_t ret = IOServiceOpen(service, mach_task_self(), 0, &port);
    (void)IOObjectRelease(service);
    if (ret != KERN_SUCCESS) return transport_errno(ret);
    *connection = port;
    return 0;
}

int drmDarwinNativeIoctl(uint32_t connection, uint32_t request, void *argument)
{
    if (connection == IO_OBJECT_NULL) return -EBADF;
    const uint64_t input[2] = { request, (uintptr_t)argument };
    uint64_t error = UINT64_MAX;
    uint32_t count = 1;
    kern_return_t ret = IOConnectCallScalarMethod(connection, GX_IOCONNECT_IOCTL_SELECTOR,
                                                 input, 2, &error, &count);
    if (ret != KERN_SUCCESS) return transport_errno(ret);
    if (count != 1 || error > 4095) return -EPROTO;
    return -(int)error;
}

int drmDarwinNativeMapOffset(uint32_t connection, uint64_t cookie, uint64_t length,
                            int writable, uint64_t *address, uint64_t *map_id)
{
    if (!address || !map_id || (writable != 0 && writable != 1)) return -EINVAL;
    struct gx_offset_map arg = { .offset = cookie, .length = length, .writable = writable };
    int ret = drmDarwinNativeIoctl(connection, GX_OFFSET_MAP, &arg);
    if (ret) return ret;
    *address = arg.address;
    *map_id = arg.map_id;
    return 0;
}

int drmDarwinNativeUnmap(uint32_t connection, uint64_t map_id)
{
    struct gx_cpu_unmap arg = { .map_id = map_id };
    return drmDarwinNativeIoctl(connection, GX_CPU_UNMAP, &arg);
}

int drmDarwinNativeClose(uint32_t connection)
{
    if (connection == IO_OBJECT_NULL) return -EBADF;
    return transport_errno(IOServiceClose(connection));
}
