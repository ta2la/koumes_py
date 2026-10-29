"""hg_interactive_applib.app_mode_zoom - mode zoom by a box (CAD Cmd_zoomBox) and box_ratio."""

from .app_mode import AppMode


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
