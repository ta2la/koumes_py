"""hg_interactive_applib.entity_line - line between two points."""

from PyQt6.QtCore import QRectF

from .entity import Entity, make_pen


class EntityLine(Entity):
    def __init__(self, p1, p2, color, width, style="solid"):
        self.p1, self.p2, self.pen = p1, p2, make_pen(color, width, style)

    def draw(self, c):
        c.p.setPen(self.pen)
        c.p.drawLine(self.p1, self.p2)

    def bound(self):
        return QRectF(self.p1, self.p2).normalized()
