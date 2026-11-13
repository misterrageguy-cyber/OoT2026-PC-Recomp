"""Classic counters: mask the pickup layout, preserve inventory events, and read
the wallet only while a live player is updating. Addresses are image-absolute
(0x80000000 base, main at 0x80020000). Fail closed on another build/layout."""

BUILD = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"
PACIBSP = 0xd503237f
HOOKS = (
    (0x80a87e50, PACIBSP, "{ extern void ocr_counters_pickup(Ctx *c); ocr_counters_pickup(c); }"),
    (0x802f8ac0, 0xbd407401, "{ extern void ocr_counters_alpha(Ctx *c); ocr_counters_alpha(c); }"),
    # (once a frame: the wallet for the bottom left corner, host/ocr_counters.c ocr_counters_frame)
    (0x831f3200, 0x39788008, "{ extern void ocr_counters_frame(Ctx *c); ocr_counters_frame(c); }"),
)
CHECKS = ((0x84c0af28, 0x80a87e50), (0x84c0af2c, 0),
          (0x80229660, 0xf9402000), (0x8045b1f0, 0xf9408008))


def install(lifter, img, build_id):
    if (build_id != BUILD or any(img.word(pc) != word for pc, word, _ in HOOKS)
            or any(img.word(pc) != word for pc, word in CHECKS)):
        print("ocarina reborn classic counters: other game build, left out")
        return 0
    for pc, _, text in HOOKS:
        text += "   /* (nx2/ocr_counters.py) */"
        lifter.after[pc] = lifter.after[pc] + "\n" + text if pc in lifter.after else text
    print("ocarina reborn classic counters: hooked")
    return 1
