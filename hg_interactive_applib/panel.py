"""hg_interactive_app.panel - floating window inside a view: title, tabs, resize."""

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QLayout, QScrollArea, QTabWidget, QVBoxLayout


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


#=============================================================================
class FloatPanel(QFrame):
#! Plovouci okno uvnitr vieweru: titulek (tahem posun), taby, resize za hrany a rohy.
#=============================================================================
    SIZE = (300, 250)
    MARGIN = 8
    EDGE = 5                 # sirka okraje, za ktery se meni velikost
    MIN = (120, 80)

    def __init__(self, parent):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.setStyleSheet("FloatPanel { background: #f7f8fa; border: 1px solid #9aa4ae; }")
        self.title = QLabel(" ⠿", self)
        self.title.setFixedHeight(14)
        self.title.setCursor(Qt.CursorShape.SizeAllCursor)
        self.title.setStyleSheet("background: #dde2e8; color: #55606b; font-size: 9px;")
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        lay = QVBoxLayout(self)
        e = self.EDGE                    # okraj patri oknu, ne obsahu - za nej resize
        lay.setContentsMargins(e, e, e, e)
        lay.setSpacing(0)
        lay.addWidget(self.title)
        lay.addWidget(self.tabs)
        self.setMouseTracking(True)          # kurzor podle hrany i bez stisku
        self.resize(*self.SIZE)
        self._grab = None
        self._edge = None        # (dx, dy, start mys, start geometrie) pri resize
        self._moved = False      # posunul ho uzivatel
        self._sized = False      # zmenil mu velikost uzivatel
        self.title.installEventFilter(self)
        self.raise_()

    def add_tab(self, widget, name):
        """Tab s posuvnikem: co se do maleho okna nevejde, jde odrolovat."""
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(widget)
        self.tabs.addTab(sa, name)

    def _hit(self, p):
        """Ktera hrana je pod bodem: dx/dy = -1 levá/horní, 1 pravá/dolní, 0 nic."""
        e = self.EDGE * 2                # rohy chytaji vic, at se trefi pohodlne
        dx = -1 if p.x() < e else 1 if p.x() >= self.width() - e else 0
        dy = -1 if p.y() < e else 1 if p.y() >= self.height() - e else 0
        # mimo roh plati jen tenky okraj
        if dx and not dy and self.EDGE <= p.x() < self.width() - self.EDGE:
            dx = 0
        if dy and not dx and self.EDGE <= p.y() < self.height() - self.EDGE:
            dy = 0
        return dx, dy

    def _cursor(self, dx, dy):
        C = Qt.CursorShape
        if dx and dy:
            return C.SizeFDiagCursor if dx == dy else C.SizeBDiagCursor
        return C.SizeHorCursor if dx else C.SizeVerCursor if dy else C.ArrowCursor

    def mousePressEvent(self, ev):
        dx, dy = self._hit(ev.position().toPoint())
        if ev.button() == Qt.MouseButton.LeftButton and (dx or dy):
            self._edge = (dx, dy, ev.globalPosition().toPoint(), self.geometry())
        ev.accept()

    def mouseMoveEvent(self, ev):
        if self._edge is None:
            self.setCursor(self._cursor(*self._hit(ev.position().toPoint())))
            ev.accept()
            return
        dx, dy, start, g = self._edge
        d = ev.globalPosition().toPoint() - start
        l, t, r, b = g.left(), g.top(), g.right(), g.bottom()
        pw, ph = self.parent().width(), self.parent().height()
        if dx < 0:
            l = max(0, min(l + d.x(), r - self.MIN[0]))
        if dx > 0:
            r = min(pw - 1, max(r + d.x(), l + self.MIN[0]))
        if dy < 0:
            t = max(0, min(t + d.y(), b - self.MIN[1]))
        if dy > 0:
            b = min(ph - 1, max(b + d.y(), t + self.MIN[1]))
        self.setGeometry(QRect(QPoint(l, t), QPoint(r, b)))
        self._sized = True
        if dx < 0 or dy < 0:
            self._moved = True           # levou/horni hranou se okno i posouva
        ev.accept()

    def mouseReleaseEvent(self, ev):
        self._edge = None
        ev.accept()

    def keep_inside(self):
        """Dokud s nim nikdo nehnul, drzi vpravo nahore; pak jen neuteci z vieweru."""
        pw, ph = self.parent().width(), self.parent().height()
        # nikdy vetsi nez viewer (s okrajem); dokud se nemenil rucne, drzi SIZE
        w = min(self.width() if self._sized else self.SIZE[0], max(80, pw - 2 * self.MARGIN))
        h = min(self.height() if self._sized else self.SIZE[1], max(80, ph - 2 * self.MARGIN))
        if (w, h) != (self.width(), self.height()):
            self.resize(w, h)
        if not self._moved:
            self.move(pw - self.width() - self.MARGIN, self.MARGIN)
        x = max(0, min(self.x(), pw - self.width()))
        y = max(0, min(self.y(), ph - self.height()))
        self.move(x, y)
        self.raise_()

    def eventFilter(self, obj, ev):
        # posun okna za titulek - to je ovladani okna, ne vstup do diagramu
        t = ev.type()
        if t == QEvent.Type.MouseButtonPress:
            self._grab = ev.globalPosition().toPoint() - self.pos()
            return True
        if t == QEvent.Type.MouseMove and self._grab is not None:
            self.move(ev.globalPosition().toPoint() - self._grab)
            self._moved = True
            self.keep_inside()
            return True
        if t == QEvent.Type.MouseButtonRelease:
            self._grab = None
            return True
        return False

