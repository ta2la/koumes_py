"""hg_interactive_applib.entity_mark - mark in screen pixels around a point: lines and circles."""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QPen

from .entity import C_BG, Entity


class EntityMark(Entity):
#! Znacka v pixelech obrazovky: polozky item_line / item_circle kolem bodu at, osa x
#! podel d, y kolmo. Velikost i tloustka cary nezavisi na scale.
    px = True

    def __init__(self, at, d, items, color, width):
        self.at, self.d, self.items, self.color, self.width = at, d, items, color, width

    def draw(self, c):
        k = 1 / c.scale
        (ox, oy), (ux, uy) = (self.at.x(), self.at.y()), self.d

        def pt(x, y):
            return QPointF(ox + (x * ux - y * uy) * k, oy + (x * uy + y * ux) * k)

        for kind, t in self.items:
            if kind == "item_line":
                x1, y1, x2, y2, w = t
                pen = QPen(self.color, w)
                pen.setCosmetic(True)
                c.p.setPen(pen)
                c.p.drawLine(pt(x1, y1), pt(x2, y2))
            elif kind == "item_circle":
                x, y, r, fill = t
                if fill:
                    c.p.setPen(Qt.PenStyle.NoPen)
                    c.p.setBrush(QBrush(self.color))
                else:
                    pen = QPen(self.color, self.width)
                    pen.setCosmetic(True)
                    c.p.setPen(pen)
                    c.p.setBrush(QBrush(C_BG))
                c.p.drawEllipse(pt(x, y), r * k, r * k)

    def bound(self):
        return QRectF(self.at, self.at)
