"""hg_interactive_applib.app_mode_stack - stack of the application's modes (like CAD CmdQueue)."""


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
