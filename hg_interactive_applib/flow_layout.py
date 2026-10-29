"""hg_interactive_applib.flow_layout - items flow left to right and wrap like words."""

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout


#=============================================================================
class FlowLayout(QLayout):
#! Polozky tecou zleva doprava a lamou se do radku, jako slova v odstavci.
#=============================================================================
    def __init__(self, parent=None, spacing=3):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._place(QRect(0, 0, w, 0), False)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._place(r, True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _place(self, r, apply):
        x, y, line_h, sp = r.x(), r.y(), 0, self.spacing()
        for it in self._items:
            hint = it.sizeHint()
            if x + hint.width() > r.right() + 1 and line_h > 0:
                x, y, line_h = r.x(), y + line_h + sp, 0
            if apply:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + sp
            line_h = max(line_h, hint.height())
        return y + line_h - r.y()
