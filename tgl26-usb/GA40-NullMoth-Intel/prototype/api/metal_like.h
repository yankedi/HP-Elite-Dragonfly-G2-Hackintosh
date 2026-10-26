/* Minimal C Metal-like call facade for offline tests; not MTLDevice ABI. */
#ifndef GA40_METAL_LIKE_H
#define GA40_METAL_LIKE_H
#include "nm_backend.h"
int metal_like_copy_and_patch(nm_device *device, nm_handle source, nm_handle destination,
                             size_t bytes, uint32_t patch, nm_handle *command);
#endif
