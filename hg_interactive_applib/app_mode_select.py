"""hg_interactive_applib.app_mode_select - mode select (default): click, ctrl+click, box by shift."""

import html

from hg_pool_py import POOL, SELSET, Sel

from .app_mode import AppMode


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


C_MARK = "#e2d2f3"               # content line that has its own object in the picture
