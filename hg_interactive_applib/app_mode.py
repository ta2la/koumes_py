"""hg_interactive_applib.app_mode - interaction modes on a stack, and the generic ones.

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
