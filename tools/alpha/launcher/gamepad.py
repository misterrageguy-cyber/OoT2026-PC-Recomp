"""The launcher with a controller (XInput: Xbox pads, and others through Steam Input or DS4Windows): the D-pad or the left
stick moves a focus ring between the page's buttons, A presses, B goes back, Start plays from the ready page, LB/RB switch
the settings tabs. A dropdown's list: up/down and A, B closes it. Only while the launcher's window has the focus, so the
game's own input is never read twice. Pure logic (pick_next) is kept apart from Windows for the tests."""
import ctypes
import time

UP, DOWN, LEFT, RIGHT = 0x0001, 0x0002, 0x0004, 0x0008
START, BACK = 0x0010, 0x0020
LB, RB = 0x0100, 0x0200
A, B, X, Y = 0x1000, 0x2000, 0x4000, 0x8000
STICK = 16000   # (of 32767: past this the stick counts as a D-pad press)
REPEAT_FIRST, REPEAT_NEXT = 0.40, 0.12   # (seconds: a held direction repeats)


class _Pad(ctypes.Structure):
    _fields_ = [('buttons', ctypes.c_ushort), ('lt', ctypes.c_ubyte), ('rt', ctypes.c_ubyte),
                ('lx', ctypes.c_short), ('ly', ctypes.c_short), ('rx', ctypes.c_short), ('ry', ctypes.c_short)]


class _State(ctypes.Structure):
    _fields_ = [('packet', ctypes.c_uint), ('pad', _Pad)]


def _xinput():
    for name in ('xinput1_4', 'xinput1_3', 'xinput9_1_0'):
        try:
            return getattr(ctypes.windll, name).XInputGetState
        except (OSError, AttributeError):
            continue
    return None


def pick_next(boxes, current, direction):
    """the index of the box to focus from boxes[current] going direction ('up', 'down', 'left', 'right'): the nearest whose
    centre lies that way, nearer to the line of travel counting more; None when there is none. current None: the first box"""
    if not boxes:
        return None
    if current is None or not 0 <= current < len(boxes):
        return 0
    x0, y0, x1, y1 = boxes[current]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    best, best_score = None, None
    for i, (a0, b0, a1, b1) in enumerate(boxes):
        if i == current:
            continue
        dx, dy = (a0 + a1) / 2 - cx, (b0 + b1) / 2 - cy
        along, across = {'up': (-dy, dx), 'down': (dy, dx), 'left': (-dx, dy), 'right': (dx, dy)}[direction]
        if along <= 1:
            continue
        score = along + 2.5 * abs(across)
        if best_score is None or score < best_score:
            best, best_score = i, score
    return best


class Gamepad:
    def __init__(self, app, stage, back=None, play=None, tab=None):
        """app: the Tk window; stage: ui.Stage; back(): the page's way back (or None); play(): Start on the ready page;
        tab(d): the settings tabs one to the left (-1) or right (+1)"""
        self.app, self.stage, self.back, self.play, self.tab = app, stage, back, play, tab
        self.get = _xinput()
        self.held, self.next_repeat, self.focus, self.focus_box, self.ring = 0, 0.0, None, None, None
        self.used = False   # (the ring shows only once a controller was used)
        if self.get:
            app.after(200, self.poll)

    def targets(self):
        return [h for h in self.stage.hots if h.cmd and h.kind == 'click' and h.cursor]

    def refresh(self):
        """after the page is drawn again: the focus on the button nearest the one it was on"""
        if not self.used:
            return
        hots = self.targets()
        if not hots:
            self.focus = None
            return self.draw()
        if self.focus_box:
            fx, fy = (self.focus_box[0] + self.focus_box[2]) / 2, (self.focus_box[1] + self.focus_box[3]) / 2
            self.focus = min(range(len(hots)), key=lambda i: abs((hots[i].box[0] + hots[i].box[2]) / 2 - fx) +
                             abs((hots[i].box[1] + hots[i].box[3]) / 2 - fy))
        else:
            self.focus = 0
        self.draw()

    def draw(self):
        c = self.stage.c
        c.delete('gamepad_focus')
        hots = self.targets()
        if self.focus is None or not self.used or self.focus >= len(hots):
            return
        h = hots[self.focus]
        self.focus_box = h.box
        x0, y0, x1, y1 = h.box
        c.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline='#f4c430', width=3, tags='gamepad_focus')
        self.stage.set_under(h)

    def move(self, direction):
        hots = self.targets()
        i = pick_next([h.box for h in hots], self.focus, direction)
        if i is not None:
            self.focus = i
        self.draw()

    def press(self, button):
        nav = getattr(self.stage, 'pop_nav', None) if self.stage.pop else None
        if nav:   # (a dropdown's list is open)
            if button in (UP, DOWN):
                nav[0](-1 if button == UP else 1)
            elif button == A:
                nav[1]()
            elif button == B:
                self.stage.close_popup()
            return
        if not self.used:   # (the first press shows the ring)
            self.used = True
            self.refresh()
            if button in (UP, DOWN, LEFT, RIGHT):
                return
        if button in (UP, DOWN, LEFT, RIGHT):
            self.move({UP: 'up', DOWN: 'down', LEFT: 'left', RIGHT: 'right'}[button])
        elif button == A:
            hots = self.targets()
            if self.focus is not None and self.focus < len(hots):
                self.app.after(1, hots[self.focus].cmd)
        elif button == B and self.back:
            self.back()
        elif button == START and self.play:
            self.play()
        elif button in (LB, RB) and self.tab:
            self.tab(-1 if button == LB else 1)

    def poll(self):
        try:
            if self.app.focus_get() is not None or (self.stage.pop and self.stage.pop.winfo_exists()):
                st = _State()
                if self.get(0, ctypes.byref(st)) == 0:
                    b = st.pad.buttons
                    if st.pad.ly > STICK:
                        b |= UP
                    if st.pad.ly < -STICK:
                        b |= DOWN
                    if st.pad.lx < -STICK:
                        b |= LEFT
                    if st.pad.lx > STICK:
                        b |= RIGHT
                    now = time.monotonic()
                    for button in (UP, DOWN, LEFT, RIGHT, A, B, START, LB, RB):
                        down, was = b & button, self.held & button
                        if down and not was:
                            self.press(button)
                            if button in (UP, DOWN, LEFT, RIGHT):
                                self.next_repeat = now + REPEAT_FIRST
                        elif down and button in (UP, DOWN, LEFT, RIGHT) and now >= self.next_repeat:
                            self.press(button)
                            self.next_repeat = now + REPEAT_NEXT
                    self.held = b
        except Exception:   # (a controller unplugged mid-read, a window closing: try again next time)
            pass
        self.app.after(40, self.poll)
