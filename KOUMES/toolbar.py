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
"""wire_toolbar - connect Panel buttons to CmdSys.

Python port of the toolbar-wiring section of the C++ predecessor's Main.cpp.

Every button click is routed through CmdSys.execute_thread_safe(cmdline, ..., "TOOLBAR")
so it gets logged, broadcast, and can be triggered externally via WS.
The actual action is performed by a callback registered with CmdsChroma
(reload / toggle / tab_toggle dispatch tables).

Which buttons a panel *has* is the panel class's business (see panel.py); this
module only says what they do.
"""

import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QPushButton

from cmd_sys import CMD_SYS
from .app_paths import AppPaths
from .cmds_chroma import CmdsChroma

if TYPE_CHECKING:
    from .main_window import MainWindow


def _exec(cmd: str) -> None:
    CMD_SYS().execute_thread_safe(cmd, "ui", -1, "TOOLBAR")


def wire_toolbar(win: "MainWindow") -> None:
    _wire_app_bar(win)
    _wire_reload(win)
    _wire_hide_toggles(win)
    _wire_tab_toggles(win)
    _wire_active_panel(win)
    _wire_dir_navigation(win)
    _wire_fm_buttons(win)
    _wire_config_buttons(win)


def _wire_app_bar(win: "MainWindow") -> None:
    # The strip belongs to the left panel now, and a panel that does not carry
    # one leaves this None rather than growing an empty bar.
    if win.app_bar is not None:
        win.app_bar.paste.clicked.connect(lambda _=False: _exec("paste_clipboard"))


def _wire_reload(win: "MainWindow") -> None:
    CmdsChroma.set_reload_fn("left", win.left_view.reload)
    # Not `dir_view.reload()` - that would drop the panel back to the dir in
    # its URL, which is where it was opened, typically the sandbox root.
    CmdsChroma.set_reload_fn("dir", win._reload_dir)
    CmdsChroma.set_reload_fn("p1", win.detail_view.reload)
    CmdsChroma.set_reload_fn("p2", win.rm_view.reload)

    for panel, key in (
        (win.p_left, "left"),
        (win.p_dir, "dir"),
        (win.p_right, "p1"),
        (win.p_rm, "p2"),
    ):
        panel.refresh.setToolTip(f"panel_reload {key}")
        panel.refresh.clicked.connect(lambda _=False, k=key: _exec(f"panel_reload {k}"))


def _wire_hide_toggles(win: "MainWindow") -> None:
    def toggle_left() -> None:
        new_visible = not win.p_left.wrap.isVisible()
        win.p_left.wrap.setVisible(new_visible)
        if new_visible:
            win.ensure_panel_width("left")
        win.p_dir.hide_parent.setText("□" if new_visible else "◧")

    def toggle_p2() -> None:
        new_visible = not win.p_rm.wrap.isVisible()
        win.p_rm.wrap.setVisible(new_visible)
        # Visible is not the same as wide: a slot left at zero shows nothing.
        if new_visible:
            win.ensure_panel_width("p2")
        win.p_right.hide_rightmost.setText("□" if new_visible else "◨")

    CmdsChroma.set_toggle_fn("left", toggle_left)
    CmdsChroma.set_toggle_fn("p2", toggle_p2)

    win.p_dir.hide_parent.setCheckable(False)
    win.p_dir.hide_parent.setToolTip("panel_toggle left")
    win.p_dir.hide_parent.clicked.connect(lambda _=False: _exec("panel_toggle left"))

    win.p_right.hide_rightmost.setCheckable(False)
    win.p_right.hide_rightmost.setToolTip("panel_toggle p2")
    win.p_right.hide_rightmost.clicked.connect(lambda _=False: _exec("panel_toggle p2"))



def _wire_active_panel(win: "MainWindow") -> None:
    """The p1 / p2 name chip picks which panel takes an unaddressed file.

    The click fires `panel_active <key>` rather than flipping anything itself -
    the painting is what the command does, so a click and a sent command end up
    in exactly the same place.
    """
    CmdsChroma.set_active_fn(win.set_active_panel)
    for panel, key in ((win.p_right, "p1"), (win.p_rm, "p2")):
        chip = panel.role_bar.label
        if not isinstance(chip, QPushButton):
            continue
        chip.clicked.connect(lambda _=False, k=key: _exec(f"panel_active {k}"))
    win.set_active_panel(CmdsChroma.active_panel())


def _wire_tab_toggles(win: "MainWindow") -> None:
    for panel, key in ((win.p_right, "p1"), (win.p_rm, "p2")):
        if panel.tab_toggle is None or panel.stack is None:
            continue

        def make_apply(p=panel):
            def apply(www: bool) -> None:
                p.stack.setCurrentIndex(1 if www else 0)
                p.info_path.setVisible(not www)
                p.info_viewer.setVisible(not www)
                if p.url_input is not None:
                    p.url_input.setVisible(www)
                if p.tab_toggle is not None:
                    p.tab_toggle.setText("www" if www else "view")
            return apply

        apply = make_apply()

        def make_toggle(p=panel, apply=apply):
            def do_toggle() -> None:
                now_www = p.stack.currentIndex() == 0
                apply(now_www)
            return do_toggle

        CmdsChroma.set_tab_toggle_fn(key, make_toggle())
        panel.tab_toggle.setToolTip(f"tab_toggle {key}")
        panel.tab_toggle.clicked.connect(lambda _=False, k=key: _exec(f"tab_toggle {k}"))

        if panel.url_input is not None and panel.www_view is not None:
            def make_url_handler(p=panel):
                def go() -> None:
                    s = p.url_input.text().strip()
                    if not s:
                        return
                    if "://" not in s:
                        s = "https://" + s
                    p.www_view.setUrl(QUrl(s))
                return go

            panel.url_input.returnPressed.connect(make_url_handler())


def _wire_dir_navigation(win: "MainWindow") -> None:
    win.p_dir.dir_up.setToolTip("dir_up")
    win.p_dir.dir_up.clicked.connect(lambda _=False: _exec("dir_up"))

    # Both document panels reveal their own file's dir - the button was on p2's
    # toolbar all along, just wired to nothing.
    for panel, key in ((win.p_right, "p1"), (win.p_rm, "p2")):
        panel.reveal_dir.setToolTip(f"reveal_dir {key}")
        panel.reveal_dir.clicked.connect(
            lambda _=False, k=key: _exec(f"reveal_dir {k}"))


def _wire_fm_buttons(win: "MainWindow") -> None:
    win.p_dir.fm.setToolTip("chroma_openfm")
    win.p_dir.fm.clicked.connect(lambda _=False: _exec("chroma_openfm"))

    # Document panels open the file they are showing. It goes through the
    # `open_extern` command rather than spawning a process here, so the click is
    # logged, broadcast, and reproducible from outside. Port of the C++
    # wireExternal lambda, minus its www branch - there is no www tab any more.
    def wire_external(pnl) -> None:
        if pnl.fm is None:
            return
        pnl.fm.setToolTip("open_extern <current file>")

        def on_click(_checked=False, p=pnl) -> None:
            target = CmdsChroma._last_file
            if not target:
                return
            _exec(f'open_extern "{target}"')

        pnl.fm.clicked.connect(on_click)

    wire_external(win.p_right)
    wire_external(win.p_rm)


def _wire_config_buttons(win: "MainWindow") -> None:
    """Extra buttons on the p1 / p2 toolbars, one per `panel_button:` line in
    the deployment's config.t2l:

        panel_button: 👥 | Employees by dir | chroma_setfile /path/to/x.t2l --{panel}

    icon | tooltip | command. `{panel}` becomes p1 or p2, so the button opens
    things in the panel it sits on. The command goes through CmdSys like every
    other toolbar click."""
    from .panel import icon_btn_qss
    for raw in AppPaths.inst().settings_list("panel_button"):
        parts = [x.strip() for x in raw.split("|", 2)]
        if len(parts) != 3 or not parts[0] or not parts[2]:
            continue
        icon, tip, cmd = parts
        for panel, key in ((win.p_right, "p1"), (win.p_rm, "p2")):
            lay = panel.toolbar.layout()
            b = QPushButton(icon, panel.toolbar)
            b.setToolTip(f"{tip}\n{cmd.replace('{panel}', key)}" if tip else cmd.replace("{panel}", key))
            b.setStyleSheet(icon_btn_qss())
            # before the trailing stretch, next to the built-in buttons
            lay.insertWidget(lay.count() - 1, b)
            b.clicked.connect(lambda _=False, c=cmd.replace("{panel}", key): _exec(c))
