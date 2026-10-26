#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define __gen_address_type uint64_t
#define __gen_user_data void
static uint64_t __gen_combine_address(void *data, void *loc,
                                     uint64_t address, uint32_t delta)
{
   (void)data;
   (void)loc;
   return address + delta;
}
#include "gen12-pack-proof.h"

static void dump(const char *name, const uint32_t *dw, unsigned n)
{
   printf("%s", name);
   for (unsigned i = 0; i < n; i++)
      printf(" %08x", dw[i]);
   putchar('\n');
}

int main(void)
{
   /* Concrete local demonstrator: Mesa TGL internal MOCS=2<<1, not a
    * claim about the MOCS register programming of the captured Apple context.
    * ISL null branch sets SurfaceType and copies db.Depth (zero here).
    */
   struct GFX12_3DSTATE_STENCIL_BUFFER sb = {
      GFX12_3DSTATE_STENCIL_BUFFER_header,
      .SurfaceType = SURFTYPE_NULL,
      .MOCS = 4,
      .Depth = 0,
   };
   uint32_t stencil[8];
   GFX12_3DSTATE_STENCIL_BUFFER_pack(NULL, stencil, &sb);
   const uint32_t expected[] = {
      0x78060006, 0xe0000000, 0, 0, 0, 4, 0, 0,
   };
   assert(sizeof(stencil) == sizeof(expected));
   assert(memcmp(stencil, expected, sizeof(expected)) == 0);
   dump("null-stencil-mocs4-depth0", stencil, 8);

   struct GFX12_3DPRIMITIVE a = {
      GFX12_3DPRIMITIVE_header,
      .ExtendedParametersPresent = true,
      .VertexCountPerInstance = 6,
      .InstanceCount = 1,
   };
   a.DWordLength = 8;
   uint32_t draw_a[10] = {0};
   GFX12_3DPRIMITIVE_pack(NULL, draw_a, &a);
   assert(draw_a[0] == 0x7b000808);
   assert(draw_a[2] == 6 && draw_a[4] == 1);
   assert(draw_a[7] == 0 && draw_a[8] == 0 && draw_a[9] == 0);
   dump("draw-A", draw_a, 10);

   struct GFX12_3DPRIMITIVE b = a;
   b.DWordLength = 5;
   b.ExtendedParametersPresent = false;
   /* The generated function writes all 10 DW even when length says 7.
    * Keep a 10-DW buffer; final three zero DW are independently MI_NOOP.
    */
   uint32_t draw_b[10] = {0};
   GFX12_3DPRIMITIVE_pack(NULL, draw_b, &b);
   assert(draw_b[0] == 0x7b000005);
   assert(memcmp(draw_a + 1, draw_b + 1, 9 * sizeof(uint32_t)) == 0);
   dump("draw-B-with-three-NOOP", draw_b, 10);
   puts("PASS: upstream Mesa generated pack bytes, not GPU execution");
   return 0;
}
