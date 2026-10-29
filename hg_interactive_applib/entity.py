"""hg_interactive_applib.entity - drawn elements (like T2l::Entity in CAD hg_display).

An object only turns itself into entities (display); a view draws entities.
Coordinates are scene coordinates.
"""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPen


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


C_SEL = QColor("#c2407e")      # vyber: oranzovofialova


C_BG = QColor("#ffffff")       # pozadi diagramu; vypln neplnych kruhu symbolu


LINE_STYLES = {"solid": Qt.PenStyle.SolidLine, "dash": Qt.PenStyle.DashLine,
               "dot": Qt.PenStyle.DotLine}


def make_pen(color, width, style="solid"):
    pen = QPen(color, width)
    pen.setStyle(LINE_STYLES.get(style, Qt.PenStyle.SolidLine))
    return pen


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
