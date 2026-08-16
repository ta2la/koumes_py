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
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from cmd_sys import CMD_SYS


def _path_from_index(abs_: str, root: str) -> str:
    """Shorten abs to '<sandbox>/rel'. Outside sandbox -> full abs path."""
    if not abs_:
        return abs_
    abs_c = os.path.normpath(os.path.abspath(abs_))
    root_c = os.path.normpath(os.path.abspath(root))
    if not abs_c.startswith(root_c):
        return abs_c
    root_base = os.path.basename(root_c) or root_c
    rel = abs_c[len(root_c):].lstrip(os.sep)
    return root_base if not rel else f"{root_base}/{rel}"


def _is_outside_sandbox(abs_: str, root: str) -> bool:
    if not abs_:
        return False
    abs_c = os.path.normpath(os.path.abspath(abs_))
    root_c = os.path.normpath(os.path.abspath(root))
    return not abs_c.startswith(root_c)


from .app_paths import AppPaths
from .chroma_page import ChromaPage
from .chroma_www_page import ChromaWwwPage
from .cmds_chroma import CmdsChroma
from .cmds_www import CmdsWww
from .fs_bridge import FsBridge
from .panel import Panel, wrap_panel
from .panel_bus import PanelBus
from . import viewer_resolver as vr
from .viewer_bar import rebuild_viewer_bar


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

// ====== [[id]] link helper (opt-in for viewers) ======
// Style + click handler are global; viewers explicitly call
// window.__chroma.linkify(text) -> HTML with <a class="chroma-link">
// for each [[id]] token. Click resolves via FsBridge.followLink (walks
// index, matches `<type>[<id>:<N>]<file>`, emits bus.fileSelected + lineChanged).
(function () {
    function installStyle() {
        if (!document.documentElement) { setTimeout(installStyle, 10); return; }
        var style = document.createElement('style');
        style.textContent =
            '.chroma-link { color: #1e40af; text-decoration: none;'
          + ' border-bottom: 1px dotted #93c5fd; cursor: pointer; }'
          + '.chroma-link:hover { color: #2563eb; border-bottom-style: solid; }';
        document.documentElement.appendChild(style);
    }
    installStyle();

    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
        });
    }
    window.__chroma = window.__chroma || {};
    window.__chroma.linkify = function (text) {
        return String(text).replace(/\[\[([^\]]+)\]\]/g, function (_, id) {
            return '<a class="chroma-link" href="javascript:void(0)" data-link="'
                 + esc(id) + '">' + esc(id) + '</a>';
        });
    };

    document.addEventListener('click', function (e) {
        var t = e.target;
        while (t && !(t.classList && t.classList.contains('chroma-link'))) t = t.parentElement;
        if (!t) return;
        e.preventDefault();
        var id = t.dataset.link;
        if (!id || !window.__chroma.fs) return;
        var params = new URLSearchParams(location.search);
        var start = params.get('file') || params.get('dir') || params.get('start') || '';
        window.__chroma.fs.followLink(id, start);
    });
})();
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
        self.display_root = self.root

        self._last_p1_html: str = ""
        self._last_p1_file: str = ""
        self._last_p2_html: str = ""
        self._last_p2_file: str = ""

        target = os.path.abspath(start_dir) if start_dir else self.root
        if not FsBridge.is_inside(target, self.root):
            target = self.root
        if os.path.isfile(target):
            self.start_dir = os.path.dirname(target)
            self.start_file: Optional[str] = target
        else:
            self.start_dir = target
            self.start_file = None

        self.setWindowTitle(f"KOUMES  {_path_from_index(self.root, self.root)}")
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
        main_split.setSizes([920, 680])

        central = QWidget()
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

        self._wire_left_panel_tabs()
        self._wire_dir_viewer_toggle()

        self.p_rm.wrap.setVisible(False)
        self.p_right.hide_rightmost.setText("◨")

        self._load_dir(self.start_dir)
        if self.start_file:
            self.bus.notify_file_selected(self.start_file)

        log_html = os.path.join(self.root, ".t2l", "cmdlog.html")
        if os.path.isfile(log_html):
            self.bus.notify_panel_show("left", log_html, "")

    def _wire_dir_viewer_toggle(self) -> None:
        """Mid panel custom/dflt buttons: switch dir viewer via CmdSys."""
        self.p_mid.dflt.clicked.connect(
            lambda _=False: CMD_SYS().execute_thread_safe(
                "viewer_switch dir dirs", "ui", -1, "TOOLBAR")
        )
        self.p_mid.custom.clicked.connect(
            lambda _=False: CMD_SYS().execute_thread_safe(
                f"viewer_switch dir {self.p_mid.custom.text()}", "ui", -1, "TOOLBAR")
        )

    def _wire_left_panel_tabs(self) -> None:
        """LEFT panel = 3-way switch: bookmarks / dirs-upper / log. Default = log."""
        bm_html = os.path.join(self.root, ".t2l", "bookmarks.html")
        dirs_html = vr.find_viewer_html(self.root, self.root, "dirs")
        log_html = os.path.join(self.root, ".t2l", "cmdlog.html")

        pL = self.p_left
        pL.custom.setText("bookmarks")
        pL.dflt.setText("dirs-upper")
        pL.log.setText("log")
        pL.custom.setVisible(True)
        pL.dflt.setVisible(True)
        pL.log.setVisible(True)
        pL.log.setChecked(True)

        pL.hide_parent.setVisible(False)
        pL.dir_up.setVisible(False)
        pL.fm.setVisible(False)
        pL.reveal_dir.setVisible(False)
        pL.hide_rightmost.setVisible(False)
        pL.viewer_bar.setVisible(False)

        pL.custom.setToolTip(f'panel_show left "{bm_html}"')
        pL.dflt.setToolTip(f'panel_show left "{dirs_html}"' if dirs_html else "panel_show left <dirs-upper>")
        pL.log.setToolTip(f'panel_show left "{log_html}"')

        pL.custom.clicked.connect(
            lambda _=False, h=bm_html: CMD_SYS().execute_thread_safe(f'panel_show left "{h}"', "ui", -1, "TOOLBAR")
        )
        pL.dflt.clicked.connect(
            lambda _=False, h=dirs_html: CMD_SYS().execute_thread_safe(f'panel_show left "{h}"', "ui", -1, "TOOLBAR") if h else None
        )
        pL.log.clicked.connect(
            lambda _=False, h=log_html: CMD_SYS().execute_thread_safe(f'panel_show left "{h}"', "ui", -1, "TOOLBAR")
        )

    def _drain_cmd_queue(self) -> None:
        sys_ = CMD_SYS()
        while sys_._deferred:
            a, sn, si, u = sys_._deferred.popleft()
            sys_.execute(a, sn, si, u)

    def _wire_bus(self) -> None:
        self.bus.dirChanged.connect(self._on_dir_changed)
        self.bus.dirChanged.connect(lambda _p: self._refresh_dir_up())
        self.bus.fileSelected.connect(self._on_file_selected)
        self.bus.fileSelectedRightmost.connect(self._on_file_selected_rightmost)
        self.bus.fileSelectedForBrowse.connect(self._on_file_selected_for_browse)
        self.bus.lineChanged.connect(self._on_line_changed)
        self.bus.wwwUrlRequested.connect(self._on_www_url_requested)
        self.bus.selectionChanged.connect(self._on_selection_changed)
        self.bus.panelShow.connect(self._on_panel_show)
        self.bus.sandboxChanged.connect(self._on_sandbox_changed)

    def _on_file_selected_for_browse(self, file_path: str, line: int) -> None:
        """Chroma-link click resolver: prefer viewer with sys__browse_support: true."""
        if not os.path.isfile(file_path):
            return
        browse = vr.read_browse_viewers(file_path, self.root)
        if not browse:
            self.bus.notify_file_selected(file_path)
            if line > 0:
                self.bus.notify_line_changed(line)
            return
        viewer = browse[0]
        target = vr.find_viewer_html(os.path.dirname(file_path), self.root, viewer)
        if not target:
            self.bus.notify_file_selected(file_path)
            if line > 0:
                self.bus.notify_line_changed(line)
            return
        CmdsChroma.set_last_file(file_path)
        CmdsChroma.set_sel_file("p1", file_path)
        self._set_info_path(self.p_right.info_path, file_path)
        self._set_info_viewer(self.p_right.info_viewer, target, False)
        CmdsChroma.set_last_file_viewer(viewer)
        self._last_p1_html = target
        self._last_p1_file = file_path
        self._load_view_html(self.detail_view, target, file_path, "detail", line)
        rebuild_viewer_bar(self.p_right.viewer_bar, file_path, self.root,
                           self._make_p1_load_fn(), viewer, "p1")

    def _make_p1_load_fn(self):
        def load_fn(target: str, file: str) -> None:
            if self._last_p1_html == target and self._last_p1_file == file:
                return
            self._last_p1_html = target
            self._last_p1_file = file
            is_native = (target == file)
            self._set_info_viewer(self.p_right.info_viewer, target, is_native)
            viewer_name = "NATIVE" if is_native else os.path.splitext(os.path.basename(target))[0]
            CmdsChroma.set_last_file_viewer(viewer_name)
            self._load_view_html(self.detail_view, target, file, "detail")
        return load_fn

    def _on_line_changed(self, line: int) -> None:
        pass  # dirs.html / viewers subscribe on their JS side

    def _refresh_dir_up(self) -> None:
        """Style dir_up button red when the parent would leave the ORIGINAL sandbox."""
        d = CmdsChroma._last_dir
        if not d:
            return
        parent = os.path.dirname(os.path.abspath(d))
        would_exit = not FsBridge.is_inside(parent, self.display_root)
        base_style = "font-size: 27px; padding: 0; min-width: 38px; min-height: 38px;"
        if would_exit:
            self.p_mid.dir_up.setStyleSheet(base_style + " color: #f87171; font-weight: 700;")
            self.p_mid.dir_up.setToolTip(f"Sandbox edge — click extends sandbox to {parent}")
        else:
            self.p_mid.dir_up.setStyleSheet(base_style)
            self.p_mid.dir_up.setToolTip(f"Dir up → {parent}")

    def _on_sandbox_changed(self, new_root: str) -> None:
        pass

    def _on_panel_show(self, panel: str, file: str, viewer: str) -> None:
        if panel == "dir":
            if os.path.isdir(file):
                self._load_dir(file)
        elif panel == "p1":
            if os.path.isfile(file):
                self._on_file_selected(file)
        elif panel == "p2":
            if os.path.isfile(file):
                self._on_file_selected_rightmost(file)
        elif panel == "left":
            self._show_left_html(file)

    def _show_left_html(self, file: str) -> None:
        if not os.path.isfile(file):
            return
        url = QUrl.fromLocalFile(file)
        base = os.path.basename(file)
        info_path_file = file
        self._left_load_ctr = getattr(self, "_left_load_ctr", 0) + 1
        if base == "cmdlog.html":
            info_path_file = os.path.join(AppPaths.inst().dir_config(), "cmdlog.txt")
            q = f"role=parent&file={info_path_file}&_ts={self._left_load_ctr}"
        elif base == "bookmarks.html":
            info_path_file = os.path.join(self.root, ".t2l", "bookmarks.t2l")
            q = f"role=parent&file={info_path_file}&_ts={self._left_load_ctr}"
        else:
            q = f"role=parent&start={self.start_dir}&_ts={self._left_load_ctr}"
        url.setQuery(q)
        self.left_view.load(url)
        self._set_info_path(self.p_left.info_path, info_path_file)
        self._set_info_viewer(self.p_left.info_viewer, file, False)

    def _load_dir(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        CmdsChroma.set_last_dir(path)
        CmdsChroma.set_sel_file("dir", path)

        custom_viewer = vr.read_viewer_name(path)

        self.p_mid.custom.setVisible(bool(custom_viewer))
        self.p_mid.dflt.setVisible(bool(custom_viewer))
        if custom_viewer:
            self.p_mid.custom.setText(custom_viewer)
            self.p_mid.custom.setToolTip(f"viewer_switch dir {custom_viewer}")
            self.p_mid.dflt.setToolTip("viewer_switch dir dirs")

        root = self.bridge.allowed_dir_
        target_html = ""
        mode = "default"
        if custom_viewer:
            target_html = vr.find_viewer_html(path, root, custom_viewer)
            if target_html:
                mode = "custom"
        if not target_html:
            target_html = vr.find_viewer_html(path, root, "dirs")

        self._set_info_path(self.p_mid.info_path, path)
        self._set_info_viewer(self.p_mid.info_viewer, target_html, is_native=False) if target_html \
            else self.p_mid.info_viewer.setText("native")
        CmdsChroma.set_last_dir_viewer(target_html)

        parent_dir = os.path.dirname(path) or path
        self._set_info_path(self.p_left.info_path, parent_dir)

        if target_html:
            if mode == "custom":
                self.p_mid.custom.setChecked(True)
                self.p_mid.dflt.setChecked(False)
            else:
                self.p_mid.dflt.setChecked(True)
                self.p_mid.custom.setChecked(False)

            url = QUrl.fromLocalFile(target_html)
            key = "dir" if mode == "custom" else "start"
            url.setQuery(f"role=mid&{key}={path}")
            self.mid_view.setUrl(url)
        else:
            self.mid_view.setUrl(QUrl.fromLocalFile(path))

        self.setWindowTitle(f"KOUMES   {_path_from_index(path, self.root)}")

        def switch_fn(viewer: str) -> None:
            if viewer == "dirs":
                html = vr.find_viewer_html(CmdsChroma._last_dir, self.bridge.allowed_dir_, "dirs")
                if not html:
                    return
                url = QUrl.fromLocalFile(html)
                url.setQuery(f"role=mid&start={CmdsChroma._last_dir}")
            else:
                html = vr.find_viewer_html(CmdsChroma._last_dir, self.bridge.allowed_dir_, viewer)
                if not html:
                    return
                url = QUrl.fromLocalFile(html)
                url.setQuery(f"role=mid&dir={CmdsChroma._last_dir}")
            self.mid_view.setUrl(url)

        CmdsChroma.set_viewer_switch_fn("dir", switch_fn)


    def _sync_copy_btn(self, label, visible: bool) -> None:
        btn = label.property("copyBtn")
        if btn is not None:
            btn.setVisible(visible)

    def _set_info_path(self, label, abs_path: str) -> None:
        label.setText(_path_from_index(abs_path, self.root))
        label.setToolTip(abs_path)
        label.setProperty("cmdPath", abs_path)
        outside = _is_outside_sandbox(abs_path, self.root)
        label.setStyleSheet(
            "color: #f87171; font-weight: 700;" if outside
            else "color: #f9fafb; font-weight: 700;"
        )
        self._sync_copy_btn(label, bool(abs_path))

    def _on_dir_changed(self, path: str) -> None:
        if path == CmdsChroma._last_dir:
            return
        self._load_dir(path)

    def _load_view_html(self, view: QWebEngineView, target: str, file: str,
                         role: str, line: int = 0) -> None:
        if target == file:
            view.setUrl(QUrl.fromLocalFile(file))
            return
        url = QUrl.fromLocalFile(target)
        q = f"file={file}&role={role}"
        if line > 0:
            q += f"&line={line}"
        url.setQuery(q)
        view.setUrl(url)

    def _set_info_viewer(self, label, target: str, is_native: bool) -> None:
        if is_native:
            label.setText("NATIVE")
            label.setToolTip("")
            label.setProperty("cmdPath", "")
        else:
            label.setText(_path_from_index(target, self.root))
            label.setToolTip(target)
            label.setProperty("cmdPath", target)
        label.setStyleSheet("color: #9ca3af;")
        self._sync_copy_btn(label, not is_native and bool(target))

    def _on_file_selected(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        if path == CmdsChroma._last_file:
            return
        CmdsChroma.set_last_file(path)
        CmdsChroma.set_sel_file("p1", path)
        self._set_info_path(self.p_right.info_path, path)

        self._last_p1_html = ""
        self._last_p1_file = ""

        def load_fn(target: str, file: str) -> None:
            if self._last_p1_html == target and self._last_p1_file == file:
                return
            self._last_p1_html = target
            self._last_p1_file = file
            is_native = (target == file)
            self._set_info_viewer(self.p_right.info_viewer, target, is_native)
            viewer_name = "NATIVE" if is_native else os.path.splitext(os.path.basename(target))[0]
            CmdsChroma.set_last_file_viewer(viewer_name)
            self._load_view_html(self.detail_view, target, file, "detail")

        def switch_fn(viewer: str) -> None:
            f = self._last_p1_file
            if not f:
                return
            file_dir = os.path.dirname(f)
            target = f if viewer == "native" else vr.find_viewer_html(file_dir, self.root, viewer)
            if not target:
                return
            self._last_p1_html = ""
            load_fn(target, f)

        CmdsChroma.set_viewer_switch_fn("p1", switch_fn)
        rebuild_viewer_bar(self.p_right.viewer_bar, path, self.root, load_fn, "", "p1")

    def _on_file_selected_rightmost(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        self._set_info_path(self.p_rm.info_path, path)
        CmdsChroma.set_sel_file("p2", path)

        self._last_p2_html = ""
        self._last_p2_file = ""

        def load_fn(target: str, file: str) -> None:
            if self._last_p2_html == target and self._last_p2_file == file:
                return
            self._last_p2_html = target
            self._last_p2_file = file
            is_native = (target == file)
            self._set_info_viewer(self.p_rm.info_viewer, target, is_native)
            self._load_view_html(self.rm_view, target, file, "rightmost")

        def switch_fn(viewer: str) -> None:
            f = self._last_p2_file
            if not f:
                return
            file_dir = os.path.dirname(f)
            target = f if viewer == "native" else vr.find_viewer_html(file_dir, self.root, viewer)
            if not target:
                return
            self._last_p2_html = ""
            load_fn(target, f)

        CmdsChroma.set_viewer_switch_fn("p2", switch_fn)
        rebuild_viewer_bar(self.p_rm.viewer_bar, path, self.root, load_fn, "", "p2")

    def _on_www_url_requested(self, url: QUrl, source: str) -> None:
        target = self.rm_www if source in ("parent", "mid", "detail") else self.right_www
        target.setUrl(url)

    def _on_selection_changed(self, panel: str, file: str, line: int) -> None:
        short = _path_from_index(file, self.root) if file else ""
        text = f"{short}:{line}" if line else short
        label = None
        if panel == "dir":
            label = self.p_mid.info_selection
        elif panel == "p1":
            label = self.p_right.info_selection
        elif panel == "p2":
            label = self.p_rm.info_selection
        if label is None:
            return
        label.setText(text)
        label.setToolTip(file)
        label.setProperty("cmdPath", file)
        outside = _is_outside_sandbox(file, self.root)
        label.setStyleSheet(
            "color: #f87171; font-weight: 400;" if outside
            else "color: #9ca3af; font-weight: 400;"
        )
        self._sync_copy_btn(label, bool(file))
