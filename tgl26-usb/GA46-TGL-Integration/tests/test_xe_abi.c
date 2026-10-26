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
  assert(xe_abi_storage_ok(0x338,0x30,0x2e0,8,0x2e0));
  assert(!xe_abi_storage_ok(0x338,-1,0x2e0,8,0x2e0));
  assert(!xe_abi_storage_ok(0x338,0x31,0x2e0,8,0x2e0));
  assert(!xe_abi_storage_ok(0x338,0x30,SIZE_MAX,8,0x2e0));
  assert(!xe_abi_storage_ok(0x338,0x30,0x2df,8,0x2e0));
  assert(!xe_abi_storage_ok(0x338,0x30,0x2e0,0,0x2e0));
  assert(!xe_abi_storage_ok(0x338,0x30,0x2e0,3,0x2e0));
  assert(!xe_abi_sample_offsets_ok(XE_VERTEX_DESCRIPTOR_OFF+sizeof(void*)-1));
  return 0;
}
