"""hg_interactive_applib.diag_canvas - drawing surface: the view's entities and dynamics on top, scale and offset."""

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .entity import C_BG
from .ref_col_scene import paint_ents


#=============================================================================
class DiagCanvas(QWidget):
#! Platno: kresli entity view (display list) a navrch dynamiku. Meritko a posun;
#! kolecko = zoom k mysi; posun obrazu je mod (AppMode_pan), ne tady.
#=============================================================================
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.scale, self.off = 1.0, QPointF(0, 0)    # obrazovka = scena * scale + off
        self.setMouseTracking(True)

    def to_scene(self, p):
        return QPointF((p.x() - self.off.x()) / self.scale, (p.y() - self.off.y()) / self.scale)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), C_BG)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.off)
        p.scale(self.scale, self.scale)
        paint_ents(p, self.view.scene.entities() + self.view.err + self.view.dyn, self.scale)
        if self.view.cross:
            # agent na diagu pracuje (testy, restarty): kriz pres cely obraz
            p.resetTransform()
            pen = QPen(QColor(200, 40, 40, 150), 6)
            p.setPen(pen)
            r = self.rect()
            p.drawLine(r.topLeft(), r.bottomRight())
            p.drawLine(r.topRight(), r.bottomLeft())
            f = QFont("Sans")
            f.setPointSize(16)
            f.setBold(True)
            p.setFont(f)
            p.drawText(r.adjusted(0, 0, 0, -r.height() // 3), Qt.AlignmentFlag.AlignCenter,
                       "pracuje agent - " + self.view.cross)
        p.end()

    def fit(self, r, max_scale=1.0):
        if r.isEmpty() or self.width() < 2:
            return
        self.scale = min(self.width() / r.width(), self.height() / r.height(), max_scale)
        c = r.center()
        self.off = QPointF(self.width() / 2 - c.x() * self.scale,
                           self.height() / 2 - c.y() * self.scale)
        self.update()

    def ensure_visible(self, r, margin=40):
        a = QPointF(r.left() * self.scale + self.off.x(), r.top() * self.scale + self.off.y())
        b = QPointF(r.right() * self.scale + self.off.x(), r.bottom() * self.scale + self.off.y())
        dx = margin - a.x() if a.x() < margin else min(0, self.width() - margin - b.x())
        dy = margin - a.y() if a.y() < margin else min(0, self.height() - margin - b.y())
        self.off += QPointF(dx, dy)
        self.update()

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        m = ev.position()
        s = self.to_scene(m)
        self.scale *= f
        self.off = QPointF(m.x() - s.x() * self.scale, m.y() - s.y() * self.scale)
        self.update()

    def pan_by(self, dx, dy):
        """Posunout obraz o (dx, dy) jednotek sceny."""
        self.off += QPointF(dx * self.scale, dy * self.scale)
        self.update()
