"""hg_pool_py.ref - Membership of one object in one collection."""


#=============================================================================
class Ref:
#! Membership of one object in one collection.
#=============================================================================
    def __init__(self, obj, parent):
        self.obj, self.parent = obj, parent
        obj.refs.append(self)

    def repaint(self):
        """The object changed. Base: only mark the collection dirty."""
        self.parent.dirty = True
