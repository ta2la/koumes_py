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
"""Shared look - the tint that marks a panel as a different category.

Left is not a viewer panel: it picks between three canned contents instead of
between viewers for a file. A faint warm wash over its chrome says so without
shouting. The web view inside paints its own background, so the tint stops at
the Qt chrome.

Both the panel chrome and the role bar wear it, hence a place of its own.
"""

from .app_paths import AppPaths

_SETTINGS = AppPaths.inst().settings()

#: One look for every tooltip, set through Qt's own API.
#:
#: Two separate things went wrong here. First, a widget stylesheet written as
#: bare declarations (`font-size: 27px;`, no selector) reaches the widget's
#: tooltip too - which is how a 27px icon button got 27px letters in its
#: tooltip. That is fixed by giving every button stylesheet its selector.
#: Second, a `QToolTip { ... }` rule did not paint anything: the tooltip kept
#: the default pale-yellow ground with black text. So the look is set on
#: QToolTip itself - font and palette, absolute values, no inheritance.
TOOLTIP_BG = _SETTINGS.get("info_bg", "#1f2937")
TOOLTIP_FG = "#d1d5db"
TOOLTIP_PX = 13


def apply_tooltip_style() -> None:
    """Call once, after the QApplication exists (see main.run_gui)."""
    from PyQt6.QtGui import QColor, QFont, QPalette
    from PyQt6.QtWidgets import QToolTip

    font = QFont("monospace")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(TOOLTIP_PX)
    QToolTip.setFont(font)

    pal = QToolTip.palette()
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(TOOLTIP_BG))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(TOOLTIP_FG))
    QToolTip.setPalette(pal)


#: plain colour -> its warm counterpart
TINT = {
    "#f5f5f5": "#fdfaec",   # toolbar
    "#eef0f3": "#f7f2df",   # role bar
    "#e2e5ea": "#efe8cf",   # role bar button hover
    "#1f2937": "#282318",   # info bar (dark by design - warmer, not yellow)
    "#111827": "#171308",   # info bar border
}


def tinted(qss: str) -> str:
    for plain, warm in TINT.items():
        qss = qss.replace(plain, warm)
    return qss
