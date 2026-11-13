"""The animated BUILD screen: a canvas over the launcher window that shows ocarina_prepare.py's real progress.

Everything shown comes from ocarina_prepare.py's JSON lines (the build's own output): the step, its fraction, its counter
(files, shaders) and the overall percentage. The animation only eases the drawn bar and number toward the last real value,
turns the active step's ring and sweeps a light along the bar; it never moves the value itself.
"""
import json
import math
import os
import queue
import signal
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path

STEPS = [('nup', ('NUP-Dateien vorbereiten', 'Preparing the NUP file')),
         ('extract', ('Spielressourcen extrahieren', 'Extracting game resources')),
         ('analyze', ('ROM-Daten analysieren', 'Analysing the game code')),
         ('build', ('Build erstellen', 'Compiling the game')),
         ('finish', ('Installation abschließen', 'Finishing the installation')),
         ('shaders', ('Shader kompilieren', 'Compiling shaders'))]
STATUS = {'nup': ('NUP-Dateien werden vorbereitet…', 'Preparing the NUP file…'),
          'extract': ('Spielressourcen werden extrahiert…', 'Extracting game resources…'),
          'analyze': ('ROM wird analysiert…', 'Analysing the game code…'),
          'build': ('Build wird erstellt…', 'Compiling the game…'),
          'finish': ('Installation wird abgeschlossen…', 'Finishing the installation…'),
          'shaders': ('Shader werden kompiliert…', 'Compiling shaders…')}
UNITS = {'files': ('Dateien', 'files'), 'shaders': ('Shader', 'shaders')}
GREY, BLUE, CYAN, GREEN, RED, GOLD, TEXT, SUB = '#59658a', '#2f7dff', '#5fd3ff', '#3ccf6e', '#ff5d5d', '#f2c752', '#eef2fc', '#a8b6d8'
W, H = 1100, 720


def fmt(n, de):
    s = f'{n:,}'
    return s.replace(',', '.') if de else s


class BuildScreen:
    def __init__(self, app, cmd, assets, de, log_path, on_done, on_back, version):
        self.app, self.cmd, self.de, self.on_done, self.on_back = app, cmd, de, on_done, on_back
        self.T = lambda d, e: d if de else e
        self.c = tk.Canvas(app, width=W, height=H, highlightthickness=0, bg='#050b1c')
        self.c.place(x=0, y=0, relwidth=1, relheight=1)
        self.img = {}
        for k in ('build-bg', 'logo-build'):
            try:
                self.img[k] = tk.PhotoImage(file=str(Path(assets) / f'{k}.png'))
            except tk.TclError:
                pass
        self.assets = Path(assets)
        self.bg_state, self.bg_item = None, None
        self.fit = (1.0, 0.0, 0.0)
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logf = open(self.log_path, 'a', encoding='utf-8')
        self.q = queue.Queue()
        self.state = {s: 'wait' for s, _ in STEPS}
        self.step_frac = {s: 0.0 for s, _ in STEPS}
        self.counter = ''
        self.target = 0.0
        self.shown = 0.0
        self.t0 = time.time()
        self.phase = 'run'      # run, done, failed, cancelled
        self.error = ''
        self.version = version
        self.proc = None
        self.log_lines = []
        self.show_log = False
        self.anim = 0.0
        self.write_log(self.T('Build gestartet', 'Build started'))
        self.draw_static()
        self.start()
        self.tick()

    # ---- the process
    def start(self):
        def work():
            try:
                self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                             encoding='utf-8', errors='replace',
                                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) |
                                             getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
                for line in self.proc.stdout:
                    try:
                        self.q.put(json.loads(line))
                    except ValueError:
                        self.q.put({'log': line.rstrip()})
                self.q.put({'exit': self.proc.wait()})
            except OSError as e:
                self.q.put({'error': f'failed: {e}', 'step': 'nup'})
                self.q.put({'exit': 1})
        threading.Thread(target=work, daemon=True).start()

    def cancel(self):
        if self.phase != 'run':
            return
        from tkinter import messagebox
        if not messagebox.askyesno('Ocarina Reborn', self.T('Build wirklich abbrechen?', 'Really cancel the build?')):
            return
        self.phase = 'cancelled'
        self.write_log(self.T('Build abgebrochen', 'Build cancelled'))
        if self.proc and self.proc.poll() is None:   # the whole tree: make_game, the compilers, hookshot.exe
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(self.proc.pid)], capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.close(back=True)

    def write_log(self, text):
        line = f'[{time.strftime("%H:%M:%S")}] {text}'
        self.log_lines.append(line)
        self.log_lines = self.log_lines[-400:]
        try:
            self.logf.write(line + '\n')
            self.logf.flush()
        except (OSError, ValueError):
            pass

    def handle(self, m):
        if 'log' in m:
            self.log_lines.append(f'      {m["log"]}')
            self.log_lines = self.log_lines[-400:]
            return
        if 'done' in m:
            if self.state.get(m['done']) != 'done':
                self.state[m['done']] = 'done'
                self.step_frac[m['done']] = 1.0
                self.done_at = getattr(self, 'done_at', {})
                self.done_at[m['done']] = time.time()
                self.write_log(dict(STEPS)[m['done']][0 if self.de else 1] + ' ✓')
            return
        if 'error' in m:
            kind, _, text = m['error'].partition(': ')
            st = m.get('step', 'nup')
            self.state[st] = 'failed'
            self.phase = 'failed'
            self.error = (self.T('Nicht unterstützte Spielversion. ', 'Unsupported game version. ') if kind == 'unsupported'
                          else '') + text
            self.write_log(self.T('FEHLER: ', 'ERROR: ') + m['error'])
            return
        if m.get('finished'):
            for s, _ in STEPS:
                self.state[s] = 'done'
            self.target = 100.0
            self.phase = 'done'
            self.write_log(self.T('Ocarina Reborn wurde erfolgreich erstellt.', 'Ocarina Reborn was built successfully.'))
            return
        if 'exit' in m:
            if self.phase == 'run':   # ended without "finished" and without an error line
                self.phase = 'failed'
                self.error = self.error or self.T(f'Der Build endete mit Code {m["exit"]}.', f'The build ended with code {m["exit"]}.')
                self.write_log(self.error)
            return
        st = m.get('step')
        if st in self.state:
            if self.state[st] == 'wait':
                self.write_log(STATUS[st][0 if self.de else 1])
            if self.state[st] != 'done':
                self.state[st] = 'run'
            self.step_frac[st] = m.get('frac', 0.0)
            self.target = max(self.target, float(m.get('total_pct', 0.0)))
            if 'count' in m and 'total' in m:
                u = UNITS.get(m.get('unit'), ('', ''))[0 if self.de else 1]
                self.counter = f'{fmt(m["count"], self.de)} / {fmt(m["total"], self.de)} {u}'
                if st in ('shaders', 'extract') and int(m['count']) % 5000 < 100 or m['count'] == m['total']:
                    self.write_log(self.counter)
            if str(m.get('text', '')).startswith('skipped: '):
                self.write_log(self.T('Shader werden beim ersten Start vorbereitet (', 'Shaders are prepared at the first start (')
                               + m['text'][9:] + ')')

    # ---- drawing
    def draw_static(self):
        c = self.c
        # (assets/build-bg.png: the Ocarina Reborn artwork with its title and BUILD; the progress where the design has it)
        self.y0 = 330
        self.bar = (130, 364, W - 130, 406)
        self.dyn = []

    def tick(self):
        if not self.c.winfo_exists():
            return
        try:
            while True:
                self.handle(self.q.get_nowait())
        except queue.Empty:
            pass
        # ease toward the real value: never past it, faster when far behind
        d = self.target - self.shown
        self.shown += d * 0.12 if abs(d) > 0.05 else d
        self.anim += 1
        self.redraw()
        if self.phase in ('run', 'done', 'failed'):
            self.c.after(33, self.tick)

    def place_background(self):
        """the screen is laid out at W x H and drawn into the window at k (the largest that fits, in the middle); the artwork
        is drawn at exactly that k from assets/build-bg.raw (2x, so it stays sharp), and the window's room on either side is
        filled with the same artwork, bigger, blurred and darker: no bars at any window shape. Drawn once per window size"""
        c = self.c
        cw, ch = c.winfo_width(), c.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = W, H
        k = min(cw / W, ch / H)
        self.fit = (k, (cw - W * k) / 2, (ch - H * k) / 2)
        if self.bg_state == (cw, ch):
            return
        self.bg_state = (cw, ch)
        photo = None
        try:
            photo = self.compose(cw, ch, k)
        except Exception:   # (no numpy or no raw artwork: the nearest prepared picture, as before)
            pct = min((100, 125, 150, 175, 200), key=lambda p: abs(p / 100 - k))
            name = 'build-bg' if pct == 100 else f'build-bg-{pct}'
            try:
                photo = self.img.get(name) or tk.PhotoImage(file=str(self.assets / f'{name}.png'))
                self.img[name] = photo
            except tk.TclError:
                photo = None
        if self.bg_item:
            c.delete(self.bg_item)
            self.bg_item = None
        if photo is not None:
            self.bg_photo = photo
            self.bg_item = c.create_image(cw / 2, ch / 2, image=photo, anchor='center')
            c.tag_lower(self.bg_item)

    def compose(self, cw, ch, k):
        import zlib
        import numpy as np
        if not hasattr(self, 'art'):
            raw = (self.assets / 'build-bg.raw').read_bytes()
            if raw[:6] != b'BGRAW1':
                raise ValueError('not the artwork')
            aw, ah = (int(v) for v in np.frombuffer(raw[6:10], '<u2'))
            self.art = np.frombuffer(zlib.decompress(raw[10:]), np.uint8).reshape(ah, aw, 3).astype(np.float32)
            a = self.art
            self.art_half = (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) / 4
            s = 16   # (a small copy for the blurred sides)
            hh, ww = ah // s * s, aw // s * s
            self.art_small = a[:hh, :ww].reshape(hh // s, s, ww // s, s, 3).mean((1, 3))

        def resample(src, w, h, x0=0.0, y0=0.0, sx=None, sy=None):
            """src sampled (bilinear) onto w x h: output pixel (i, j) reads src at (x0 + (i + .5) * sx - .5, ...)"""
            sh_, sw_ = src.shape[:2]
            sx = sx if sx is not None else sw_ / w
            sy = sy if sy is not None else sh_ / h
            xs = np.clip(x0 + (np.arange(w, dtype=np.float32) + 0.5) * sx - 0.5, 0, sw_ - 1)
            ys = np.clip(y0 + (np.arange(h, dtype=np.float32) + 0.5) * sy - 0.5, 0, sh_ - 1)
            xi, yi = np.minimum(xs.astype(np.int32), sw_ - 2), np.minimum(ys.astype(np.int32), sh_ - 2)
            fx, fy = (xs - xi)[None, :, None], (ys - yi)[:, None, None]
            a, b = src[yi][:, xi], src[yi][:, xi + 1]
            c_, d = src[yi + 1][:, xi], src[yi + 1][:, xi + 1]
            return (a * (1 - fx) + b * fx) * (1 - fy) + (c_ * (1 - fx) + d * fx) * fy

        # the sides: the artwork covering the window, blurred (from the small copy) and darker
        sm = self.art_small
        kc = max(cw / sm.shape[1], ch / sm.shape[0])
        out = resample(sm, cw, ch, (sm.shape[1] - cw / kc) / 2, (sm.shape[0] - ch / kc) / 2, 1 / kc, 1 / kc) * 0.45
        # the middle: the artwork at exactly k (from the 2x art, or its half when that is closer)
        iw, ih = max(1, round(W * k)), max(1, round(H * k))
        src = self.art if k > 1.0 else self.art_half   # (the art is 2x: below 1x its half is the sharper source)
        mid = resample(src, iw, ih)
        ox, oy = (cw - iw) // 2, (ch - ih) // 2
        f = max(1.0, 28 * k)   # (its edges fade into the sides)
        ax = np.clip(np.minimum(np.arange(iw) + 0.5, iw - np.arange(iw) - 0.5) / f, 0, 1)
        ay = np.clip(np.minimum(np.arange(ih) + 0.5, ih - np.arange(ih) - 0.5) / f, 0, 1)
        if ox <= 0:
            ax[:] = 1
        if oy <= 0:
            ay[:] = 1
        al = (ay[:, None] * ax[None, :])[..., None]
        x0, y0 = max(0, ox), max(0, oy)
        sx0, sy0 = x0 - ox, y0 - oy
        wv, hv = min(iw - sx0, cw - x0), min(ih - sy0, ch - y0)
        region = out[y0:y0 + hv, x0:x0 + wv]
        out[y0:y0 + hv, x0:x0 + wv] = region + (mid[sy0:sy0 + hv, sx0:sx0 + wv] - region) * al[sy0:sy0 + hv, sx0:sx0 + wv]
        b = np.clip(out, 0, 255).astype(np.uint8)
        return tk.PhotoImage(master=self.c, data=b'P6 %d %d 255 ' % (cw, ch) + b.tobytes(), format='PPM')

    def redraw(self):
        self.place_background()
        self.draw()
        k, ox, oy = self.fit
        if abs(k - 1) > 0.01 or abs(ox) > 0.5 or abs(oy) > 0.5:   # (Tk's fonts already follow Windows' scaling)
            for i in self.dyn:
                self.c.scale(i, 0, 0, k, k)
                self.c.move(i, ox, oy)

    def draw(self):
        c = self.c
        for i in self.dyn:
            c.delete(i)
        self.dyn = []
        add = self.dyn.append
        x0, y0, x1, y1 = self.bar
        r = (y1 - y0) // 2
        pulse = 0.5 + 0.5 * math.sin(self.anim / 14)
        glow = [('#0b3a7a', 9), ('#1458b8', 5), ('#2f86ff' if pulse > 0.5 else '#2a78e6', 2)]
        for col, wdt in glow:   # the glowing frame
            add(c.create_line(x0 + r, y0, x1 - r, y0, fill=col, width=wdt))
            add(c.create_line(x0 + r, y1, x1 - r, y1, fill=col, width=wdt))
            add(c.create_arc(x0, y0, x0 + 2 * r, y1, start=90, extent=180, style='arc', outline=col, width=wdt))
            add(c.create_arc(x1 - 2 * r, y0, x1, y1, start=-90, extent=180, style='arc', outline=col, width=wdt))
        add(c.create_rectangle(x0 + r, y0 + 2, x1 - r, y1 - 2, fill='#081430', outline=''))
        add(c.create_oval(x0 + 2, y0 + 2, x0 + 2 * r - 2, y1 - 2, fill='#081430', outline=''))
        add(c.create_oval(x1 - 2 * r + 2, y0 + 2, x1 - 2, y1 - 2, fill='#081430', outline=''))
        pct = max(0.0, min(100.0, self.shown))
        fw = (x1 - x0 - 6) * pct / 100
        fill = RED if self.phase == 'failed' else '#1f8bff'
        if fw > 2:
            fx1 = x0 + 3 + fw
            add(c.create_oval(x0 + 3, y0 + 4, x0 + 3 + 2 * (r - 4), y1 - 4, fill=fill, outline=''))
            add(c.create_rectangle(x0 + 3 + r - 4, y0 + 4, max(x0 + 3 + r - 4, fx1 - (r - 4)), y1 - 4, fill=fill, outline=''))
            add(c.create_oval(max(x0 + 3, fx1 - 2 * (r - 4)), y0 + 4, fx1, y1 - 4, fill=fill, outline=''))
            add(c.create_rectangle(x0 + r, y0 + 6, max(x0 + r, fx1 - r), y0 + 12, fill='#63b4ff', outline=''))   # top shine
            for k in range(0, int(fw), 26):   # diagonal stripes, drifting
                sx = x0 + 6 + k + (self.anim * 1.2) % 26
                if sx + 14 < fx1 - 6:
                    add(c.create_line(sx, y1 - 6, sx + 12, y0 + 6, fill='#3d9cff', width=5))
            if self.phase == 'run':   # the light sweep
                sw = x0 + ((self.anim * 6) % max(1, int(fw) + 120)) - 60
                if x0 + 8 < sw < fx1 - 8:
                    add(c.create_line(sw, y0 + 5, sw, y1 - 5, fill='#bfe6ff', width=3))
                    add(c.create_line(sw - 5, y0 + 6, sw - 5, y1 - 6, fill='#7cc4ff', width=2))
            add(c.create_line(fx1 - 2, y0 - 3, fx1 - 2, y1 + 3, fill='#cfeeff', width=2))
        add(c.create_text((x0 + x1) // 2 + 2, (y0 + y1) // 2 + 2, text=f'{pct:.0f}%', fill='#000000', font=('Segoe UI', 24, 'bold')))
        add(c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=f'{pct:.0f}%', fill=TEXT, font=('Segoe UI', 24, 'bold')))
        add(c.create_text(x1 - 6, y1 + 16, text=self.counter, fill=TEXT, anchor='e', font=('Segoe UI', 11)))

        # the steps
        sy = 455
        for i, (s, names) in enumerate(STEPS):
            y = sy + i * 31
            st = self.state[s]
            name = names[0 if self.de else 1]
            cx, right = 318, 802
            if i < len(STEPS) - 1:   # (a thin line under each row, as in the design)
                add(c.create_line(cx + 20, y + 15, 814, y + 15, fill='#16305e'))
            if st == 'run':
                add(c.create_rectangle(cx - 18, y - 14, 814, y + 14, fill='#0e2a5e', outline=''))
                add(c.create_line(cx - 18, y - 14, 814, y - 14, fill='#2a6fd6'))
                add(c.create_line(cx - 18, y + 14, 814, y + 14, fill='#2a6fd6'))
            if st == 'done':
                age = time.time() - getattr(self, 'done_at', {}).get(s, 0)
                rr = 11 if age > 0.25 else 6 + 20 * age   # (the check grows in)
                add(c.create_oval(cx - rr, y - rr, cx + rr, y + rr, fill=GREEN, outline=''))
                add(c.create_text(cx, y, text='✓', fill='#ffffff', font=('Segoe UI Symbol', 10, 'bold')))
            elif st == 'run':
                add(c.create_oval(cx - 11, y - 11, cx + 11, y + 11, outline='#1d3f7a', width=3))
                add(c.create_arc(cx - 11, y - 11, cx + 11, y + 11, start=-self.anim * 12, extent=110, style='arc',
                                 outline=CYAN, width=3))
            elif st == 'failed':
                add(c.create_oval(cx - 11, y - 11, cx + 11, y + 11, fill=RED, outline=''))
                add(c.create_text(cx, y, text='✕', fill='#ffffff', font=('Segoe UI Symbol', 10, 'bold')))
            else:
                add(c.create_oval(cx - 11, y - 11, cx + 11, y + 11, outline=GREY, width=2))
            col = {'run': TEXT, 'done': TEXT, 'failed': RED}.get(st, SUB)
            label = name + ('…' if st == 'run' else '')
            add(c.create_text(cx + 26, y, text=label, fill=col, anchor='w', font=('Segoe UI Semibold' if st == 'run' else 'Segoe UI', 12)))
            if st == 'run':
                add(c.create_text(right, y, text=f'{self.step_frac[s] * 100:.0f}%', fill=CYAN, anchor='e', font=('Segoe UI Semibold', 12)))

        # the message box at the bottom
        by = 645
        if self.phase == 'failed':
            msg, col = self.T('BUILD FEHLGESCHLAGEN — Fehler: ', 'BUILD FAILED — Error: ') + self.error, RED
        elif self.phase == 'done':
            msg, col = self.T('BUILD ABGESCHLOSSEN — Ocarina Reborn wurde erfolgreich erstellt.',
                              'BUILD COMPLETE — Ocarina Reborn was built successfully.'), GOLD
        else:
            msg = self.T('Der Build wird erstellt. Bitte das Fenster nicht schließen.',
                         'The build is running. Please do not close the window.')
            col = TEXT
        edge = '#2a8cff' if self.phase != 'failed' else RED
        add(c.create_rectangle(228, by, W - 229, by + 46, fill='#081633', outline=edge, width=2))
        add(c.create_rectangle(231, by + 3, W - 232, by + 43, outline='#123a7a', width=1))
        add(c.create_text(262, by + 23, text='ⓘ', fill=CYAN, font=('Segoe UI Symbol', 16)))
        add(c.create_text(288, by + 23, text=msg, fill=col, anchor='w', width=W - 540, font=('Segoe UI', 11)))

        # buttons
        if self.phase == 'run':
            self.btn(W - 160, H - 30, self.T('Abbrechen', 'Cancel'), self.cancel, '#3a2030')
        elif self.phase == 'done':
            self.btn(W - 170, H - 30, self.T('SPIEL STARTEN', 'START GAME'), lambda: self.close(done=True), BLUE, big=True)
        elif self.phase == 'failed':
            self.btn(W - 170, H - 30, self.T('Zurück', 'Back'), lambda: self.close(back=True), '#3a2030', big=True)
        self.btn(150, H - 30, self.T('Log ausblenden', 'Hide log') if self.show_log else self.T('Log anzeigen', 'Show log'),
                 self.toggle_log, '#14254d')
        if self.show_log:
            add(c.create_rectangle(40, 300, W - 40, H - 60, fill='#040a18', outline='#24396e'))
            lines = self.log_lines[-22:]
            add(c.create_text(52, 308, text='\n'.join(l[:150] for l in lines), fill='#b9c6e6', anchor='nw', font=('Consolas', 9)))

    def btn(self, x, y, text, cmd, bg, big=False):
        c, add = self.c, self.dyn.append
        f = ('Segoe UI Semibold', 15 if big else 10)
        w = (len(text) * (11 if big else 7)) // 2 + (34 if big else 16)
        h = 22 if big else 15
        tag = f'btn{len(self.dyn)}'
        add(c.create_rectangle(x - w, y - h, x + w, y + h, fill=bg, outline='#4c93ff' if big else '#2c4a86', tags=tag))
        add(c.create_text(x, y, text=text, fill=TEXT, font=f, tags=tag))
        c.tag_bind(tag, '<Button-1>', lambda e: cmd())
        c.tag_bind(tag, '<Enter>', lambda e: c.config(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda e: c.config(cursor=''))

    def toggle_log(self):
        self.show_log = not self.show_log

    def close(self, done=False, back=False):
        self.phase = 'closed' if self.phase not in ('done', 'failed', 'cancelled') else self.phase
        try:
            self.logf.close()
        except OSError:
            pass
        self.c.destroy()
        (self.on_done if done else self.on_back)()
