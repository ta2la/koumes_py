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

Which buttons a panel *has* is the panel class's business (see panel.py); this
module only says what they do.
"""

import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import QUrl

from cmd_sys import CMD_SYS
from .cmds_chroma import CmdsChroma
from . import help_resolver as hr

if TYPE_CHECKING:
    from .main_window import MainWindow


def _exec(cmd: str) -> None:
    CMD_SYS().execute_thread_safe(cmd, "ui", -1, "TOOLBAR")


def wire_toolbar(win: "MainWindow") -> None:
    _wire_app_bar(win)
    _wire_reload(win)
    _wire_hide_toggles(win)
    _wire_tab_toggles(win)
    _wire_dir_navigation(win)
    _wire_fm_buttons(win)
    _wire_help(win)


def _wire_app_bar(win: "MainWindow") -> None:
    # The strip belongs to the left panel now, and a panel that does not carry
    # one leaves this None rather than growing an empty bar.
    if win.app_bar is not None:
        win.app_bar.paste.clicked.connect(lambda _=False: _exec("paste_clipboard"))


def _wire_reload(win: "MainWindow") -> None:
    CmdsChroma.set_reload_fn("left", win.left_view.reload)
    CmdsChroma.set_reload_fn("dir", win.dir_view.reload)
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
        win.p_dir.hide_parent.setText("□" if new_visible else "◧")

    def toggle_p2() -> None:
        new_visible = not win.p_rm.wrap.isVisible()
        win.p_rm.wrap.setVisible(new_visible)
        win.p_right.hide_rightmost.setText("□" if new_visible else "◨")

    CmdsChroma.set_toggle_fn("left", toggle_left)
    CmdsChroma.set_toggle_fn("p2", toggle_p2)

    win.p_dir.hide_parent.setCheckable(False)
    win.p_dir.hide_parent.setToolTip("panel_toggle left")
    win.p_dir.hide_parent.clicked.connect(lambda _=False: _exec("panel_toggle left"))

    win.p_right.hide_rightmost.setCheckable(False)
    win.p_right.hide_rightmost.setToolTip("panel_toggle p2")
    win.p_right.hide_rightmost.clicked.connect(lambda _=False: _exec("panel_toggle p2"))



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



#: what a freshly generated help says - enough to show the button works and to
#: say where to write the real thing.
_HELP_STUB = """# Nápověda

Tenhle soubor zatím nikdo nenapsal. Koumes ho založil sám, když jste poprvé
klikli na ❓ a ve stromu žádná nápověda nebyla.

**Sem se píše nápověda k tomuhle stromu.** Leží v jeho kořeni, jmenuje se po
adresáři (`<jméno adresáře>.help.md`) a je to obyčejný markdown.

Nápověda se dá napsat ke každému adresáři i ke každému souboru, vždycky pod
stejným jménem - `<jméno>.help.md` vedle toho, co vysvětluje; u adresáře uvnitř
něj. Tlačítko ❓ vezme tu nejužší, kterou najde, a když soubor svoji nemá,
zeptá se jeho adresáře a postupně jeho rodičů - až sem.

Co sem patří: co v tomhle stromu je, jak je uspořádaný, na co si dát pozor.
Klidně to nechte napsat agenta - vidí do stejných souborů jako vy.
"""


def _ensure_root_help(root: str) -> str:
    """Last resort: a tree with no help anywhere gets a starter one at its root.

    A help button that opens nothing looks broken. Rather than reporting a
    missing file, the first click writes one that says what belongs in it - and
    from then on it is the answer every deeper level falls back to.
    """
    path = hr.root_help_path(root)
    if os.path.exists(path):
        return path
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_HELP_STUB)
    except OSError:
        return ""     # read-only tree - nothing to open, say so by staying quiet
    return path


def _wire_help(win: "MainWindow") -> None:
    """❓ on dir, p1 and p2 - each shows the help of what its panel holds.

    Where it lands: a panel that shows documents shows its own help (p1 into p1,
    p2 into p2). The dir panel has nowhere to put a document, so its help goes
    to p1.

    It goes through `chroma_setfile` like any other navigation, so the click is
    logged and broadcast; a button that reached into the view directly would be
    the one thing on the toolbar an agent could not reproduce.
    """
    def show(target_panel: str, help_path: str) -> None:
        if not help_path:
            help_path = _ensure_root_help(win.root)
        if not help_path:
            return
        # The target may be sitting on its www tab, where the file would load
        # behind it.
        pnl = win.p_rm if target_panel == "p2" else win.p_right
        if pnl.stack is not None and pnl.stack.currentIndex() == 1:
            _exec(f"tab_toggle {target_panel}")
        tail = " --p2" if target_panel == "p2" else ""
        _exec(f'chroma_setfile "{help_path}"{tail}')

    def wire(button, tip: str, resolve) -> None:
        if button is None:
            return
        button.setToolTip(tip)
        button.clicked.connect(lambda _=False: resolve())

    wire(win.p_dir.help, "chroma_setfile <help of this dir>",
         lambda: show("p1", hr.find_help_for_dir(
             CmdsChroma._last_dir or win.root, win.root)))

    wire(win.p_right.help, "chroma_setfile <help of this file>",
         lambda: show("p1", hr.find_help_for_file(
             CmdsChroma._last_file, win.root)))

    def p2_file() -> str:
        sel = CmdsChroma._sel_for("p2")
        return sel.file if sel is not None else ""

    wire(win.p_rm.help, "chroma_setfile <help of this file> --p2",
         lambda: show("p2", hr.find_help_for_file(p2_file(), win.root)))


def _wire_fm_buttons(win: "MainWindow") -> None:
    win.p_dir.fm.setToolTip("chroma_openfm")
    win.p_dir.fm.clicked.connect(lambda _=False: _exec("chroma_openfm"))

    # Tabbable panels: context-aware. View mode opens the current file, www mode
    # opens the current URL. Both go through the `open_extern` command rather
    # than spawning a process here, so the click is logged, broadcast, and
    # reproducible from outside. Port of the C++ wireExternal lambda.
    def wire_external(pnl, www_view) -> None:
        if pnl.fm is None:
            return
        pnl.fm.setToolTip("open_extern <current file / url>")

        def on_click(_checked=False, p=pnl, w=www_view) -> None:
            in_www = p.stack is not None and p.stack.currentIndex() == 1
            if in_www:
                if w is None:
                    return
                target = w.url().toString()
                if not target or target == "about:blank":
                    return
            else:
                target = CmdsChroma._last_file
                if not target:
                    return
            _exec(f'open_extern "{target}"')

        pnl.fm.clicked.connect(on_click)

    wire_external(win.p_right, win.right_www)
    wire_external(win.p_rm, win.rm_www)
