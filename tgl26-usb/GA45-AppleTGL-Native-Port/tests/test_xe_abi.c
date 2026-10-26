#include <assert.h>
#include <stddef.h>
#include "xe_abi.h"

int main(void) {
  assert(xe_abi_layout_ok(0x338, 0x30, 0x10, 0x8));
  assert(!xe_abi_layout_ok(0x337, 0x30, 0x10, 0x8));
  assert(!xe_abi_layout_ok(0x338, 0x28, 0x10, 0x8));
  assert(!xe_abi_layout_ok(0x338, 0x30, 0x18, 0x8));
  assert(!xe_abi_layout_ok(0x338, 0x30, 0x10, 0x10));
  assert(xe_abi_logicop_ok(27, 32));
  assert(!xe_abi_logicop_ok(27, 27));
  assert(xe_abi_sample_offsets_ok(0x2e0));
  return 0;
}
