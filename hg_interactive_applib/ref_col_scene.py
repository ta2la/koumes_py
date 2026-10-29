"""hg_interactive_applib.ref_col_scene - a collection that is drawn (view): refs keep entities."""

from PyQt6.QtCore import QRectF
from hg_pool_py import RefCol

from .canvas import Canvas
from .ref_scene import RefScene


#=============================================================================
class RefColScene(RefCol):
#! Kolekce, ktera se kresli (view): entity svych refu podle layer - vyssi navrchu.
#! Pool o kresleni nevi; scena si vyrabi vlastni refy (make_ref).
#=============================================================================
    def make_ref(self, obj):
        return RefScene(obj, self)

    def entities(self):
        out = []
        for r in self.refs:
            out += r.ents
        return sorted(out, key=lambda e: e.layer)          # stabilni razeni

    def ordered(self):
        """Objekty v poradi pro pick (Z)."""
        return [r.obj for r in sorted(self.refs, key=lambda r: r.obj.Z)]


def paint_ents(p, ents, scale):
    c = Canvas(p, scale)
    for e in ents:
        e.draw(c)


def ents_bound(ents):
    r = QRectF()
    for e in ents:
        r = r.united(e.bound())
    return r
