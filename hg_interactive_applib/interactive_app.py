"""hg_interactive_applib.interactive_app - root of an interactive application.

InteractiveApp holds the mode stack, the commands (a CmdsInteractive on its own
CmdSys), the views and the active view (where input goes). Mouse input becomes
commands: a point is `<prefix>_xy`, a reset `<prefix>_reset`; the movement goes
into the active mode directly (dynamics). `execute(line)` runs a command through
the application's CmdSys - from code it is the same as from an agent or the WS
connector (logged, broadcast, under the lock). An application derives from it
and keeps one instance (its secondary singleton, application scope only).
"""

import weakref

from .app_mode_stack import AppModeStack


class InteractiveApp:
    """Root: mode stack, commands, views and the active view, mouse input."""

    def __init__(self, prefix, default_mode, cmds, ws_default=0):
        self.prefix = prefix
        self.queue = AppModeStack(default_mode)
        self.cmds = cmds
        cmds.app = self
        self.ws_default = ws_default
        self.views = weakref.WeakSet()       # whose bar and log to refresh
        self.view = None                     # the active view - where input goes
        self.queue.listeners.append(self.changed)
        cmds.changed = self.changed
        cmds.mode = lambda: self.queue.active().name

    def active_view(self):
        return self.view

    def execute(self, line, view=None):
        """Run a command through the CmdSys of the app; view = where the input came from
        (it becomes the active one)."""
        if view is not None:
            self.view = view
        self.cmds.run(line)

    def start_ws(self, port=0):
        return self.cmds.start_ws(port, self.ws_default)

    def drain(self):
        self.cmds.drain()

    #! @section Mouse input - everything goes as a command
    def point(self, x, y, view, mods=()):
        """A point from the mouse always becomes the command <prefix>_xy."""
        if self.queue.active().snap:
            x, y = view.snap(x, y)
        self.execute("%s_xy %g %g%s" % (self.prefix, x, y, "".join(" " + m for m in mods)), view)

    def move(self, x, y, view):
        """Mouse movement (dynamics) goes into the active mode directly, not logged."""
        self.view = view
        self.queue.move(x, y, view)

    def reset(self, view):
        self.execute(self.prefix + "_reset", view)

    def changed(self):
        """Refresh the views (refresh_bar)."""
        for v in list(self.views):
            try:
                v.refresh_bar()
            except RuntimeError:         # a dead Qt widget behind the wrapper
                self.views.discard(v)
                if self.view is v:
                    self.view = None
