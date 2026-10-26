/* GA4.5: pure-C 25G83 Metal descriptor ABI constants and checks.
 *
 * These values are the expected Tahoe 25G83 layout used by libxedrv.  They
 * are NOT a claim that the target has been probed at runtime; the probe must
 * supply the actual values and the wrapper must reject a mismatch.
 */
#ifndef XE_ABI_H
#define XE_ABI_H
#include <stddef.h>
#include <stdint.h>

#define XE_RPD_SIZE                 0x338u
#define XE_RPD_PRIVATE_OFFSET       0x30
#define XE_RPD_PRIVATE_SIZE         0x2e0u
#define XE_ATT_SIZE                 0x10u
#define XE_ATT_PRIVATE_OFFSET       0x8
#define XE_RASTER_SAMPLE_COUNT_OFF  0xb8u
#define XE_VERTEX_DESCRIPTOR_OFF    0x110u
#define XE_LOGICOP_OLD_BIT          27u
#define XE_LOGICOP_NEW_BIT          32u

static inline int xe_abi_layout_ok(size_t rpd_size, ptrdiff_t rpd_priv,
                                   size_t att_size, ptrdiff_t att_priv) {
  if (rpd_size != XE_RPD_SIZE || rpd_priv != XE_RPD_PRIVATE_OFFSET) return 0;
  if (att_size != XE_ATT_SIZE || att_priv != XE_ATT_PRIVATE_OFFSET) return 0;
  if (rpd_priv < 0 || (size_t)rpd_priv > rpd_size) return 0;
  if (rpd_size - (size_t)rpd_priv < XE_RPD_PRIVATE_SIZE) return 0;
  return 1;
}

static inline int xe_abi_logicop_ok(unsigned old_bit, unsigned new_bit) {
  return old_bit == XE_LOGICOP_OLD_BIT && new_bit == XE_LOGICOP_NEW_BIT;
}

static inline int xe_abi_sample_offsets_ok(size_t private_size) {
  return private_size >= XE_RASTER_SAMPLE_COUNT_OFF + sizeof(uint64_t) &&
         private_size >= XE_VERTEX_DESCRIPTOR_OFF + sizeof(void *);
}
#endif
