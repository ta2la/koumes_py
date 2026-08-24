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
"""AppBar - the one strip above all four panels.

Panel toolbars act on their own panel; this one acts on the application. Right
now that is a single button (paste the clipboard into a file) plus the status
line that says where the last one landed.
"""

import html
import os
from typing import Callable, Optional

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QPixmap
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)


_APP_BAR_QSS = (
    "QWidget { background: #111827; border-bottom: 1px solid #000; }"
    "QPushButton { color: #e5e7eb; background: #374151; border: 1px solid #6b7280;"
    " border-radius: 3px; padding: 2px 10px; font: 700 12px 'ui-monospace', monospace;"
    " min-height: 22px; }"
    "QPushButton:hover { background: #4b5563; color: #fff; }"
    "QPushButton:disabled { color: #6b7280; background: #1f2937;"
    " border-color: #374151; }"
)

_STATUS_QSS = (
    "QLabel { background: transparent; border: none; color: #9ca3af;"
    " font: 12px 'ui-monospace', monospace; }"
)

#: how long a "saved: …" line stays before the bar goes quiet again
_STATUS_MS = 12000

_PREVIEW_QSS = (
    "QLabel { background: #0b1220; color: #e5e7eb; border: 1px solid #6b7280;"
    " padding: 6px; font: 12px 'ui-monospace', monospace; }"
)

#: widest edge of the thumbnail shown when hovering over a copied image
_THUMB_PX = 200

#: how much of a copied text the tooltip shows
_TEXT_PREVIEW = 200


class ClipPreview(QLabel):
    """What the clipboard holds, shown while the pointer sits on the button.

    A window of our own rather than a rich-text tooltip: `setToolTip` with an
    `<img>` depends on Qt finding the file, resolving it past its own pixmap
    cache and on the desktop honouring tooltips at all. Too many links in the
    chain for something that is just a picture in a box - here the pixmap is
    handed over directly.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setStyleSheet(_PREVIEW_QSS)
        self.setTextFormat(Qt.TextFormat.PlainText)

    def show_at(self, widget: QWidget) -> None:
        if not (self.pixmap() or self.text()):
            return
        self.adjustSize()
        below = widget.mapToGlobal(widget.rect().bottomLeft())
        self.move(below.x(), below.y() + 4)
        self.show()


class AppBar(QWidget):
    """Paste strip. It lives in the left panel, the one panel that is not a view
    of a file - a control that acts on the clipboard rather than on what is on
    screen belongs there rather than across the top of the whole window.

    `compact` stacks the button above the status line instead of setting them
    side by side: the left panel can be dragged down to 150px, and a row that
    narrow would clip the status text away completely.
    """

    def __init__(self, parent: Optional[QWidget] = None, compact: bool = False):
        super().__init__(parent)
        self.setStyleSheet(_APP_BAR_QSS)
        self.setFixedHeight(56 if compact else 32)

        lay = QVBoxLayout(self) if compact else QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2 if compact else 8)

        self.paste = QPushButton("📥 paste", self)
        lay.addWidget(self.paste)

        self.status = QLabel("", self)
        self.status.setStyleSheet(_STATUS_QSS)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.status)
        if not compact:
            lay.addStretch(1)

        self._last_path = ""
        self._open_fn: Optional[Callable[[str], None]] = None
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_status)

        self.status.mousePressEvent = self._status_clicked

        # The button says what it would paste, so the user does not have to
        # click to find out. Driven by the signal, not by polling.
        self.preview = ClipPreview(self)
        self.paste.installEventFilter(self)

        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.dataChanged.connect(self._read_clipboard)
        app = QGuiApplication.instance()
        if app is not None:
            # X11 does not always deliver dataChanged for a copy made while we
            # were in the background; coming back to the window re-reads it.
            app.applicationStateChanged.connect(lambda _s: self._read_clipboard())
        self._read_clipboard()

    # -- what is on the clipboard -------------------------------------------
    def eventFilter(self, obj, ev) -> bool:
        if obj is self.paste:
            if ev.type() == QEvent.Type.Enter:
                self.preview.show_at(self.paste)
            elif ev.type() == QEvent.Type.Leave:
                self.preview.hide()
        return super().eventFilter(obj, ev)

    def _read_clipboard(self) -> None:
        cb = QGuiApplication.clipboard()
        mime = cb.mimeData() if cb is not None else None

        if mime is not None and mime.hasImage():
            image = cb.image()
            if not image.isNull():
                thumb = QPixmap.fromImage(image).scaled(
                    _THUMB_PX, _THUMB_PX,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                self.preview.setText("")
                self.preview.setPixmap(thumb)
                self._show_kind("📸 image", f"{image.width()}×{image.height()} px", True)
                return

        if mime is not None and mime.hasUrls():
            files = [u.toLocalFile() for u in mime.urls() if u.toLocalFile()]
            if files:
                extra = f"\n+ {len(files) - 1} další" if len(files) > 1 else ""
                self._preview_text(f"{os.path.basename(files[0])}\n{files[0]}{extra}")
                self._show_kind("📎 file", os.path.basename(files[0]), True)
                return

        if mime is not None and mime.hasText() and cb.text().strip():
            text = cb.text()
            cut = text[:_TEXT_PREVIEW] + (" …" if len(text) > _TEXT_PREVIEW else "")
            self._preview_text(cut)
            self._show_kind("📝 text", f"{len(text)} znaků", True)
            return

        self._preview_text("clipboard is empty")
        self._show_kind("⊘ empty", "clipboard is empty", False)

    def _preview_text(self, text: str) -> None:
        self.preview.setPixmap(QPixmap())
        self.preview.setText(text)

    def _show_kind(self, label: str, tooltip: str, enabled: bool) -> None:
        # The word on the button carries the type - one emoji apart is not a
        # difference anybody spots at 12px in a dark bar.
        self.paste.setText(label)
        self.paste.setToolTip(f"paste_clipboard → exchange · {tooltip}")
        self.paste.setEnabled(enabled)
        if not enabled:
            # A disabled button gets no Enter event, so the popup would stay up.
            self.preview.hide()

    def set_open_fn(self, fn: Callable[[str], None]) -> None:
        """What a click on the status line does with the saved path."""
        self._open_fn = fn

    def show_saved(self, path: str) -> None:
        self._last_path = path
        self.status.setText(f"saved: {os.path.basename(path)}  ▸ klik otevře v p1")
        self.status.setToolTip(path)
        self.status.setStyleSheet(_STATUS_QSS.replace("#9ca3af", "#fbbf24"))
        self.status.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_timer.start(_STATUS_MS)

    def _clear_status(self) -> None:
        # The path is kept after the text fades - the file is still the last one
        # pasted, and the click target should not silently change meaning.
        self.status.setText("")
        self.status.setToolTip("")

    def _status_clicked(self, ev) -> None:
        if self._last_path and self._open_fn is not None:
            self._open_fn(self._last_path)
