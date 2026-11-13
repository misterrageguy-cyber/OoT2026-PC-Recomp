// ---- (Ocarina Reborn) the HUD's look: a dark navy panel with a glowing cyan frame, a golden project mark and the title in the
// header, RESUME and X at its right (the options page; both close the HUD, nothing else), "Powered by Sorax" under the title.
// Drawn with fill() only (no GDI paths), at the menu's own scale s, so it is as sharp at 4K as at 720p ----
int hud_hover = -1;   // the header button under the cursor: 0 RESUME, 1 X, -1 none (menu_tick)
namespace hud {
constexpr int kBtnY = 9, kBtnH = 26, kResumeW = 96, kCloseW = 26, kGap = 8, kRight = 14;
inline int resume_x(int w, int s) { return w - (kRight + kCloseW + kGap + kResumeW) * s; }
inline int close_x(int w, int s) { return w - (kRight + kCloseW) * s; }
/// which header button a point in the menu's pixels is on (the options page's): 0 RESUME, 1 X, -1 none
inline int button_at(int mx, int my, int w, int s) {
    if (my < kBtnY * s || my >= (kBtnY + kBtnH) * s) return -1;
    if (mx >= resume_x(w, s) && mx < resume_x(w, s) + kResumeW * s) return 0;
    if (mx >= close_x(w, s) && mx < close_x(w, s) + kCloseW * s) return 1;
    return -1;
}
/// a triangle pointing up, its top at (cx, y), side wide: a fill per line
void triangle(HDC dc, int cx, int y, int side, COLORREF c) {
    const int th = side * 866 / 1000;
    for (int r = 0; r < th; r++) {
        const int half = side * (r + 1) / (2 * th);
        fill(dc, cx - half, y + r, std::max(1, 2 * half), 1, c);
    }
}
/// a small arrow, 9 wide and 5 high, its middle at cx: up or down (the list scrolls on that way)
void arrow(HDC dc, int cx, int y, bool up, int s) {
    for (int r = 0; r < 5; r++) {
        const int half = (up ? r : 4 - r) * s;
        fill(dc, cx - half - s / 2, y + r * s, 2 * half + s, s, RGB(0, 229, 255));
    }
}
/// the project mark: three triangles, size wide, its top at (x + size / 2, y); a darker rim under it for depth
void project_mark(HDC dc, int x, int y, int size, int s) {
    HPEN pen = CreatePen(PS_SOLID, 2 * s, RGB(114, 215, 234));
    HGDIOBJ oldpen = SelectObject(dc, pen), oldbrush = SelectObject(dc, GetStockObject(HOLLOW_BRUSH));
    Ellipse(dc, x, y, x + size, y + size);
    MoveToEx(dc, x + size / 4, y + size / 2, nullptr);
    LineTo(dc, x + size * 3 / 4, y + size / 2);
    SelectObject(dc, oldbrush); SelectObject(dc, oldpen); DeleteObject(pen);
}
/// the glowing frame: bright cyan at the edge, fading into the navy over 4 lines (times s)
void frame(HDC dc, int w, int h, int s) {
    static const COLORREF ring[4] = {RGB(0, 229, 255), RGB(0, 168, 232), RGB(6, 98, 170), RGB(10, 48, 96)};
    for (int i = 0; i < 4; i++) {
        const int o = i * s;
        fill(dc, o, o, w - 2 * o, s, ring[i]);
        fill(dc, o, h - o - s, w - 2 * o, s, ring[i]);
        fill(dc, o, o, s, h - 2 * o, ring[i]);
        fill(dc, w - o - s, o, s, h - 2 * o, ring[i]);
    }
}
/// the header: the project mark, the title, "Powered by Sorax" under it; RESUME and X when buttons
void header(HDC dc, int w, int s, const char* title, bool buttons) {
    fill(dc, 0, 0, w, 44 * s, RGB(10, 22, 52));                        // (a shade lighter than the panel)
    fill(dc, 12 * s, 43 * s, w - 24 * s, std::max(1, s), RGB(0, 150, 220));   // (a cyan rule under it)
    project_mark(dc, 16 * s, 10 * s, 26 * s, s);
    HFONT big = font(18 * s, FW_BOLD), small = font(11 * s, FW_SEMIBOLD);
    HGDIOBJ old = SelectObject(dc, big);
    SetTextColor(dc, RGB(236, 242, 255));
    TextOutA(dc, 52 * s, 5 * s, title, (int)strlen(title));
    SelectObject(dc, small);
    SetTextColor(dc, RGB(110, 190, 255));
    TextOutA(dc, 53 * s, 26 * s, "Powered by Sorax", 16);
    if (buttons) {
        HFONT label = font(12 * s, FW_BOLD);
        SelectObject(dc, label);
        const int y = kBtnY * s, bh = kBtnH * s;
        for (int b = 0; b < 2; b++) {
            const int x = b ? close_x(w, s) : resume_x(w, s), bw = (b ? kCloseW : kResumeW) * s;
            const bool hot = hud_hover == b;
            startup_gdi::round_rect(dc, x - s, y - s, bw + 2 * s, bh + 2 * s, 7 * s, hot ? RGB(0, 229, 255) : RGB(0, 120, 200));
            startup_gdi::round_rect(dc, x, y, bw, bh, 6 * s, b && hot ? RGB(170, 40, 56) : hot ? RGB(0, 110, 200) : RGB(14, 40, 92));
            const char* t = b ? "X" : "RESUME";
            SIZE sz{};
            GetTextExtentPoint32A(dc, t, (int)strlen(t), &sz);
            SetTextColor(dc, RGB(255, 255, 255));
            TextOutA(dc, x + (bw - (int)sz.cx) / 2, y + (bh - (int)sz.cy) / 2, t, (int)strlen(t));
        }
        SelectObject(dc, small);
        DeleteObject(label);
    }
    SelectObject(dc, old);
    DeleteObject(big);
    DeleteObject(small);
}
} // namespace hud
void paint_menu_body(HDC dc, uint32_t w, uint32_t h, int s);
/// the menu: its pages (paint_menu_body), then the frame over their edges
void paint_menu(HDC dc, uint32_t w, uint32_t h, int s) {
    paint_menu_body(dc, w, h, s);
    hud::frame(dc, (int)w, (int)h, s);
}
void paint_menu_body(HDC dc, uint32_t w, uint32_t h, int s) {
