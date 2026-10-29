"""hg_pool_py.source_file - a source in a file: id = normalized path, reading, atomic writing."""

import os

from .source import Source


#=============================================================================
class SourceFile(Source):
#! Source in a file: id = normalized path; reading, atomic writing, own writes ignored.
#=============================================================================
    def __init__(self, path):
        super().__init__(os.path.realpath(path))
        self._last_written = None    # content we wrote ourselves

    @property
    def path(self):
        return self.id

    def read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    def write_text(self, new):
        """Atomic write; remembered, so its own change on disk is not a reload."""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new)
        os.replace(tmp, self.path)
        self._last_written = new

    def _outdated(self):
        text = self.read()
        return text is not None and text != self._last_written
