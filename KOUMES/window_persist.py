#
# Copyright (C) 2026 Petr Talla. [petr.talla@gmail.com]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#           http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""WindowPersist - save and restore the session across restarts.

Python port of the C++ predecessor's WindowPersist.h + the config helper from
base2/app_common/AppUtility.h::replaceOrAppendInConfig, grown to cover what the
window was showing, not only where it stood.

Written to `<dir_config>/config.t2l` on quit, one replaceable line each:

    set_window <x> <y> <w> <h> <screenIdx> <screenW> <screenH>
    set_panels --dir <path> --p1 <file> --p1v <viewer> --p2 <file> --p2v <viewer>
               --active <p1|p2>
    set_splitter <left> <dir> <p1> <p2>

and executed again by `restore()` after the window is on screen. They are plain
commands, so the same state can be set by hand or over the WS bridge.

**Monitors move.** A position saved on a screen that is now gone, or that has
changed resolution, would put the window somewhere the user cannot reach it.
When the saved screen does not match, the position is dropped and the window is
centred on the primary screen at its saved size - never restored blind.
"""

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QWidget

from cmd_sys import CMD_SYS
from .app_paths import AppPaths


def replace_or_append_in_config(line: str) -> None:
    """Replace or append a line in `<dir_config>/config.t2l`. First word = cmd name."""
    cmd_name = line.split(" ", 1)[0]
    dir_config = AppPaths.inst().dir_config()
    path = os.path.join(dir_config, "config.t2l")

    lines = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    replaced = False
    for i, existing in enumerate(lines):
        if existing.strip().startswith(cmd_name):
            lines[i] = line + "\n"
            replaced = True
            break
    if not replaced:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(line + "\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


class WindowPersist:
    _main_window: Optional[QWidget] = None

    @classmethod
    def install(cls, main_window: QWidget, app: QApplication) -> None:
        cls._main_window = main_window
        cls._register_cmds()
        app.aboutToQuit.connect(lambda: cls._save_inline(main_window))

    @staticmethod
    def _screen_index(mw: QWidget) -> int:
        screens = QGuiApplication.screens()
        win_screen = mw.screen()
        for i, s in enumerate(screens):
            if s is win_screen:
                return i
        return -1

    @classmethod
    def _serialize(cls, mw: QWidget) -> str:
        # A maximised window would go down at its maximised size and come back
        # as a window with no draggable edges. normalGeometry() is the size it
        # would return to, and that is what belongs in the config.
        rect = mw.normalGeometry()
        if not rect.isValid():
            rect = mw.geometry()
        w, h = rect.width(), rect.height()

        # X11 puts setGeometry's corner at the top left of the *frame*, but
        # reports geometry() from the top left of the *client area*. Save what
        # was reported and the window walks down by the height of its own title
        # bar on every restart - which is how a config ends up reading -49 and
        # the window ends up with its edges off the screen. Save the corner
        # setGeometry will consume.
        frame, inner = mw.frameGeometry(), mw.geometry()
        x = rect.x() - max(0, inner.x() - frame.x())
        y = rect.y() - max(0, inner.y() - frame.y())
        idx = cls._screen_index(mw)
        if idx < 0:
            return f"set_window {x} {y} {w} {h}"
        screen = QGuiApplication.screens()[idx]
        g = screen.geometry()
        # The connector name (HDMI-1, eDP-2, DP-4) is what actually identifies a
        # monitor. The index is the order Qt happened to enumerate them in and
        # shifts as soon as one is unplugged, so it is kept only as a fallback
        # for configs written before this and for screens with no name.
        name = screen.name().replace(" ", "_") or ""
        tail = f" --screen {name}" if name else ""
        return (
            f"set_window {x - g.x()} {y - g.y()} {w} {h} "
            f"{idx} {g.width()} {g.height()}{tail}"
        )

    @staticmethod
    def _quote(value: str) -> str:
        return '"' + str(value).replace('"', '') + '"'

    @classmethod
    def _serialize_session(cls, mw: QWidget) -> list:
        """Every line worth writing. Panels and splitter only if mw offers them."""
        lines = [cls._serialize(mw)]

        state = getattr(mw, "panel_state", None)
        if callable(state):
            st = state()
            parts = []
            for key in ("dir", "p1", "p1v", "p2", "p2v", "active"):
                if st.get(key):
                    parts.append(f"--{key} {cls._quote(st[key])}")
            if parts:
                lines.append("set_panels " + " ".join(parts))

        sizes = getattr(mw, "splitter_state", None)
        if callable(sizes):
            w = sizes()
            if len(w) == 4 and any(w):
                lines.append("set_splitter " + " ".join(str(int(n)) for n in w))

        return lines

    @classmethod
    def _save_inline(cls, mw: Optional[QWidget]) -> None:
        if mw is None:
            return
        for line in cls._serialize_session(mw):
            try:
                replace_or_append_in_config(line)
            except OSError:
                pass

    @classmethod
    def restore(cls) -> None:
        """Run the saved lines. Call once the window is up - `set_window` on a
        window that has not been shown yet gets overruled by the show itself.

        Nothing ran these before, which is why the geometry was faithfully
        written on every quit and never seen again.
        """
        path = os.path.join(AppPaths.inst().dir_config(), "config.t2l")
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.readlines()
        except OSError:
            return

        sys_ = CMD_SYS()
        for line in raw:
            line = line.strip()
            # Skip blanks, comments, and t2l attribute lines - config.t2l is a
            # t2l file that happens to hold commands, not the other way round.
            if not line or line.startswith("#"):
                continue
            head = line.split(" ", 1)[0]
            if head.endswith(":"):
                continue
            sys_.execute_thread_safe(line, "config", -1, "CONFIG")

    @classmethod
    def _register_cmds(cls) -> None:
        sys_ = CMD_SYS()

        def set_window(args, data, ctx):
            pos = []
            for i in range(1, args.count()):
                a = args.get(i)
                if not a.name:
                    pos.append(a.value)
            if len(pos) < 4:
                return args.append_error(
                    "set_window: usage: set_window <x> <y> <w> <h> [screen [sw sh]]"
                )
            mw = cls._main_window
            if mw is None:
                return args.append_error("set_window: no main window")
            try:
                x = int(pos[0]); y = int(pos[1]); w = int(pos[2]); h = int(pos[3])
            except ValueError:
                return args.append_error("set_window: x/y/w/h must be integers")
            if len(pos) < 5:
                screen = mw.screen() or QGuiApplication.primaryScreen()
                if screen is None:
                    cls._unmaximise(mw)
                    mw.resize(w, h)
                else:
                    cls._place(mw, x, y, w, h, screen.availableGeometry())
                args.append(f"{mw.x()},{mw.y()} {mw.width()}x{mw.height()}",
                            "WINDOW")
                return 0
            try:
                idx = int(pos[4])
            except ValueError:
                return args.append_error("set_window: screen must be integer")
            screens = QGuiApplication.screens()

            # Prefer the monitor by connector name: indices renumber whenever a
            # screen is unplugged, and restoring onto "screen 1" then means a
            # different physical monitor than the one the window was left on.
            want = args.get_arg("screen")
            named = -1
            if want is not None and want.value:
                target = str(want.value)
                for i, sc in enumerate(screens):
                    if sc.name().replace(" ", "_") == target:
                        named = i
                        break
                if named < 0:
                    cls._centre_on_primary(mw, w, h)
                    args.append(f"screen {target} not connected - centred on primary",
                                "FALLBACK")
                    return 0
                idx = named

            if idx < 0 or idx >= len(screens):
                cls._centre_on_primary(mw, w, h)
                args.append(f"no screen {idx} - centred on primary", "FALLBACK")
                return 0
            g = screens[idx].geometry()
            if len(pos) >= 7:
                try:
                    sw = int(pos[5]); sh = int(pos[6])
                except ValueError:
                    return args.append_error("set_window: sw/sh must be integers")
                if named < 0 and (sw != g.width() or sh != g.height()):
                    cls._centre_on_primary(mw, w, h)
                    args.append(
                        f"screen {idx} is {g.width()}x{g.height()}, saved {sw}x{sh}"
                        " - centred on primary",
                        "FALLBACK",
                    )
                    return 0
            avail = screens[idx].availableGeometry()
            cls._place(mw, g.x() + x, g.y() + y, w, h, avail)
            args.append(
                f"{mw.x()},{mw.y()} {mw.width()}x{mw.height()} @ screen {idx}",
                "WINDOW")
            return 0
        sys_.add("set_window", set_window, category="chroma")

        def save_window_position(args, data, ctx):
            mw = cls._main_window
            if mw is None:
                return args.append_error("save_window_position: no main window")
            line = cls._serialize(mw)
            try:
                replace_or_append_in_config(line)
            except OSError as e:
                return args.append_error(f"save_window_position: {e}")
            args.append(line, "SAVED")
            return 0
        sys_.add("save_window_position", save_window_position, category="chroma")

        def positional(args) -> list:
            return [args.get(i).value for i in range(1, args.count())
                    if not args.get(i).name]

        def set_panels(args, data, ctx):
            mw = cls._main_window
            restore = getattr(mw, "restore_panels", None) if mw else None
            if restore is None:
                return args.append_error("set_panels: no main window")
            state = {k: args.get_by_name(k).value
                     for k in ("dir", "p1", "p1v", "p2", "p2v", "active")}
            restore(state)
            args.append(state.get("dir", ""), "PANELS")
            return 0
        sys_.add("set_panels", set_panels, category="chroma")

        def set_splitter(args, data, ctx):
            mw = cls._main_window
            restore = getattr(mw, "restore_splitter", None) if mw else None
            if restore is None:
                return args.append_error("set_splitter: no main window")
            pos = positional(args)
            if len(pos) < 4:
                return args.append_error(
                    "set_splitter: usage: set_splitter <left> <dir> <p1> <p2>")
            try:
                widths = [int(v) for v in pos[:4]]
            except ValueError:
                return args.append_error("set_splitter: widths must be integers")
            restore(*widths)
            args.append(" ".join(str(w) for w in widths), "SPLITTER")
            return 0
        sys_.add("set_splitter", set_splitter, category="chroma")

    @staticmethod
    def _unmaximise(mw: QWidget) -> None:
        """Drop a maximised / full-screen window back to a normal one.

        While the window manager owns the size, `setGeometry` is quietly
        ignored - and the user cannot drag the edges either, because a
        maximised window has none to drag. Restoring into that state is how an
        app ends up looking like it cannot be resized at all.
        """
        state = mw.windowState()
        managed = (Qt.WindowState.WindowMaximized
                   | Qt.WindowState.WindowFullScreen)
        if state & managed:
            mw.setWindowState(state & ~managed)

    @classmethod
    def _place(cls, mw: QWidget, x: int, y: int, w: int, h: int, avail) -> None:
        """Put the window at x,y - but never off `avail`.

        All four edges have to stay on the screen. A geometry that hangs off
        the top or the left takes the title bar and those edges with it, and
        the window is then stuck at whatever size it happens to have. That is
        easy to end up with on Wayland: a client there cannot know its own
        absolute position, so what gets written on quit need not mean anything
        on the next start (`config.t2l` held `-11 -49` when this was found).
        """
        cls._unmaximise(mw)
        min_w = max(mw.minimumWidth(), mw.minimumSizeHint().width())
        min_h = max(mw.minimumHeight(), mw.minimumSizeHint().height())

        # The title bar and borders are not part of geometry(), but the screen
        # still has to hold them. Without this a window sized to the full height
        # lands with its title bar - and its top resize edge - above the top of
        # the screen. On Wayland the two rects are the same and all of this is
        # zero, because the client never sees its own decorations.
        frame, inner = mw.frameGeometry(), mw.geometry()
        pad_l = max(0, inner.x() - frame.x())
        pad_t = max(0, inner.y() - frame.y())
        pad_r = max(0, frame.right() - inner.right())
        pad_b = max(0, frame.bottom() - inner.bottom())

        w = max(min_w, min(w, avail.width() - pad_l - pad_r))
        h = max(min_h, min(h, avail.height() - pad_t - pad_b))
        # max() last: on a screen too small for the minimum, being reachable at
        # the top left beats being centred with the title bar out of range.
        x = max(avail.x() + pad_l, min(x, avail.right() - pad_r - w + 1))
        y = max(avail.y() + pad_t, min(y, avail.bottom() - pad_b - h + 1))
        mw.setGeometry(x, y, w, h)

        # A window that is still being mapped takes the position and drops the
        # size: the window manager hands out its own geometry as the window
        # appears, and a call made before that lands has nothing to hold on to.
        # This is what made every restart come up at the default 1600x900 while
        # the position looked right. Re-assert once the event loop turns, and
        # again a moment later in case the manager had the last word.
        # Both are re-asserted, and the move is not redundant: setGeometry puts
        # the frame at y, geometry() then reports the client area at y + title
        # bar, and moving to y again settles the two into a fixed relationship.
        # Saving subtracts that same offset back out, so a save/restore cycle
        # returns the window exactly where it was. Dropping this move brings the
        # drift straight back, measured at 37px per restart.
        def confirm() -> None:
            if mw.width() != w or mw.height() != h:
                mw.resize(w, h)
            if mw.x() != x or mw.y() != y:
                mw.move(x, y)

        QTimer.singleShot(0, confirm)
        QTimer.singleShot(300, confirm)

    @staticmethod
    def _centre_on_primary(mw: QWidget, w: int, h: int) -> None:
        """Last-resort placement: the saved size, in the middle of the screen we
        are sure exists, clipped to what that screen can hold."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            WindowPersist._unmaximise(mw)
            mw.resize(w, h)
            return
        avail = screen.availableGeometry()
        w = min(w, avail.width())
        h = min(h, avail.height())
        WindowPersist._place(mw, avail.x() + (avail.width() - w) // 2,
                             avail.y() + (avail.height() - h) // 2,
                             w, h, avail)
