"""hg_pool_py.ref_col - Collection of refs with a filter; membership is kept by the pool."""

from .filter import Filter
from .pool import POOL
from .ref import Ref


#=============================================================================
class RefCol:
#! Collection of refs with a filter; membership is kept by the pool.
#=============================================================================
    def __init__(self, flt=None):
        self.filter = flt or Filter()
        self.refs = []
        self.dirty = False
        self.listeners = []      # called by refresh_display

    def make_ref(self, obj):
        """Ref kind of this collection - a scene returns one that keeps drawing."""
        return Ref(obj, self)

    def objs(self):
        return [r.obj for r in self.refs]

    def ref_of(self, obj):
        return next((r for r in obj.refs if r.parent is self), None)

    def initialize(self):
        for o in POOL.objs:
            self.sync(o)
        self.dirty = True

    def sync(self, obj):
        """Membership by the filter."""
        ref = self.ref_of(obj)
        if self.filter.pass_(obj):
            if ref is None:
                self.refs.append(self.make_ref(obj))
                self.dirty = True
        elif ref is not None:
            self.remove(ref)

    def remove(self, ref):
        if ref in self.refs:
            self.refs.remove(ref)
        if ref in ref.obj.refs:
            ref.obj.refs.remove(ref)
        self.dirty = True

    def refresh_display(self):
        for f in list(self.listeners):
            try:
                f()
            except RuntimeError:     # a dead Qt widget behind the listener
                self.listeners.remove(f)
