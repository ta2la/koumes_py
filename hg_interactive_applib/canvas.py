"""hg_interactive_applib.canvas - where entities draw: a painter in scene coordinates and the scale."""


#=============================================================================
# Entity - kreslene elementy (jako T2l::Entity v hg_display). Objekt diagramu se
# umi jen prevest na entity (display); view kresli entity. Souradnice jsou sceny.
#=============================================================================
class Canvas:
#! Kam entity kresli: QPainter uz s transformaci sceny a meritko px na jednotku.
#=============================================================================
    def __init__(self, painter, scale):
        self.p, self.scale = painter, scale
