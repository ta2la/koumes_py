"""hg_pool_py.filter_selection - Passes selected objects only."""

from .filter import Filter
from .sel import Sel


class FilterSelection(Filter):
    """Passes selected objects only."""
    def pass_(self, obj):
        return obj.sel != Sel.NONE
