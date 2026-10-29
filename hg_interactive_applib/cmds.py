"""hg_interactive_app.cmds - commands every interactive application has.

CmdsInteractive(cmd_sys.Cmds) registers, under the application's prefix:

    <prefix>_xy x y [mods]    a point into the active mode (a click)
    <prefix>_reset            reset: one step back / end the mode
    <prefix>_cmd_select       mode select (default)
    <prefix>_cmd_pan          moving the picture, on top of the stack
    <prefix>_cmd_zoom         zoom by a box (2 points), on top of the stack
    <prefix>_zoom_extent [kind]  zoom to the extent of the objects (of that kind)
    <prefix>_sel              content of the selection
    <prefix>_save             unsaved changes of the active source into it
    <prefix>_state            source, port, mode stack, selection, changes
    <prefix>_cross on|off     a cross over the picture: an agent is working
    <prefix>_screenshot png   snapshot of the active view
    <prefix>_window png       snapshot of the whole window
    <prefix>_help             list of commands (from cmd_sys.Cmds)

The commands keep no state; they reach the application root through `app`
(set once by InteractiveApp). An application subclasses it and registers its
own commands next to these.
"""

from cmd_sys import Cmds
from hg_pool_py import POOL, SELSET, SOURCES

from .modes import AppMode_pan, AppMode_select, AppMode_zoom


class CmdsInteractive(Cmds):
    def __init__(self, prefix):
        super().__init__(prefix, POOL.lock)
        self.app = None                  # application root, set by InteractiveApp
        p = prefix
        for name, fn, desc in (
            (p + "_xy", self._cmd_xy, "x y [ctrl|shift] - point into the active mode (click)"),
            (p + "_reset", self._cmd_reset, "reset: one step back / end the mode"),
            (p + "_cmd_select", self.mode(AppMode_select), "mode select"),
            (p + "_cmd_pan", self.mode(AppMode_pan, True), "moving the picture, on top of the stack"),
            (p + "_cmd_zoom", self.mode(AppMode_zoom, True), "zoom by a box (2 points), on top of the stack"),
            (p + "_zoom_extent", self._cmd_zoom_extent, "[kind] - zoom to the extent of the objects"),
            (p + "_sel", self._cmd_sel, "content of the selection"),
            (p + "_save", self._cmd_save, "active source: unsaved changes into it"),
            (p + "_state", self._cmd_state, "source, port, mode stack, selection, changes"),
            (p + "_cross", self._cmd_cross, "on [who] | off - cross over the picture: an agent works"),
            (p + "_screenshot", self._cmd_screenshot, "<png> - snapshot of the active view"),
            (p + "_window", self._cmd_window, "<png> - snapshot of the whole window")):
            self.register(name, fn, desc)

    def mode(self, cls, once=False):
        """Handler of a command that starts a mode."""
        return lambda a: self.app.queue.add(cls(), once=once, view=self.app.view)

    def _cmd_xy(self, args):
        if self.app.view is None or len(args) < 2:
            return "%s_xy: no view or coordinates" % self.prefix
        try:
            self.app.queue.point(float(args[0]), float(args[1]), self.app.view, args[2:])
        except (RuntimeError, ValueError) as e:
            return "%s_xy: %s" % (self.prefix, e)
        return None

    def _cmd_zoom_extent(self, args):
        """The rectangle where the objects lie, whole in the window (as zoom by a box)."""
        v = self.app.view
        if v is None:
            return "%s_zoom_extent: no view" % self.prefix
        r = v.extent(args[0] if args else None)
        if r.isEmpty():
            return "%s_zoom_extent: nothing there" % self.prefix
        v.zoom_to((r.left(), r.top(), r.right(), r.bottom()))
        return [("%g %g %g %g" % (r.left(), r.top(), r.right(), r.bottom()), "EXTENT")]

    def _cmd_reset(self, args):
        if self.app.view is None:
            return "%s_reset: no view" % self.prefix
        self.app.queue.reset(self.app.view)
        return None

    def _cmd_sel(self, args):
        """Each selected object as ITEM and its data under it (from obj.describe)."""
        out = []
        for it in SELSET.items():
            level = SELSET.level(it).name
            describe = getattr(it, "describe", None)
            out += describe(level) if describe else [
                ("%s %s %s %s" % (it.key, it.kind, level, it.id), "ITEM")]
        return out

    def _cmd_save(self, args):
        d = SOURCES.active
        if d is None:
            return "%s_save: no source" % self.prefix
        n = d.changes
        d.save()
        return [(str(n), "SAVED"), (d.id, "FILE")]

    def _cmd_state(self, args):
        d = SOURCES.active
        out = [(d.id if d else "", "FILE"), (str(self.ws.port if self.ws else 0), "PORT"),
               (" ".join(m.name for m in self.app.queue.stack), "STACK"),
               (str(len(SOURCES.items)), "SOURCES")]
        if d is not None:
            out.append((str(SELSET.selected_key(d.id)), "SELECTED"))
            out.append((str(d.changes), "CHANGES"))
        return out

    def _cmd_cross(self, args):
        """An agent works on the application (tests, restarts) - a cross over the
        picture; off = the user's again. Views provide set_cross(text)."""
        if not args:
            return "%s_cross: on/off missing" % self.prefix
        on = args[0] == "on"
        for v in list(self.app.views):
            v.set_cross((" ".join(args[1:]) or "KOUMES") if on else "")
        return [("on" if on else "off", "CROSS")]

    def _cmd_screenshot(self, args):
        if self.app.view is None or not args:
            return "%s_screenshot: no view or file" % self.prefix
        if not self.app.view.grab().save(args[0]):
            return "%s_screenshot: cannot save %s" % (self.prefix, args[0])
        return [(args[0], "FILE")]

    def _cmd_window(self, args):
        """Snapshot of the whole window in logical pixels."""
        if self.app.view is None or not args:
            return "%s_window: no view or file" % self.prefix
        win = self.app.view.window()
        pm = win.grab()
        if pm.devicePixelRatio() != 1:
            pm = pm.scaled(win.size())
        if not pm.save(args[0]):
            return "%s_window: cannot save %s" % (self.prefix, args[0])
        return [(args[0], "FILE"), ("%d %d" % (win.width(), win.height()), "SIZE")]
