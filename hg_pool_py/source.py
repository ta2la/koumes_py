"""hg_pool_py.source - sources of pool objects: a file, a database, ...

A source does not own its objects - they live in the pool and carry the source
id. The source knows them through its own collection (RefCol with
FilterSource). It keeps the state of the source: unsaved changes and their
count, a read error. Loading objects from and writing changes to the source
is up to a subclass; the open sources are kept by SOURCES, one is active
(new objects go there), objects of any source can be edited.
"""

from .filter_source import FilterSource
from .pool import POOL
from .ref_col import RefCol


#=============================================================================
class Source:
#! Source of pool objects: id, own collection, unsaved changes. Subclass loads/writes.
#=============================================================================
    def __init__(self, sid):
        self.id = sid
        self.refcol = RefCol(FilterSource(sid))   # its objects; the pool owns them
        self.error = None            # the source cannot be read
        self._pending = {}           # unsaved changes: key -> {attr: value}
        self.changes = 0             # count of unsaved changes (each change +1)
        self.listeners = []          # f(source, what): what = "changed" | "saved"

    def objs(self):
        """Objects of the source (its collection), pick order."""
        return sorted(self.refcol.objs(), key=lambda o: o.Z)

    def item(self, key):
        return next((o for o in self.refcol.objs() if o.key == key), None)

    #! @section Load
    def load(self):
        """Objects of the source into the pool; its previous objects leave it.
        Returns {key: object} - they reach the collection after the lock."""
        with POOL.lock():
            self.unload()
            return self._load()

    def unload(self):
        """All objects of the source out of the pool (through its collection)."""
        with POOL.lock():
            for o in self.refcol.objs():
                o.destroy()

    def reload(self):
        """The source changed outside. Load again and give the unsaved changes back
        to the new objects. True = loaded again."""
        if not self._outdated():
            return False
        with POOL.lock():
            made = self.load()
            for key, attrs in self._pending.items():
                if key in made:
                    self._apply(made[key], attrs)
        return True

    #! @section Changes
    def stage(self, changes):
        """Unsaved changes {key: {attr: value}}; one call = one change."""
        for key, attrs in changes.items():
            self._pending.setdefault(key, {}).update(attrs)
        self.changes += 1
        self._notify("changed")

    def save(self):
        if self._pending:
            self._write(self._pending)
        self._saved()
        self._pending = {}
        self.changes = 0
        self._notify("saved")

    #! @section Subclass
    def _load(self):
        """Create the objects; return {key: object}."""
        return {}

    def _write(self, pending):
        """Write the unsaved changes into the source."""

    def _apply(self, obj, attrs):
        """Give an unsaved change back to an object after a reload."""

    def _saved(self):
        """Hook after a save (e.g. a preview)."""

    def _outdated(self):
        return True

    #! @section Hidding
    def _notify(self, what):
        for f in list(self.listeners):
            f(self, what)
