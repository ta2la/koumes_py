"""hg_interactive_applib.entity_box - rectangle (rounded corners), outline and fill."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush

from .entity import Entity, make_pen


class EntityBox(Entity):
#! Obdelnik (s kulatymi rohy), obrys a vypln.
    def __init__(self, rect, color, width, fill=None, style="solid", radius=0):
        self.rect, self.pen, self.fill, self.radius = rect, make_pen(color, width, style), fill, radius

    def draw(self, c):
        c.p.setPen(self.pen)
        c.p.setBrush(QBrush(self.fill) if self.fill else Qt.BrushStyle.NoBrush)
        c.p.drawRoundedRect(self.rect, self.radius, self.radius)

    def bound(self):
        return QRectF(self.rect)
