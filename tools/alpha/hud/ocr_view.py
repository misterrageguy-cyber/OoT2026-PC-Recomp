"""(Ocarina Reborn) the View distance rows: host/ocr_view.c's ocr_view_frame at the head of the game's render setup
(f_831f3200, main+0x31d3200, once a frame). Only on the game build it was found on, and only while that word is there:
otherwise left out, and the rows do nothing."""

BUILD = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"
AT = 0x80020000 + 0x31d3200
EXPECT = 0x39788008   # ldrb w8, [x0, #0xe20]
CALL = "{ extern void ocr_view_frame(Ctx *c); ocr_view_frame(c); }   /* (nx2/ocr_view.py) */"


def install(lifter, img, build_id):
    if build_id != BUILD or img.word(AT) != EXPECT:
        print("ocarina reborn view distance: other game build, left out")
        return 0
    lifter.after[AT] = lifter.after[AT] + "\n" + CALL if AT in lifter.after else CALL
    print("ocarina reborn view distance: hooked")
    return 1
