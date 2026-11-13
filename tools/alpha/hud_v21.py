"""Ocarina Reborn's look for the F1 menu of the v2.1.0 engine (Dear ImGui: gpu/vk/vk_ui.h's palette, vk_menu.cpp's drawing).

The menu keeps the engine's layout and behaviour; what the player sees is Ocarina Reborn's: night navy panels, a glowing cyan
edge, blue tabs and selection, white text, gold for the chosen value; the banner's left says OCARINA REBORN beside a gold
project mark, "Powered by Sorax" under it, and no version; the start-up screen shows the Ocarina Reborn logo on navy, no wordmark,
no version. HDR is the engine's own (vk_imgui.cpp converts the overlays for HDR10).
"""
import re

# the warm palette (the game's pause menu) to Ocarina Reborn's: (r, g, b[, a]) -> (r, g, b[, a])
COLOURS = {
    # text
    (240, 232, 214): (236, 242, 255), (255, 250, 240): (255, 255, 255), (214, 204, 184): (205, 216, 240),
    (168, 156, 136): (150, 170, 210), (246, 232, 204): (236, 242, 255), (150, 140, 126): (130, 145, 180),
    (40, 30, 20): (10, 20, 45),
    # gold: the chosen value, as the launcher's
    (222, 152, 40): (232, 176, 36), (238, 168, 52): (250, 204, 70), (36, 24, 8): (24, 18, 4),
    # accents and edges: cyan
    (214, 170, 96): (0, 200, 255), (122, 98, 64, 150): (0, 150, 230, 150), (122, 98, 64, 220): (0, 200, 255, 220),
    (122, 98, 64, 230): (0, 180, 255, 230), (190, 154, 98, 90): (0, 180, 255, 90),
    # cells and panels: navy, blue when selected
    (30, 25, 19, 246): (8, 16, 38, 246), (60, 47, 32, 240): (16, 34, 74, 240), (92, 70, 42, 248): (26, 64, 140, 248),
    (84, 64, 38): (20, 56, 120), (34, 26, 17, 228): (6, 12, 30, 228), (36, 28, 19, 248): (8, 16, 38, 248),
    (36, 28, 19, 250): (8, 16, 38, 250), (22, 17, 11, 232): (5, 10, 26, 232),
    # the banner: dark blue, light ink, a cyan rule; the shown tab blue
    (184, 146, 96, 246): (14, 44, 104, 246), (176, 138, 88, 246): (8, 24, 60, 246), (46, 30, 12): (200, 220, 250),
    (70, 48, 24): (0, 180, 255), (226, 192, 138, 140): (0, 229, 255, 170), (84, 56, 30, 250): (26, 64, 140, 250),
    (52, 34, 16): (0, 180, 255),
    # the start-up screen and the FPS counter
    (14, 10, 6): (5, 10, 26), (46, 33, 18, 4): (0, 110, 255, 4), (72, 255, 110): (90, 190, 255),
}

PROJECT_TITLE = '''    {   // (Ocarina Reborn) the banner's left: an original circle mark, OCARINA REBORN, Powered by Sorax under it (no version: the log has it)
        const float room = (c.w - total) * 0.5f - 60 * s - c.safe, x0 = c.safe, tri = 30 * s;
        if (room > tri + 40 * s) {
            const ImVec2 centre(x0 + tri * 0.5f, ty);
            c.d->AddCircle(centre, tri * 0.42f, ui::rgba(114, 215, 234), 24, 2 * s);
            c.d->AddLine(ImVec2(x0 + tri * 0.25f, ty), ImVec2(x0 + tri * 0.75f, ty), ui::kInkBright, 2 * s);
            const float tx = x0 + tri + 12 * s, text_room = room - tri - 12 * s;
            const auto width = [&](float p) { return ui::size_of(c.f.heading, p, "OCARINA REBORN").x; };
            const float px = ui::fit_px(20 * s, 12 * s, 0.5f * s, text_room, width);
            if (px > 0) {
                ui::text_mid(c, c.f.heading, px, tx, ty - 7 * s, ui::kInkBright, "OCARINA REBORN");
                ui::text_mid(c, c.f.body, std::max(10 * s, px * 0.55f), tx + s, ty + 11 * s, ui::kAccent, "Powered by Sorax");
            }
        }
    }
'''


def apply(H):
    """the look onto H's vk_ui.h and vk_menu.cpp"""
    n = 0
    for rel in ('gpu/vk/vk_ui.h', 'gpu/vk/vk_menu.cpp'):
        f = H / rel
        t = f.read_text(encoding='utf-8')

        def recolour(m):
            nonlocal n
            key = tuple(int(v) for v in re.findall(r'\d+', m.group(1)))
            if key not in COLOURS:
                return m.group(0)
            n += 1
            return 'rgba(' + ', '.join(str(v) for v in COLOURS[key]) + ')'
        t = re.sub(r'rgba\((\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*\d+\s*)?)\)', recolour, t)
        if rel.endswith('vk_ui.h'):
            # (the gold buttons' glow: cyan, not the warm white)
            old = 'rgba(255, 244, 220, 12 + 4 * (6 - i))'
            if old not in t:
                raise SystemExit('hud_v21: vk_ui.h no longer has the glow colour (the engine changed: update hud_v21.py)')
            t = t.replace(old, 'rgba(120, 230, 255, 12 + 4 * (6 - i))')
        else:
            t = patch_menu(t)
        f.write_text(t, encoding='utf-8', newline='')
    print(f'hud: {n} colours, banner title, start-up screen')


def swap(t, old, new, what, regex=False):
    if regex:
        t2, k = re.subn(old, lambda m: new, t, count=1, flags=re.S)
    else:
        k = t.count(old)
        t2 = t.replace(old, new, 1)
    if not k:
        raise SystemExit(f'hud_v21: vk_menu.cpp no longer has {what} (the engine changed: update hud_v21.py)')
    return t2


def patch_menu(t):
    # the banner's left: the build's version -> the project mark and the name
    t = swap(t, r'    \{   // \(which build, at the banner\'s left.*?\n    \}\n(?=    // the rows, in the column)', PROJECT_TITLE,
             'the version at the banner\'s left', regex=True)
    # (the tab keys' caps: dark, as the banner's ink is light now)
    t = swap(t, 'hover ? ui::kTabInset : ui::kBannerInk, 3 * s);', 'hover ? ui::kTabInset : ui::kCellDark, 3 * s);', 'the tab key caps')
    # the start-up screen: the Ocarina Reborn logo (its wordmark in it) larger, no HOOKSHOT wordmark, no version
    t = swap(t, 'const float lh = 112 * s, top = h * 0.5f - 176 * s;', 'const float lh = 250 * s, top = h * 0.5f - 300 * s;   // (Ocarina Reborn: its logo has the name)',
             'the start-up logo size')
    t = swap(t, '    ui::spaced(c, c.f.heading, 42 * k, ImVec2(cx, y), ui::rgba(236, 242, 255), "HOOKSHOT", 6 * k);\n', '',
             'the start-up wordmark')
    t = swap(t, '    ui::text_centre(c, c.f.body, 14.5f * k, ImVec2(cx, y + 78 * k), ui::kDim, v.version.c_str());\n', '',
             'the start-up version')
    return t
