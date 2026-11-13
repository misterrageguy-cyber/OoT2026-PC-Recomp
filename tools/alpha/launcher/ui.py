"""The launcher's look: one canvas per window, drawn again whenever the window's size changes.

Panels, glows, gradients and rounded edges are painted with numpy into one picture of the window's own size (anti-aliased,
at the screen's pixels: sharp at any size and any Windows scaling, nothing stretched). Text and icons are the canvas's own
(vector fonts: Segoe UI Variable and Segoe Fluent Icons), entry fields are Tk widgets placed into the canvas. A page is a
function that lays itself out for the size it is given (Ctx: the size, the scale, and the drawing calls); Stage draws it,
finds what is under the mouse, and calls back.

Chrome: the window keeps its Windows frame (snap, resize edges, shadow, the taskbar), but its caption is taken away
(WM_NCCALCSIZE), so the header with its own minimise / maximise / close buttons is the top of the window, as in the design.
OCARINA_NATIVE_FRAME=1 keeps Windows' own caption.
"""
import ctypes
import os
import tkinter as tk
import tkinter.font as tkfont
from ctypes import wintypes

import numpy as np

# ---- the palette (the design: dark navy, blue glass panels, a bright blue accent)
BG_TOP, BG_BOTTOM = '#0d1b36', '#081226'
HEAD = '#0a1730'
PANEL, PANEL_HI = '#10224a', '#132a58'
CELL = '#0c1a3a'
LINE, LINE_HI = '#22427e', '#3768c8'
ACCENT, ACCENT_HI, ACCENT_LO = '#2e7bff', '#4a95ff', '#1556e0'
GLOW = '#2f7bff'
TEXT, SUB, MUTED = '#f2f6ff', '#a9bbdb', '#7d92ba'
LINK = '#86d0ff'
GOLD, RED, GREEN = '#f4c430', '#ff8a80', '#3ccf6e'

ICON = 'Segoe Fluent Icons'
GLYPH = dict(download='', folder='', folder_open='', cube='', play='', globe='',
             chip='', file='', drive='', sync='', refresh='', down='', right='',
             minimize='', maximize='', restore='', close='', settings='', save='',
             bug='', wrench='', layers='', speaker='', mute='', music='', info='',
             check='', clock='', back='', import_='', history='', warning='',
             logs='', key='', checkbox='', checked='')


def rgb(c):
    return np.array([int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)], np.float32)


def font_family(*names):
    have = set(tkfont.families())
    return next((n for n in names if n in have), names[-1])


# ---- painting
class Painter:
    """a picture of w x h (float RGB), at offset (ox, oy) in the window"""

    def __init__(self, a, ox=0, oy=0):
        self.a, self.ox, self.oy = a, ox, oy

    @classmethod
    def background(cls, w, h, cache={}):
        key = (w, h)
        if key not in cache:
            cache.clear()
            y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
            a = rgb(BG_TOP) * (1 - y) + rgb(BG_BOTTOM) * y
            a = np.broadcast_to(a, (h, w, 3)).copy()
            # (a soft blue light from above the middle, and a darker edge)
            yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
            xx = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
            light = np.exp(-((xx / 0.9) ** 2 + ((yy - 0.05) / 0.55) ** 2) * 1.6)
            a += light[..., None] * np.array([10, 26, 60], np.float32)
            vign = np.clip((np.abs(xx) - 0.55) / 0.45, 0, 1) ** 2 * 0.35
            a *= (1 - vign)[..., None]
            cache[key] = a
        return cls(cache[key].copy())

    def crop(self, x, y, w, h):
        x0, y0 = max(0, int(x) - self.ox), max(0, int(y) - self.oy)
        x1, y1 = min(self.a.shape[1], int(x + w) - self.ox), min(self.a.shape[0], int(y + h) - self.oy)
        return Painter(self.a[y0:y1, x0:x1].copy(), x0 + self.ox, y0 + self.oy)

    def _blend(self, ys, xs, cov, col):
        sub = self.a[ys, xs]
        sub += (col - sub) * cov[..., None]

    def rrect(self, x, y, w, h, r, fill=None, fill2=None, alpha=1.0, border=None, border2=None, bw=1.0, balpha=1.0,
              glow=None, gr=14.0, ga=0.0):
        """a rounded rectangle: fill (to fill2 downwards), a border of bw (border to border2 downwards), a glow outside"""
        if w <= 0 or h <= 0:
            return
        pad = int(gr * 3) + 2 if glow and ga else 2
        H, W = self.a.shape[:2]
        x0, y0 = max(0, int(x - pad) - self.ox), max(0, int(y - pad) - self.oy)
        x1, y1 = min(W, int(x + w + pad) + 1 - self.ox), min(H, int(y + h + pad) + 1 - self.oy)
        if x1 <= x0 or y1 <= y0:
            return
        py = (np.arange(y0, y1, dtype=np.float32) + self.oy + 0.5)[:, None]
        px = (np.arange(x0, x1, dtype=np.float32) + self.ox + 0.5)[None, :]
        r = min(r, w / 2, h / 2)
        qx = np.abs(px - (x + w / 2)) - (w / 2 - r)
        qy = np.abs(py - (y + h / 2)) - (h / 2 - r)
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
        ys, xs = slice(y0, y1), slice(x0, x1)
        if glow and ga:
            g = ga * np.exp(-np.maximum(d, 0) / gr) * np.clip(d + 0.5, 0, 1)
            self._blend(ys, xs, g, rgb(glow))
        t = np.clip((py - y) / max(h, 1), 0, 1)
        if fill:
            col = rgb(fill) if not fill2 else rgb(fill) * (1 - t[..., None]) + rgb(fill2) * t[..., None]
            cov = np.clip(0.5 - d, 0, 1) * alpha
            if fill2:
                sub = self.a[ys, xs]
                sub += (col - sub) * cov[..., None]
            else:
                self._blend(ys, xs, cov, col)
        if border:
            col = rgb(border) if not border2 else rgb(border) * (1 - t[..., None]) + rgb(border2) * t[..., None]
            cov = np.minimum(np.clip(0.5 - d, 0, 1), np.clip(d + bw + 0.5, 0, 1)) * balpha
            sub = self.a[ys, xs]
            sub += (col - sub) * cov[..., None]

    def rect(self, x, y, w, h, color, alpha=1.0):
        self.rrect(x, y, w, h, 0, fill=color, alpha=alpha)

    def photo(self, master):
        b = np.clip(self.a, 0, 255).astype(np.uint8)
        return tk.PhotoImage(master=master, data=b'P6 %d %d 255 ' % (b.shape[1], b.shape[0]) + b.tobytes(), format='PPM')


# ---- a page's drawing calls
class Hot:
    def __init__(self, x, y, w, h, cmd=None, cursor='hand2', enter=None, leave=None, kind='click', hover=None):
        self.box = (x, y, x + w, y + h)
        self.cmd, self.cursor, self.enter, self.leave, self.kind, self.hover = cmd, cursor, enter, leave, kind, hover
        self.item = None

    def has(self, x, y):
        return self.box[0] <= x < self.box[2] and self.box[1] <= y < self.box[3]


class Ctx:
    def __init__(self, stage, w, h, s):
        self.stage, self.W, self.H, self.s = stage, w, h, s
        self.p = Painter.background(w, h)
        self.ops = []      # (canvas items made after the picture: text, icons, images, widgets)
        self.hots = []
        self.hovers = []   # (hot, draw function for its hovered look)
        self.bars = []

    def S(self, v):
        return v * self.s

    def font(self, size, weight='regular'):
        st = self.stage
        fam = {'regular': st.f_text, 'semibold': st.f_semi, 'bold': st.f_bold, 'display': st.f_disp}[weight]
        return (fam, -max(8, round(size * self.s)))

    def text_width(self, text, size, weight='regular'):
        return self.stage.measure(self.font(size, weight), text)

    # (the picture)
    def panel(self, x, y, w, h, r=14, fill=PANEL, fill2=None, alpha=0.92, border=LINE, bw=1.0, balpha=1.0, glow=None,
              gr=16, ga=0.0, border2=None):
        s = self.s
        self.p.rrect(x, y, w, h, r * s, fill=fill, fill2=fill2, alpha=alpha, border=border, border2=border2,
                     bw=max(1.0, bw * s), balpha=balpha, glow=glow, gr=gr * s, ga=ga)

    def hline(self, x, y, w, color=LINE, alpha=0.7):
        self.p.rect(x, y, w, max(1, round(self.s)), color, alpha)

    def vline(self, x, y, h, color=LINE, alpha=0.7):
        self.p.rect(x, y, max(1, round(self.s)), h, color, alpha)

    # (canvas items)
    def text(self, x, y, text, size=18, weight='regular', color=TEXT, anchor='nw', width=None, key=None, justify='left'):
        self.ops.append(('text', x, y, text, self.font(size, weight), color, anchor, width, key, justify))

    def icon(self, x, y, name, size=24, color=TEXT, anchor='center', key=None):
        self.ops.append(('text', x, y, GLYPH.get(name, name), (ICON, -max(8, round(size * self.s))), color, anchor, None, key,
                         'left'))

    def image(self, x, y, photo, anchor='nw'):
        self.ops.append(('image', x, y, photo, anchor))

    def entry(self, key, x, y, w, h, var, size=19, mono=False):
        self.panel(x, y, w, h, r=10, fill=CELL, alpha=0.95, border=LINE, balpha=0.9)
        pad = 16 * self.s
        self.ops.append(('entry', key, x + pad, y + 3, w - 2 * pad, h - 6, var,
                         ('Consolas', -round(size * self.s)) if mono else self.font(size)))

    def hot(self, x, y, w, h, cmd=None, cursor='hand2', enter=None, leave=None, kind='click', hover=None):
        hot = Hot(x, y, w, h, cmd, cursor, enter, leave, kind)
        self.hots.append(hot)
        if hover:
            self.hovers.append((hot, hover))
        return hot

    # (controls)
    def button(self, x, y, w, h, text, cmd, kind='secondary', icon=None, size=19, r=12, weight='semibold', color=None):
        """kind: primary (blue, glowing), secondary (dark glass), pill (link coloured), quiet (text only), danger"""
        s = self.s

        def look(p_ctx, hover):
            if kind == 'primary':
                p_ctx.panel(x, y, w, h, r=r, fill=ACCENT_HI if hover else '#3b8bff', fill2=ACCENT_LO, alpha=1.0,
                            border='#8cc2ff', border2=ACCENT, bw=1.5, glow=GLOW, gr=18, ga=0.55 if hover else 0.38)
            elif kind == 'pill':
                p_ctx.panel(x, y, w, h, r=h / s / 2, fill=PANEL_HI if hover else PANEL, alpha=0.95,
                            border=LINE_HI if hover else LINE, balpha=1.0)
            elif kind == 'quiet':
                if hover:
                    p_ctx.panel(x, y, w, h, r=r, fill=PANEL, alpha=0.7, border=LINE, balpha=0.6)
            else:
                p_ctx.panel(x, y, w, h, r=r, fill=PANEL_HI if hover else PANEL, fill2=None, alpha=0.95,
                            border=LINE_HI if hover else LINE, balpha=1.0, glow=GLOW if hover else None, gr=10, ga=0.18)
        look(self, False)
        fg = color or (LINK if kind == 'pill' else TEXT if kind != 'quiet' else SUB)
        if icon:
            tw = self.text_width(text, size, weight)
            iw = size * 1.15 * s
            gap = 12 * s
            total = iw + gap + tw
            x0 = x + (w - total) / 2
            self.icon(x0 + iw / 2, y + h / 2, icon, size * (1.05 if kind == 'primary' else 0.95), fg)
            self.text(x0 + iw + gap, y + h / 2, text, size, weight, fg, anchor='w')
        else:
            self.text(x + w / 2, y + h / 2, text, size, weight, fg, anchor='center')
        return self.hot(x, y, w, h, cmd, hover=look)

    def dropdown(self, x, y, w, h, values, current, pick, size=19, key=None):
        self.panel(x, y, w, h, r=10, fill=CELL, alpha=0.95, border=LINE, balpha=0.9)
        pad = 22 * self.s
        self.text(x + pad, y + h / 2, current, size, color=TEXT, anchor='w', key=key)
        self.icon(x + w - pad, y + h / 2, 'down', size * 0.8, SUB)

        def hover(c, on):
            c.panel(x, y, w, h, r=10, fill=PANEL if on else CELL, alpha=0.95, border=LINE_HI if on else LINE, balpha=1.0)
        return self.hot(x, y, w, h, lambda: self.stage.popup(x, y + h + 4 * self.s, w, values, current, pick, size),
                        hover=hover)

    def radio(self, x, y, d, on, cmd=None):
        s = self.s
        self.panel(x, y, d, d, r=d / s / 2, fill=CELL, alpha=1, border=ACCENT_HI if on else LINE_HI, bw=2)
        if on:
            k = d * 0.27
            self.panel(x + k, y + k, d - 2 * k, d - 2 * k, r=d / s, fill=ACCENT_HI, alpha=1, border=None, glow=GLOW, gr=6,
                       ga=0.5)
        if cmd:
            self.hot(x - 6, y - 6, d + 12, d + 12, cmd)

    def check(self, x, y, d, on, cmd):
        self.panel(x, y, d, d, r=6, fill=ACCENT if on else CELL, fill2=ACCENT_LO if on else None, alpha=1,
                   border=ACCENT_HI if on else LINE_HI, bw=1.5)
        if on:
            self.icon(x + d / 2, y + d / 2, 'check', d / self.s * 0.62, TEXT)

    def icon_box(self, x, y, d, name, size=None, color=ACCENT_HI, r=12, fill=CELL):
        self.panel(x, y, d, d, r=r, fill=fill, alpha=0.95, border=LINE, balpha=0.9)
        self.icon(x + d / 2, y + d / 2, name, size or d / self.s * 0.45, color)

    def progress(self, key, x, y, w, h, value):
        self.panel(x, y, w, h, r=h / self.s / 2, fill='#1a2c52', alpha=1, border=None)
        self.bars.append((key, x, y, w, h, value))


class Stage:
    """the window's canvas: draws a page for the window's size, again on every resize"""

    def __init__(self, root, canvas):
        self.root, self.c = root, canvas
        self.f_text = font_family('Segoe UI Variable Text', 'Segoe UI')
        self.f_semi = font_family('Segoe UI Variable Text Semibold', 'Segoe UI Semibold')
        self.f_bold = font_family('Segoe UI Variable Display Semib', 'Segoe UI Semibold')
        self.f_disp = font_family('Segoe UI Variable Display', 'Segoe UI')
        self.fonts = {}
        self.builder = None
        self.photos = []
        self.hots = []
        self.under = None
        self.entries = {}
        self.items = {}
        self.bar_items = {}
        self.size = (0, 0)
        self.pending = None
        self.pop = None
        c = canvas
        c.bind('<Configure>', self.resized)
        c.bind('<Motion>', self.motion)
        c.bind('<Leave>', lambda e: self.set_under(None))
        c.bind('<Button-1>', self.press)
        c.bind('<Double-Button-1>', self.double)

    def measure(self, font, text):
        f = self.fonts.get(font)
        if f is None:
            f = self.fonts[font] = tkfont.Font(root=self.root, family=font[0], size=font[1])
        return f.measure(text)

    def scale(self, w, h):
        """the design is drawn for 1672 x 941; bigger windows grow it (to 1.3x), smaller ones shrink it (to 0.6x)"""
        return max(0.6, min(1.3, min(w / 1672, h / 941)))

    def show(self, builder):
        self.builder = builder
        self.close_popup()
        self.render()

    def resized(self, e):
        if (e.width, e.height) != self.size:
            if self.pending:
                self.root.after_cancel(self.pending)
            self.pending = self.root.after(15, self.render)

    def render(self):
        self.pending = None
        w, h = self.c.winfo_width(), self.c.winfo_height()
        if w < 50 or h < 50 or not self.builder:
            return
        self.size = (w, h)
        ctx = Ctx(self, w, h, self.scale(w, h))
        self.builder(ctx)
        c = self.c
        c.delete('all')
        self.photos = [ctx.p.photo(c)]
        c.create_image(0, 0, image=self.photos[0], anchor='nw')
        for hot, look in ctx.hovers:   # (each hovered look: the picture under it, drawn again hovered, shown on hover)
            x0, y0, x1, y1 = hot.box
            m = 70 * ctx.s   # (room for the hovered glow)
            sub = Ctx.__new__(Ctx)
            sub.__dict__.update(ctx.__dict__)
            sub.p = ctx.p.crop(x0 - m, y0 - m, x1 - x0 + 2 * m, y1 - y0 + 2 * m)
            look(sub, True)
            ph = sub.p.photo(c)
            self.photos.append(ph)
            hot.item = c.create_image(sub.p.ox, sub.p.oy, image=ph, anchor='nw', state='hidden')
        self.items = {}
        used = set()
        for op in ctx.ops:
            if op[0] == 'text':
                _, x, y, text, font, color, anchor, width, key, justify = op
                i = c.create_text(x, y, text=text, font=font, fill=color, anchor=anchor, width=width or 0, justify=justify, tags='fg')
                if key:
                    self.items[key] = i
            elif op[0] == 'image':
                _, x, y, photo, anchor = op
                c.create_image(x, y, image=photo, anchor=anchor, tags='fg')
            elif op[0] == 'entry':
                _, key, x, y, w_, h_, var, font = op
                e = self.entries.get(key)
                if e is None or not e.winfo_exists():
                    e = self.entries[key] = tk.Entry(c, textvariable=var, relief='flat', bd=0, highlightthickness=0,
                                                     bg=CELL, fg=TEXT, insertbackground=TEXT, disabledbackground=CELL,
                                                     readonlybackground=CELL, selectbackground=ACCENT)
                e.config(font=font)
                c.create_window(x, y, window=e, anchor='nw', width=w_, height=h_)
                used.add(key)
        for k in [k for k in self.entries if k not in used]:
            self.entries.pop(k).destroy()
        self.ctx = ctx
        self.bar_items = {}
        for key, x, y, w_, h_, v in ctx.bars:
            self.bar_items[key] = (x, y, w_, h_, None)
            self.set_bar(key, v)
        self.hots = ctx.hots
        self.under = None
        self.ctx = ctx
        px, py = c.winfo_pointerx() - c.winfo_rootx(), c.winfo_pointery() - c.winfo_rooty()
        self.motion(type('E', (), {'x': px, 'y': py})())
        if getattr(self, 'on_render', None):   # (gamepad.py: the controller's focus ring on the new page)
            self.on_render()

    def set_bar(self, key, value):
        """a progress bar's filled part (0..1), drawn again on its own"""
        if key not in self.bar_items:
            return
        x, y, w, h, item = self.bar_items[key]
        if item:
            self.c.delete(item)
        fw = w * max(0.0, min(1.0, value))
        if fw < h * 0.6:
            self.bar_items[key] = (x, y, w, h, None)
            return
        m = 8
        p = self.ctx.p.crop(x - m, y - m, fw + 2 * m, h + 2 * m)
        p.rrect(x, y, fw, h, h / 2, fill=ACCENT_HI, fill2=ACCENT_LO, alpha=1, glow=GLOW, gr=5, ga=0.35)
        p.rrect(x + 2, y + 1, max(0, fw - 4), h * 0.4, h * 0.2, fill='#9fd0ff', alpha=0.25)
        ph = p.photo(self.c)
        self.photos.append(ph)
        self.bar_items[key] = (x, y, w, h, self.c.create_image(p.ox, p.oy, image=ph, anchor='nw', tags='fg'))

    def set_text(self, key, text=None, color=None):
        i = self.items.get(key)
        if i:
            kw = {}
            if text is not None:
                kw['text'] = text
            if color:
                kw['fill'] = color
            self.c.itemconfig(i, **kw)

    def hot_at(self, x, y):
        return next((h for h in reversed(self.hots) if h.has(x, y)), None)

    def set_under(self, hot):
        if hot is self.under:
            return
        old, self.under = self.under, hot
        if old:
            if old.item:
                self.c.itemconfig(old.item, state='hidden')
            if old.leave:
                old.leave()
        if hot:
            if hot.item:
                self.c.itemconfig(hot.item, state='normal')
                self.c.tag_raise(hot.item)
                self.c.tag_raise('fg')   # (every text, icon and picture over the hovered look: its glow reaches its neighbours)
            if hot.enter:
                hot.enter()
        self.c.config(cursor=hot.cursor if hot else '')

    def motion(self, e):
        self.set_under(self.hot_at(e.x, e.y))

    def press(self, e):
        hot = self.hot_at(e.x, e.y)
        if hot and hot.cmd:
            if hot.kind == 'drag':
                hot.cmd(e)
            else:
                self.root.after(1, hot.cmd)

    def double(self, e):
        hot = self.hot_at(e.x, e.y)
        if hot and hot.kind == 'drag' and hot.cursor == '' and getattr(self, 'on_double', None):
            self.on_double()

    # (the dropdowns' lists)
    def close_popup(self, *_):
        if self.pop:
            try:
                self.pop.grab_release()
                self.pop.destroy()
            except tk.TclError:
                pass
            self.pop = None

    def popup(self, x, y, w, values, current, pick, size):
        self.close_popup()
        s = self.scale(*self.size)
        rh = round(44 * s)
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.configure(bg=LINE_HI)
        n = len(values)
        sh = self.root.winfo_screenheight()
        hh = min(n * rh + 2, int(sh * 0.6))
        sx, sy = self.c.winfo_rootx() + int(x), self.c.winfo_rooty() + int(y)
        if sy + hh > sh - 40:
            sy = max(0, sy - hh - int(56 * s))
        top.geometry(f'{int(w)}x{hh}+{sx}+{sy}')
        cv = tk.Canvas(top, bg=PANEL, highlightthickness=0, bd=0)
        cv.pack(fill='both', expand=True, padx=1, pady=1)
        font = (self.f_text, -round(size * s))
        rows = []
        for i, v in enumerate(values):
            r = cv.create_rectangle(0, i * rh, w, (i + 1) * rh, fill=ACCENT if v == current else PANEL, outline='')
            cv.create_text(round(20 * s), i * rh + rh / 2, text=v, font=font, fill=TEXT, anchor='w')
            rows.append(r)
        cv.configure(scrollregion=(0, 0, w, n * rh))
        hov = [None]

        def move(e):
            i = int(cv.canvasy(e.y) // rh)
            if hov[0] is not None and hov[0] != i and 0 <= hov[0] < n:
                cv.itemconfig(rows[hov[0]], fill=ACCENT if values[hov[0]] == current else PANEL)
            if 0 <= i < n:
                cv.itemconfig(rows[i], fill=ACCENT_HI)
            hov[0] = i

        def click(e):
            inside = 0 <= e.x_root - top.winfo_rootx() < top.winfo_width() and 0 <= e.y_root - top.winfo_rooty() < top.winfo_height()
            if not inside:
                return self.close_popup()
            i = int(cv.canvasy(e.y) // rh)
            self.close_popup()
            if 0 <= i < n:
                pick(values[i])
        cv.bind('<Motion>', move)
        top.bind('<Button-1>', click)
        cv.bind('<MouseWheel>', lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        cv.configure(yscrollincrement=rh)
        top.bind('<Escape>', self.close_popup)
        top.bind('<FocusOut>', lambda e: self.root.after(50, self.close_popup))
        if current in values:
            cv.yview_moveto(max(0, values.index(current) - 3) / max(1, n))
        top.update_idletasks()
        top.focus_force()
        top.grab_set()
        self.pop = top

        # (a controller's up/down and A: gamepad.py moves the highlighted row and picks it)
        def nav_move(d):
            i = (hov[0] if hov[0] is not None else (values.index(current) if current in values else 0)) + d
            i = max(0, min(n - 1, i))
            if hov[0] is not None and 0 <= hov[0] < n:
                cv.itemconfig(rows[hov[0]], fill=ACCENT if values[hov[0]] == current else PANEL)
            cv.itemconfig(rows[i], fill=ACCENT_HI)
            hov[0] = i
            first, last = cv.yview()
            if not first * n <= i < last * n - 0.5:
                cv.yview_moveto(max(0, i - 3) / max(1, n))

        def nav_pick():
            i = hov[0] if hov[0] is not None else (values.index(current) if current in values else -1)
            self.close_popup()
            if 0 <= i < n:
                pick(values[i])
        self.pop_nav = (nav_move, nav_pick)


# ---- the window's frame without Windows' caption
WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION, HTTOP = 2, 12
LRESULT = ctypes.c_ssize_t


class Chrome:
    """takes the caption away from the Tk window (the frame stays: resizing at the edges, snap, shadow, the taskbar), and
    takes dropped files: on_drop(paths). The window procedure that does it is ocr_chrome.dll's (chrome.c), never Python's:
    Windows calls it inside its move and size loops while Tk runs Python callbacks, and Python inside a Python window
    procedure on the same thread ends in abort() (the build screen's crash while its window was resized)"""

    def __init__(self, root, on_drop=None):
        self.root, self.on_drop, self.ok = root, on_drop, False
        if os.name != 'nt' or os.environ.get('OCARINA_NATIVE_FRAME') == '1':
            return
        u = ctypes.windll.user32
        self.u = u
        u.GetParent.restype = wintypes.HWND
        u.GetParent.argtypes = [wintypes.HWND]
        u.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u.SendMessageW.restype = LRESULT
        try:
            from pathlib import Path
            dll = ctypes.WinDLL(str(Path(__file__).resolve().parent / 'ocr_chrome.dll'))
            dll.ocr_chrome_install.argtypes = [wintypes.HWND]
            dll.ocr_chrome_take_drop.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
            dll.ocr_chrome_begin.argtypes = [wintypes.HWND, ctypes.c_int]
        except (OSError, AttributeError):   # (no DLL: Windows' own caption, the launcher otherwise the same)
            return
        root.update_idletasks()
        self.hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
        self.dll = dll
        self.ok = bool(dll.ocr_chrome_install(self.hwnd))
        if self.ok and on_drop:
            self.root.after(300, self.poll_drop)

    def poll_drop(self):
        buf = ctypes.create_unicode_buffer(32768)
        try:
            if self.dll.ocr_chrome_take_drop(buf, 32768):
                self.on_drop([p for p in buf.value.split(chr(10)) if p])
        except Exception:
            pass
        try:
            self.root.after(300, self.poll_drop)
        except tk.TclError:   # (the window is gone)
            pass

    def drag(self, e=None):
        """moves the window as its caption would (Windows' own move: snap). Posted from the DLL: a move started from here
        with SendMessage would run Windows' move loop inside this Python call, and Tk's callbacks inside it end in abort()"""
        if self.ok:
            self.dll.ocr_chrome_begin(self.hwnd, HTCAPTION)

    def resize_top(self, e=None, where=HTTOP):
        if self.ok and self.root.state() != 'zoomed':
            self.dll.ocr_chrome_begin(self.hwnd, where)

    def zoomed(self):
        return self.root.state() == 'zoomed'
