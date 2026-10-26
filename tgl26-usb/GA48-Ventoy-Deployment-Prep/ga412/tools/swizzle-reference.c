// CPU-only adapter to an unmodified, separately archived Intel source file.
// The Intel file retains its own license; it is not copied into this adapter.
#include <stddef.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>
#include GA412_INTEL_SWIZZLE_SOURCE

int ga412_reference_offset(const uint32_t masks[3], int pitch, int x, int y) {
    SWIZZLE_DESCRIPTOR descriptor = {{masks[0], masks[1], masks[2]}};
    return SwizzleOffset(&descriptor, pitch, x, y, 0);
}

void ga412_reference_read(const uint32_t masks[3], int pitch, const void *tiled,
                          void *linear, int row, int width, int height) {
    SWIZZLE_DESCRIPTOR descriptor = {{masks[0], masks[1], masks[2]}};
    CPU_SWIZZLE_BLT_SURFACE source = {0}, destination = {0};
    source.pBase = (void *)tiled;
    source.Pitch = pitch;
    source.Height = height;
    source.pSwizzle = &descriptor;
    destination.pBase = linear;
    destination.Pitch = row;
    destination.Height = height;
    CpuSwizzleBlt(&destination, &source, width, height);
}
