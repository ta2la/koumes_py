"""hg_pool_py.pool_obj - Pool object: identity (source, key) and a selection flag. Not graphics."""

from .pool import POOL


#=============================================================================
class PoolObj:
#! Pool object: identity (source, key) and a selection flag. Not graphics.
#=============================================================================
    kind = ""
    Z = 0                    # pick priority (higher first)
    SEL_MAX = 1              # how many selection levels the object has

    def __init__(self, source, key, oid="", st=None):
        self.source, self.key, self.id = source, key, oid
        self.st = st if st is not None else {}
        self.sel = 0                 # selection flag (0 = none); its levels are
                                     # defined in sel.py (Sel)
        self.refs = []           # Refs of the collections that hold it
        POOL.register(self)

    def modified(self):
        """The object changed - the pool repaints it once the lock is released."""
        POOL.changed(self)

    def set_sel(self, level):
        if self.sel != level:
            self.sel = level
            self.modified()

    def display(self, lst, plain=False):
        """Contract for drawing collections: append what draws this object.
        plain = without selection marks. The pool itself never calls it."""

    def hit(self, x, y, tol):
        """Does point (x, y) hit the object, judged from its own data."""
        return False

    def destroy(self):
        for r in list(self.refs):
            r.parent.remove(r)
        POOL.unregister(self)
