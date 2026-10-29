"""hg_pool_py.sources - the open sources (singleton SOURCES); one is active."""

from .pool import POOL


#=============================================================================
class Sources:
#! Open sources (singleton). One is active - new objects go there.
#=============================================================================
    def __init__(self):
        self.items = []
        self.active = None

    def open(self, src):
        """For now only one open: opening a new one unloads the previous.
        The source collection is registered in the pool."""
        for s in list(self.items):
            self.close(s)
        self.items.append(src)
        self.active = src
        POOL.add_refcol(src.refcol)

    def find(self, sid):
        return next((s for s in self.items if s.id == sid), None)

    def close(self, src):
        src.unload()
        POOL.remove_refcol(src.refcol)
        if src in self.items:
            self.items.remove(src)
        if self.active is src:
            self.active = self.items[-1] if self.items else None


SOURCES = Sources()
