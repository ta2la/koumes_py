"""hg_interactive_applib.entity_handle - handle: a square of constant size in screen pixels."""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QBrush, QPen

from .entity import C_BG, C_SEL, Entity


class EntityHandle(Entity):
#! Uchyt: ctverecek stale velikosti v pixelech obrazovky.
    PX = 7

    def __init__(self, at):
        self.at = at

    def draw(self, c):
        h = self.PX / c.scale
        c.p.setPen(QPen(C_SEL, 1 / c.scale))
        c.p.setBrush(QBrush(C_BG))
        c.p.drawRect(QRectF(self.at.x() - h / 2, self.at.y() - h / 2, h, h))

    def bound(self):
        return QRectF(self.at, self.at)
