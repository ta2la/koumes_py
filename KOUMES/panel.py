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

A panel = toolbar row (refresh + navigation buttons + viewer switch bar)
       + info bar (path / selection / viewer with per-row copy buttons)
       + content stack (view widget, optionally with a www view tab)
"""

from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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

_INFO_BAR_QSS = (
    "QWidget { background: #1f2937; border-bottom: 1px solid #111827; }"
    "QLabel  { background: transparent; border: none;"
    "          font: 15px 'ui-monospace', monospace; }"
    "QLabel[clickable=\"true\"]:hover { color: #fbbf24; }"
)

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


@dataclass
class Panel:
    wrap: QWidget = None
    custom: QPushButton = None
    dflt: QPushButton = None
    log: QPushButton = None
    viewer_bar: QWidget = None
    fm: QPushButton = None
    hide_parent: QPushButton = None
    hide_rightmost: QPushButton = None
    dir_up: QPushButton = None
    reveal_dir: QPushButton = None
    refresh: QPushButton = None
    tab_toggle: Optional[QPushButton] = None
    info_path: QLabel = None
    info_viewer: QLabel = None
    info_selection: QLabel = None
    copy_path: QPushButton = None
    copy_viewer: QPushButton = None
    copy_selection: QPushButton = None
    url_input: Optional[QLineEdit] = None
    info_bar: QWidget = None
    stack: Optional[QStackedWidget] = None
    www_view: Optional[QWebEngineView] = None


def _make_copy_btn(parent: QWidget, target_label: QLabel) -> QPushButton:
    btn = QPushButton("📋", parent)
    btn.setToolTip("Copy path to clipboard")
    btn.setStyleSheet(_COPY_BTN_QSS)
    target_label.setProperty("copyBtn", btn)
    btn.hide()

    def do_copy() -> None:
        p = target_label.property("cmdPath")
        if not p:
            p = target_label.toolTip()
        if p:
            QGuiApplication.clipboard().setText(str(p))

    btn.clicked.connect(do_copy)
    return btn


def wrap_panel(content: QWidget, www_view: Optional[QWebEngineView] = None) -> Panel:
    """Build a panel widget = toolbar + info bar + content (view [+ www stack])."""
    p = Panel()
    p.www_view = www_view
    p.wrap = QWidget()

    layout = QVBoxLayout(p.wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    toolbar = QWidget(p.wrap)
    toolbar.setStyleSheet(_TOOLBAR_QSS)
    toolbar.setFixedHeight(54)
    tb_layout = QHBoxLayout(toolbar)
    tb_layout.setContentsMargins(8, 6, 8, 6)
    tb_layout.setSpacing(8)

    p.custom = QPushButton("custom", toolbar)
    p.dflt = QPushButton("default", toolbar)
    p.log = QPushButton("log", toolbar)
    p.custom.setCheckable(True)
    p.dflt.setCheckable(True)
    p.log.setCheckable(True)
    p.dflt.setChecked(True)
    p.custom.setVisible(False)
    p.log.setVisible(False)

    grp = QButtonGroup(toolbar)
    grp.setExclusive(True)
    grp.addButton(p.custom)
    grp.addButton(p.dflt)
    grp.addButton(p.log)

    if www_view is not None:
        p.tab_toggle = QPushButton("view", toolbar)
        p.tab_toggle.setToolTip("Toggle view/www")
        p.tab_toggle.setStyleSheet(_TAB_TOGGLE_QSS)
        tb_layout.addWidget(p.tab_toggle)

    p.refresh = QPushButton("🔄", toolbar)
    p.refresh.setToolTip("Reload")
    p.refresh.setStyleSheet(_ICON_BTN_QSS)
    tb_layout.addWidget(p.refresh)

    p.hide_parent = QPushButton("□", toolbar)
    p.hide_parent.setToolTip("Dir Panel")
    p.hide_parent.setCheckable(True)
    p.hide_parent.setStyleSheet(_ICON_BTN_QSS)
    tb_layout.addWidget(p.hide_parent)

    p.dir_up = QPushButton("⬅", toolbar)
    p.dir_up.setToolTip("Dir Up")
    p.dir_up.setStyleSheet(_ICON_BTN_QSS)
    tb_layout.addWidget(p.dir_up)

    p.fm = QPushButton("⬈", toolbar)
    p.fm.setToolTip("Open externally (fm / browser)")
    p.fm.setStyleSheet(_ICON_BTN_QSS)
    tb_layout.addWidget(p.fm)

    p.reveal_dir = QPushButton("📂", toolbar)
    p.reveal_dir.setToolTip("Show doc's dir in mid panel")
    p.reveal_dir.setStyleSheet(_ICON_BTN_QSS)
    tb_layout.addWidget(p.reveal_dir)

    p.hide_rightmost = QPushButton("□", toolbar)
    p.hide_rightmost.setToolTip("Rightmost Panel")
    p.hide_rightmost.setCheckable(True)
    p.hide_rightmost.setStyleSheet(_ICON_BTN_QSS)
    tb_layout.addWidget(p.hide_rightmost)

    tb_layout.addStretch(1)

    p.viewer_bar = QWidget(toolbar)
    vb_layout = QHBoxLayout(p.viewer_bar)
    vb_layout.setContentsMargins(0, 0, 0, 0)
    vb_layout.setSpacing(4)
    tb_layout.addWidget(p.viewer_bar)
    tb_layout.addWidget(p.custom)
    tb_layout.addWidget(p.dflt)
    tb_layout.addWidget(p.log)

    layout.addWidget(toolbar)

    info_bar = QWidget(p.wrap)
    info_bar.setStyleSheet(_INFO_BAR_QSS)
    info_bar.setFixedHeight(76)
    ib_layout = QVBoxLayout(info_bar)
    ib_layout.setContentsMargins(10, 4, 10, 4)
    ib_layout.setSpacing(2)

    p.info_path = QLabel(info_bar)
    p.info_selection = QLabel(info_bar)
    p.info_viewer = QLabel(info_bar)
    p.info_path.setAlignment(Qt.AlignmentFlag.AlignLeft)
    p.info_selection.setAlignment(Qt.AlignmentFlag.AlignLeft)
    p.info_viewer.setAlignment(Qt.AlignmentFlag.AlignRight)
    p.info_path.setStyleSheet("color: #f9fafb; font-weight: 700;")
    p.info_selection.setStyleSheet("color: #9ca3af; font-weight: 400;")
    p.info_viewer.setStyleSheet("color: #fecaca; font-weight: 700;")
    p.info_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    p.info_selection.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    p.info_viewer.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    p.copy_path = _make_copy_btn(info_bar, p.info_path)
    p.copy_viewer = _make_copy_btn(info_bar, p.info_viewer)
    p.copy_selection = _make_copy_btn(info_bar, p.info_selection)

    row1 = QHBoxLayout()
    row1.setContentsMargins(0, 0, 0, 0)
    row1.setSpacing(4)
    row1.addWidget(p.copy_path)
    row1.addWidget(p.info_path, 1)
    ib_layout.addLayout(row1)

    row2 = QHBoxLayout()
    row2.setContentsMargins(0, 0, 0, 0)
    row2.setSpacing(4)
    row2.addWidget(p.copy_selection)
    row2.addWidget(p.info_selection, 1)
    ib_layout.addLayout(row2)

    row3 = QHBoxLayout()
    row3.setContentsMargins(0, 0, 0, 0)
    row3.setSpacing(4)
    row3.addWidget(p.info_viewer, 1)
    row3.addWidget(p.copy_viewer)
    ib_layout.addLayout(row3)

    if www_view is not None:
        p.url_input = QLineEdit(info_bar)
        p.url_input.setPlaceholderText("https://…")
        p.url_input.setStyleSheet(_URL_INPUT_QSS)
        p.url_input.setVisible(False)
        ib_layout.addWidget(p.url_input)

    layout.addWidget(info_bar)
    p.info_bar = info_bar

    if www_view is not None:
        p.stack = QStackedWidget()
        p.stack.addWidget(content)
        p.stack.addWidget(www_view)
        layout.addWidget(p.stack, 1)
    else:
        layout.addWidget(content, 1)

    return p
