/* CPU-only Mesa native command packing proof, NOT_FOR_HARDWARE.
 * No device, memory address, kernel backend, or shader dispatch is involved.
 */
#include <stdint.h>
#include <stdio.h>
#define __gen_address_type uint64_t
#define __gen_user_data void
#define __gen_combine_address(data,location,address,delta) ((uint64_t)(address)+(delta))
#include "gen120_minimal_pack.h"

int main(void) {
    uint32_t words[GFX12_MI_NOOP_length+GFX12_MI_BATCH_BUFFER_END_length];
    struct GFX12_MI_NOOP noop={GFX12_MI_NOOP_header};
    struct GFX12_MI_BATCH_BUFFER_END end={GFX12_MI_BATCH_BUFFER_END_header};
    GFX12_MI_NOOP_pack(NULL,words,&noop);
    GFX12_MI_BATCH_BUFFER_END_pack(NULL,words+GFX12_MI_NOOP_length,&end);
    printf("{\"scope\":\"NOT_FOR_HARDWARE_CPU_PACK_ONLY\",\"gen\":120,\"bytes\":%zu,\"words\":[%u,%u],\"submitted\":false}\n",sizeof words,words[0],words[1]);
    return sizeof words==8 && words[0]==0 && words[1]==0x05000000 ? 0 : 1;
}
