"""(Ocarina Reborn, diagnostics) host/ocr_uidiag.c: the UI manager's find-by-name f_8100dde0 (each new name and caller), and
each place in the game's code that names one of the counter layouts by its Murmur3 hash (a mov of the hash), logged when it
runs: which code shows a counter when Link picks something up. Only on the known game build; a site whose word is not the
expected mov is left out. Addresses are the image's (it starts at 0x80000000, main at 0x80020000)."""

BUILD = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"
AT = 0x8100ddec          # mov x29, sp in f_8100dde0 (x0, x1, x30 untouched so far)
EXPECT = 0x910003fd
CALL = "{ extern void ocr_uidiag(Ctx *c); ocr_uidiag(c); }   /* (nx2/ocr_uidiag.py) */"
SITES = (
    (0x804cd250, "SimpleInfo_00"),
    (0x804d42dc, "SimpleInfo_00"),
    (0x806a3d3c, "PlayerStatus_00"),
    (0x808571f8, "PlayerStatus_00"),
    (0x80a97d8c, "PlayerStatus_00"),
    (0x80bcf6dc, "PlayerStatus_00"),
    (0x80bcfb68, "PlayerStatus_00"),
    (0x80bcfbd8, "PlayerStatus_00"),
    (0x80bcfc9c, "PlayerStatus_00"),
    (0x80c31200, "PlayerStatus_00"),
    (0x80e5536c, "PlayerStatus_00"),
    (0x80fac450, "NumDisplay_00"),
    (0x81000408, "NumDisplayMiniGame_00"),
    (0x8100dd98, "NumDisplay_00"),
    (0x82673350, "PlayerStatus_00"),
    (0x826733a8, "PlayerStatus_00"),
    (0x82673758, "PlayerStatus_00"),
    (0x826737e8, "PlayerStatus_00"),
    (0x8278d040, "NumDisplay_00"),
    (0x8278d298, "NumDisplay_00"),
    (0x8278d4bc, "NumDisplayMiniGame_00"),
    (0x8278d658, "NumDisplayMiniGame_00"),
    (0x828825e8, "PlayerStatus_00"),
    (0x8288265c, "PlayerStatus_00"),
    (0x828abec8, "NumDisplay_00"),
    (0x828abf3c, "NumDisplay_00"),
    (0x828c43f8, "PlayerStatus_00"),
    (0x828e1d18, "NumDisplayMiniGame_00"),
    (0x82918ca0, "NumDisplay_00"),
    (0x82919050, "NumDisplay_00"),
    (0x8291940c, "NumDisplayMiniGame_00"),
    (0x8293c208, "NumDisplayMiniGame_00"),
    (0x82942ab8, "PlayerStatus_00"),
    (0x82942c88, "PlayerStatus_00"),
    (0x829430b8, "PlayerStatus_00"),
    (0x82953068, "PlayerStatus_00"),
    (0x82959ce8, "PlayerStatus_00"),
    (0x8321696c, "PlayerStatus_00"),
    (0x832fdf5c, "PlayerStatus_00"),
    (0x83321d48, "NumDisplayMiniGame_00"),
    (0x83321ee8, "NumDisplay_00"),
    (0x833b84e8, "NumDisplay_00"),
    (0x833b8644, "NumDisplay_00"),
    (0x833b88b4, "NumDisplay_00"),
    (0x833b896c, "NumDisplay_00"),
    (0x833b8ce4, "NumDisplay_00"),
    (0x833b95f0, "NumDisplay_00"),
    (0x833b9638, "NumDisplay_00"),
    (0x833b9694, "NumDisplay_00"),
    (0x833ce0a0, "SimpleInfo_00"),
    (0x833ce6d8, "SimpleInfo_00"),
    (0x833d27d4, "PlayerStatus_00"),
    (0x833d27ec, "NumDisplay_00"),
    (0x833d28d0, "PlayerStatus_00"),
    (0x833d2918, "NumDisplay_00"),
    (0x833d2938, "PlayerStatus_00"),
    (0x833d2950, "NumDisplay_00"),
    (0x833d29a4, "NumDisplay_00"),
    (0x8342a654, "SimpleInfo_00"),
)
NAMES = sorted({n for _, n in SITES})
# (calls logged with x0..x2 and the caller: the place after each function's frame setup, the word expected there)
CALLS = (((0x80fac440, 0x910003fd), (0x8340e364, 0x910003fd),
         # (PlayerStatus_00: the functions that run when Link picks something up, at their first instruction (pacibsp))
         (0x80bcfb50, 0xd503237f), (0x80bcf7e0, 0xd503237f), (0x80bcf6c0, 0xd503237f), (0x808571e0, 0xd503237f),
         (0x806a3d20, 0xd503237f), (0x80a97d70, 0xd503237f), (0x80e55350, 0xd503237f), (0x80857240, 0xd503237f))
         # (UIPlayerStatus3DScreen, the count over Link, and its neighbours' code 0x83415000..0x83418d40: every function start)
         + tuple((a, 0xd503237f) for a in (
    0x83415020, 0x83415050, 0x83415290, 0x83415420, 0x834154d0, 0x834155c0, 0x83415a2c, 0x83415a80, 0x83415ac0, 0x83415b00,
    0x83415ba0, 0x83415bd0, 0x83415d20, 0x83416b30, 0x83416cec, 0x83416d40, 0x83416d80, 0x83416dc0, 0x83416e00, 0x83416e40,
    0x83416e70, 0x83416ee0, 0x83417070, 0x8341719c, 0x83417ae0, 0x83417c9c, 0x83417cf0, 0x83417d30, 0x83417d80, 0x83417dd0,
    0x83417e20, 0x83417e50, 0x83417fd0, 0x83418140, 0x834182dc, 0x83418330, 0x83418370, 0x83418410, 0x83418460, 0x83418520,
    0x834185ec, 0x83418640, 0x83418680, 0x83418720, 0x83418750, 0x8341882c, 0x83418880, 0x834188c0, 0x83418950, 0x834189b0,
    0x83418a50, 0x83418a80, 0x83418b50)))


def install(lifter, img, build_id):
    if build_id != BUILD or img.word(AT) != EXPECT:
        print("ocarina reborn ui diagnostics: other game build, left out")
        return 0
    lifter.after[AT] = lifter.after[AT] + "\n" + CALL if AT in lifter.after else CALL
    n = 0
    for pc, name in SITES:
        if (img.word(pc) & 0x7f800000) != 0x52800000:   # (movz w)
            continue
        text = "{ extern void ocr_uidiag_site(unsigned long long pc, int name); ocr_uidiag_site(%#xULL, %d); }" % (pc, NAMES.index(name))
        lifter.after[pc] = lifter.after[pc] + "\n" + text if pc in lifter.after else text
        n += 1
    for pc, word in CALLS:
        if img.word(pc) == word:
            text = "{ extern void ocr_uidiag_call(Ctx *c, unsigned long long pc); ocr_uidiag_call(c, %#xULL); }" % pc
            lifter.after[pc] = lifter.after[pc] + "\n" + text if pc in lifter.after else text
    print("ocarina reborn ui diagnostics: hooked, %d of %d layout sites (%s)" % (n, len(SITES), ", ".join(NAMES)))
    return 1
