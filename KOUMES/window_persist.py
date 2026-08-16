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
"""WindowPersist - save/restore main window geometry across sessions.

Python port of APPS/AI_T2LS/WindowPersist.h + the config helper from
base2/app_common/AppUtility.h::replaceOrAppendInConfig.

Line format written to `<dir_config>/config.t2l`:
    set_window <x> <y> <w> <h> <screenIdx> <screenW> <screenH>

Restore skips the line if the screen at `screenIdx` doesn't match the saved
(screenW, screenH) - protects against monitor topology changes.
"""

import os
from pathlib import Path
from typing import Optional

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
        x, y, w, h = mw.x(), mw.y(), mw.width(), mw.height()
        idx = cls._screen_index(mw)
        if idx < 0:
            return f"set_window {x} {y} {w} {h}"
        g = QGuiApplication.screens()[idx].geometry()
        return (
            f"set_window {x - g.x()} {y - g.y()} {w} {h} "
            f"{idx} {g.width()} {g.height()}"
        )

    @classmethod
    def _save_inline(cls, mw: Optional[QWidget]) -> None:
        if mw is None:
            return
        try:
            replace_or_append_in_config(cls._serialize(mw))
        except OSError:
            pass

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
                mw.setGeometry(x, y, w, h)
                args.append(f"{x},{y} {w}x{h}", "WINDOW")
                return 0
            try:
                idx = int(pos[4])
            except ValueError:
                return args.append_error("set_window: screen must be integer")
            screens = QGuiApplication.screens()
            if idx < 0 or idx >= len(screens):
                args.append("no such screen — skipping restore", "SKIP")
                return 0
            g = screens[idx].geometry()
            if len(pos) >= 7:
                try:
                    sw = int(pos[5]); sh = int(pos[6])
                except ValueError:
                    return args.append_error("set_window: sw/sh must be integers")
                if sw != g.width() or sh != g.height():
                    args.append(
                        f"screen {idx} size {g.width()}x{g.height()} != saved {sw}x{sh} — skipping",
                        "SKIP",
                    )
                    return 0
            mw.setGeometry(g.x() + x, g.y() + y, w, h)
            args.append(f"{x},{y} {w}x{h} @ screen {idx}", "WINDOW")
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
