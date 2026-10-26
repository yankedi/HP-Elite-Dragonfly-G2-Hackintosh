/* SPDX-License-Identifier: MIT */
#ifndef GA43_GX_USER_ABI_H
#define GA43_GX_USER_ABI_H
#include <stdint.h>

/* IOConnectCallScalarMethod: input {BSD request, user address}, output errno.
 * No task pointer, CPU test selector, process-global syscall override or fd.
 * All nested addresses are copied by the authenticated per-open kernel client.
 */
#define GX_IOCONNECT_IOCTL_SELECTOR 0u
#define GX_CPU_MAP UINT32_C(0xc02864e0)
#define GX_CPU_UNMAP UINT32_C(0x801064e1)
struct gx_cpu_map {
    uint32_t handle, writable;
    uint64_t offset, length, address, map_id;
};
struct gx_cpu_unmap { uint64_t map_id, reserved; };
/* Standard GEM_MMAP_OFFSET cookie consumed by a private IOUserClient operation.
 * NOT a BSD mmap/pager ABI or GPU-visible mapping. */
#define GX_OFFSET_MAP UINT32_C(0xc02864e2)
struct gx_offset_map {
    uint64_t offset, length, address, map_id;
    uint32_t writable, reserved;
};
#endif
