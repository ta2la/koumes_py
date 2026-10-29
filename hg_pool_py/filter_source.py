"""hg_pool_py.filter_source - Passes objects of one source only."""

from .filter import Filter


class FilterSource(Filter):
#! Passes objects of one source only.
    def __init__(self, source):
        self.source = source

    def pass_(self, obj):
        return obj.source == self.source
