"""The fairy that flies over the launcher, endlessly: a layered window of its own (true per-pixel alpha, so its glow blends
over whatever is behind it), owned by the launcher's window (it stays on top of it, minimises with it), never active and never
in the way of a click (WS_EX_TRANSPARENT). Its frames come from assets/fairy.bin (make_fairy.py): premultiplied BGRA, facing
right, then the same facing left. It wanders on a smooth, never-repeating path inside the launcher's window, turns to face where
it goes, and bobs as it flaps. Windows only; anything that fails leaves the launcher as it was.
"""
import ctypes
import math
import random
import struct
import time
from ctypes import wintypes
from pathlib import Path

user32, gdi32, kernel32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x80, 0x08000000
ULW_ALPHA, AC_SRC_ALPHA = 2, 1
SW_SHOWNOACTIVATE, SW_HIDE = 4, 0
GWLP_HWNDPARENT = -8

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE   # (a 64-bit handle: not cut to an int)
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_void_p, ctypes.c_void_p, wintypes.HDC,
                                       ctypes.c_void_p, wintypes.COLORREF, ctypes.c_void_p, wintypes.DWORD]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.HANDLE, wintypes.DWORD]
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('style', wintypes.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', wintypes.HINSTANCE), ('hIcon', wintypes.HICON),
                ('hCursor', wintypes.HANDLE), ('hbrBackground', wintypes.HBRUSH), ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR), ('hIconSm', wintypes.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD), ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long), ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [('BlendOp', ctypes.c_ubyte), ('BlendFlags', ctypes.c_ubyte), ('SourceConstantAlpha', ctypes.c_ubyte),
                ('AlphaFormat', ctypes.c_ubyte)]


class Fairy:
    def __init__(self, root, asset, size=None):
        """root: the launcher's Tk window. size: the fairy's width in pixels (default: the frames' own, times the DPI's scale)"""
        self.root = root
        raw = Path(asset).read_bytes()
        if raw[:6] != b'FAIRY1':
            raise ValueError('not a fairy file')
        self.n, self.frames_n, self.ms = struct.unpack_from('<HHH', raw, 6)
        step = self.n * self.n * 4
        self.frames = [raw[12 + i * step:12 + (i + 1) * step] for i in range(self.frames_n * 2)]
        self.scale = max(1.0, root.winfo_fpixels('1i') / 96)
        self.alive = True
        self.t0 = time.perf_counter()
        self.seed = random.random() * 100
        self.facing = 1   # 1 right, -1 left
        self.last_x = None
        # (its window procedure is Windows' own, registered by ocr_chrome.dll: a Python one would run Python inside Windows'
        # calls from Tk's thread, which ends in abort())
        hinst = kernel32.GetModuleHandleW(None)
        dll = ctypes.WinDLL(str(Path(__file__).resolve().parent / 'ocr_chrome.dll'))
        dll.ocr_plain_class.argtypes = [wintypes.LPCWSTR]
        dll.ocr_plain_class('OcarinaRebornFairy')
        owner = user32.GetParent(root.winfo_id()) or root.winfo_id()
        self.hwnd = user32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                                           'OcarinaRebornFairy', '', WS_POPUP, 0, 0, self.n, self.n, owner, None, hinst, None)
        if not self.hwnd:
            raise OSError('no window')
        # the bitmap a frame is put in, then handed to the window with its alpha
        self.screen = user32.GetDC(None)
        self.mem = gdi32.CreateCompatibleDC(self.screen)
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), self.n, -self.n, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = ctypes.c_void_p()
        self.bmp = gdi32.CreateDIBSection(self.mem, ctypes.byref(bi), 0, ctypes.byref(self.bits), None, 0)
        gdi32.SelectObject(self.mem, self.bmp)
        self.shown = False
        self.tick()

    def place(self, now):
        """where it is at time now, inside the launcher's window: two slow sines each way (a path that does not repeat soon),
        and a small bob with the wings"""
        x0, y0 = self.root.winfo_rootx(), self.root.winfo_rooty()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        n = self.n
        t = now * 0.11 + self.seed
        u = 0.5 + 0.30 * math.sin(t * 1.3) + 0.18 * math.sin(t * 2.9 + 1.7)
        v = 0.5 + 0.26 * math.sin(t * 1.7 + 0.6) + 0.14 * math.sin(t * 3.7 + 2.3)
        bob = math.sin(now * 2 * math.pi * 1000 / (self.ms * self.frames_n)) * 6 * self.scale
        x = x0 + int(u * max(1, w - n))
        y = y0 + int(v * max(1, h - n) + bob)
        return x, y

    def tick(self):
        if not self.alive:
            return
        try:
            if self.root.state() == 'iconic' or not self.root.winfo_viewable():
                if self.shown:
                    user32.ShowWindow(self.hwnd, SW_HIDE)
                    self.shown = False
            else:
                now = time.perf_counter() - self.t0
                x, y = self.place(now)
                if self.last_x is not None and abs(x - self.last_x) > 0:
                    self.facing = 1 if x > self.last_x else -1
                self.last_x = x
                k = int(now * 1000 / self.ms) % self.frames_n + (0 if self.facing > 0 else self.frames_n)
                ctypes.memmove(self.bits, self.frames[k], len(self.frames[k]))
                pt, size, src = wintypes.POINT(x, y), wintypes.SIZE(self.n, self.n), wintypes.POINT(0, 0)
                blend = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
                user32.UpdateLayeredWindow(self.hwnd, self.screen, ctypes.byref(pt), ctypes.byref(size), self.mem,
                                           ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA)
                if not self.shown:
                    user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
                    self.shown = True
        except Exception:   # (a window gone, a DC lost: the fairy goes, the launcher stays)
            self.close()
            return
        self.root.after(33, self.tick)

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            user32.DestroyWindow(self.hwnd)
            gdi32.DeleteObject(self.bmp)
            gdi32.DeleteDC(self.mem)
            user32.ReleaseDC(None, self.screen)
        except Exception:
            pass
