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
"""Role bar - the narrow strip between a panel's toolbar and its info bar.

    [ p1 ]                                   [ mdid ][ md ][ txt ][ native ]
      ^ which panel this is                    ^ what it is showing through

The left half is the same everywhere. The right half is what separates the
panels: p1 and p2 pick a viewer for the current file, dir picks between its
custom viewer and the plain listing, and left picks between three canned
contents and has no viewers at all. One class per answer.

The bar owns those controls; the panel reaches them through it.
"""

from typing import List, Optional

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from .theme import tinted

_ROLE_BAR_QSS = (
    "QWidget { background: #eef0f3; border-bottom: 1px solid #ccc; }"
    "QPushButton { padding: 1px 8px; border: 1px solid #bbb; border-radius: 3px;"
    " background: #fff; font-size: 11px; min-height: 18px; }"
    "QPushButton:checked { background: #dbeafe; border-color: #2563eb; color: #1e40af;"
    " font-weight: 700; }"
    "QPushButton:hover:!checked { background: #e2e5ea; }"
)

_ROLE_LABEL_QSS = (
    "QLabel { background: #fff; border: 1px solid #bbb; border-radius: 3px;"
    " color: #4b5563; font: 700 11px 'ui-monospace', monospace;"
    " letter-spacing: 1px; padding: 2px 6px; }"
)

_HEIGHT = 26


#: a blanked button is half as wide as the bar is tall - a target to click,
#: not a box that looks like it should have said something
_BLANK_W = _HEIGHT // 2


def button_label(btn: QPushButton) -> str:
    """The name of a switch button, whether or not it currently shows it.

    A squeezed bar strips the text off everything except the active choice, so
    `btn.text()` is not the place to read a viewer name from any more.
    """
    return btn.property("label") or btn.text()


class BaseRoleBar(QWidget):
    """Name on the left, switch on the right. Subclasses fill the right."""

    def __init__(self, role: str, tint: bool = False,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.role = role
        self.setStyleSheet(tinted(_ROLE_BAR_QSS) if tint else _ROLE_BAR_QSS)
        self.setFixedHeight(_HEIGHT)

        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(10, 2, 8, 2)
        self._lay.setSpacing(8)

        #: button whose name is on loan while the pointer rests on it
        self._peeked: Optional[QPushButton] = None

        self.label = QLabel(role, self)
        self.label.setStyleSheet(_ROLE_LABEL_QSS)
        self.label.setToolTip(f"panel role: {role}" if role else "")
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter
                                | Qt.AlignmentFlag.AlignLeft)
        self.label.setVisible(bool(role))
        self._lay.addWidget(self.label)
        self._lay.addStretch(1)

        self._build_switch()

    def _build_switch(self) -> None:
        """Fill the right-hand side. Nothing by default."""

    def add_switch(self, widget: QWidget) -> None:
        self._lay.addWidget(widget)

    # -- fitting into a narrow panel ----------------------------------------
    # A panel can be narrow in a wide window - the user drags the splitter. So
    # the bar measures itself, not the window. When its buttons no longer fit,
    # the one that is currently in effect stays and the rest step aside; they
    # come back while the pointer is over the bar. The buttons are words, not
    # icons, so "degrade without text" can only mean "show fewer of them".
    def switch_buttons(self) -> List[QPushButton]:
        """Buttons this bar can hide when space runs out, left to right."""
        return []

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self.refit()

    def refit(self) -> None:
        """Two things give way, in this order:

            full       [dir] [mdid][md][txt][native]
            squeeze A  [mdid][md][txt][native]        the name goes first
            squeeze B  [mdid][  ][  ][  ]             only the active one reads

        The choices outlive the label: the panel's name is repeated by its own
        content, while a viewer button that cannot be read is a dead end. The
        stripped ones stay as targets, share the leftover width between them,
        and say what they are on hover.
        """
        buttons = [b for b in self.switch_buttons() if b.isVisibleTo(self)]
        if not buttons:
            return

        for b in buttons:
            if b.text():
                # Remember the wording while it is still there - after the
                # squeeze the button itself no longer knows what it is.
                b.setProperty("label", b.text())
                b.setProperty("fullWidth", b.sizeHint().width())

        margins = self._lay.contentsMargins()
        spacing = self._lay.spacing()
        label_w = self.label.sizeHint().width() + spacing if self.role else 0
        fixed = margins.left() + margins.right() + spacing

        def full_w(b: QPushButton) -> int:
            return int(b.property("fullWidth") or b.sizeHint().width())

        room = self.width()
        all_named = fixed + sum(full_w(b) + spacing for b in buttons)

        show_label = bool(self.role) and all_named + label_w <= room
        # Squeezed, exactly one button is named. Normally the active one; while
        # the pointer rests on another, that one instead. The swap is why the
        # row does not change width when a name is borrowed.
        wants = self._peeked if (self._peeked is not None
                                 and self._peeked in buttons) else None
        named = buttons if all_named <= room else [
            b for b in buttons if (b is wants if wants is not None
                                   else b.isChecked())]

        for b in buttons:
            self._set_named(b, b in named)

        if self.label.isVisibleTo(self) != show_label:
            self.label.setVisible(show_label)

        # Width limits changed; without this the row keeps the old ones until
        # something else happens to trigger a re-layout, and a name swapped in
        # on hover would stay squeezed into a blank button's width.
        self._lay.activate()

    def _set_named(self, btn: QPushButton, named: bool) -> None:
        label = button_label(btn)
        if named:
            if btn.text() != label:
                btn.setText(label)
                btn.setToolTip(self._command_hint(btn))
                btn.setSizePolicy(QSizePolicy.Policy.Preferred,
                                  QSizePolicy.Policy.Fixed)
                btn.setMaximumWidth(16777215)
            return
        if btn.text():
            btn.setText("")
            # Hover is the only way left to tell them apart, so the name goes
            # into the tooltip - alongside the command, which was there before.
            hint = self._command_hint(btn)
            btn.setToolTip(f"{label}\n{hint}" if hint else label)
            # Small and fixed. A stripped button is a target, not a label -
            # letting them stretch turned four of them into a row of wide empty
            # boxes that read as broken rather than as compact.
            btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                              QSizePolicy.Policy.Fixed)
            btn.setMinimumWidth(_BLANK_W)
            btn.setMaximumWidth(_BLANK_W)

    def eventFilter(self, obj, ev) -> bool:
        # Enter only. A button's own Leave is worthless here - the swap that
        # Enter triggers is what moves the button out from under the pointer,
        # so Leave would arrive as a consequence of the peek and cancel it.
        # leaveEvent on the bar does the resetting.
        if ev.type() == QEvent.Type.Enter:
            try:
                tabs = self.switch_buttons()
            except AttributeError:
                # The filter is installed as each button is built, so the first
                # ones receive events while the later ones do not exist yet.
                tabs = []
            if obj in tabs:
                self._peek(obj)
        return super().eventFilter(obj, ev)

    def _peek(self, btn: Optional[QPushButton]) -> None:
        """Hand the name to the button under the pointer, taking it off the
        active one. The row keeps its total width - one word in, one word out.
        """
        if btn is self._peeked:
            return
        self._peeked = btn
        self.refit()

    @staticmethod
    def _command_hint(btn: QPushButton) -> str:
        """The `viewer_switch …` line a button was given when it was built."""
        tip = btn.toolTip()
        for line in tip.split("\n"):
            if line.startswith("viewer_switch") or line.startswith("panel_show"):
                return line
        return ""

    def leaveEvent(self, ev) -> None:
        """Give the name back only once the pointer is off the bar entirely.

        Resetting on a button's own Leave would fight the swap that caused it:
        the button grows, slides out from under the pointer, Leave fires, the
        name goes back, the button shrinks, Enter fires again - the flicker
        Petr saw. The bar as a whole is the boundary that does not move.
        """
        self._peek(None)
        super().leaveEvent(ev)

    def _tab(self, text: str) -> QPushButton:
        """A checkable button belonging to this bar's exclusive group."""
        if not hasattr(self, "_group"):
            self._group = QButtonGroup(self)
            self._group.setExclusive(True)
        btn = QPushButton(text, self)
        btn.setCheckable(True)
        # For the hover peek - see _peek. Installed once here rather than in
        # refit, which runs on every resize and would stack filters up.
        btn.installEventFilter(self)
        btn.setVisible(False)
        self._group.addButton(btn)
        self.add_switch(btn)
        return btn


class ContentRoleBar(BaseRoleBar):
    """Left panel: four fixed contents, no viewers.

    The buttons are born unnamed and hidden - what each one shows is the panel
    owner's business (bookmarks, the dirs listing one level up, the command
    log), and it wires them to `panel_show left <file>`.

    `menu` is the odd one out: the other three swap a page in the web view,
    while menu shows actions built as widgets. Anything that has live state of
    its own - what is on the clipboard right now - cannot be a static page
    without a bridge to fetch it, so the panel keeps a stack and menu is its
    second layer.
    """

    def _build_switch(self) -> None:
        # Order is the order they are built in: menu, dirs-upper, bookmarks, log.
        self.menu = self._tab("menu")
        self.dflt = self._tab("default")
        self.custom = self._tab("custom")
        self.log = self._tab("log")
        self.dflt.setChecked(True)

    def switch_buttons(self) -> List[QPushButton]:
        return [self.menu, self.dflt, self.custom, self.log]


class ViewerRoleBar(BaseRoleBar):
    """p1 / p2: whichever viewers are registered for the file on screen.

    The buttons come and go with the file, so the bar only holds the container;
    `viewer_bar.rebuild_viewer_bar()` fills it on every selection.
    """

    def _build_switch(self) -> None:
        self.viewer_bar = QWidget(self)
        lay = QHBoxLayout(self.viewer_bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.add_switch(self.viewer_bar)
        # The buttons are built anew for every file, so the bar cannot cache
        # them - it re-measures whenever the container gains or loses a child.
        self.viewer_bar.installEventFilter(self)

    def eventFilter(self, obj, ev) -> bool:
        if obj is self.viewer_bar and ev.type() in (QEvent.Type.ChildAdded,
                                                    QEvent.Type.ChildRemoved):
            self.refit()
        return super().eventFilter(obj, ev)

    def switch_buttons(self) -> List[QPushButton]:
        return self.viewer_bar.findChildren(QPushButton)


class DirRoleBar(ViewerRoleBar):
    """dir: the same viewer container plus the pair that no file-driven bar can
    express - this directory's own viewer versus the plain listing. Which is
    why dir is a third class and not a flag on the second."""

    def _build_switch(self) -> None:
        super()._build_switch()
        self.custom = self._tab("custom")
        self.dflt = self._tab("default")
        self.dflt.setChecked(True)

    def switch_buttons(self) -> List[QPushButton]:
        return super().switch_buttons() + [self.custom, self.dflt]
