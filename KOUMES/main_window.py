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
"""MainWindow - 4-panel splitter shell for KOUMES.

Python port of the main-window portion of APPS/AI_T2LS/Main.cpp.

Layout:  [ parent (L) | dir (D) | detail (P1) | rightmost (P2) ]
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineScript
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QWidget,
)

from cmd_sys import CMD_SYS

from .chroma_page import ChromaPage
from .chroma_www_page import ChromaWwwPage
from .cmds_chroma import CmdsChroma
from .cmds_www import CmdsWww
from .fs_bridge import FsBridge
from .panel import Panel, wrap_panel
from .panel_bus import PanelBus
from . import viewer_resolver as vr


_WWW_PROFILE: Optional[QWebEngineProfile] = None
_QWEBCHANNEL_JS: Optional[str] = None


def www_profile() -> QWebEngineProfile:
    """Isolated profile for www panels (cookies/cache separated from view panels)."""
    global _WWW_PROFILE
    if _WWW_PROFILE is None:
        _WWW_PROFILE = QWebEngineProfile("koumes-www")
    return _WWW_PROFILE


def _load_qwebchannel_js() -> str:
    """Read qwebchannel.js. PyQt6 does NOT ship it as a resource like C++ Qt does,
    so we bundle a copy at KOUMES/qwebchannel.js (copied from a Qt install)."""
    global _QWEBCHANNEL_JS
    if _QWEBCHANNEL_JS is not None:
        return _QWEBCHANNEL_JS
    bundled = os.path.join(os.path.dirname(__file__), "qwebchannel.js")
    try:
        with open(bundled, "r", encoding="utf-8") as f:
            _QWEBCHANNEL_JS = f.read()
    except OSError:
        _QWEBCHANNEL_JS = ""
    return _QWEBCHANNEL_JS


_CHROMA_BOOTSTRAP_JS = r"""
window.__chroma = window.__chroma || {};
window.__chroma.role = (function () {
    var p = new URLSearchParams(location.search);
    return p.get('role') || 'mid';
})();
window.__chroma.ready = new Promise(function (resolve) {
    new QWebChannel(qt.webChannelTransport, function (channel) {
        window.__chroma.fs  = channel.objects.fs;
        window.__chroma.bus = channel.objects.bus;
        resolve(channel.objects.fs);
    });
});
window.__chroma.ready.then(function (fs) {
    document.addEventListener('selectionchange', function () {
        var s = window.getSelection();
        if (!s || !s.rangeCount) { fs.setSelection(''); return; }
        var r = s.getRangeAt(0);
        var e = r.commonAncestorContainer;
        if (e && e.nodeType === 3) e = e.parentElement;
        var attrs = {};
        if (e && e.attributes) {
            for (var i = 0; i < e.attributes.length; ++i) {
                var a = e.attributes[i];
                attrs[a.name] = a.value;
            }
        }
        fs.setSelection(JSON.stringify({
            text: s.toString(),
            tag:  e && e.tagName ? e.tagName : '',
            id:   e && e.id ? e.id : '',
            cls:  e && e.className ? e.className : '',
            attrs: attrs,
            role: window.__chroma.role
        }));
    });
});
"""


def setup_panel(view: QWebEngineView, role: str, bridge: FsBridge, bus: PanelBus) -> ChromaPage:
    """Attach a ChromaPage (with role) + WebChannel exposing fs + bus + panel + inject __chroma bootstrap."""
    page = ChromaPage(role, view)
    view.setPage(page)

    channel = QWebChannel(page)
    channel.registerObject("fs", bridge)
    channel.registerObject("bus", bus)
    channel.registerObject("panel", _PanelInfo(role, parent=page))
    page.setWebChannel(channel)

    inject_src = _load_qwebchannel_js() + _CHROMA_BOOTSTRAP_JS
    script = QWebEngineScript()
    script.setName(f"chroma-inject-{role}")
    script.setSourceCode(inject_src)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(False)
    page.scripts().insert(script)

    return page


class _PanelInfo(QObject):
    """Tiny QObject exposed to JS via WebChannel so viewers can query their own role."""

    def __init__(self, role: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._role = role

    @pyqtSlot(result=str)
    def role(self) -> str:
        return self._role


class MainWindow(QMainWindow):
    def __init__(self, root: str, start_dir: Optional[str] = None):
        super().__init__()
        self.root = os.path.abspath(root)

        target = os.path.abspath(start_dir) if start_dir else self.root
        if not FsBridge.is_inside(target, self.root):
            target = self.root
        if os.path.isfile(target):
            self.start_dir = os.path.dirname(target)
            self.start_file: Optional[str] = target
        else:
            self.start_dir = target
            self.start_file = None

        self.setWindowTitle(f"koumes - {self.root}")
        self.resize(1600, 900)

        self.bridge = FsBridge(self.root)
        self.bus = PanelBus()

        FsBridge.set_bus(self.bus)
        ChromaPage.set_bus(self.bus)
        CmdsChroma.set_bus(self.bus)

        self.left_view = QWebEngineView()
        self.mid_view = QWebEngineView()
        self.detail_view = QWebEngineView()
        self.rm_view = QWebEngineView()

        self.right_www = QWebEngineView()
        self.rm_www = QWebEngineView()
        self.right_www.setPage(ChromaWwwPage(www_profile(), self.right_www))
        self.rm_www.setPage(ChromaWwwPage(www_profile(), self.rm_www))

        setup_panel(self.left_view, "parent", self.bridge, self.bus)
        setup_panel(self.mid_view, "mid", self.bridge, self.bus)
        setup_panel(self.detail_view, "detail", self.bridge, self.bus)
        setup_panel(self.rm_view, "rightmost", self.bridge, self.bus)

        self.p_left: Panel = wrap_panel(self.left_view)
        self.p_mid: Panel = wrap_panel(self.mid_view)
        self.p_right: Panel = wrap_panel(self.detail_view, self.right_www)
        self.p_rm: Panel = wrap_panel(self.rm_view, self.rm_www)

        self.p_left.wrap.setMinimumWidth(150)
        self.p_mid.wrap.setMinimumWidth(150)

        pm_split = QSplitter(Qt.Orientation.Horizontal)
        pm_split.addWidget(self.p_left.wrap)
        pm_split.addWidget(self.p_mid.wrap)
        pm_split.setSizes([200, 300])

        right_split = QSplitter(Qt.Orientation.Horizontal)
        right_split.addWidget(self.p_right.wrap)
        right_split.addWidget(self.p_rm.wrap)
        right_split.setSizes([500, 500])

        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(pm_split)
        main_split.addWidget(right_split)
        main_split.setSizes([500, 1100])

        central = QWidget()
        from PyQt6.QtWidgets import QVBoxLayout
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(main_split)
        self.setCentralWidget(central)

        CmdsChroma.set_page(self.mid_view.page())
        CmdsChroma.set_detail_page(self.detail_view.page())
        CmdsChroma.set_rightmost_page(self.rm_view.page())
        CmdsChroma.set_detail_view(self.detail_view)
        CmdsChroma.set_rightmost_view(self.rm_view)
        CmdsWww.set_detail_www(self.right_www)
        CmdsWww.set_rightmost_www(self.rm_www)

        self._wire_bus()

        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(50)
        self._drain_timer.timeout.connect(self._drain_cmd_queue)
        self._drain_timer.start()

        self._load_dir(self.start_dir)
        if self.start_file:
            self.bus.notify_file_selected(self.start_file)

    def _drain_cmd_queue(self) -> None:
        sys_ = CMD_SYS()
        while sys_._deferred:
            a, sn, si, u = sys_._deferred.popleft()
            sys_.execute(a, sn, si, u)

    def _wire_bus(self) -> None:
        self.bus.dirChanged.connect(self._on_dir_changed)
        self.bus.fileSelected.connect(self._on_file_selected)
        self.bus.fileSelectedRightmost.connect(self._on_file_selected_rightmost)
        self.bus.wwwUrlRequested.connect(self._on_www_url_requested)
        self.bus.selectionChanged.connect(self._on_selection_changed)

    def _load_dir(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        CmdsChroma.set_last_dir(path)
        CmdsChroma.set_last_dir_viewer("dirs")
        html = vr.find_viewer_html(path, self.root, "dirs")
        if html:
            url = QUrl.fromLocalFile(html)
            url.setQuery(f"start={path}&role=mid")
        else:
            url = QUrl.fromLocalFile(path)
        self.mid_view.setUrl(url)
        self.p_mid.info_path.setText(path)
        self.p_mid.info_viewer.setText("dirs" if html else "native")

    def _on_dir_changed(self, path: str) -> None:
        if path == CmdsChroma._last_dir:
            return
        self._load_dir(path)

    def _resolve_view_url(self, file_path: str, role: str = "detail") -> QUrl:
        """Pick viewer HTML for file_path, wrap it with ?file=abspath&role=<role>."""
        viewer = vr.read_viewer_for_ext(file_path, self.root)
        if not viewer:
            return QUrl.fromLocalFile(file_path)
        html = vr.find_viewer_html(os.path.dirname(file_path), self.root, viewer)
        if not html:
            return QUrl.fromLocalFile(file_path)
        url = QUrl.fromLocalFile(html)
        url.setQuery(f"file={file_path}&role={role}")
        return url

    def _on_file_selected(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        if path == CmdsChroma._last_file:
            return
        CmdsChroma.set_last_file(path)
        viewer = vr.read_viewer_for_ext(path, self.root) or "native"
        CmdsChroma.set_last_file_viewer(viewer)
        self.p_right.info_viewer.setText(viewer)
        self.detail_view.setUrl(self._resolve_view_url(path, role="detail"))
        self.p_right.info_path.setText(path)
        CmdsChroma.set_sel_file("p1", path)

    def _on_file_selected_rightmost(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        self.rm_view.setUrl(self._resolve_view_url(path, role="rightmost"))
        self.p_rm.info_path.setText(path)
        CmdsChroma.set_sel_file("p2", path)

    def _on_www_url_requested(self, url: QUrl, source: str) -> None:
        target = self.rm_www if source in ("parent", "mid", "detail") else self.right_www
        target.setUrl(url)

    def _on_selection_changed(self, panel: str, file: str, line: int) -> None:
        text = f"{file}:{line}" if line else file
        if panel == "dir":
            self.p_mid.info_selection.setText(text)
        elif panel == "p1":
            self.p_right.info_selection.setText(text)
        elif panel == "p2":
            self.p_rm.info_selection.setText(text)
