#
# Copyright (C) 2026 Petr Talla. [petr.talla@gmail.com]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#           http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""qt_viewer - a viewer that is a Python class instead of an HTML page.

What it is (2026-10-21): some views are too much drawing and
logic for HTML - a diagram whose nodes stay where they were put is the first
one. Qt has that ready (QGraphicsScene), so p1 and p2 can show a Qt widget in
place of the web view. Everything around it stays: the viewer bar, the info
bar, `viewer_switch`, `chroma_line` / `chroma_setline`.

Which viewer a file gets is decided as for HTML - an in-file `type: viewer /
name: X` directive or `viewer_ext` in a `config.t2l` up the tree. What code a
name stands for is decided **only by the deployment config** of koumes
(`other_config/config.t2l`), one attribute line per viewer:

    qt_viewer: diag /path/to/diag_view.py:DiagView

Not by the tree: a `.t2l/` anywhere could otherwise hand koumes code to run.
The module stays outside koumes (koumes_py is a public repo); it is loaded from
its file, its dir goes on sys.path so it can import its siblings.

The class koumes expects (agreed 2026-10-21):

    class DiagView(QWidget):
        selected = pyqtSignal(int)      # record number, 1-based like t2lunit.py
        def __init__(self, path: str, parent: QWidget): ...
        def select(self, record_no: int): ...  # highlight + scroll, no emit
        def reload(self): ...                   # the file changed on disk

`selected` goes where an HTML viewer's `fs.setSelectedLine(N)` goes, so
`chroma_line` answers it. `chroma_setline` comes back as `select()`. `select()`
must not emit, or the two would chase each other. `reload()` is called on
every change of the file, including the viewer's own write after a drag - it
is the viewer that knows what it wrote, so it decides whether to do anything.

A viewer that fails to import or to build does not take koumes down: the
panel shows the error and the file falls back to `txt`.
"""

import importlib.util
import os
import sys
import traceback
from typing import Callable, Dict, Optional, Tuple

from PyQt6.QtCore import QFileSystemWatcher, QTimer
from PyQt6.QtWidgets import QLabel, QStackedWidget, QWidget

from .app_paths import AppPaths

#: Prefix that marks a viewer target as a Qt class, not an HTML file. The
#: rest of the target is the viewer name: `qt:diag`.
QT_PREFIX = "qt:"


def is_qt_target(target: str) -> bool:
    return target.startswith(QT_PREFIX)


def registry() -> Dict[str, Tuple[str, str]]:
    """`qt_viewer:` lines of the deployment config -> {name: (file, class)}.
    A line that does not parse is skipped; the viewer is then just missing."""
    out: Dict[str, Tuple[str, str]] = {}
    for value in AppPaths.inst().settings_list("qt_viewer"):
        parts = value.split(None, 1)
        if len(parts) != 2 or ":" not in parts[1]:
            continue
        file_, cls = parts[1].strip().rsplit(":", 1)
        out[parts[0]] = (os.path.expanduser(file_), cls.strip())
    return out


_classes: Dict[str, type] = {}


def load_class(name: str) -> type:
    """Import the viewer class once per run. Raises on any failure - the
    caller turns it into the error page and the fallback."""
    if name in _classes:
        return _classes[name]
    reg = registry()
    if name not in reg:
        raise LookupError(f"qt_viewer {name}: not in config.t2l")
    file_, cls_name = reg[name]
    mod_dir = os.path.dirname(file_)
    if mod_dir not in sys.path:
        sys.path.insert(0, mod_dir)
    spec = importlib.util.spec_from_file_location(
        "koumes_qt_" + name, file_)
    if spec is None or spec.loader is None:
        raise ImportError(f"qt_viewer {name}: cannot load {file_}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _classes[name] = getattr(mod, cls_name)
    return _classes[name]


class ViewerHost(QStackedWidget):
    """Content of p1 / p2: the web view on page 0, a Qt viewer on page 1.

    The panel keeps one web view for its whole life (its page carries the
    bridge to Python). A Qt viewer is built per file and thrown away when the
    panel moves on - to another file or back to an HTML viewer.
    """

    def __init__(self, web: QWidget, on_selected: Callable[[str, int], None],
                 on_failed: Callable[[str], None]) -> None:
        super().__init__()
        self.web = web
        self.addWidget(web)
        self._on_selected = on_selected
        self._on_failed = on_failed
        self.widget: Optional[QWidget] = None
        self.name = ""
        self.path = ""
        self._watch = QFileSystemWatcher(self)
        self._watch.fileChanged.connect(self._changed)
        # An editor or a t2l writer saves by rename: the watched file goes
        # away and the watch with it. The dir sees the rename.
        self._watch.directoryChanged.connect(self._changed)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._reload)
        self._mtime = 0.0

    def is_qt(self) -> bool:
        return self.widget is not None and self.currentWidget() is self.widget

    def show_web(self) -> None:
        self._drop()
        self.setCurrentWidget(self.web)

    def show_qt(self, name: str, path: str, line: int = 0) -> bool:
        """Build viewer `name` for `path` and show it. False = it failed, the
        error is on screen and `on_failed` was told."""
        self._drop()
        try:
            cls = load_class(name)
            w = cls(path, self)
            w.selected.connect(lambda n, p=path: self._on_selected(p, n))
        except Exception:  # noqa: BLE001 - any failure of foreign code
            msg = f"qt_viewer {name} - {path}\n\n{traceback.format_exc()}"
            err = QLabel(msg)
            err.setWordWrap(True)
            self.widget = err
            self.addWidget(err)
            self.setCurrentWidget(err)
            self._on_failed(msg)
            return False
        self.widget, self.name, self.path = w, name, path
        self.addWidget(w)
        self.setCurrentWidget(w)
        self._mtime = self._stat()
        self._watch.addPath(path)
        self._watch.addPath(os.path.dirname(path))
        if line > 0:
            self.select(line)
        return True

    def select(self, record_no: int) -> None:
        if self.is_qt() and hasattr(self.widget, "select"):
            self.widget.select(record_no)

    def _drop(self) -> None:
        if self._watch.files() or self._watch.directories():
            self._watch.removePaths(self._watch.files() + self._watch.directories())
        if self.widget is not None:
            self.removeWidget(self.widget)
            self.widget.deleteLater()
        self.widget, self.name, self.path = None, "", ""

    def _stat(self) -> float:
        try:
            return os.stat(self.path).st_mtime
        except OSError:
            return 0.0

    def _changed(self, _p: str) -> None:
        if self.path:
            self._debounce.start()

    def _reload(self) -> None:
        # The dir watch fires for any file in it; only our file counts.
        m = self._stat()
        if not m or m == self._mtime:
            return
        self._mtime = m
        if self.path not in self._watch.files():
            self._watch.addPath(self.path)
        if hasattr(self.widget, "reload"):
            self.widget.reload()
