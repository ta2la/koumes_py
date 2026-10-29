"""hg_interactive_applib.entity_text - formatted text, top left corner at `at`."""

from PyQt6.QtCore import QRectF

from .entity import Entity


class EntityText(Entity):
#! Formatovany text (QTextDocument), levy horni roh v `at`.
    def __init__(self, doc, at):
        self.doc, self.at = doc, at

    def draw(self, c):
        c.p.save()
        c.p.translate(self.at)
        self.doc.drawContents(c.p)
        c.p.restore()

    def bound(self):
        s = self.doc.size()
        return QRectF(self.at.x(), self.at.y(), s.width(), s.height())
