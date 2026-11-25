"""The animated BUILD screen: the forest artwork over the launcher window, showing ocarina_prepare.py's real progress.

Everything it reports comes from ocarina_prepare.py's JSON lines (the build's own output): which step runs, its measured
fraction, its counter (files, shaders) and the overall percentage. The animation only eases the drawn bar and number
toward the last real value (never past it) and decorates; a step without a measured fraction shows an indeterminate
spinner, not an invented percentage.

The picture (assets/build-forest.pack, made by tools/alpha/make_build_art.py from the reference artwork) is the scenery
with the interface's live parts taken out; this file draws those parts at the reference's positions, scaled to the window:

    layer                               how it is drawn
    scenery (forest, Ocarina, title)    one picture per window size (bicubic from the art; the window's room beyond 16:9
                                        filled with the same art, blurred and darker)
    sunlight, Ocarina glow, title glow  pre-rendered translucent sprites whose few frames are swapped slowly
    title highlight                     a light band sweeping across the letters only (their mask), every few seconds
    energy rings                        light running along the painted rings; hidden where the ring passes behind
                                        the Ocarina (its mask)
    particles, sparkles                 small sprites moved by the canvas (no picture is redrawn for them)
    progress bar                        its inside rendered with numpy at 30 frames a second from the real value
    rows, status, buttons, window keys  canvas text and small sprites (anti-aliased, drawn at the window's pixels)

All sprites are made at the window's own pixels (sharp at any size and Windows scaling); Windows' "animation effects"
off (or OCARINA_REDUCED_MOTION=1) keeps the screen still apart from the bar's value and the active step's spinner.
"""
import base64
import json
import math
import os
import queue
import random
import struct
import subprocess
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import zlib
from pathlib import Path

import numpy as np

import pt_br
from pt_br import tr

STEPS = [('nup', ('NUP-Dateien vorbereiten', 'Preparing the NUP file')),
         ('extract', ('Spielressourcen extrahieren', 'Extracting game resources')),
         ('analyze', ('ROM-Daten analysieren', 'Analysing the game code')),
         ('build', ('Build erstellen', 'Compiling the game')),
         ('finish', ('Installation abschließen', 'Finishing the installation')),
         ('shaders', ('Shader kompilieren', 'Compiling shaders'))]
STATUS = {'nup': ('NUP-Datei wird geprüft …', 'Checking the NUP file …'),
          'extract': ('Spielressourcen werden extrahiert …', 'Extracting game resources …'),
          'analyze': ('ROM-Daten werden analysiert …', 'Analysing the game code …'),
          'build': ('Der Build wird erstellt. Bitte das Fenster nicht schließen.',
                    'The build is running. Please do not close the window.'),
          'finish': ('Installation wird abgeschlossen …', 'Finishing the installation …'),
          'shaders': ('Shader werden kompiliert …', 'Compiling shaders …')}
UNITS = {'files': ('Dateien', 'files'), 'shaders': ('Shader', 'shaders')}
DOC_GLYPH = ''     # (Segoe Fluent Icons' page with lines: the reference's log icon)
LOG_BOX = (470, 508, 1202, 744)   # where the log shows (over the rows), in the reference's pixels
W, H = 1672, 941          # the reference artwork's size: every position below is in its pixels


def fmt(n, de):
    s = f'{n:,}'
    return s.replace(',', '.') if de or pt_br.UI_LANG[0] == 'pt-BR' else s


def reduced_motion():
    """Windows' "Show animations in Windows" off (SPI_GETCLIENTAREAANIMATION), or OCARINA_REDUCED_MOTION=1"""
    if os.environ.get('OCARINA_REDUCED_MOTION') == '1':
        return True
    try:
        import ctypes
        v = ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(v), 0):
            return not v.value
    except (AttributeError, OSError):
        pass
    return False


# ---- pictures for Tk ---------------------------------------------------------------------------------------------------
def to_photo(master, a):
    """a uint8 H x W x 3 (PPM) or H x W x 4 (PNG, its alpha blended by Tk over what is under it) array as a PhotoImage"""
    a = np.ascontiguousarray(a)
    h, w = a.shape[:2]
    if a.shape[2] == 3:
        return tk.PhotoImage(master=master, data=b'P6 %d %d 255 ' % (w, h) + a.tobytes(), format='PPM')
    raw = np.zeros((h, w * 4 + 1), np.uint8)
    raw[:, 1:] = a.reshape(h, w * 4)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
           chunk(b'IDAT', zlib.compress(raw.tobytes(), 1)) + chunk(b'IEND', b''))
    return tk.PhotoImage(master=master, data=base64.b64encode(png).decode('ascii'), format='png')


def rgba(color, alpha):
    """color (3,) + alpha (H, W) 0..1 -> uint8 RGBA"""
    h, w = alpha.shape
    out = np.empty((h, w, 4), np.uint8)
    out[..., :3] = np.asarray(color, np.uint8)
    out[..., 3] = np.clip(alpha * 255 + 0.5, 0, 255).astype(np.uint8)
    return out


def cubic(x):
    x = np.abs(x)
    return np.where(x < 1, 1.5 * x ** 3 - 2.5 * x ** 2 + 1,
                    np.where(x < 2, -0.5 * x ** 3 + 2.5 * x ** 2 - 4 * x + 2, 0.0))


def resize_axis(a, n, axis, x0=0.0, scale=None):
    """a resampled along axis to n samples (bicubic; antialiased when shrinking): sample i reads a at
    x0 + (i + .5) * scale - .5 (scale default: a's length / n)"""
    m = a.shape[axis]
    scale = m / n if scale is None else scale
    s = max(scale, 1.0)
    centers = x0 + (np.arange(n) + 0.5) * scale - 0.5
    taps = int(math.ceil(2 * s)) * 2 + 1
    left = np.floor(centers - 2 * s).astype(np.int64) + 1
    pos = left[:, None] + np.arange(taps)[None, :]
    wts = cubic((pos - centers[:, None]) / s)
    wts /= np.maximum(wts.sum(1, keepdims=True), 1e-6)
    pos = np.clip(pos, 0, m - 1)
    a = np.moveaxis(a, axis, 0)
    out = np.zeros((n,) + a.shape[1:], np.float32)
    for t in range(taps):
        out += a[pos[:, t]] * wts[:, t].reshape((n,) + (1,) * (a.ndim - 1)).astype(np.float32)
    return np.moveaxis(out, 0, axis)


def resize(a, w, h, box=None):
    """a (H x W [x C]) resized to w x h; box (x0, y0, x1, y1) in a's pixels: only that part"""
    a = a.astype(np.float32)
    if box is None:
        box = (0, 0, a.shape[1], a.shape[0])
    x0, y0, x1, y1 = box
    a = resize_axis(a, h, 0, y0, (y1 - y0) / h)
    return resize_axis(a, w, 1, x0, (x1 - x0) / w)


def blur(a, r):
    """a cheap gaussian-like blur: three box passes along each axis"""
    r = max(1, int(r))
    a = a.astype(np.float32)
    for axis in (0, 1):
        for _ in range(3):
            c = np.cumsum(np.pad(a, [(r + 1, r) if i == axis else (0, 0) for i in range(a.ndim)], mode='edge'), axis)
            hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis)
            lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis)
            a = (hi - lo) / (2 * r + 1)
    return a


def disc(n, sigma):
    """a soft dot: n x n gaussian 0..1"""
    c = (n - 1) / 2
    yy, xx = np.mgrid[0:n, 0:n]
    return np.exp(-((xx - c) ** 2 + (yy - c) ** 2) / (2 * sigma ** 2))


def star(n, k=1.0):
    """a four-pointed sparkle 0..1, n x n"""
    c = (n - 1) / 2
    yy, xx = np.mgrid[0:n, 0:n]
    dx, dy = np.abs(xx - c) / (n / 2), np.abs(yy - c) / (n / 2)
    rays = np.exp(-dy / 0.05) * np.clip(1 - dx, 0, 1) ** 2 + np.exp(-dx / 0.05) * np.clip(1 - dy, 0, 1) ** 2
    core = np.exp(-(dx ** 2 + dy ** 2) / 0.015)
    return np.clip(rays * 0.9 + core, 0, 1) * k


def sdf_round_rect(xx, yy, x0, y0, x1, y1, r):
    """signed distance to a rounded rectangle (negative inside)"""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    qx, qy = np.abs(xx - cx) - hx, np.abs(yy - cy) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def load_pack(path):
    raw = Path(path).read_bytes()
    if raw[:8] != b'OCRPACK1':
        raise ValueError('not the build artwork')
    n = struct.unpack('<I', raw[8:12])[0]
    head = json.loads(raw[12:12 + n])
    base = 12 + n
    arrays = {}
    for name, e in head['index'].items():
        b = zlib.decompress(raw[base + e['offset']:base + e['offset'] + e['length']])
        arrays[name] = np.frombuffer(b, e['dtype']).reshape(e['shape'])
    return arrays, head['geom']


# ---- the screen --------------------------------------------------------------------------------------------------------
class BuildScreen:
    def __init__(self, app, cmd, assets, de, log_path, on_done, on_back, version, window=None):
        """window: dict(minimize=, maximize=, close=, drag=, controls=bool): the launcher's window calls; controls: the
        screen draws the window's own buttons (the launcher's caption is its own: ui.Chrome), else Windows draws them"""
        self.app, self.cmd, self.de, self.on_done, self.on_back = app, cmd, de, on_done, on_back
        self.window = window
        self.T = lambda d, e: d if de else tr(e)
        self.assets = Path(assets)
        self.c = tk.Canvas(app, highlightthickness=0, bd=0, bg='#04140f')
        self.c.place(x=0, y=0, relwidth=1, relheight=1)
        self.art, self.geom = load_pack(self.assets / 'build-forest.pack')
        self.bgf = self.art['bg'].astype(np.float32)
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logf = open(self.log_path, 'a', encoding='utf-8')
        self.build_log = self.find_build_log(cmd)
        self.q = queue.Queue()
        self.state = {s: 'wait' for s, _ in STEPS}      # wait, run, done, failed, cancelled, skipped
        self.step_frac = {s: 0.0 for s, _ in STEPS}
        self.measured = {s: False for s, _ in STEPS}    # (a fraction above 0 came in: the step's % is shown)
        self.done_at = {}
        self.counter = ''
        self.target = 0.0
        self.shown = 0.0
        self.phase = 'run'      # run, done, failed, cancelled
        self.error = ''
        self.note = ''
        self.version = version
        self.proc = None
        self.log_lines = []
        self.show_log = False
        self.confirm = None     # (Abbrechen once: the question; its time)
        self.closing_app = False
        self.still = reduced_motion()
        self.t0 = time.perf_counter()
        self.frame = 0
        self.hover = self.pressed = None
        self.layout_state = None
        self.items, self.sprites = {}, {}
        self.finished_at = None
        self.write_log(self.T('Build gestartet', 'Build started'))
        self.c.bind('<Configure>', lambda e: self.schedule_layout())
        self.c.bind('<Motion>', self.motion)
        self.c.bind('<Leave>', lambda e: self.set_hover(None))
        self.c.bind('<ButtonPress-1>', self.press)
        self.c.bind('<ButtonRelease-1>', self.release)
        self.c.bind('<Double-Button-1>', self.double)
        self.c.bind('<Escape>', self.escape)
        self.c.focus_set()
        self.prev_protocol = None
        try:   # (the window's own close button and Alt+F4 while the build runs: the same safe way as Abbrechen)
            self.prev_protocol = app.protocol('WM_DELETE_WINDOW')
            app.protocol('WM_DELETE_WINDOW', self.request_close)
        except tk.TclError:
            pass
        self.layout_job = None
        self.start()
        self.c.after(10, self.relayout)
        self.tick()

    # ---- the process (unchanged contract with ocarina_prepare.py)
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

    @staticmethod
    def find_build_log(cmd):
        """the build's own full log: ocarina_prepare.py writes <--logs>/build.log (a replay: the recorded log)"""
        try:
            if '--replay' in cmd:
                return Path(cmd[cmd.index('--replay') + 1])
            if '--logs' in cmd:
                return Path(cmd[cmd.index('--logs') + 1]) / 'build.log'
        except IndexError:
            pass
        return None

    def cancel_now(self):
        """the build's safe stop, as before: the whole process tree ends (make_game, the compilers, the shader
        preparation); build-state.json stays, so the launcher offers to resume or start again (resume_page), and the
        game folder's saves were backed up before the build began (run_build)"""
        if self.phase != 'run':
            return
        self.phase = 'cancelled'
        for s, _ in STEPS:
            if self.state[s] == 'run':
                self.state[s] = 'cancelled'
        self.write_log(self.T('Build abgebrochen', 'Build cancelled'))
        if self.proc and self.proc.poll() is None:
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(self.proc.pid)], capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def ask_cancel(self, closing=False):
        if self.phase != 'run':
            return
        self.confirm = time.perf_counter()
        self.closing_app = closing

    def request_close(self):
        """the window's close button / Alt+F4: while the build runs, the same question as Abbrechen, then the stop and the
        launcher's own quit"""
        if self.phase == 'run':
            return self.ask_cancel(closing=True)
        self.close(back=True, then_quit=True)

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
        if self.phase == 'cancelled':
            return
        if 'skip' in m:   # (a step this kind of build does not have, e.g. the NUP check of an update)
            if m['skip'] in self.state and self.state[m['skip']] in ('wait', 'run'):
                self.state[m['skip']] = 'skipped'
            return
        if 'done' in m:
            s = m['done']
            if s in self.state and self.state[s] not in ('done', 'skipped'):
                self.state[s] = 'done'
                self.step_frac[s] = 1.0
                self.done_at[s] = time.perf_counter()
                self.write_log(self.T(*dict(STEPS)[s][:2]) + ' ✓')
            return
        if 'error' in m:
            kind, _, text = m['error'].partition(': ')
            st = m.get('step', 'nup')
            if st in self.state:
                self.state[st] = 'failed'
            self.phase = 'failed'
            self.error = (self.T('Nicht unterstützte Spielversion. ', 'Unsupported game version. ') if kind == 'unsupported'
                          else '') + tr(text)
            self.write_log(self.T('FEHLER: ', 'ERROR: ') + m['error'])
            return
        if m.get('finished'):
            for s, _ in STEPS:
                if self.state[s] != 'skipped':
                    if self.state[s] != 'done':
                        self.done_at[s] = time.perf_counter()
                    self.state[s] = 'done'
            self.target = 100.0
            self.phase = 'done'
            self.finished_at = time.perf_counter()
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
                self.write_log(self.T(*STATUS[st][:2]))
            if self.state[st] not in ('done', 'skipped'):
                self.state[st] = 'run'
            f = min(max(float(m.get('frac', 0.0)), 0.0), 1.0)
            self.step_frac[st] = f
            if f > 0:
                self.measured[st] = True
            self.target = max(self.target, min(100.0, float(m.get('total_pct', 0.0))))
            if 'count' in m and 'total' in m:
                total = max(int(m['total']), 0)
                count = min(max(int(m['count']), 0), total)   # (never "761 / 760")
                u = self.T(*UNITS.get(m.get('unit'), ('', ''))[:2])
                self.counter = f'{fmt(count, self.de)} / {fmt(total, self.de)} {u}'
                if st in ('shaders', 'extract') and count % 5000 < 100 or count == total:
                    self.write_log(self.counter)
            else:
                self.counter = ''
            text = str(m.get('text', ''))
            if text.startswith('skipped: '):
                self.note = self.T('Shader werden beim ersten Spielstart vorbereitet.',
                                   'Shaders are prepared at the first start of the game.')
                self.write_log(self.T('Shader werden beim ersten Start vorbereitet (', 'Shaders are prepared at the first start (')
                               + text[9:] + ')')

    # ---- layout: everything scaled from the reference's pixels to the window ------------------------------------------
    def P(self, x, y):
        k, ox, oy = self.fit
        return ox + x * k, oy + y * k

    def S(self, v):
        return v * self.fit[0]

    def font(self, family, px, weight='normal'):
        return (family, -max(6, int(round(px * self.fit[0]))), weight)

    def schedule_layout(self):
        if self.layout_job:
            self.c.after_cancel(self.layout_job)
        self.layout_job = self.c.after(90, self.relayout)

    def relayout(self):
        self.layout_job = None
        cw, ch = self.c.winfo_width(), self.c.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = max(cw, self.app.winfo_width(), 400), max(ch, self.app.winfo_height(), 240)
        if self.layout_state == (cw, ch):
            return
        self.layout_state = (cw, ch)
        k = min(cw / W, ch / H)
        self.fit = (k, (cw - W * k) / 2, (ch - H * k) / 2)
        self.cw, self.ch = cw, ch
        self.c.delete('all')
        self.items, self.sprites = {}, {}
        self.make_background()
        self.make_sprites()
        self.make_items()
        self.update_items(force=True)

    def make_background(self):
        """the scenery at exactly the window's scale; outside the 16:9 picture the same art, blurred and darker"""
        k, ox, oy = self.fit
        cw, ch = self.cw, self.ch
        art = self.bgf
        iw, ih = max(1, round(W * k)), max(1, round(H * k))
        mid = resize(art, iw, ih)
        if (iw, ih) != (cw, ch):
            small = blur(resize(art, W // 8, H // 8), 3)
            kc = max(cw / small.shape[1], ch / small.shape[0])
            vw, vh = cw / kc, ch / kc
            out = resize(small, cw, ch, ((small.shape[1] - vw) / 2, (small.shape[0] - vh) / 2,
                                         (small.shape[1] + vw) / 2, (small.shape[0] + vh) / 2)) * 0.42
            x0, y0 = int(round(ox)), int(round(oy))
            f = max(1.0, 24 * k)
            ax = np.clip(np.minimum(np.arange(iw) + 0.5, iw - np.arange(iw) - 0.5) / f, 0, 1) if x0 > 0 else np.ones(iw)
            ay = np.clip(np.minimum(np.arange(ih) + 0.5, ih - np.arange(ih) - 0.5) / f, 0, 1) if y0 > 0 else np.ones(ih)
            al = (ay[:, None] * ax[None, :])[..., None]
            sx0, sy0 = max(0, -x0), max(0, -y0)
            dx0, dy0 = max(0, x0), max(0, y0)
            wv, hv = min(iw - sx0, cw - dx0), min(ih - sy0, ch - dy0)
            reg = out[dy0:dy0 + hv, dx0:dx0 + wv]
            out[dy0:dy0 + hv, dx0:dx0 + wv] = reg + (mid[sy0:sy0 + hv, sx0:sx0 + wv] - reg) * al[sy0:sy0 + hv, sx0:sx0 + wv]
        else:
            out = mid
        self.bg_pixels = np.clip(out, 0, 255).astype(np.uint8)
        self.bg_photo = to_photo(self.c, self.bg_pixels)
        self.c.create_image(0, 0, image=self.bg_photo, anchor='nw', tags='bg')

    def sprite_box(self, x0, y0, x1, y1):
        """a design box -> its window pixels (x, y, w, h), whole pixels"""
        X0, Y0 = self.P(x0, y0)
        X1, Y1 = self.P(x1, y1)
        X0, Y0 = int(math.floor(X0)), int(math.floor(Y0))
        return X0, Y0, max(1, int(math.ceil(X1)) - X0), max(1, int(math.ceil(Y1)) - Y0)

    def grid(self, X0, Y0, w, h):
        """the design coordinates of a window-pixel box's pixel centres"""
        k, ox, oy = self.fit
        xs = (X0 + np.arange(w) + 0.5 - ox) / k
        ys = (Y0 + np.arange(h) + 0.5 - oy) / k
        return np.meshgrid(xs, ys)

    def mask_at(self, name, box, X0, Y0, w, h):
        """one of the pack's masks (made for box, design px) at a window-pixel box"""
        m = self.art[name].astype(np.float32) / 255
        k, ox, oy = self.fit
        bx0, by0 = box[0], box[1]
        sx0 = (X0 - ox) / k - bx0
        sy0 = (Y0 - oy) / k - by0
        out = resize_axis(m, h, 0, sy0, 1 / k)
        out = resize_axis(out, w, 1, sx0, 1 / k)
        return np.clip(out, 0, 1)

    def make_sprites(self):
        g, k, c = self.geom, self.fit[0], self.c
        sp = self.sprites
        # the slow light layers (sunlight, the Ocarina's and the title's glow, the title's highlight) are not canvas
        # sprites: Tk would blend them again over the whole window for every moving particle. They are blended into the
        # scenery picture itself, only where they are and only when their frame changes (refresh_lights)
        self.lights = {}
        # sunlight through the leaves: soft beams, their brightness in 8 slow steps
        sp['rays'] = []
        for ri, (x0, y0, x1, y1) in enumerate(g['rays']):
            X0, Y0, w, h = self.sprite_box(x0, y0, x1, y1)
            xx, yy = self.grid(X0, Y0, w, h)
            # beams fall from the top corner toward the middle of the picture
            ox_, oy_ = (x1, y0) if ri == 0 else (x0, y0)
            ang = math.radians(124 if ri == 0 else 52)
            ux, uy = math.cos(ang), math.sin(ang)
            along = (xx - ox_) * ux + (yy - oy_) * uy
            across = -(xx - ox_) * uy + (yy - oy_) * ux
            span = max(x1 - x0, y1 - y0)
            fade = np.clip(along / (0.12 * span), 0, 1) * np.clip(1 - along / span, 0, 1) ** 1.5
            edge = np.clip(np.minimum(np.minimum(xx - x0, x1 - xx), np.minimum(yy - y0, y1 - yy)) / 30, 0, 1)
            beams = [(-70, 26), (-10, 18), (55, 34), (120, 22), (170, 16)] if ri == 0 else [(-40, 20), (30, 26), (90, 16)]
            frames = []
            for f in range(8):
                a = np.zeros_like(xx)
                for bi, (off, wd) in enumerate(beams):
                    lvl = 0.55 + 0.45 * math.sin(2 * math.pi * f / 8 + bi * 1.9)
                    spread = wd * (0.5 + along / span)
                    a += lvl * np.exp(-((across - off * (0.6 + 0.6 * along / span)) / np.maximum(spread, 1)) ** 2)
                al = np.clip(a * fade * edge * (0.13 if ri == 0 else 0.08), 0, 0.35)
                frames.append((al * 255 + 0.5).astype(np.uint8))
            self.lights[f'rays{ri}'] = dict(box=(X0, Y0, w, h), color=(255, 226, 150), frames=frames, frame=0)
        # the Ocarina's breathing glow: a blue halo around (not over) the instrument
        cx, cy, ax_, ay_ = g['glow']
        X0, Y0, w, h = self.sprite_box(cx - ax_ * 1.3, cy - ay_ * 1.3, cx + ax_ * 1.3, cy + ay_ * 1.3)
        xx, yy = self.grid(X0, Y0, w, h)
        r2 = ((xx - cx) / ax_) ** 2 + ((yy - cy) / ay_) ** 2
        occ = self.mask_at('occ', g['ocarina'], X0, Y0, w, h)
        halo = np.exp(-r2 * 1.6) * (1 - 0.85 * occ)
        edge = np.clip(np.minimum(np.minimum(xx - (cx - ax_ * 1.3), (cx + ax_ * 1.3) - xx),
                                  np.minimum(yy - (cy - ay_ * 1.3), (cy + ay_ * 1.3) - yy)) / 40, 0, 1)
        self.lights['glow'] = dict(box=(X0, Y0, w, h), color=(70, 150, 255), frame=3,
                                   frames=[(halo * edge * (0.05 + 0.03 * i) * 255 + 0.5).astype(np.uint8) for i in range(6)])
        # the title: its green letters' glow (breathing) and a light band sweeping across all its letters
        lx0, ly0, lx1, ly1 = g['logo']
        X0, Y0, w, h = self.sprite_box(lx0, ly0, lx1, ly1)
        green = self.mask_at('green', g['logo'], X0, Y0, w, h)
        letters = self.mask_at('letters', g['logo'], X0, Y0, w, h)
        gl = blur(green, 5 * k)
        gl = gl / max(gl.max(), 1e-3)
        self.lights['logo_glow'] = dict(box=(X0, Y0, w, h), color=(120, 255, 120), frame=2,
                                        frames=[(gl * (0.06 + 0.035 * i) * 255 + 0.5).astype(np.uint8) for i in range(5)])
        xx, yy = self.grid(X0, Y0, w, h)
        shine = []
        for i in range(14):
            pos = lx0 - 120 + (lx1 - lx0 + 240) * i / 13
            band = np.exp(-((xx - pos + (yy - ly0) * 0.45) / 38) ** 2)
            shine.append((letters * band * 0.55 * 255 + 0.5).astype(np.uint8))
        self.lights['shine'] = dict(box=(X0, Y0, w, h), color=(255, 255, 240), frames=shine, frame=None)
        # particles and sparkles
        def dot(r, col, peak):
            n = max(3, int(round(r * 4 * k)) | 1)
            return to_photo(c, rgba(col, disc(n, n / 5.5) * peak))
        sp['dots'] = {
            'blue': [dot(3.0, (110, 200, 255), p) for p in (0.35, 0.65, 0.95)],
            'green': [dot(2.6, (150, 255, 160), p) for p in (0.3, 0.6, 0.9)],
            'gold': [dot(2.2, (255, 230, 160), p) for p in (0.3, 0.55, 0.85)],
            'spark': [dot(1.6, (200, 240, 255), p) for p in (0.4, 0.7, 1.0)],
        }
        n = max(5, int(round(26 * k)) | 1)
        sp['star'] = [to_photo(c, rgba((255, 250, 225), star(n, s))) for s in (0.3, 0.6, 0.9, 0.6, 0.3)]
        sp['comet'] = [dot(r, (170, 230, 255), p) for r, p in ((5.2, 0.95), (4.4, 0.8), (3.8, 0.62), (3.2, 0.48),
                                                                (2.6, 0.36), (2.2, 0.25), (1.8, 0.16))]
        # the status panel's border light
        n = max(5, int(round(70 * k)))
        m = max(3, int(round(10 * k)))
        yy, xx = np.mgrid[0:m, 0:n]
        a = np.exp(-((xx - (n - 1) / 2) / (n / 5)) ** 2 - ((yy - (m - 1) / 2) / (m / 5)) ** 2)
        sp['edge_light'] = to_photo(c, rgba((255, 236, 170), a * 0.9))
        # the log's panel: dark glass with a thin gold edge, over the rows
        X0, Y0, w, h = self.sprite_box(*LOG_BOX)
        xx, yy = self.grid(X0, Y0, w, h)
        d = sdf_round_rect(xx, yy, LOG_BOX[0] + 2, LOG_BOX[1] + 2, LOG_BOX[2] - 2, LOG_BOX[3] - 2, 12)
        body = np.clip(0.5 - d * k, 0, 1)
        edge = np.clip(1 - np.abs(d + 1.5) * k / 1.0, 0, 1)
        glow = np.exp(-np.maximum(d, 0) / 3.0) * (d > 0)
        v = np.clip((yy - LOG_BOX[1]) / (LOG_BOX[3] - LOG_BOX[1]), 0, 1)
        out = np.zeros((h, w, 4), np.float32)
        out[..., 0], out[..., 1], out[..., 2] = 3 + 4 * v, 18 + 10 * v, 17 + 12 * v
        out[..., 3] = body * 0.93
        e = np.clip(edge + glow * 0.35, 0, 1)
        for i, cc in enumerate((214, 182, 104)):
            out[..., i] = out[..., i] * (1 - e) + cc * e
        out[..., 3] = np.maximum(out[..., 3], e * 0.95)
        sp['log_panel'] = (X0, Y0, to_photo(c, np.clip(out * [1, 1, 1, 255], 0, 255).astype(np.uint8)))
        # the rows: icons, the spinner, the active row's highlight
        self.make_row_sprites()
        self.make_button_sprites()
        self.make_bar()

    def make_row_sprites(self):
        g, k, c = self.geom, self.fit[0], self.c
        sp = self.sprites
        n = int(math.ceil(40 * k)) | 1
        ctr = (n - 1) / 2
        ss = 3   # (supersampled: anti-aliased rings and marks)
        yy, xx = np.mgrid[0:n * ss, 0:n * ss]
        X = ((xx + 0.5) / ss - 0.5 - ctr) / k
        Y = ((yy + 0.5) / ss - 0.5 - ctr) / k
        R = np.hypot(X, Y)
        down = lambda a: a.reshape(n, ss, n, ss).mean((1, 3))

        def ring(r, wd):
            return down(np.clip(wd / 2 - np.abs(R - r) + 0.5, 0, 1).astype(np.float32))

        def seg(ax, ay, bx, by, wd):
            px, py = X - ax, Y - ay
            dx, dy = bx - ax, by - ay
            t = np.clip((px * dx + py * dy) / (dx * dx + dy * dy), 0, 1)
            d = np.hypot(px - t * dx, py - t * dy)
            return down(np.clip(wd / 2 - d + 0.5, 0, 1).astype(np.float32))

        def glow_of(a, r):
            return np.clip(blur(a, r * k) * 2.2, 0, 1)

        def icon(layers):
            out = np.zeros((n, n, 4), np.float32)
            for col, al in layers:
                a = np.clip(al, 0, 1)[..., None]
                out[..., :3] = out[..., :3] * (1 - a) + np.asarray(col, np.float32) * a
                out[..., 3:] = out[..., 3:] + a * (1 - out[..., 3:])
            out[..., :3] = np.where(out[..., 3:] > 0, out[..., :3], 0)
            return to_photo(c, np.clip(out * [1, 1, 1, 255], 0, 255).astype(np.uint8))

        rg = ring(12.2, 2.4)
        check = np.maximum(seg(-5.6, 0.4, -1.6, 4.6, 2.8), seg(-1.6, 4.6, 6.0, -4.4, 2.8))
        inner = down((R < 11.0).astype(np.float32))
        done = [((6, 38, 15), inner * 0.55), ((40, 200, 70), glow_of(rg, 3) * 0.5), ((96, 236, 96), rg),
                ((214, 255, 205), check)]
        flash = [((90, 255, 120), glow_of(rg + check, 5) * 0.9)] + done[1:]
        sp['icon_done'] = icon(done)
        sp['icon_flash'] = icon(flash)
        sp['icon_wait'] = icon([((84, 124, 130), ring(12.2, 1.7) * 0.85)])
        x_ = np.maximum(seg(-4.5, -4.5, 4.5, 4.5, 2.6), seg(-4.5, 4.5, 4.5, -4.5, 2.6))
        sp['icon_failed'] = icon([((80, 10, 10), inner * 0.5), ((255, 90, 80), glow_of(rg, 3) * 0.45),
                                  ((255, 110, 100), rg), ((255, 225, 220), x_)])
        sp['icon_skipped'] = icon([((80, 110, 116), ring(12.2, 1.6) * 0.7), ((120, 150, 156), seg(-5, 0, 5, 0, 2.2))])
        sp['icon_cancelled'] = icon([((150, 120, 90), ring(12.2, 1.8) * 0.85), ((220, 190, 150), seg(-5, 0, 5, 0, 2.4))])
        # the spinner: a cyan ring, its bright arc turning (24 frames)
        th = np.arctan2(Y, X)
        Rr = np.hypot(X, Y)
        spin = []
        for f in range(24):
            a0 = 2 * math.pi * f / 24
            d = (th - a0) % (2 * math.pi)
            # (the reference: a thick bright cyan ring, brightest at its head, with one short dark gap)
            on = d < 1.8 * math.pi
            body = np.clip(2.4 - np.abs(Rr - 12.4) * 0.95, 0, 1) * on
            lvl = 0.7 + 0.3 * np.clip(1 - d / (1.8 * math.pi), 0, 1)
            rr = down((body * lvl).astype(np.float32))
            core = down((np.clip(1.7 - np.abs(Rr - 12.4) * 1.25, 0, 1) * on * lvl).astype(np.float32))
            spin.append(icon([((30, 150, 255), glow_of(rr, 3.5)), ((90, 210, 255), rr), ((225, 250, 255), core)]))
        sp['spinner'] = spin
        # the active row's highlight (the reference's last row): a small box round the spinner and a long bar, blue glass
        ax0, ay0, ax1, ay1 = g['active']
        X0, Y0, w, h = self.sprite_box(ax0 - 8, ay0 - 8, ax1 + 8, ay1 + 8)
        xx, yy = self.grid(X0, Y0, w, h)
        cyc = (ay0 + ay1) / 2
        sp['active_off'] = cyc - (ay0 - 8)

        def part(x0, x1, r):
            d = sdf_round_rect(xx, yy, x0, ay0, x1, ay1, r)
            fill = np.clip(0.5 - d * k, 0, 1)
            line = np.clip(1 - np.abs(d) * k / 1.1, 0, 1)
            glow = np.exp(-np.maximum(d, 0) / 4.5) * (d > -1)
            return fill, line, glow
        f1, l1, g1 = part(ax0, ax0 + 52, 7)
        f2, l2, g2 = part(ax0 + 58, ax1, 9)
        v = np.clip((yy - ay0) / (ay1 - ay0), 0, 1)
        body = np.maximum(f1, f2)
        shade = np.stack([16 + 20 * v, 70 + 40 * v, 150 + 50 * v], -1)
        out = np.zeros((h, w, 4), np.float32)
        out[..., :3] = shade
        out[..., 3] = body * (0.55 + 0.15 * v)
        lines = np.clip(np.maximum(l1, l2) + np.maximum(g1, g2) * 0.35, 0, 1)
        lc = np.array([110, 200, 255], np.float32)
        a = lines[..., None]
        out[..., :3] = out[..., :3] * (1 - a) + lc * a
        out[..., 3] = np.maximum(out[..., 3], lines * 0.95)
        sp['active'] = to_photo(c, np.clip(out * [1, 1, 1, 255], 0, 255).astype(np.uint8))
        # the counter's and labels' fonts
        sans = self.sans()   # (the reference's lettering: a narrow humanist sans; its numbers and buttons a serif)
        self.f_row = self.font(sans, 20.5)
        self.f_pct = self.font(sans, 20.5)
        self.f_counter = self.font(sans, 17)
        self.f_status = self.font(sans, 21)
        self.f_status_small = self.font(sans, 17)
        self.f_big = self.font(self.serif(), 54)
        self.f_btn = self.font(self.serif2(), 20.5)
        self.f_log = self.font('Consolas', 13)
        self.f_icon = self.font(self.icon_font(), 25)
        self.f_icon_s = self.font(self.icon_font(), 19)
        self.fonts = {}

    @staticmethod
    def has_font(name):
        try:
            return name in tkfont.families()
        except tk.TclError:
            return False

    def sans(self):
        return next((f for f in ('Calibri', 'Segoe UI') if self.has_font(f)), 'Segoe UI')

    def serif(self):
        return next((f for f in ('Palatino Linotype', 'Book Antiqua', 'Cambria', 'Georgia') if self.has_font(f)), 'Georgia')

    def serif2(self):
        return next((f for f in ('Cambria', 'Constantia', 'Georgia') if self.has_font(f)), 'Georgia')

    def icon_font(self):
        return next((f for f in ('Segoe Fluent Icons', 'Segoe MDL2 Assets') if self.has_font(f)), 'Segoe UI Symbol')

    def make_button_sprites(self):
        """hover and press: the button's own picture (from the scenery), brighter or darker, inside its outline"""
        g, c = self.geom, self.c
        self.btn_sprites = {}
        for name in ('btn_left', 'btn_right'):
            x0, y0, x1, y1 = g[name]
            X0, Y0, w, h = self.sprite_box(x0, y0, x1, y1)
            X0c, Y0c = max(0, X0), max(0, Y0)
            crop = self.bg_pixels[Y0c:Y0c + h, X0c:X0c + w].astype(np.float32)
            if crop.shape[:2] != (h, w):
                continue
            xx, yy = self.grid(X0, Y0, w, h)
            cy = (y0 + y1) / 2
            # the outline: a long hexagon (pointed ends), as the reference's frame
            dx = np.maximum(0, np.abs(xx - (x0 + x1) / 2) - ((x1 - x0) / 2 - 16))
            inside = np.abs(yy - cy) + dx * 1.45 < (y1 - y0) / 2 - 1
            soft = np.clip(blur(inside.astype(np.float32), 1.2 * self.fit[0]), 0, 1)
            hov = crop * 1.18 + np.array([10, 22, 24], np.float32)
            prs = crop * 0.82
            self.btn_sprites[name] = (X0, Y0, {
                'hover': to_photo(c, np.dstack([np.clip(hov, 0, 255), soft * 255]).astype(np.uint8)),
                'press': to_photo(c, np.dstack([np.clip(prs, 0, 255), soft * 255]).astype(np.uint8))})
        # the right button as "Zum Launcher" (done): the left button's teal frame at its place
        if 'btn_left' in self.btn_sprites:
            lx0, ly0, lx1, ly1 = g['btn_left']
            rx0, ry0, rx1, ry1 = g['btn_right']
            X0, Y0, w, h = self.sprite_box(lx0, ly0, lx1, ly1)
            X1, Y1, w1, h1 = self.sprite_box(rx0, ry0, rx0 + (lx1 - lx0), ry0 + (ly1 - ly0))
            crop = self.bg_pixels[Y0:Y0 + h, X0:X0 + w]
            if crop.shape[:2] == (h, w):
                xx, yy = self.grid(X0, Y0, w, h)
                cy = (ly0 + ly1) / 2
                dx = np.maximum(0, np.abs(xx - (lx0 + lx1) / 2) - ((lx1 - lx0) / 2 - 10))
                inside = np.abs(yy - cy) + dx * 1.3 < (ly1 - ly0) / 2 + 2
                soft = np.clip(blur(inside.astype(np.float32), 1.0 * self.fit[0]), 0, 1)
                self.teal_right = (X1, Y1, to_photo(c, np.dstack([crop, soft * 255]).astype(np.uint8)),
                                   to_photo(c, np.dstack([np.clip(crop * 1.18 + [10, 22, 24], 0, 255), soft * 255])
                                            .astype(np.uint8)))

    def make_bar(self):
        """the bar's inside, prepared once per size: the empty bar (from the scenery), its shape, the gems' places, and
        every per-pixel term that does not change from frame to frame"""
        g = self.geom
        k = self.fit[0]
        bx0, by0, bx1, by1 = g['bar_box']
        X0, Y0, w, h = self.sprite_box(bx0, by0, bx1, by1)
        X0, Y0 = max(0, X0), max(0, Y0)
        w, h = min(w, self.cw - X0), min(h, self.ch - Y0)
        self.bar_px = (X0, Y0, w, h)
        self.bar_base = self.bg_pixels[Y0:Y0 + h, X0:X0 + w].astype(np.float32)
        xx, yy = self.grid(X0, Y0, w, h)
        xx, yy = xx.astype(np.float32), yy.astype(np.float32)
        x0, y0, x1, y1 = g['bar']
        r = (y1 - y0) / 2
        cy = (y0 + y1) / 2
        d = np.hypot(np.maximum(0, np.maximum(x0 + r - xx, xx - (x1 - r))), yy - cy) - r
        inside = np.clip(0.5 - d * k, 0, 1)
        for gx, gy, gh in g['gems']:
            gem = np.abs(xx - gx) + np.abs(yy - gy) - (gh + 2)
            inside *= np.clip(gem * k * 0.7, 0, 1)
        # (only the rows the inside covers are rendered each frame)
        rows = np.where(inside.max(1) > 0)[0]
        self.bar_rows = slice(int(rows.min()), int(rows.max()) + 1) if len(rows) else slice(0, h)
        R = self.bar_rows
        self.bar_xs = xx[0]                                 # design x of each column
        self.bar_ys = yy[R, 0]                              # design y of each rendered row
        self.bar_inside = inside[R]
        v = np.clip((self.bar_ys - y0) / (y1 - y0), 0, 1)[:, None]
        self.bar_v = v
        self.bar_u = np.clip((self.bar_xs - x0) / (x1 - x0), 0, 1)[None, :]
        mix = np.clip((self.bar_xs - x0) / 520, 0, 1)[None, :, None]
        shade = (0.55 + 0.2 * np.exp(-((v - 0.5) / 0.3) ** 2) + 0.75 * np.exp(-((v - 0.2) / 0.12) ** 2)
                 + 0.35 * np.exp(-((v - 0.86) / 0.1) ** 2))[..., None]
        self.bar_col = {}
        for phase, a_, b_ in (('run', (14, 120, 190), (24, 150, 52)), ('failed', (170, 40, 36), (210, 70, 50)),
                              ('cancelled', (70, 90, 96), (100, 120, 110))):
            self.bar_col[phase] = ((np.array(a_, np.float32) * (1 - mix) + np.array(b_, np.float32) * mix) * shade
                                   ).astype(np.float32)
        self.bar_blue = np.clip(1.2 - mix[..., 0] * 1.1, 0.15, 1).astype(np.float32)   # (1, w)
        self.bar_r, self.bar_cy = r, cy
        # the decoration beside the number: two small gems on thin gold lines (the reference has them on the fill)
        px, py = g['pct']
        deco = np.zeros_like(xx)
        col = np.zeros(xx.shape + (3,), np.float32)
        for dxc, dyc in g['pct_diamonds']:
            dd = np.abs(xx - dxc) + np.abs(yy - dyc)
            ring_ = np.clip(1 - np.abs(dd - 7.5) * k / 1.2, 0, 1)
            core = np.clip((5.5 - dd) * k, 0, 1)
            side = 1 if dxc > px else -1
            line = np.clip(1 - np.abs(yy - dyc) * k / 0.9, 0, 1) * ((xx - dxc) * side > 8) * ((xx - dxc) * side < 46)
            line *= np.clip(1 - ((xx - dxc) * side - 8) / 38, 0, 1)
            a = np.maximum(np.maximum(ring_, line * 0.8), core)
            deco = np.maximum(deco, a)
            c_ = np.where(core[..., None] > ring_[..., None], [[[150, 255, 170]]], [[[240, 210, 130]]])
            col = np.where(a[..., None] > 0.01, c_, col)
        Rr = self.bar_rows   # (the gems lie inside the rendered rows)
        self.bar_deco = (deco[Rr][..., None].astype(np.float32), col[Rr].astype(np.float32))
        cols = np.where(deco.max(0) > 0.004)[0]
        self.bar_deco_cols = (int(cols.min()), int(cols.max()) + 1) if len(cols) else (0, 0)
        # small stamps for the sparks and leaves (window pixels)
        n = max(3, int(round(9 * k)) | 1)
        self.stamp_spark = disc(n, n / 5.0).astype(np.float32)
        n = max(5, int(round(18 * k)) | 1)
        self.stamp_burst = disc(n, n / 5.0).astype(np.float32)
        self.stamp_leaves = []
        n = max(5, int(round(22 * k)) | 1)
        cc = (n - 1) / 2
        ly, lx = np.mgrid[0:n, 0:n]
        for i in range(8):
            ang = i * math.pi / 8
            ca, sa = math.cos(ang), math.sin(ang)
            dx, dy = (lx - cc) / k, (ly - cc) / k
            a_ = (dx * ca + dy * sa) / 7.5
            b_ = (-dx * sa + dy * ca) / 3.2
            self.stamp_leaves.append(np.clip((1 - (a_ ** 2 + b_ ** 2 * (1 + 0.6 * a_ ** 2))) * 3, 0, 1).astype(np.float32))
        rng = np.random.default_rng(5)
        self.bar_sparks = rng.random((44, 4))     # u, v, speed, phase
        self.bar_leaves = rng.random((9, 4))
        self.bar_photo = None

    @staticmethod
    def clip_box(shape, st, X, Y):
        n = st.shape[0]
        x0, y0 = int(round(X)) - n // 2, int(round(Y)) - n // 2
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(shape[1], x0 + n), min(shape[0], y0 + n)
        if cx0 >= cx1 or cy0 >= cy1:
            return None
        return (slice(cy0, cy1), slice(cx0, cx1)), (slice(cy0 - y0, cy1 - y0), slice(cx0 - x0, cx1 - x0))

    def blend_stamp(self, img, st, X, Y, color, k):
        """img (H x W x 3) blended toward color by stamp st (0..1) times k, at column X / row Y"""
        b = self.clip_box(img.shape, st, X, Y)
        if b:
            dst, src = b
            a = st[src][..., None] * k
            img[dst] += (color - img[dst]) * a

    def add_stamp(self, img, st, X, Y, color):
        b = self.clip_box(img.shape, st, X, Y)
        if b:
            dst, src = b
            img[dst] += st[src][..., None] * color

    @staticmethod
    def stamp(layer, st, X, Y, k=1.0):
        """adds stamp st, centred at column X / row Y of layer (clipped), times k"""
        n = st.shape[0]
        x0, y0 = int(round(X)) - n // 2, int(round(Y)) - n // 2
        H_, W_ = layer.shape[:2]
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(W_, x0 + n), min(H_, y0 + n)
        if cx0 < cx1 and cy0 < cy1:
            layer[cy0:cy1, cx0:cx1] += st[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0] * k

    def render_bar(self, t):
        """the bar's inside for this moment: the real value's fill with its flowing light, sparks and a bright edge.
        Only the filled columns of the inside's rows are computed"""
        g = self.geom
        x0, y0, x1, y1 = g['bar']
        k, ox = self.fit[0], self.fit[1]
        X0b = self.bar_px[0]
        pct = max(0.0, min(100.0, self.shown))
        fx = x0 + (x1 - x0) * pct / 100
        r, cy = self.bar_r, self.bar_cy
        R = self.bar_rows
        out = self.bar_base[R].copy()   # (only the inside's rows change; returned with their offset)
        row0 = self.bar_ys[0]
        tt = 0 if self.still else t
        col_of = lambda x: ox + x * k - X0b      # design x -> column
        row_of = lambda y: (y - row0) * k        # design y -> rendered row
        last = int(min(len(self.bar_xs), np.searchsorted(self.bar_xs, fx + 14)))
        if pct > 0.05 and last > 0:
            C = slice(0, last)
            ys = self.bar_ys[:, None]
            v = self.bar_v
            u1 = self.bar_u[0, C]                      # (1-D: per column)
            # the fill's shape: the bar's inside up to the value, its end a round cap (computed only at the cap)
            fill = self.bar_inside[:, C].copy()
            cap0 = int(np.searchsorted(self.bar_xs, fx - max(r, (fx - x0) / 2) - 2))
            if cap0 < last:
                xs = self.bar_xs[cap0:last][None, :]
                if fx - x0 < 2 * r:
                    cap = np.hypot(xs - (x0 + (fx - x0) / 2), ys - cy) - (fx - x0) / 2
                else:
                    cap = np.hypot(np.maximum(0, xs - (fx - r)), ys - cy) - r
                fill[:, cap0 - 0:] *= np.clip(0.5 - cap * k, 0, 1)
            phase = self.phase if self.phase in ('failed', 'cancelled') else 'run'
            col = self.bar_col[phase][:, C].copy()
            if phase == 'run':
                # the two ribbons of light are soft: computed on every second pixel and doubled (a quarter of the work)
                vh, uh = v[::2], u1[None, ::2]
                w1 = np.exp(-((vh - 0.5 - 0.22 * np.sin(uh * 9.0 - tt * 1.6)) / 0.07) ** 2)
                w2 = np.exp(-((vh - 0.5 - 0.18 * np.sin(uh * 13.0 + 1.3 - tt * 2.3)) / 0.05) ** 2)
                bh = self.bar_blue[:, C][:, ::2]
                hh, ww = col.shape[:2]
                add = np.stack([w1 * 33 * bh + w2 * 52, w1 * 94 + w2 * 89, w1 * (140 * bh + 66 * (1 - bh)) + w2 * 60], -1)
                col += np.repeat(np.repeat(add, 2, 0), 2, 1)[:hh, :ww]
                col *= (0.92 + 0.08 * np.sin(u1 * 40 - tt * 3.0))[None, :, None]
                leafc = np.array([120, 235, 110], np.float32)
                for lu, lv, ls, lp in self.bar_leaves:      # leaves carried along inside the fill (each where it is)
                    lx = x0 + ((lu + tt * 0.025 * (0.6 + ls)) % 1.0) * (x1 - x0)
                    if lx > fx - 10:
                        continue
                    ly = y0 + 14 + lv * (y1 - y0 - 28) + 4 * math.sin(tt * 1.4 + lp * 6)
                    self.blend_stamp(col, self.stamp_leaves[int((lp * 8 + tt * 0.6) % 8)], col_of(lx), row_of(ly), leafc, 0.75)
                sparkc = np.array([180, 230, 207], np.float32)
                for su, sv, ss_, sph in self.bar_sparks:      # sparks drifting through it
                    sx = x0 + ((su + tt * (0.04 + 0.08 * ss_)) % 1.0) * (x1 - x0)
                    if sx > fx - 4:
                        continue
                    sy = y0 + 8 + sv * (y1 - y0 - 16)
                    self.add_stamp(col, self.stamp_spark, col_of(sx), row_of(sy), sparkc * (0.5 + 0.5 * math.sin(tt * 5 + sph * 9)))
            sub = out[:, C]
            sub += (col - sub) * fill[..., None]
            if self.phase != 'failed':   # the bright edge at the value and its halo, only near it
                e0 = int(np.searchsorted(self.bar_xs, fx - 40))
                e1 = int(min(len(self.bar_xs), np.searchsorted(self.bar_xs, fx + 40)))
                if e0 < e1:
                    xs = self.bar_xs[e0:e1][None, :]
                    pulse = 0.85 + 0.15 * math.sin(t * 4.0) if not self.still else 1.0
                    f_ = np.zeros((fill.shape[0], e1 - e0), np.float32)
                    m = min(e1, last) - e0
                    f_[:, :m] = fill[:, e0:e0 + m]
                    edge = np.exp(-((xs - (fx - 6)) / 7.0) ** 2) * f_
                    halo = np.exp(-((xs - fx) / 10.0) ** 2) * np.exp(-((ys - cy) / 20) ** 2) * self.bar_inside[:, e0:e1] * (1 - f_)
                    seg = out[:, e0:e1] if e1 > last else out[:, e0:e1]
                    seg += edge[..., None] * (np.array([150, 255, 240], np.float32) * pulse) \
                        + halo[..., None] * np.array([36, 120, 114], np.float32)
        # the gems beside the number (only where they are), then the finishing sparkle
        a, c_ = self.bar_deco
        d0, d1 = self.bar_deco_cols
        out[:, d0:d1] += (c_[:, d0:d1] - out[:, d0:d1]) * a[:, d0:d1]
        if self.finished_at and not self.still:
            age = t - (self.finished_at - self.t0)
            if age < 1.6:
                burst = np.zeros(out.shape[:2], np.float32)
                for su, sv, ss_, sph in self.bar_sparks[:28]:
                    life = math.sin(math.pi * min(1, max(0, age * 1.2 - sph * 0.5)))
                    self.stamp(burst, self.stamp_burst, col_of(x0 + su * (x1 - x0)),
                               row_of(y0 + 6 + sv * (y1 - y0 - 12)), life)
                out += burst[..., None] * np.array([230, 255, 210], np.float32)
                sx = x0 + (x1 - x0) * min(1, age / 0.9)
                sweep = np.exp(-((self.bar_xs - sx) / 30) ** 2)[None, :] * self.bar_inside
                out += sweep[..., None] * np.array([120, 160, 120], np.float32) * max(0, 1 - age / 1.6)
        return np.clip(out, 0, 255).astype(np.uint8), 0, R.start

    # ---- the canvas items ---------------------------------------------------------------------------------------------
    def make_items(self):
        g, c, sp = self.geom, self.c, self.sprites
        it = self.items
        if self.still:   # (no sunlight beams in reduced motion: they are the most moving part of the scenery)
            for n in ('rays0', 'rays1'):
                self.lights[n]['frame'] = None
        for k in self.lights:
            self.refresh_lights([k])
        # energy on the rings
        it['comets'] = []
        if not self.still:
            for ri in range(len(g['rings'])):
                it['comets'].append([c.create_image(-50, -50, image=img, anchor='center') for img in sp['comet']])
        # particles
        self.parts = []
        if not self.still:
            rnd = random.Random(1)
            for i in range(46):
                kind = ('blue', 'green', 'blue', 'gold')[i % 4] if i < 34 else 'spark'
                p = dict(kind=kind, item=c.create_image(-50, -50, image=sp['dots'][kind][0], anchor='center'))
                self.respawn(p, rnd, first=True)
                self.parts.append(p)
            self.sparkles = [dict(item=c.create_image(-50, -50, image=sp['star'][0], anchor='center', state='hidden'),
                                  at=rnd.uniform(0.5, 4.0), where=None) for _ in range(3)]
        else:
            self.sparkles = []
        # the bar (its picture is rendered each frame), the number, the counter
        X0, Y0, w, h = self.bar_px
        self.bar_photo = to_photo(c, self.bar_base.astype(np.uint8))
        it['bar'] = c.create_image(X0, Y0, image=self.bar_photo, anchor='nw')
        px, py = self.P(*g['pct'])
        it['pct_shadow'] = c.create_text(px + self.S(1.2), py + self.S(1.8), text='', fill='#0d3a16', font=self.f_big)
        it['pct'] = c.create_text(px, py - self.S(1), text='', fill='#f3fbef', font=self.f_big)
        cx, cy = self.P(*g['counter'])
        it['counter'] = c.create_text(cx, cy, text='', fill='#e2ecee', anchor='e', font=self.f_counter)
        # the rows
        it['active'] = c.create_image(0, 0, image=sp['active'], anchor='nw', state='hidden')
        it['rows'] = []
        for i, (s, names) in enumerate(STEPS):
            ix, iy = self.P(g['row_icon_x'], g['rows'][i])
            lx, _ = self.P(g['row_label_x'], g['rows'][i])
            rx, _ = self.P(g['row_pct_x'], g['rows'][i])
            it['rows'].append(dict(
                icon=c.create_image(ix, iy, image=sp['icon_wait'], anchor='center'),
                label=c.create_text(lx, iy, text=self.T(*names[:2]), fill='#7f989e', anchor='w', font=self.f_row),
                pct=c.create_text(rx, iy, text='', fill='#ffffff', anchor='e', font=self.f_pct)))
        # the status panel
        x0, y0, x1, y1 = g['panel']
        it['edge'] = c.create_image(-50, -50, image=sp['edge_light'], anchor='center',
                                    state='hidden' if self.still else 'normal')
        ix, iy = self.P(*g['panel_icon'])
        it['status_icon'] = c.create_text(ix, iy, text='', fill='#d9eef4', font=self.f_icon)
        tx, ty = self.P(*g['panel_text'])
        it['status'] = c.create_text(tx, ty, text='', fill='#f2f7f6', anchor='w', font=self.f_status)
        # the buttons
        self.buttons = {}
        for name in ('btn_left', 'btn_right'):
            x0, y0, x1, y1 = g[name]
            b = dict(box=(x0, y0, x1, y1))
            if name in self.btn_sprites:
                X0, Y0, imgs = self.btn_sprites[name]
                b['over'] = c.create_image(X0, Y0, image=imgs['hover'], anchor='nw', state='hidden')
            if name == 'btn_right' and hasattr(self, 'teal_right'):
                X1, Y1, img, img_h = self.teal_right
                b['teal'] = c.create_image(X1, Y1, image=img, anchor='nw', state='hidden')
            ix, iy = self.P(*g[name + '_icon'])
            b['icon'] = c.create_text(ix, iy, text='', fill='#f0ebdc', font=self.f_icon_s)
            lx, ly = self.P(*g[name + '_label'])
            b['label'] = c.create_text(lx, ly, text='', fill='#f3efe4', anchor='w', font=self.f_btn)
            self.buttons[name] = b
        # the window's own buttons (the launcher's caption is its own)
        self.winbtns = []
        if self.window and self.window.get('controls'):
            import ui
            for (gx, gy), name in zip(g['winctl'], ('minimize', 'maximize', 'close')):
                X, Y = self.P(gx, gy)
                hl = c.create_rectangle(X - self.S(22), Y - self.S(18), X + self.S(22), Y + self.S(18), fill='#a52a1e'
                                        if name == 'close' else '#1b4f43', outline='', state='hidden')
                glyph = 'restore' if name == 'maximize' and self.app.state() == 'zoomed' else name
                t = c.create_text(X, Y, text=ui.GLYPH[glyph], fill='#e6d6a2', font=self.font(self.icon_font(), 15))
                self.winbtns.append(dict(name=name, center=(gx, gy), hl=hl, text=t))
        # the log (over the rows, when shown)
        X0, Y0, img = sp['log_panel']
        it['log_bg'] = c.create_image(X0, Y0, image=img, anchor='nw', state='hidden')
        it['log_title'] = c.create_text(0, 0, text='', fill='#e8d9a6', anchor='nw', font=self.font('Segoe UI Semibold', 16),
                                        state='hidden')
        it['log_open'] = c.create_text(0, 0, text='', fill='#86e0ff', anchor='ne', font=self.font('Segoe UI', 15),
                                       state='hidden')
        it['log_text'] = c.create_text(0, 0, text='', fill='#bcd3cf', anchor='nw', font=self.f_log, state='hidden')
        self.last = {}

    def respawn(self, p, rnd=random, first=False):
        """a particle: drifting slowly up through the forest, mostly at the sides and in the upper picture (not over the
        text), or a small blue spark near the Ocarina"""
        if p['kind'] == 'spark':
            cx, cy, a, b, ang = self.geom['rings'][0]
            th = rnd.uniform(0, 2 * math.pi)
            p['x'] = cx + a * 1.05 * math.cos(th) + rnd.uniform(-20, 20)
            p['y'] = cy + b * 1.4 * math.sin(th) + rnd.uniform(-30, 20)
            p['vx'], p['vy'] = rnd.uniform(-6, 6), rnd.uniform(-14, -4)
            p['life'] = rnd.uniform(1.2, 2.6)
        else:
            zone = rnd.random()
            if zone < 0.36:
                p['x'], p['y'] = rnd.uniform(0, 470), rnd.uniform(380, 940)
            elif zone < 0.72:
                p['x'], p['y'] = rnd.uniform(1200, 1672), rnd.uniform(380, 940)
            else:
                p['x'], p['y'] = rnd.uniform(0, 1672), rnd.uniform(0, 380)
            p['vx'], p['vy'] = rnd.uniform(-9, 9), rnd.uniform(-16, -5)
            p['life'] = rnd.uniform(3.5, 8.0)
        p['age'] = rnd.uniform(0, p['life']) if first else 0.0
        p['tw'] = rnd.uniform(0, 6.28)

    # ---- every frame --------------------------------------------------------------------------------------------------
    def tick(self):
        if not self.c.winfo_exists():
            return
        try:
            while True:
                self.handle(self.q.get_nowait())
        except queue.Empty:
            pass
        now = time.perf_counter()
        t = now - self.t0
        dt = min(0.1, t - getattr(self, 'last_t', t))
        self.last_t = t
        # ease toward the real value: never past it
        d = self.target - self.shown
        self.shown += d * min(1.0, dt * 6.0) if abs(d) > 0.05 else d
        if self.confirm and now - self.confirm > 10 and self.phase == 'run':
            self.confirm = None
            self.closing_app = False
        if self.phase == 'cancelled' and not getattr(self, 'left', False):
            self.left = True
            then_quit = self.closing_app
            self.c.after(250, lambda: self.close(back=True, then_quit=then_quit))
        self.frame += 1
        visible = True
        try:
            visible = self.app.state() != 'iconic' and self.c.winfo_ismapped()
        except tk.TclError:
            pass
        if visible and self.items:
            self.animate(t, dt)
            if t - getattr(self, 'bar_t', -1.0) >= 0.031:   # (the bar and the texts: 30 times a second)
                self.bar_t = t
                self.update_items()
                self.draw_bar(t)
        if self.phase in ('run', 'done', 'failed', 'cancelled'):
            # 60 frames a second; 30 while the compilers or the shader preparation keep every CPU thread busy (and in a
            # window bigger than 1440p), so the screen takes as little as it can from them. (Windows' timer runs in ~15.6 ms steps: the wait is what is
            # left of the frame, a little early)
            busy = self.phase == 'run' and any(self.state[s] == 'run' for s in ('build', 'shaders'))
            big = getattr(self, 'cw', 0) * getattr(self, 'ch', 0) > 4_000_000   # (a 4K window: Tk paints it in software)
            frame_ms = 33.3 if busy or big else 16.7
            # (Tk paints the canvas in its idle time: the next frame is queued behind that painting, never ahead of it,
            # so a slow machine gets fewer frames instead of a screen that is never painted)
            wait = max(6, int(frame_ms - (time.perf_counter() - now) * 1000) - 4)
            self.c.after(wait, lambda: self.c.after_idle(self.tick) if self.c.winfo_exists() else None)

    def draw_bar(self, t):
        if not self.bar_photo:
            return
        key = (round(self.shown, 2), self.phase)
        if self.still and self.last.get('bar') == key:
            return
        self.last['bar'] = key
        px, x_off, y_off = self.render_bar(t)
        part = to_photo(self.c, px)
        self.bar_photo.tk.call(self.bar_photo.name, 'copy', part.name, '-to', x_off, y_off)

    def animate(self, t, dt):
        c, sp, it, g = self.c, self.sprites, self.items, self.geom
        if self.still:
            return
        # the slow light layers: each one's frame from the time; the picture is blended again only where one changed
        L = self.lights
        want = {'rays0': int(t * 1.6) % 8, 'rays1': int(t * 1.6 + 3) % 8,
                'glow': int((math.sin(t * 1.1) * 0.5 + 0.5) * 5.99),
                'logo_glow': int((math.sin(t * 0.9 + 1) * 0.5 + 0.5) * 4.99)}
        cyc = t % 6.0   # (the title's highlight: one sweep every 6 s)
        n = len(L['shine']['frames'])
        want['shine'] = min(n - 1, int(cyc / 1.1 * n)) if cyc < 1.1 else None
        changed = [k for k, v in want.items() if L[k]['frame'] != v]
        for k in changed:
            L[k]['frame'] = want[k]
        for k in changed:   # (each in its own box: one union of far-apart boxes would be most of the window)
            self.refresh_lights([k])
        # light running along the painted rings; behind the Ocarina it is hidden
        occ = self.art['occ']
        ox0, oy0 = g['ocarina'][:2]
        for ri, dots in enumerate(it['comets']):
            cx, cy, a, b, ang = g['rings'][ri]
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            head = (t * (0.55 if ri == 0 else -0.42) + ri * 2.1) % (2 * math.pi)
            for j, item in enumerate(dots):
                th = head - (0.075 * j if ri == 0 else -0.075 * j)
                ex, ey = a * math.cos(th), b * math.sin(th)
                x, y = cx + ex * ca - ey * sa, cy + ex * sa + ey * ca
                hidden = False
                if math.sin(th) < 0.15:   # (the far half of the ring)
                    ix, iy = int(x - ox0), int(y - oy0)
                    if 0 <= iy < occ.shape[0] and 0 <= ix < occ.shape[1] and occ[iy, ix] > 90:
                        hidden = True
                X, Y = self.P(x, y)
                c.coords(item, X, Y)
                c.itemconfigure(item, state='hidden' if hidden else 'normal')
        # particles
        for p in self.parts:
            p['age'] += dt
            if p['age'] > p['life']:
                self.respawn(p)
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt + math.sin(t * 0.7 + p['tw']) * 4 * dt
            life = math.sin(math.pi * p['age'] / p['life'])
            lvl = life * (0.7 + 0.3 * math.sin(t * 3 + p['tw']))
            X, Y = self.P(p['x'], p['y'])
            c.coords(p['item'], X, Y)
            v = 0 if lvl < 0.33 else 1 if lvl < 0.66 else 2
            if p.get('v') != v:
                p['v'] = v
                c.itemconfigure(p['item'], image=sp['dots'][p['kind']][v])
        # sparkles near the flowers
        for s in self.sparkles:
            if s['where'] is None and t > s['at']:
                s['where'] = random.choice(g['flowers'])
                s['at'] = t
                X, Y = self.P(s['where'][0] + random.uniform(-12, 12), s['where'][1] + random.uniform(-12, 12))
                c.coords(s['item'], X, Y)
                c.itemconfigure(s['item'], state='normal')
            if s['where'] is not None:
                age = t - s['at']
                if age > 0.75:
                    s['where'] = None
                    s['at'] = t + random.uniform(1.0, 3.5)
                    c.itemconfigure(s['item'], state='hidden')
                else:
                    c.itemconfigure(s['item'], image=sp['star'][min(4, int(age / 0.75 * 5))])
        # the status panel's border light: along its top edge, then back along its bottom
        x0, y0, x1, y1 = g['panel']
        ph = (t % 7.0) / 7.0
        if ph < 0.5:
            x, y = x0 + 30 + (x1 - x0 - 60) * (ph / 0.5), y0 - 1
        else:
            x, y = x1 - 30 - (x1 - x0 - 60) * ((ph - 0.5) / 0.5), y1 + 1
        c.coords(it['edge'], *self.P(x, y))

    def refresh_lights(self, names):
        """the scenery picture again where the named light layers are: the plain scenery there with every light layer
        that overlaps it blended in (its current frame), copied into the canvas's picture"""
        L = self.lights
        boxes = [L[n]['box'] for n in names]
        x0 = max(0, min(b[0] for b in boxes))
        y0 = max(0, min(b[1] for b in boxes))
        x1 = min(self.cw, max(b[0] + b[2] for b in boxes))
        y1 = min(self.ch, max(b[1] + b[3] for b in boxes))
        if x1 <= x0 or y1 <= y0:
            return
        out = self.bg_pixels[y0:y1, x0:x1].astype(np.float32)
        for name in ('rays0', 'rays1', 'glow', 'logo_glow', 'shine'):
            lay = L.get(name)
            if not lay or lay['frame'] is None:
                continue
            bx, by, bw, bh = lay['box']
            ix0, iy0, ix1, iy1 = max(x0, bx), max(y0, by), min(x1, bx + bw), min(y1, by + bh)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            a = lay['frames'][lay['frame']][iy0 - by:iy1 - by, ix0 - bx:ix1 - bx].astype(np.float32)[..., None] / 255
            reg = out[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0]
            reg += (np.asarray(lay['color'], np.float32) - reg) * a
        part = to_photo(self.c, np.clip(out, 0, 255).astype(np.uint8))
        self.bg_photo.tk.call(self.bg_photo.name, 'copy', part.name, '-to', x0, y0)

    def set_text(self, item, text, **kw):
        key = (item, 'text')
        if self.last.get(key) != (text, tuple(sorted(kw.items()))):
            self.last[key] = (text, tuple(sorted(kw.items())))
            self.c.itemconfigure(item, text=text, **kw)

    def set_image(self, item, image, **kw):
        key = (item, 'img')
        if self.last.get(key) != (str(image), tuple(sorted(kw.items()))):
            self.last[key] = (str(image), tuple(sorted(kw.items())))
            self.c.itemconfigure(item, image=image, **kw)

    def update_items(self, force=False):
        if not self.items:
            return
        if force:
            self.last = {}
        g, c, sp, it = self.geom, self.c, self.sprites, self.items
        t = time.perf_counter() - self.t0
        pct = max(0.0, min(100.0, self.shown))
        self.set_text(it['pct'], f'{pct:.0f}%')
        self.set_text(it['pct_shadow'], f'{pct:.0f}%')
        self.set_text(it['counter'], self.counter if self.phase == 'run' else '')
        active = None
        for i, (s, names) in enumerate(STEPS):
            row = it['rows'][i]
            st = self.state[s]
            name = self.T(*names[:2])
            if st == 'done':
                age = time.perf_counter() - self.done_at.get(s, 0)
                img = sp['icon_flash'] if age < 0.7 and not self.still and int(age * 10) % 3 != 2 else sp['icon_done']
                self.set_image(row['icon'], img)
                self.set_text(row['label'], name, fill='#e9f3ee')
                self.set_text(row['pct'], '')
            elif st == 'run':
                active = i
                fr = sp['spinner'][int(t * (12 if self.still else 24)) % 24]
                self.set_image(row['icon'], fr)
                self.set_text(row['label'], name + ' …', fill='#ffffff')
                self.set_text(row['pct'], f'{self.step_frac[s] * 100:.0f}%' if self.measured[s] else '', fill='#ffffff')
            elif st == 'failed':
                self.set_image(row['icon'], sp['icon_failed'])
                self.set_text(row['label'], name, fill='#ff9d92')
                self.set_text(row['pct'], self.T('Fehler', 'Error'), fill='#ff9d92')
            elif st == 'cancelled':
                self.set_image(row['icon'], sp['icon_cancelled'])
                self.set_text(row['label'], name, fill='#d8c3a5')
                self.set_text(row['pct'], self.T('Abgebrochen', 'Cancelled'), fill='#d8c3a5')
            elif st == 'skipped':
                self.set_image(row['icon'], sp['icon_skipped'])
                self.set_text(row['label'], name, fill='#6f878c')
                self.set_text(row['pct'], self.T('nicht nötig', 'not needed'), fill='#6f878c')
            else:
                self.set_image(row['icon'], sp['icon_wait'])
                self.set_text(row['label'], name, fill='#9db3b8')
                self.set_text(row['pct'], '')
        if active is not None:
            ax0 = g['active'][0] - 8
            X, Y = self.P(ax0, g['rows'][active] - sp['active_off'])
            key = ('active', active, self.layout_state)
            if self.last.get('active') != key:
                self.last['active'] = key
                c.coords(it['active'], int(X), int(Y))
                c.itemconfigure(it['active'], state='hidden' if self.show_log else 'normal')
        elif self.last.get('active') is not None:
            self.last['active'] = None
            c.itemconfigure(it['active'], state='hidden')
        # the status
        icon_font = self.icon_font()
        import ui
        if self.confirm and self.phase == 'run':
            msg = self.T('Build wirklich abbrechen? Er kann danach fortgesetzt werden.',
                         'Really cancel the build? It can be resumed afterwards.')
            icon, icol, tcol = ui.GLYPH['warning'], '#f2c752', '#fff4d6'
        elif self.phase == 'failed':
            msg = self.T('Build fehlgeschlagen: ', 'Build failed: ') + (self.error or '')
            icon, icol, tcol = ui.GLYPH['warning'], '#ff8a80', '#ffd9d4'
        elif self.phase == 'cancelled':
            msg = self.T('Build abgebrochen.', 'Build cancelled.')
            icon, icol, tcol = ui.GLYPH['info'], '#d9eef4', '#f2f7f6'
        elif self.phase == 'done':
            msg = self.T('Installation erfolgreich abgeschlossen.', 'Installation completed successfully.')
            icon, icol, tcol = ui.GLYPH['check'], '#7dff9a', '#f2fff4'
        else:
            run = next((s for s, _ in STEPS if self.state[s] == 'run'), None)
            upd = '--update' in self.cmd
            if run in (None, 'build', 'nup', 'extract', 'analyze'):
                msg = self.T('Update wird installiert. Bitte das Fenster nicht schließen.' if upd else
                             'Der Build wird erstellt. Bitte das Fenster nicht schließen.',
                             'The update is being installed. Please do not close the window.' if upd else
                             'The build is running. Please do not close the window.') if run in (None, 'build') \
                    else self.T(*STATUS[run][:2])
            else:
                msg = self.T(*STATUS[run][:2])
            if self.note and run == 'shaders':
                msg = self.note
            icon, icol, tcol = ui.GLYPH['info'], '#d9eef4', '#f2f7f6'
        self.place_status(msg, icon, icol, tcol)
        # the buttons: what they do in this phase
        if self.phase == 'run':
            right = (self.T('Ja, abbrechen', 'Yes, cancel') if self.confirm else self.T('Abbrechen', 'Cancel'), ui.GLYPH['close'])
            left = (self.T('Weiter bauen', 'Keep building'), ui.GLYPH['play']) if self.confirm else \
                (self.T('Log ausblenden', 'Hide log') if self.show_log else self.T('Log anzeigen', 'Show log'), DOC_GLYPH)
        elif self.phase == 'done':
            right = (self.T('Zum Launcher', 'To the launcher'), ui.GLYPH['right'])
            left = (self.T('Log ausblenden', 'Hide log') if self.show_log else self.T('Log anzeigen', 'Show log'), DOC_GLYPH)
        else:
            right = (self.T('Zurück', 'Back'), ui.GLYPH['back'])
            left = (self.T('Log ausblenden', 'Hide log') if self.show_log else self.T('Log anzeigen', 'Show log'), DOC_GLYPH)
        for name, (label, glyph) in (('btn_left', left), ('btn_right', right)):
            b = self.buttons[name]
            self.set_text(b['icon'], glyph)
            self.set_text(b['label'], label)
            # (the label in the frame's middle, after its icon)
            x0, y0, x1, y1 = b['box']
            tw = self.measure(self.f_btn, label)
            iw = self.S(24)
            gap = self.S(15)
            total = iw + gap + tw
            mx = self.P((x0 + x1) / 2, 0)[0]
            start = mx - total / 2
            _, Y = self.P(0, (y0 + y1) / 2)
            if self.last.get((name, 'pos')) != (start, label):
                self.last[(name, 'pos')] = (start, label)
                c.coords(b['icon'], start + iw / 2, Y)
                c.coords(b['label'], start + iw + gap, Y)
            if 'teal' in b:
                want = 'normal' if self.phase == 'done' else 'hidden'
                if self.last.get((name, 'teal')) != want:
                    self.last[(name, 'teal')] = want
                    c.itemconfigure(b['teal'], state=want)
        self.update_hover_visuals()
        self.update_log()

    def measure(self, font, text):
        f = self.fonts.get(font)
        if f is None:
            f = self.fonts[font] = tkfont.Font(root=self.c, font=font)
        return f.measure(text)

    def place_status(self, msg, icon, icol, tcol):
        g, c, it = self.geom, self.c, self.items
        x0, y0, x1, y1 = g['panel']
        maxw = self.S(x1 - x0 - 110)
        key = (msg, icon, icol, tcol, self.layout_state)
        if self.last.get('status') == key:
            return
        self.last['status'] = key
        font = self.f_status
        if self.measure(font, msg) > maxw:
            font = self.f_status_small
        lines_w = min(maxw, self.measure(font, msg))
        iw = self.S(28)
        gap = self.S(14)
        total = iw + gap + lines_w
        mx, my = self.P((x0 + x1) / 2, (y0 + y1) / 2)
        start = mx - total / 2
        c.itemconfigure(it['status_icon'], text=icon, fill=icol)
        c.coords(it['status_icon'], start + iw / 2, my)
        c.itemconfigure(it['status'], text=msg, fill=tcol, font=font, width=int(maxw))
        c.coords(it['status'], start + iw + gap, my)

    def update_log(self):
        it, c = self.items, self.c
        rows = [i for r in it['rows'] for i in r.values()] + [it['active']]
        if not self.show_log:
            if self.last.get('log_shown'):
                self.last['log_shown'] = False
                for k in ('log_bg', 'log_title', 'log_open', 'log_text'):
                    c.itemconfigure(it[k], state='hidden')
                for i in rows:   # (the rows again; the active row's highlight as update_items left it)
                    c.itemconfigure(i, state='normal')
                if self.last.get('active') is None:
                    c.itemconfigure(it['active'], state='hidden')
            return
        X0, Y0 = self.P(LOG_BOX[0], LOG_BOX[1])
        X1, Y1 = self.P(LOG_BOX[2], LOG_BOX[3])
        if not self.last.get('log_shown'):
            self.last['log_shown'] = True
            c.coords(it['log_title'], X0 + self.S(18), Y0 + self.S(10))
            c.coords(it['log_open'], X1 - self.S(18), Y0 + self.S(12))
            c.coords(it['log_text'], X0 + self.S(18), Y0 + self.S(42))
            c.itemconfigure(it['log_title'], text=self.T('Build-Log', 'Build log'))
            c.itemconfigure(it['log_open'], text=self.T('Logdatei öffnen', 'Open log file') if self.build_log else '')
            for i in rows:   # (the log covers the rows: they are hidden under it, not shown through)
                c.itemconfigure(i, state='hidden')
            for k in ('log_bg', 'log_title', 'log_open', 'log_text'):
                c.itemconfigure(it[k], state='normal')
                c.tag_raise(it[k])
        # (each line cut to what the panel holds: the build's lines are long, and ran past its right edge)
        room = (X1 - X0) - self.S(36)
        cols = max(20, int(room // max(1, self.measure(self.f_log, '0'))))
        lines = [l if len(l) <= cols else l[:cols - 1] + '…' for l in self.log_lines[-11:]]
        self.set_text(it['log_text'], '\n'.join(lines))

    # ---- the mouse ----------------------------------------------------------------------------------------------------
    def design(self, e):
        # (a mouse move before the first draw: no fit yet, the pointer is nowhere on the design. 1.1.4-20 logged a traceback here)
        k, ox, oy = getattr(self, 'fit', None) or (1.0, -1e9, -1e9)
        return (e.x - ox) / k, (e.y - oy) / k

    def target_at(self, e):
        x, y = self.design(e)
        for name, b in self.buttons.items():
            x0, y0, x1, y1 = b['box']
            cy = (y0 + y1) / 2
            dx = max(0, abs(x - (x0 + x1) / 2) - ((x1 - x0) / 2 - 16))
            if abs(y - cy) + dx * 1.45 < (y1 - y0) / 2:
                return name
        for w in self.winbtns:
            gx, gy = w['center']
            if abs(x - gx) < 23 and abs(y - gy) < 21:
                return 'win_' + w['name']
        if self.show_log and self.build_log:
            X1, Y0 = self.P(LOG_BOX[2], LOG_BOX[1])
            if X1 - self.S(170) < e.x < X1 and Y0 < e.y < Y0 + self.S(34):
                return 'log_open'
        return None

    def set_hover(self, name):
        if name != self.hover:
            self.hover = name
            self.c.configure(cursor='hand2' if name else '')
            self.update_hover_visuals()

    def update_hover_visuals(self):
        c = self.c
        for name, b in self.buttons.items():
            over = b.get('over')
            want = 'hover' if self.hover == name else None
            if self.pressed == name and self.hover == name:
                want = 'press'
            if name == 'btn_right' and self.phase == 'done' and 'teal' in b:
                X1, Y1, img, img_h = self.teal_right
                key = ('tealhover', want)
                if self.last.get(key[0]) != want:
                    self.last[key[0]] = want
                    c.itemconfigure(b['teal'], image=img_h if want else img)
                want = None
            if over is not None and self.last.get((name, 'over')) != want:
                self.last[(name, 'over')] = want
                if want:
                    c.itemconfigure(over, image=self.btn_sprites[name][2][want], state='normal')
                else:
                    c.itemconfigure(over, state='hidden')
        for w in self.winbtns:
            want = 'normal' if self.hover == 'win_' + w['name'] else 'hidden'
            if self.last.get(('win', w['name'])) != want:
                self.last[('win', w['name'])] = want
                c.itemconfigure(w['hl'], state=want)
                c.itemconfigure(w['text'], fill='#ffffff' if want == 'normal' else '#e6d6a2')

    def motion(self, e):
        self.set_hover(self.target_at(e))

    def press(self, e):
        name = self.target_at(e)
        self.pressed = name
        self.update_hover_visuals()
        if name is None and self.winbtns and self.design(e)[1] < 60:
            self.window['drag']()

    def double(self, e):
        if self.target_at(e) is None and self.winbtns and self.design(e)[1] < 60:
            self.window['maximize']()

    def release(self, e):
        name = self.target_at(e)
        was = self.pressed
        self.pressed = None
        self.update_hover_visuals()
        if not name or name != was:
            return
        if name == 'btn_left':
            if self.confirm and self.phase == 'run':
                self.confirm = None
                self.closing_app = False
            else:
                self.show_log = not self.show_log
        elif name == 'btn_right':
            if self.phase == 'run':
                if self.confirm:
                    self.cancel_now()
                else:
                    self.ask_cancel()
            elif self.phase == 'done':
                self.close(done=True)
            else:
                self.close(back=True)
        elif name == 'log_open':
            self.open_build_log()
        elif name.startswith('win_') and self.window:
            n = name[4:]
            if n == 'close':
                self.request_close()
            else:
                self.window[n]()
                if n == 'maximize':
                    self.c.after(200, self.refresh_max_glyph)
        self.update_items()

    def refresh_max_glyph(self):
        import ui
        for w in self.winbtns:
            if w['name'] == 'maximize':
                self.c.itemconfigure(w['text'], text=ui.GLYPH['restore' if self.app.state() == 'zoomed' else 'maximize'])

    def escape(self, e=None):
        if self.confirm:
            self.confirm = None
            self.closing_app = False
        elif self.show_log:
            self.show_log = False

    def open_build_log(self):
        """the build's own full log (build.log) in Windows' editor for text files"""
        p = self.build_log
        if p and p.is_file():
            try:
                os.startfile(str(p))
            except OSError:
                pass

    def close(self, done=False, back=False, then_quit=False):
        if self.phase == 'run':
            self.phase = 'closed'
        try:
            self.logf.close()
        except OSError:
            pass
        try:
            self.app.protocol('WM_DELETE_WINDOW', self.prev_protocol or '')
        except tk.TclError:
            pass
        self.items = {}
        self.c.destroy()
        (self.on_done if done else self.on_back)()
        if then_quit and self.window:
            self.window['close']()
