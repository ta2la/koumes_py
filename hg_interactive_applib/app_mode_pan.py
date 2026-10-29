"""hg_interactive_applib.app_mode_pan - mode pan: dragging moves the picture."""

from .app_mode import AppMode


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
