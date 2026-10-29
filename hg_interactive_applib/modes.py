"""hg_interactive_app.modes - interaction modes on a stack, and the generic ones.

Modelled on the CAD Cmd / CmdQueue (a mode is called "command" there), with
MicroStation logic:

- AppMode: name, hint, dialog buttons, enter_point / move / reset, busy, snap,
  finish. A mode counts its steps by collected points (like CAD `points_`);
  a click accepts.
- AppModeStack: the active mode is the last one. once=False replaces the stack
  (replaced modes are reset in the view), once=True pushes a mode on top; it
  removes itself when done. Reset steps one back: a busy mode goes back a step,
  an idle one ends and the default mode returns; a mode on top is removed.
  The view comes as an argument (like CAD `enterPoint(pt, view)`).
- Generic modes: AppMode_select (click selects, ctrl+click adds/removes),
  AppMode_pan (dragging moves the picture), AppMode_zoom (zoom by a box).

A view used by the modes provides: snap(x, y), pick(x, y, kind=None),
pan_by(dx, dy), ratio(), zoom_to(rect) and the dynamics of the application.
"""

import html

C_MARK = "#e2d2f3"               # content line that has its own object in the picture

from hg_pool_py import POOL, SELSET, Sel


class AppMode:
    """Interaction mode: name, hint, dialog buttons and input handlers."""

    name = "void"
    snap = True              # points into the mode snap to the grid

    def __init__(self):
        self.queue = None        # set by AppModeStack.add
        self.once = False

    def hint(self) -> str:
        return ""

    def dialog(self):
        """Mode buttons: [(label, command)]."""
        return []

    def enter_point(self, x, y, view):
        pass

    def enter_move(self, x, y, view):
        pass

    def enter_reset(self, view):
        pass

    def busy(self) -> bool:
        """Is the mode in progress? Reset then steps it back instead of ending it."""
        return False

    def finish(self):
        """A mode pushed on top (once) is done - remove it from the stack."""
        self.queue.remove(self)


class AppModeStack:
    """Stack of the application's modes, the active one is the last (like CAD
    CmdQueue). Fed with points, movement and step-back reset; the view comes as
    an argument."""

    def __init__(self, default_mode):
        """default_mode = class of the mode reset returns to."""
        self.default_mode = default_mode
        self.stack = []
        self.mods = set()            # modifiers of the last point (e.g. ctrl)
        self.listeners = []          # f(), called after every change
        self.add(default_mode())

    def active(self):
        return self.stack[-1]

    def add(self, mode, once=False, view=None):
        """once=False replaces the stack (modes on it are reset in view),
        once=True pushes the mode on top."""
        mode.queue, mode.once = self, once
        if not once:
            if view is not None:
                for m in self.stack:
                    m.enter_reset(view)
            self.stack = []
        self.stack.append(mode)
        self.changed()

    def remove(self, mode):
        """Remove a mode pushed on top; the bottom one always stays."""
        if len(self.stack) > 1 and mode in self.stack:
            self.stack.remove(mode)
        self.changed()

    def point(self, x, y, view, mods=()):
        self.mods = set(mods)
        self.active().enter_point(x, y, view)
        self.changed()

    def move(self, x, y, view):
        self.active().enter_move(x, y, view)

    def reset(self, view):
        """One step back: a mode on top removes itself, a busy mode steps back,
        an idle mode ends and the default one returns."""
        mode = self.active()
        if mode.once or mode.busy():
            mode.enter_reset(view)
        elif not isinstance(mode, self.default_mode):
            self.add(self.default_mode(), view=view)
        else:
            mode.enter_reset(view)
        self.changed()

    def changed(self):
        for f in list(self.listeners):
            f()


class AppMode_select(AppMode):
    """Default mode: a click selects the object under it (topmost by pick order),
    ctrl+click adds it or removes it. Shift: a rectangle by 2 points - the 1st
    shift point is a corner, the 2nd adds what lies wholly inside (additive).
    The dialog shows the id of the object under the mouse (and its content, when
    it offers some); with exactly one object selected it shows that one instead
    and the mouse does not overwrite it."""

    name = "select"

    def __init__(self):
        super().__init__()
        self.corner = None           # 1st point of the rectangle (shift)
        self.under = ""              # id of the object under the mouse
        self.under_text = ""         # its content, when it offers some (obj.hover)
        self.room = (6, 40)          # lines, columns of content that fit the panel

    def hint(self):
        if self.corner is not None:
            text = "shift+click the other corner (right button = back)"
        else:
            text = "click selects, ctrl+click adds/removes, shift: rectangle by 2 points, drag moves the selected"
        name, body = self.under, self.under_text
        sel = SELSET.items()
        if len(sel) == 1:                # the one selected wins over the mouse
            hover = getattr(sel[0], "hover", None)
            name, body = getattr(sel[0], "id", ""), hover(*self.room) if hover else ""
        if name:
            text += "<br><b>%s</b>" % html.escape(name)
        if isinstance(body, list):       # [(line, marked)] - marked lines get a background
            body = "\n".join('<span style="background:%s">%s</span>' % (C_MARK, html.escape(t))
                             if mark else html.escape(t) for t, mark in body)
        elif body:
            body = html.escape(body)
        if body:
            text += '<pre style="font-size:9pt">%s</pre>' % body
        return text

    def enter_point(self, x, y, view):
        if "shift" in self.queue.mods:
            if self.corner is None:
                self.corner = (x, y)
                return
            with POOL.lock():
                for o in view.objs_in(self.corner, (x, y)):
                    if o.sel == Sel.NONE:
                        SELSET.set(o, Sel.SEL)
            self.enter_reset(view)
            return
        self.enter_reset(view)
        hit = view.pick(x, y)
        if "ctrl" in self.queue.mods:
            SELSET.toggle(hit)
        else:
            SELSET.click(hit)

    def enter_move(self, x, y, view):
        if self.corner is not None:
            view.dyn_clear()
            view.dyn_box(self.corner, view.snap(x, y))
        self.room = view.hover_room()
        if len(SELSET.items()) == 1:
            return
        hit = view.pick(x, y)
        under = getattr(hit, "id", "") if hit is not None else ""
        if under != self.under:
            self.under = under
            hover = getattr(hit, "hover", None)
            self.under_text = hover(*view.hover_room()) if hover else ""
            view.refresh_bar()

    def enter_reset(self, view):
        if self.corner is not None:
            self.corner = None
            view.dyn_clear()

    def busy(self):
        return self.corner is not None


class AppMode_pan(AppMode):
    """Moving the picture: the 1st point grabs a place, movement keeps it under
    the mouse, the 2nd point ends. Pushed on top (once), removes itself."""

    name = "pan"
    snap = False             # the picture moves smoothly, not by the grid

    def __init__(self):
        super().__init__()
        self.grab = None

    def hint(self):
        return "drag the picture"

    def enter_point(self, x, y, view):
        if self.grab is None:
            self.grab = (x, y)
            return
        self.finish()

    def enter_move(self, x, y, view):
        if self.grab is not None:
            # bring the scene point under the mouse back to the grabbed place
            view.pan_by(x - self.grab[0], y - self.grab[1])

    def enter_reset(self, view):
        self.finish()


def box_ratio(a, b, ratio):
    """Box from corner a towards b, widened to ratio w/h (the view's proportions),
    like CAD Cmd_zoomBox::newDisplay_: (x1, y1, x2, y2)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    dx = dx if abs(dx) > 1e-9 else 1e-9
    dy = dy if abs(dy) > 1e-9 else 1e-9
    if ratio > abs(dx / dy):
        dx = (1 if dx > 0 else -1) * abs(dy * ratio)
    else:
        dy = (1 if dy > 0 else -1) * abs(dx / ratio)
    return a[0], a[1], a[0] + dx, a[1] + dy


class AppMode_zoom(AppMode):
    """Zoom by a box (CAD Cmd_zoomBox): the 1st point is a corner, movement shows
    the box kept in the window's proportions, the 2nd point zooms to it. Pushed
    on top (once), removes itself."""

    name = "zoom"
    snap = False

    def __init__(self):
        super().__init__()
        self.corner = None

    def hint(self):
        return "enter second point of box" if self.corner else "enter first point of box"

    def enter_point(self, x, y, view):
        if self.corner is None:
            self.corner = (x, y)
            return
        x1, y1, x2, y2 = box_ratio(self.corner, (x, y), view.ratio())
        self.corner = None
        view.dyn_clear()
        view.zoom_to((x1, y1, x2, y2))
        self.finish()

    def enter_move(self, x, y, view):
        if self.corner is None:
            return
        x1, y1, x2, y2 = box_ratio(self.corner, (x, y), view.ratio())
        view.dyn_clear()
        view.dyn_box((x1, y1), (x2, y2))
        view.dyn_dot(self.corner)

    def enter_reset(self, view):
        if self.corner is not None:
            self.corner = None
            view.dyn_clear()
            return
        self.finish()

    def busy(self):
        return self.corner is not None
