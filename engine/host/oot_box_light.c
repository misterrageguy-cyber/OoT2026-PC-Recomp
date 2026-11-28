/* (hookshot) A recycled box light starts with the constructor's parameters (Ganon's Tower: dark squares on the floor).
   Box lights come from a pool; a reused one kept the previous owner's rotation, half-extents, blend vectors and dimming
   factor when the new owner has no parameter resource to replace them (a corner box with a ceiling dimmer's 17,4,17 and
   factor 0.1 darkened a 34x8x34 region with a sharp edge). nx2/oot_patches.py puts the call right after the box manager's
   acquire callback (f_831eaa90, 0x831eab10), while the pool and light locks are held and before the new owner loads its
   own parameters. Box lights only (their vtable); identity, ownership, position and the cached matrices are kept, and the
   transform's dirty bit makes the game rebuild the matrices. HOS_OOT_BOX_LIGHT_RESET=0: as before. */
#include "hos.h"
#include <stdlib.h>

#define OOT_BOX_LIGHT_VTABLE 0x84baa5f8ULL   /* (the supported build's) */

void hos_oot_box_light_acquired(Ctx *c) {
    static int on = -1;
    if (on < 0) on = !getenv("HOS_OOT_BOX_LIGHT_RESET") || atoi(getenv("HOS_OOT_BOX_LIGHT_RESET")) != 0;
    const uint64_t box = c->x[20];
    if (!on || !box || recomp_load64(c, box) != OOT_BOX_LIGHT_VTABLE) return;
    for (unsigned off = 580; off < 632; off += 4) recomp_store32(c, box + off, 0);
    for (unsigned off = 592; off <= 600; off += 4) recomp_store32(c, box + off, 0x3f800000u);
    recomp_store32(c, box + 628, 0x3f800000u);
    recomp_store8(c, box + 632, recomp_load8(c, box + 632) | 1);
}
