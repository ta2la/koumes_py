"""hg_pool_py.pool - object pool and reference collections.

Modelled on the CAD interaction layer (GObjectPool, GObject, Ref, RefCol,
UpdateLock), not a 1:1 port. No Qt, no drawing; the selection collection is in
ref_col_selection.py:

- The pool owns every object. An object carries its identity as
  (source, key): `source` is the id of where it came from (a file path,
  a database, ...), `key` its id inside that source.
- Whoever shows, selects or loads objects keeps a RefCol with a filter.
  A Ref is one object's membership in one collection. A drawing collection
  (a scene) lives outside this module and makes its own Ref subclass via
  `make_ref`, which keeps whatever it draws.
- Changes are resolved under a lock (`POOL.lock()`): after the outermost lock
  is released the pool re-checks membership of changed objects, repaints their
  refs and refreshes dirty collections.
"""

from contextlib import contextmanager


#=============================================================================
class Pool:
#! Singleton: all objects, all collections, changed ones; lock.
#=============================================================================
    def __init__(self):
        self.objs = []
        self.refcols = []
        self._changed = []
        self._lock = 0

    def add_refcol(self, rc):
        self.refcols.append(rc)
        rc.initialize()
        self._solve()

    def remove_refcol(self, rc):
        if rc in self.refcols:
            self.refcols.remove(rc)
        for r in list(rc.refs):
            rc.remove(r)

    def register(self, obj):
        self.objs.append(obj)
        self.changed(obj)

    def unregister(self, obj):
        if obj in self.objs:
            self.objs.remove(obj)
        if obj in self._changed:
            self._changed.remove(obj)

    def changed(self, obj):
        if obj not in self._changed:
            self._changed.append(obj)
        if self._lock == 0:
            self._solve()

    @contextmanager
    def lock(self):
        """Changes are resolved after the outermost lock is released."""
        self._lock += 1
        try:
            yield
        finally:
            self._lock -= 1
            if self._lock == 0:
                self._solve()

    def _solve(self):
        changed, self._changed = self._changed, []
        for obj in changed:
            if obj not in self.objs:
                continue
            for rc in self.refcols:
                rc.sync(obj)
            for r in obj.refs:
                r.repaint()
        for rc in self.refcols:
            if rc.dirty:
                rc.dirty = False
                rc.refresh_display()


POOL = Pool()
