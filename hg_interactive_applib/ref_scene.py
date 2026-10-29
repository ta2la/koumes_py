"""hg_interactive_applib.ref_scene - ref in a scene: keeps the object's entities."""

from hg_pool_py import Ref


#=============================================================================
class RefScene(Ref):
#! Ref ve scene: drzi entity objektu; repaint je prekresli jen pro nej.
#=============================================================================
    def __init__(self, obj, parent):
        super().__init__(obj, parent)
        self.ents = []

    def repaint(self):
        self.ents = []
        self.obj.display(self.ents)
        self.parent.dirty = True
