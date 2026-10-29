"""hg_interactive_applib.entity_circle - circle: filled, or an outline with the background inside."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QPen

from .entity import C_BG, Entity


class EntityCircle(Entity):
#! Kruh: fill = barva vyplne (plny), jinak obrys tloustky width a uvnitr pozadi.
    def __init__(self, center, r, color, width, fill=None):
        self.center, self.r, self.color, self.width, self.fill = center, r, color, width, fill

    def draw(self, c):
        if self.fill:
            c.p.setPen(Qt.PenStyle.NoPen)
            c.p.setBrush(QBrush(self.fill))
        else:
            pen = QPen(self.color, self.width)
            pen.setCosmetic(self.px)
            c.p.setPen(pen)
            c.p.setBrush(QBrush(C_BG))
        c.p.drawEllipse(self.center, self.r, self.r)

    def bound(self):
        return QRectF(self.center.x() - self.r, self.center.y() - self.r, 2 * self.r, 2 * self.r)
