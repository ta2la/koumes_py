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
"""Panel - one column of the 4-panel main window.

Python port of the `Panel_` struct + `wrapPanel_` factory from
APPS/AI_T2LS/Main.cpp.

A panel = toolbar row (refresh + navigation buttons)
       + role bar (role label left, switcher right - see role_bar.py)
       + info bar (path / selection / viewer with per-row copy buttons)
       + content stack (view widget, optionally with a www view tab)
"""

from typing import Optional

from PyQt6.QtCore import Qt

from .app_paths import AppPaths
from .app_bar import AppBar
from .role_bar import ContentRoleBar, DirRoleBar, ViewerRoleBar
from .theme import tinted
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


_TOOLBAR_QSS = (
    "QWidget { background: #f5f5f5; border-bottom: 1px solid #ccc; }"
    "QPushButton { padding: 4px 14px; border: 1px solid #bbb; border-radius: 3px;"
    " background: #fff; font-size: 12px; }"
    "QPushButton:checked { background: #dbeafe; border-color: #2563eb; color: #1e40af;"
    " font-weight: 700; }"
    "QPushButton:hover:!checked { background: #eef0f3; }"
)

_ICON_BTN_QSS = "font-size: 27px; padding: 0; min-width: 38px; min-height: 38px;"

_TAB_TOGGLE_QSS = (
    "background: #fef3c7; color: #92400e; border: 1px solid #d97706;"
    " border-radius: 4px; padding: 4px 12px; font-weight: 700; font-size: 13px;"
    " min-width: 60px; min-height: 34px;"
)

_SETTINGS = AppPaths.inst().settings()
_INFO_BG = _SETTINGS.get("info_bg", "#1f2937")
_INFO_BORDER = _SETTINGS.get("info_border", "#111827")

def _info_bar_qss(bg: str, border: str) -> str:
    return (
        f"QWidget {{ background: {bg}; border-bottom: 1px solid {border}; }}"
        "QLabel  { background: transparent; border: none; color: #d1d5db;"
        "          font: 15px 'ui-monospace', monospace; }"
        "QLabel[clickable=\"true\"]:hover { color: #fbbf24; }"
    )


_INFO_BAR_QSS = _info_bar_qss(_INFO_BG, _INFO_BORDER)
# Warm counterpart for the tinted panel - the info bar is dark by design, so it
# takes the tint as a warmer dark rather than a yellow one.
_INFO_BAR_QSS_TINT = tinted(_INFO_BAR_QSS)

_URL_INPUT_QSS = (
    "QLineEdit { background: #111827; color: #f9fafb; border: 1px solid #4b5563;"
    "            border-radius: 3px; padding: 4px 8px; font: 14px monospace; }"
)

_COPY_BTN_QSS = (
    "QPushButton { background: transparent; border: none;"
    " color: #6b7280; padding: 0 4px; min-width: 20px;"
    " font-size: 13px; }"
    "QPushButton:hover { color: #fbbf24; }"
)


def _make_copy_btn(parent: QWidget, target_label: QLabel, prop: str = "cmdPath",
                   btn_prop: str = "copyBtn",
                   tooltip: str = "Copy path to clipboard") -> QPushButton:
    btn = QPushButton("📋", parent)
    btn.setToolTip(tooltip)
    btn.setStyleSheet(_COPY_BTN_QSS)
    # One label can carry several copy buttons (path, path:line), so each is
    # parked under its own key - `_sync_copy_btn` toggles them by that key.
    target_label.setProperty(btn_prop, btn)
    btn.hide()

    def do_copy() -> None:
        p = target_label.property(prop)
        if not p:
            p = target_label.toolTip()
        if p:
            QGuiApplication.clipboard().setText(str(p))

    btn.clicked.connect(do_copy)
    return btn


_MENU_PAGE_QSS = (
    "QWidget#menuPage { background: #111827; }"
)


class MenuPage(QWidget):
    """The left panel's fourth tab: actions, not a document.

    A page rather than a strip, so its controls get the panel's full width and
    a status line that has room to say what happened. Built to be added to -
    right now it holds the clipboard paste; anything else that acts on the app
    rather than on the file in view belongs here too.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("menuPage")
        self.setStyleSheet(_MENU_PAGE_QSS)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.app_bar = AppBar(self)
        lay.addWidget(self.app_bar)
        # Actions sit at the top and the slack goes underneath, so adding a
        # second one later does not re-centre the first.
        lay.addStretch(1)


class Panel(QWidget):
    """One column of the main window - the shape all four panels share.

        [ toolbar    ]  action buttons for this role
        [ role bar   ]  role label left, viewer / content switcher right
        [ info bar   ]  path / selection / viewer, each with a copy button
        [ content    ]  the view, or a view/www stack on the tabbable panels

    A subclass says what its role *is* by setting the class attributes below;
    it does not rebuild the layout. Every button exists on every panel so the
    wiring code can reach it unconditionally - `TOOLBAR` decides which ones are
    on screen, in the fixed order the base lays them out.
    """

    #: command-level panel key: left / dir / p1 / p2 (`panel_reload <key>`)
    ROLE = ""
    #: toolbar buttons this role shows, by attribute name
    TOOLBAR: tuple = ("refresh",)
    #: carries a second (www) tab: adds tab_toggle, url_input and the stack
    HAS_WWW = False
    #: which role bar this panel wears - see role_bar.py
    ROLE_BAR = ViewerRoleBar
    #: washes the chrome in a faint warm tone (see theme.TINT)
    TINT = False
    #: carries the paste strip - the left panel only, see app_bar.AppBar
    HAS_APP_BAR = False

    def __init__(self, content: QWidget,
                 www_view: Optional[QWebEngineView] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.role = self.ROLE
        self.www_view = www_view if self.HAS_WWW else None
        self.stack: Optional[QStackedWidget] = None
        self.url_input: Optional[QLineEdit] = None
        self.tab_toggle: Optional[QPushButton] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_toolbar(layout)
        self._build_role_bar(layout)
        self._build_info_bar(layout)
        self._build_content(layout, content)

    @property
    def wrap(self) -> QWidget:
        """The panel widget itself. Kept as a name for the splitter code."""
        return self

    def _qss(self, qss: str) -> str:
        return tinted(qss) if self.TINT else qss

    # -- toolbar ------------------------------------------------------------
    def _build_toolbar(self, outer: QVBoxLayout) -> None:
        toolbar = QWidget(self)
        toolbar.setStyleSheet(self._qss(_TOOLBAR_QSS))
        toolbar.setFixedHeight(54)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 6, 8, 6)
        tb.setSpacing(8)
        self.toolbar = toolbar

        if self.HAS_WWW:
            self.tab_toggle = QPushButton("view", toolbar)
            self.tab_toggle.setToolTip("Toggle view/www")
            self.tab_toggle.setStyleSheet(_TAB_TOGGLE_QSS)

        def icon_btn(text: str, tip: str, checkable: bool = False) -> QPushButton:
            b = QPushButton(text, toolbar)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setStyleSheet(_ICON_BTN_QSS)
            return b

        self.refresh = icon_btn("🔄", "Reload")
        self.hide_parent = icon_btn("□", "Dir Panel", checkable=True)
        self.dir_up = icon_btn("⬅", "Dir Up")
        self.fm = icon_btn("⬈", "Open externally (fm / browser)")
        self.reveal_dir = icon_btn("📂", "Show doc's dir in dir panel")
        self.hide_rightmost = icon_btn("□", "Rightmost Panel", checkable=True)

        for name in ("tab_toggle", "refresh", "hide_parent", "dir_up",
                     "fm", "reveal_dir", "hide_rightmost"):
            btn = getattr(self, name)
            if btn is None:
                continue
            btn.setVisible(name in self.TOOLBAR)
            tb.addWidget(btn)

        tb.addStretch(1)
        outer.addWidget(toolbar)

    # -- role bar -----------------------------------------------------------
    def _build_role_bar(self, outer: QVBoxLayout) -> None:
        self.role_bar = self.ROLE_BAR(self.ROLE, tint=self.TINT, parent=self)
        outer.addWidget(self.role_bar)

    # The switches live in the role bar; these keep the old names working for
    # the wiring code, and fail loudly on a panel whose bar has no such thing.
    @property
    def role_label(self) -> QLabel:
        return self.role_bar.label

    @property
    def viewer_bar(self) -> QWidget:
        return self.role_bar.viewer_bar

    @property
    def custom(self) -> QPushButton:
        return self.role_bar.custom

    @property
    def dflt(self) -> QPushButton:
        return self.role_bar.dflt

    @property
    def log(self) -> QPushButton:
        return self.role_bar.log

    @property
    def menu(self) -> QPushButton:
        return self.role_bar.menu

    # -- info bar -----------------------------------------------------------
    def _build_info_bar(self, outer: QVBoxLayout) -> None:
        bar = QWidget(self)
        bar.setStyleSheet(_INFO_BAR_QSS_TINT if self.TINT else _INFO_BAR_QSS)
        bar.setFixedHeight(54)
        ib = QVBoxLayout(bar)
        ib.setContentsMargins(10, 4, 10, 4)
        ib.setSpacing(2)
        self.info_bar = bar

        self.info_path = QLabel(bar)
        self.info_selection = QLabel(bar)
        self.info_viewer = QLabel(bar)
        self.info_path.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.info_selection.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.info_viewer.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.info_path.setStyleSheet("color: #f9fafb; font-weight: 700;")
        self.info_selection.setStyleSheet("color: #9ca3af; font-weight: 400;")
        self.info_viewer.setStyleSheet("color: #fecaca; font-weight: 700;")
        for lbl in (self.info_path, self.info_selection, self.info_viewer):
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # Both copy buttons sit on the path row: that is the row which stays
        # when the selection row goes, and a button is worth having next to the
        # text it copies rather than one row below it.
        self.copy_path = _make_copy_btn(bar, self.info_path)
        self.copy_path_line = _make_copy_btn(
            bar, self.info_path, prop="cmdPathLine", btn_prop="copyBtnLine",
            tooltip="Copy path with line to clipboard",
        )
        self.copy_viewer = _make_copy_btn(bar, self.info_viewer)

        def row(*widgets, tail: bool = False) -> None:
            r = QHBoxLayout()
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(4)
            for w, stretch in widgets:
                r.addWidget(w, stretch)
            # `tail` parks the slack behind the last widget instead of inside
            # the label, so the buttons follow the text instead of drifting off
            # to the far edge of the bar.
            if tail:
                r.addStretch(1)
            ib.addLayout(r)

        # Maximum, not the default Preferred: the label asks for the width of
        # its whole path, and without this the row would rather push the button
        # off the panel than let the text be clipped.
        self.info_path.setSizePolicy(QSizePolicy.Policy.Maximum,
                                     QSizePolicy.Policy.Preferred)

        row((self.copy_path, 0), (self.info_path, 0), (self.copy_path_line, 0),
            tail=True)
        row((self.info_viewer, 1), (self.copy_viewer, 0))
        # info_selection is kept and kept up to date - `chroma_*` reads it and
        # the bus broadcasts it - but it is no longer laid out. It said the
        # same thing as the path row, which now carries the position itself.
        self.info_selection.hide()

        if self.HAS_WWW:
            self.url_input = QLineEdit(bar)
            self.url_input.setPlaceholderText("https://…")
            self.url_input.setStyleSheet(_URL_INPUT_QSS)
            self.url_input.setVisible(False)
            ib.addWidget(self.url_input)

        outer.addWidget(bar)

    # -- content ------------------------------------------------------------
    def _build_content(self, outer: QVBoxLayout, content: QWidget) -> None:
        if self.HAS_APP_BAR:
            # Left is a stack of a page and a menu, not a page and a www tab.
            # Three of its tabs swap the HTML behind `content`; the fourth one
            # brings up widgets, which is why they cannot share one view.
            self.menu_page = MenuPage(self)
            self.app_bar = self.menu_page.app_bar
            self.stack = QStackedWidget()
            self.stack.addWidget(content)
            self.stack.addWidget(self.menu_page)
            outer.addWidget(self.stack, 1)
            return
        self.app_bar = None
        if self.www_view is None:
            outer.addWidget(content, 1)
            return
        self.stack = QStackedWidget()
        self.stack.addWidget(content)
        self.stack.addWidget(self.www_view)
        outer.addWidget(self.stack, 1)


class LeftPanel(Panel):
    """Parent / bookmarks / log panel. Outside the viewer world: it switches
    between three canned contents, so it carries the content switch instead of
    a viewer bar and wears the tint that says "different category"."""

    ROLE = "left"
    TOOLBAR = ("refresh",)
    ROLE_BAR = ContentRoleBar
    TINT = True
    HAS_APP_BAR = True


class DirPanel(Panel):
    """The file browser. Owns dir navigation and the ◧ that hides left - the
    button for a neighbour lives here, never the one that would hide us."""

    ROLE = "dir"
    TOOLBAR = ("refresh", "hide_parent", "dir_up", "fm")
    ROLE_BAR = DirRoleBar


class DetailPanel(Panel):
    """p1 - the document panel. Tabbable (view/www), reveals a doc's dir in
    dir, and carries the ◨ that hides its neighbour p2."""

    ROLE = "p1"
    TOOLBAR = ("tab_toggle", "refresh", "hide_rightmost", "fm", "reveal_dir")
    HAS_WWW = True


class RightmostPanel(Panel):
    """p2 - second document panel, the one `chroma_setfile --p2` writes to.
    Same as p1 minus the toggle that would hide itself."""

    ROLE = "p2"
    TOOLBAR = ("tab_toggle", "refresh", "fm", "reveal_dir")
    HAS_WWW = True
