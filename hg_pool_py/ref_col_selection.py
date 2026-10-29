"""hg_pool_py.ref_col_selection - selection of pool objects.

The object keeps a numeric flag `sel` (PoolObj.sel); its levels are defined
here and the selection is an ordinary pool collection filtered on it. What a
click does to it (modes) is up to the interaction layer of an application.
"""

from .filter_selection import FilterSelection
from .pool import POOL
from .ref_col import RefCol
from .sel import Sel


class RefColSelection(RefCol):
    """Selection = collection with FilterSelection. A click on the same object
    cycles its levels to unselected (up to obj.SEL_MAX); elsewhere selects only
    that one; on nothing clears all. Toggle (ctrl+click) adds or removes and
    keeps the rest."""

    def __init__(self):
        super().__init__(FilterSelection())

    def items(self):
        return self.objs()

    def level(self, obj):
        return Sel(obj.sel) if obj is not None else Sel.NONE

    def click(self, obj):
        with POOL.lock():
            if obj is None:
                self.clear()
            elif obj.sel != Sel.NONE:
                nxt = obj.sel + 1
                obj.set_sel(Sel(nxt) if nxt <= obj.SEL_MAX else Sel.NONE)
            else:
                self.clear()
                obj.set_sel(Sel.SEL)

    def toggle(self, obj):
        if obj is None:
            return
        with POOL.lock():
            obj.set_sel(Sel.NONE if obj.sel != Sel.NONE else Sel.SEL)

    def set(self, obj, level):
        with POOL.lock():
            obj.set_sel(level)

    def clear(self):
        with POOL.lock():
            for o in self.objs():
                o.set_sel(Sel.NONE)

    def selected_key(self, source):
        """Key of the first selected object of a source, 0 when none."""
        sel = [o for o in self.objs() if o.source == source]
        return sel[0].key if sel else 0


SELSET = RefColSelection()


POOL.add_refcol(SELSET)
