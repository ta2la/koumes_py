"""hg_pool_py.sel - Selection level - the meaning of PoolObj.sel."""

from enum import IntEnum


class Sel(IntEnum):
    """Selection level - the meaning of PoolObj.sel."""
    NONE = 0
    SEL = 1
    HANDLES = 2              # selected, with handles shown
