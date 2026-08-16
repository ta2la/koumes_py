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

Python port of the toolbar-wiring section of APPS/AI_T2LS/Main.cpp.

Every button click is routed through CmdSys.execute_thread_safe(cmdline, ..., "TOOLBAR")
so it gets logged, broadcast, and can be triggered externally via WS.
The actual action is performed by a callback registered with CmdsChroma
(reload / toggle / tab_toggle dispatch tables).
"""

import subprocess
from typing import TYPE_CHECKING

from PyQt6.QtCore import QUrl

from cmd_sys import CMD_SYS
from .cmds_chroma import CmdsChroma

if TYPE_CHECKING:
    from .main_window import MainWindow


def _exec(cmd: str) -> None:
    CMD_SYS().execute_thread_safe(cmd, "ui", -1, "TOOLBAR")


def wire_toolbar(win: "MainWindow") -> None:
    _wire_reload(win)
    _wire_hide_toggles(win)
    _wire_tab_toggles(win)
    _wire_dir_navigation(win)
    _wire_fm_buttons(win)


def _wire_reload(win: "MainWindow") -> None:
    CmdsChroma.set_reload_fn("left", win.left_view.reload)
    CmdsChroma.set_reload_fn("dir", win.mid_view.reload)
    CmdsChroma.set_reload_fn("p1", win.detail_view.reload)
    CmdsChroma.set_reload_fn("p2", win.rm_view.reload)

    for panel, key in (
        (win.p_left, "left"),
        (win.p_mid, "dir"),
        (win.p_right, "p1"),
        (win.p_rm, "p2"),
    ):
        panel.refresh.setToolTip(f"panel_reload {key}")
        panel.refresh.clicked.connect(lambda _=False, k=key: _exec(f"panel_reload {k}"))


def _wire_hide_toggles(win: "MainWindow") -> None:
    def toggle_left() -> None:
        new_visible = not win.p_left.wrap.isVisible()
        win.p_left.wrap.setVisible(new_visible)
        win.p_mid.hide_parent.setText("□" if new_visible else "◧")

    def toggle_p2() -> None:
        new_visible = not win.p_rm.wrap.isVisible()
        win.p_rm.wrap.setVisible(new_visible)
        win.p_right.hide_rightmost.setText("□" if new_visible else "◨")

    CmdsChroma.set_toggle_fn("left", toggle_left)
    CmdsChroma.set_toggle_fn("p2", toggle_p2)

    win.p_mid.hide_parent.setCheckable(False)
    win.p_mid.hide_parent.setToolTip("panel_toggle left")
    win.p_mid.hide_parent.clicked.connect(lambda _=False: _exec("panel_toggle left"))

    win.p_right.hide_rightmost.setCheckable(False)
    win.p_right.hide_rightmost.setToolTip("panel_toggle p2")
    win.p_right.hide_rightmost.clicked.connect(lambda _=False: _exec("panel_toggle p2"))

    win.p_rm.hide_rightmost.setVisible(False)
    win.p_left.hide_parent.setVisible(False)


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
    win.p_mid.dir_up.setToolTip("dir_up")
    win.p_mid.dir_up.clicked.connect(lambda _=False: _exec("dir_up"))

    win.p_right.reveal_dir.setToolTip("reveal_dir")
    win.p_right.reveal_dir.clicked.connect(lambda _=False: _exec("reveal_dir"))

    for pnl in (win.p_left, win.p_mid, win.p_right, win.p_rm):
        pnl.reveal_dir.setVisible(pnl is win.p_right)
        pnl.dir_up.setVisible(pnl is win.p_mid)


def _wire_fm_buttons(win: "MainWindow") -> None:
    win.p_mid.fm.setToolTip("chroma_openfm")
    win.p_mid.fm.clicked.connect(lambda _=False: _exec("chroma_openfm"))

    win.p_right.fm.setToolTip("open_extern (detail file)")

    def open_detail() -> None:
        f = CmdsChroma._last_file
        if f:
            subprocess.Popen(["xdg-open", f])

    win.p_right.fm.clicked.connect(lambda _=False: open_detail())

    for pnl in (win.p_left, win.p_rm):
        pnl.fm.setVisible(False)
