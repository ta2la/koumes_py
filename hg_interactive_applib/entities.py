"""hg_interactive_app.entities - drawn elements (like T2l::Entity in CAD hg_display).

An object only turns itself into entities (display); a view draws entities.
Coordinates are scene coordinates.
"""

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen

C_SEL = QColor("#c2407e")      # vyber: oranzovofialova
C_BG = QColor("#ffffff")       # pozadi diagramu; vypln neplnych kruhu symbolu
LINE_STYLES = {"solid": Qt.PenStyle.SolidLine, "dash": Qt.PenStyle.DashLine,
               "dot": Qt.PenStyle.DotLine}


#=============================================================================
# Entity - kreslene elementy (jako T2l::Entity v hg_display). Objekt diagramu se
# umi jen prevest na entity (display); view kresli entity. Souradnice jsou sceny.
#=============================================================================
class Canvas:
#! Kam entity kresli: QPainter uz s transformaci sceny a meritko px na jednotku.
#=============================================================================
    def __init__(self, painter, scale):
        self.p, self.scale = painter, scale


def make_pen(color, width, style="solid"):
    pen = QPen(color, width)
    pen.setStyle(LINE_STYLES.get(style, Qt.PenStyle.SolidLine))
    return pen


#=============================================================================
class Entity:
#! Kresleny element: draw, bound a layer. O objektu, ze ktereho vznikl, nevi nic.
#! Scena kresli podle layer - vyssi navrchu (jako layer_ entity v CAD).
#=============================================================================
    layer = 0
    px = False               # tloustka cary v pixelech obrazovky, nezavisle na scale

    def draw(self, c):
        raise NotImplementedError

    def bound(self):
        return QRectF()


def on_layer(layer, ents):
    for e in ents:
        e.layer = layer
    return ents


def on_screen(ents):
    """Cary entit citelne pri kazdem scale (dynamika, vyber): tloustka v pixelech."""
    for e in ents:
        e.px = True
        if hasattr(e, "pen"):
            e.pen.setCosmetic(True)
    return ents


class EntityLine(Entity):
    def __init__(self, p1, p2, color, width, style="solid"):
        self.p1, self.p2, self.pen = p1, p2, make_pen(color, width, style)

    def draw(self, c):
        c.p.setPen(self.pen)
        c.p.drawLine(self.p1, self.p2)

    def bound(self):
        return QRectF(self.p1, self.p2).normalized()


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

