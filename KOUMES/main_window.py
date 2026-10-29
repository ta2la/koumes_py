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

Python port of the main-window portion of the C++ predecessor's Main.cpp.

Layout:  [ parent (L) | dir (D) | detail (P1) | rightmost (P2) ]
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from cmd_sys import CMD_SYS


def _is_outside_sandbox(abs_: str, root: str) -> bool:
    """The boundary is a path separator, not a string prefix: '<root>_files.html'
    lies outside even though it starts with '<root>'."""
    if not abs_:
        return False
    abs_c = os.path.normpath(os.path.abspath(abs_))
    root_c = os.path.normpath(os.path.abspath(root))
    return abs_c != root_c and not abs_c.startswith(root_c + os.sep)


def _path_from_index(abs_: str, root: str) -> str:
    """Shorten abs to '<sandbox>/rel'. Outside sandbox -> full abs path."""
    if not abs_:
        return abs_
    abs_c = os.path.normpath(os.path.abspath(abs_))
    if _is_outside_sandbox(abs_c, root):
        return abs_c
    root_c = os.path.normpath(os.path.abspath(root))
    root_base = os.path.basename(root_c) or root_c
    rel = abs_c[len(root_c):].lstrip(os.sep)
    return root_base if not rel else f"{root_base}/{rel}"


from .app_paths import AppPaths
from .chroma_page import ChromaPage
from .cmds_chroma import CmdsChroma
from .cmds_paste import CmdsPaste
from .cmds_www import CmdsWww
from .fs_bridge import FsBridge
from .panel import (DetailPanel, DirPanel, HOVER_QSS, LeftPanel, Panel,
                    RightmostPanel, dir_up_qss, icon_btn_qss, make_label_clickable,
                    set_label_clickable)
from .panel_bus import PanelBus
from .qt_viewer import ViewerHost, is_qt_target, QT_PREFIX, registry as qt_registry
from .role_bar import button_label
from . import viewer_resolver as vr
from .viewer_bar import rebuild_viewer_bar


_QWEBCHANNEL_JS: Optional[str] = None


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
// ====== path -> URL the browser can load ======
// A viewer knows a path; what the <img src> needs is a URL, and the two are
// not the same thing in every host. Here they nearly are - Qt loads the page
// off the disk, so a path becomes a `file://` URL. A host that serves the same
// viewers over http gives this function its own body; that is the whole of the
// difference, and it is the reason no viewer writes `file://` itself.
//
// Synchronous on purpose. It is called while building markup, not inside a
// promise - a bridge round trip here would force every viewer to render twice.
window.__chroma.fileUrl = function (path) {
    if (!path) return '';
    if (/^([a-z]+:|\/\/|data:)/i.test(path)) return path;   // already a URL
    return 'file://' + path;
};
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
        var h = null;
        for (var n = e; n; n = n.parentElement) {
            if (n.dataset && n.dataset.h) { h = n.dataset.h; break; }
        }
        var attrs = {};
        if (e && e.attributes) {
            for (var i = 0; i < e.attributes.length; ++i) {
                var a = e.attributes[i];
                attrs[a.name] = a.value;
            }
        }
        var startNode = r.startContainer;
        var startOffset = r.startOffset;
        var nodeText = (startNode && startNode.nodeType === 3)
            ? (startNode.textContent || '') : '';
        var preview = {
            before: nodeText.slice(Math.max(0, startOffset - 30), startOffset),
            after:  nodeText.slice(startOffset, startOffset + 30)
        };
        fs.setSelection(JSON.stringify({
            text: s.toString(),
            handler: h,
            offset: startOffset,
            preview: preview,
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

    # Relaxed settings - same 8 attributes the C++ setupPanel_ applies.
    # LocalContentCanAccessFileUrls is load-bearing: viewer HTMLs are loaded
    # via file:// and must be able to reach the files they render.
    s = view.settings()
    A = QWebEngineSettings.WebAttribute
    for attr in (
        A.LocalContentCanAccessFileUrls,
        A.LocalContentCanAccessRemoteUrls,
        A.AllowRunningInsecureContent,
        A.JavascriptEnabled,
        A.JavascriptCanAccessClipboard,
        A.JavascriptCanPaste,
        A.PluginsEnabled,
        A.PdfViewerEnabled,
    ):
        s.setAttribute(attr, True)

    # Nothing a page opens here may keep anything. A viewer is a way of looking
    # at a file, not a site with a memory: state belongs next to the file, in
    # t2l the tree can read, never in a cookie jar or a localStorage key that
    # only Chromium knows about. Off for every panel, so it holds for viewers
    # in the tree as much as for the ones shipped with the app.
    s.setAttribute(A.LocalStorageEnabled, False)
    prof = page.profile()
    prof.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    prof.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
    prof.cookieStore().deleteAllCookies()

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

        self._last_dir_html: str = ""
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

        self.setWindowTitle(self._window_title())
        self.resize(1600, 900)

        self.bridge = FsBridge(self.root)
        self.bus = PanelBus()

        FsBridge.set_bus(self.bus)
        ChromaPage.set_bus(self.bus)
        CmdsChroma.set_bus(self.bus)

        self.left_view = QWebEngineView()
        self.dir_view = QWebEngineView()
        self.detail_view = QWebEngineView()
        self.rm_view = QWebEngineView()


        setup_panel(self.left_view, "parent", self.bridge, self.bus)
        setup_panel(self.dir_view, "mid", self.bridge, self.bus)
        setup_panel(self.detail_view, "detail", self.bridge, self.bus)
        setup_panel(self.rm_view, "rightmost", self.bridge, self.bus)

        # One class per role - each knows which buttons it carries, whether it
        # switches viewers or contents, and how it is tinted. See panel.py.
        self.p_left: Panel = LeftPanel(self.left_view)
        self.p_dir: Panel = DirPanel(self.dir_view)
        # p1 and p2 show a document either in their web view or in a Qt
        # viewer (qt_viewer.py); the host swaps between the two.
        self.p1_host = ViewerHost(self.detail_view,
                                  lambda p, n: self._on_qt_selected("p1", p, n),
                                  self._on_qt_failed)
        self.p2_host = ViewerHost(self.rm_view,
                                  lambda p, n: self._on_qt_selected("p2", p, n),
                                  self._on_qt_failed)

        self.p_right: Panel = DetailPanel(self.p1_host)
        self.p_rm: Panel = RightmostPanel(self.p2_host)

        self.p_left.wrap.setMinimumWidth(150)
        self.p_dir.wrap.setMinimumWidth(150)

        left_dir_split = QSplitter(Qt.Orientation.Horizontal)
        left_dir_split.addWidget(self.p_left.wrap)
        left_dir_split.addWidget(self.p_dir.wrap)

        right_split = QSplitter(Qt.Orientation.Horizontal)
        right_split.addWidget(self.p_right.wrap)
        right_split.addWidget(self.p_rm.wrap)

        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(left_dir_split)
        main_split.addWidget(right_split)

        # Widths are handed out in showEvent, not here - setSizes() before the
        # window has its final geometry only sets a ratio, and the window gets
        # resized twice on the way up (resize() here, then `set_window` from
        # config.t2l). What came out depended on that order: dir ended up at its
        # 150px minimum in one window and at a third of the width in another.
        self._left_dir_split = left_dir_split
        self._right_split = right_split
        self._main_split = main_split
        self._sized_once = False
        # Set once a saved layout has been restored - the startup shares must
        # not overwrite what the user left behind.
        self._size_locked = False

        # The paste strip is built by the left panel, which owns it - see
        # app_bar.AppBar. The window only wires it up, because what a paste
        # does (write a file, then open it in p1) is not the left panel's
        # business.
        self.app_bar = self.p_left.app_bar
        CmdsPaste.configure(self.bus, self.root)
        if self.app_bar is not None:
            CmdsPaste.set_saved_fn(self.app_bar.show_saved)
            self.app_bar.set_open_fn(self.bus.notify_file_selected)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(main_split)
        self.setCentralWidget(central)

        CmdsChroma.set_page(self.dir_view.page())
        CmdsChroma.set_detail_page(self.detail_view.page())
        CmdsChroma.set_rightmost_page(self.rm_view.page())
        CmdsChroma.set_detail_view(self.detail_view)
        CmdsChroma.set_rightmost_view(self.rm_view)
        CmdsChroma.set_window(self)
        CmdsChroma.set_hosts(self.p1_host, self.p2_host)

        self._wire_bus()

        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(50)
        self._drain_timer.timeout.connect(self._drain_cmd_queue)
        self._drain_timer.start()

        self._wire_left_panel_tabs()
        self._wire_dir_viewer_toggle()
        self._wire_infobar_clicks()
        self._wire_downloads()

        # p2 starts visible, like C++ ("□" = both shown). It used
        # to be hidden here from the days it was an empty www skeleton; now it
        # loads the same startup page as p1, so there is nothing to hide.
        self.p_right.hide_rightmost.setText("□")

        # Left starts collapsed - the log / bookmarks / dirs-upper tabs are a
        # look-something-up panel, not something you need in view all the time.
        # Startup state only; `panel_toggle left` (◧ button) pulls it back out
        # and works both ways from there.
        self.p_left.wrap.setVisible(False)
        self.p_dir.hide_parent.setText("◧")

        self._load_dir(self.start_dir)
        # _load_dir is called directly, not via the bus, so dirChanged never
        # fires at startup - without this the dir_up button keeps its default
        # style and tooltip until the user navigates. C++ calls refreshDirUp()
        # once right after wiring the same signal.
        self._refresh_dir_up()
        self._load_startup_detail()
        if self.start_file:
            self.bus.notify_file_selected(self.start_file)

        log_html = vr.find_viewer_html(self.root, self.root, "cmdlog")
        if os.path.isfile(log_html):
            self.bus.notify_panel_show("left", log_html, "")

    # Startup width shares of the whole window. dir is the file list - it needs
    # a readable width and no more; the two viewer panels take what is left.
    _INIT_LEFT_FRAC = 0.13
    _INIT_DIR_FRAC = 0.21
    _INIT_DIR_MIN = 240


    def _window_title(self) -> str:
        """`KOUMES <sandbox>` - nic vic.

        Sandbox je identita instance: pri vice bezicich koumesech je to jedina
        vec, podle ktere se v prepinaci oken poznaji. Aktualni adresar do
        titulku nepatri - meni se pri kazdem kroku a tim tu identitu rozmazava;
        kde jsi, rekne info bar.
        """
        if self._title_short:
            return "KOUMES"
        return f"KOUMES  {self.root}"

    _title_short = False

    def set_title_short(self, short: bool) -> None:
        """`title_toggle`: hide the sandbox path in the window title (screenshots),
        or bring it back. The stripe inside the window is not touched."""
        self._title_short = short
        self.setWindowTitle(self._window_title())

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        if self._sized_once:
            return
        self._sized_once = True
        self._apply_initial_sizes()
        # ...and once more once the window has stopped moving. `set_window` from
        # config.t2l lands through the command queue a few ticks after show and
        # resizes us; the splitter answers that by shrinking whatever it likes -
        # which used to squeeze dir down onto its 150px minimum.
        QTimer.singleShot(400, self._apply_initial_sizes)

    def _apply_initial_sizes(self) -> None:
        """Deal out panel widths once, on the first show."""
        if self._size_locked:
            return
        total = self._main_split.width()
        if total <= 0:
            return
        dir_w = max(self._INIT_DIR_MIN, int(total * self._INIT_DIR_FRAC))
        left_w = max(150, int(total * self._INIT_LEFT_FRAC))
        # A hidden left panel holds no width, but the splitter still needs a
        # number for it - that is what it gets back when the user toggles it on.
        left_dir_w = dir_w + (left_w if self.p_left.wrap.isVisible() else 0)
        rest = max(300, total - left_dir_w)
        self._left_dir_split.setSizes([left_w, dir_w])
        self._main_split.setSizes([left_dir_w, rest])
        self._right_split.setSizes([rest // 2, rest - rest // 2])

    # -- session state (WindowPersist) --------------------------------------
    def splitter_state(self) -> list:
        """Panel widths, left to right. A hidden panel reports 0.

        `isVisibleTo` rather than `isVisible`: this is read while the window is
        going down, and by then the window itself is hidden, which makes every
        `isVisible()` false. The first save wrote left and p2 as closed even
        though both were open.
        """
        left = self.p_left.wrap.width() if self.p_left.wrap.isVisibleTo(self) else 0
        rm = self.p_rm.wrap.width() if self.p_rm.wrap.isVisibleTo(self) else 0
        return [left, self.p_dir.wrap.width(), self.p_right.wrap.width(), rm]

    def ensure_panel_width(self, which: str) -> None:
        """Give a just-unhidden panel a share of the splitter.

        Hiding a panel and showing it again are two different things to a
        splitter: `setVisible(True)` puts the widget back, but if its slot was
        dragged (or restored) to zero, it comes back as a stripe zero pixels
        wide - visible, and still nothing to see. That is what "the panel does
        not come up" looks like from the outside. So when the slot is empty,
        halve the neighbour and hand it over.
        """
        split, idx = ((self._right_split, 1) if which == "p2"
                      else (self._left_dir_split, 0))
        sizes = split.sizes()
        if len(sizes) != 2 or sizes[idx] > 0:
            return
        total = sum(sizes) or split.width()
        if total <= 0:
            return
        half = max(1, total // 2)
        split.setSizes([total - half, half] if idx == 1 else [half, total - half])

    def restore_splitter(self, left: int, dir_w: int, p1: int, p2: int) -> None:
        self._size_locked = True
        # A panel saved at zero was hidden, not shrunk - restoring it as a
        # sliver would leave a stripe nobody can grab.
        self.p_left.wrap.setVisible(left > 0)
        self.p_dir.hide_parent.setText("□" if left > 0 else "◧")
        self.p_rm.wrap.setVisible(p2 > 0)
        self.p_right.hide_rightmost.setText("□" if p2 > 0 else "◨")
        self._left_dir_split.setSizes([left or 200, dir_w])
        self._main_split.setSizes([(left if left > 0 else 0) + dir_w, p1 + p2])
        self._right_split.setSizes([p1, p2])

    def panel_state(self) -> dict:
        """What each panel is showing - dir path, and file + viewer for p1/p2."""
        def viewer_of(target: str, file: str) -> str:
            if not target or not file:
                return ""
            return "native" if target == file else os.path.splitext(os.path.basename(target))[0]

        return {
            "active": CmdsChroma.active_panel(),
            "dir": CmdsChroma._last_dir,
            "p1": self._last_p1_file,
            "p1v": viewer_of(self._last_p1_html, self._last_p1_file),
            "p2": self._last_p2_file,
            "p2v": viewer_of(self._last_p2_html, self._last_p2_file),
        }

    def restore_panels(self, state: dict) -> None:
        """Put the panels back where they were. Anything gone is skipped."""
        d = state.get("dir", "")
        if d and os.path.isdir(d) and FsBridge.is_inside(d, self.root):
            self._load_dir(d)

        for panel, notify in (("p1", self.bus.notify_file_selected),
                              ("p2", self.bus.notify_file_selected_rightmost)):
            f = state.get(panel, "")
            if not f or not os.path.isfile(f):
                continue
            # Same rule as the dir above: a file outside this run's root is not
            # restored. It would render, but its viewer could not write, so it
            # came back as a half-working page instead of a sandbox boundary.
            if not FsBridge.is_inside(f, self.root):
                continue
            notify(f)
            viewer = state.get(panel + "v", "")
            # The switch handler is registered by the selection above, so this
            # order is the only one that works.
            fn = CmdsChroma._switch_fns.get(panel)
            if viewer and fn is not None:
                fn(viewer)

        # Last, so it is not undone by the two selections above.
        active = state.get("active", "")
        if active in ("p1", "p2"):
            CMD_SYS().execute_thread_safe(f"panel_active {active}", "ui", -1, "RESTORE")

    def _startup_html(self) -> str:
        """HTML shown in p1 / p2 before the user picks anything.

        C++ takes `help.html` co-located with the app's dirs HTML and falls back
        to that HTML itself (Main.cpp: `helpPath` / `detailInitHtml`). Same here,
        only the dirs HTML is resolved through the viewer walk-up instead of an
        argv path, so a project can shadow it from its own `.t2l/`.
        """
        dirs_html = vr.find_viewer_html(self.start_dir, self.root, "dirs")
        if dirs_html:
            co_located = os.path.join(os.path.dirname(dirs_html), "help.html")
            if os.path.isfile(co_located):
                return co_located
        return vr.find_viewer_html(self.start_dir, self.root, "help") or dirs_html

    def _load_startup_detail(self) -> None:
        """Give p1 and p2 initial content - port of the detailInitHtml block.

        Without this both right panels start blank until the user clicks a file.
        p1 is skipped when a start file was passed on the command line: that file
        is loaded a moment later anyway and the help page would only flash.
        """
        init_html = self._startup_html()
        if not init_html:
            return

        if not self.start_file:
            self._set_info_path(self.p_right.info_path, init_html)
            self._set_info_viewer(self.p_right.info_viewer, init_html, is_native=True)
            CmdsChroma.set_last_file(init_html)
            CmdsChroma.set_last_file_viewer("NATIVE")
            self._load_view_html(self.detail_view, init_html, "", "detail",
                                 start=self.start_dir)

        # p2 has no other startup source, so it always gets the page. C++ puts a
        # "(rightmost - www skeleton)" placeholder in its info bar; p2 is a real
        # viewer panel here (chroma_setfile --p2), so it shows the page like p1.
        self._set_info_path(self.p_rm.info_path, init_html)
        self._set_info_viewer(self.p_rm.info_viewer, init_html, is_native=True)
        self._load_view_html(self.rm_view, init_html, "", "rightmost",
                             start=self.start_dir)

    def _wire_downloads(self) -> None:
        """Accept what a page in a panel downloads, instead of dropping it.

        Without a handler on `downloadRequested` QtWebEngine cancels every
        download, so an HTML app whose "export" is a Blob + `<a download>` did
        nothing on click. The file goes where a paste goes - `exchange_dir`
        (`<root>/exchange` unless config says otherwise): the drop box between
        the user and the agents. Not next to the file shown in the panel - that can
        be a git repo or a private directory, and a download nobody looked at yet does
        not belong in either.

        Only the download itself is let through; localStorage and cookies stay
        off (see setup_panel).
        """
        self._downloads_pending: set[str] = set()
        seen = set()
        for view in (self.left_view, self.dir_view, self.detail_view, self.rm_view):
            prof = view.page().profile()
            if id(prof) in seen:
                continue
            seen.add(id(prof))
            prof.downloadRequested.connect(self._on_download)

    def _free_download_name(self, folder: str, name: str) -> str:
        # Never overwrite: `kalkulace.json`, then `kalkulace_1.json`, ...
        # Names of downloads still in flight count as taken too.
        base, ext = os.path.splitext(name)
        cand, n = name, 0
        while (os.path.exists(os.path.join(folder, cand))
               or os.path.join(folder, cand) in self._downloads_pending):
            n += 1
            cand = f"{base}_{n}{ext}"
        return cand

    def _on_download(self, req: QWebEngineDownloadRequest) -> None:
        folder = CmdsPaste.exchange_dir()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            req.cancel()
            return
        name = os.path.basename(req.downloadFileName() or "") or "download"
        name = self._free_download_name(folder, name)
        path = os.path.join(folder, name)
        self._downloads_pending.add(path)
        req.setDownloadDirectory(folder)
        req.setDownloadFileName(name)

        page = req.page()

        def finished() -> None:
            if not req.isFinished():
                return
            self._downloads_pending.discard(path)
            ok = req.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted
            if ok:
                # Same command a canvas export uses: it lands in the command
                # log and lights the paste status line.
                CMD_SYS().execute_thread_safe(f'export_saved "{path}"', "js", -1, "HTML")
            msg = (f"downloaded: {path}" if ok
                   else f"download failed: {name} ({req.interruptReasonString()})")
            self._flash_on_panel(page, msg)

        req.isFinishedChanged.connect(finished)
        req.accept()

    def _flash_on_panel(self, page, msg: str) -> None:
        """Short-lived note over the info bar of the panel `page` lives in.

        The paste status line sits in the left panel, which is collapsed most
        of the time; the note has to show up where the click was.
        """
        pairs = ((self.left_view, self.p_left), (self.dir_view, self.p_dir),
                 (self.detail_view, self.p_right), (self.rm_view, self.p_rm))
        panel = next((p for v, p in pairs if v.page() is page), self.p_right)
        bar = panel.info_bar
        QToolTip.showText(bar.mapToGlobal(bar.rect().bottomLeft()), msg, bar,
                          bar.rect(), 8000)

    def _wire_infobar_clicks(self) -> None:
        """The viewer row is an address: click it and that viewer lands in p1.

        `t2l.html` is a file like any other and has to be able to step into the
        file's place and be shown. The path row above it is deliberately left
        inert - it names the document the panel already displays. Port of the
        C++ wireClickToP1, which wired both rows.
        """
        def wire(label) -> None:
            def go(lbl=label) -> None:
                path = lbl.property("cmdPath")
                if not lbl.property("clickable") or not path:
                    return
                # Through CmdSys, so an info bar click reaches the cmdlog and
                # the bus like every other command - the same one an agent
                # would send over the socket.
                CMD_SYS().execute_thread_safe(
                    f'panel_show p1 "{path}"', "ui", -1, "INFOBAR")
            make_label_clickable(label, go)

        for panel in (self.p_left, self.p_dir, self.p_right, self.p_rm):
            wire(panel.info_viewer)

    def _wire_dir_viewer_toggle(self) -> None:
        """Mid panel custom/dflt buttons: switch dir viewer via CmdSys."""
        self.p_dir.dflt.clicked.connect(
            lambda _=False: CMD_SYS().execute_thread_safe(
                "viewer_switch dir dirs", "ui", -1, "TOOLBAR")
        )
        # Read the name off the button, not its face - a squeezed role bar
        # strips the text from everything but the active choice.
        self.p_dir.custom.clicked.connect(
            lambda _=False: CMD_SYS().execute_thread_safe(
                f"viewer_switch dir {button_label(self.p_dir.custom)}", "ui", -1, "TOOLBAR")
        )

    def _wire_left_panel_tabs(self) -> None:
        """LEFT panel = 4-way switch: bookmarks / dirs-upper / log / menu.

        The first three swap the page in the web view; menu raises the widget
        page behind it. Default stays on log - menu is somewhere you go to do
        a thing, not something you want in view all the time.
        """
        bm_html = vr.find_viewer_html(self.root, self.root, "bookmarks")
        dirs_html = vr.find_viewer_html(self.root, self.root, "dirs")
        log_html = vr.find_viewer_html(self.root, self.root, "cmdlog")

        pL = self.p_left
        pL.custom.setText("bookmarks")
        pL.dflt.setText("dirs-upper")
        pL.log.setText("log")
        pL.menu.setText("menu")
        pL.custom.setVisible(True)
        pL.dflt.setVisible(True)
        pL.log.setVisible(True)
        pL.menu.setVisible(True)
        pL.log.setChecked(True)

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

        pL.menu.setToolTip("Actions on the app, not on the file in view")

        # The three page tabs also have to lower the menu again, otherwise a
        # `panel_show left` would swap a page nobody can see.
        def show_page(_=False) -> None:
            if pL.stack is not None:
                pL.stack.setCurrentIndex(0)

        def show_menu(_=False) -> None:
            if pL.stack is not None:
                pL.stack.setCurrentIndex(1)

        for btn in (pL.custom, pL.dflt, pL.log):
            btn.clicked.connect(show_page)
        pL.menu.clicked.connect(show_menu)

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
        self.bus.lineChanged.connect(lambda n: self._on_qt_line(self.p1_host, n))
        self.bus.lineChangedRightmost.connect(lambda n: self._on_qt_line(self.p2_host, n))
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
        target = vr.find_viewer_target(os.path.dirname(file_path), self.root, viewer)
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
        if would_exit:
            self.p_dir.dir_up.setStyleSheet(icon_btn_qss("color: #f87171;"))
            self.p_dir.dir_up.setToolTip(f"Sandbox edge — click extends sandbox to {parent}")
        else:
            self.p_dir.dir_up.setStyleSheet(dir_up_qss())
            self.p_dir.dir_up.setToolTip(f"Dir up → {parent}")

    def _on_sandbox_changed(self, new_root: str) -> None:
        pass

    def set_active_panel(self, key: str) -> None:
        """Paint which document panel takes an unaddressed file.

        Called by the `panel_active` command, never directly by the chip - the
        chip fires the command like every other button, so the switch is logged
        and an agent sees it happen.
        """
        if key not in ("p1", "p2"):
            return
        self.p_right.role_bar.set_active(key == "p1")
        self.p_rm.role_bar.set_active(key == "p2")

    def _mark_viewer_button(self, bar, name: str) -> None:
        """Tick the viewer the panel really ended up with.

        The bar is built with the first choice ticked; when the file was opened
        *through* a named viewer, the tick has to follow, or the bar would say
        one thing and the panel show another.
        """
        for b in bar.findChildren(QPushButton):
            b.setChecked(button_label(b) == name)

    def _on_panel_show(self, panel: str, file: str, viewer: str) -> None:
        # Re-emit on the bus instead of calling the handlers directly, so every
        # listener sees the change (e.g. _refresh_dir_up, and the viewers' own
        # JS-side subscriptions) - not just this window's own handler.
        # Mirrors the C++ panelShow router. No loop: panelShow and
        # dirChanged / fileSelected are separate signals.
        if panel == "dir":
            if os.path.isdir(file):
                self.bus.notify_dir_change(file)
        elif panel in ("p1", "p2"):
            if not os.path.isfile(file):
                return
            if panel == "p1":
                self.bus.notify_file_selected(file)
                bar = self.p_right.viewer_bar
            else:
                self.bus.notify_file_selected_rightmost(file)
                bar = self.p_rm.viewer_bar
            if not viewer:
                return
            # The panel is loaded by now (the signal is direct), so its switch
            # function is registered and knows which file it is switching.
            fn = CmdsChroma._switch_fns.get(panel)
            if fn is not None:
                fn(viewer)
                self._mark_viewer_button(bar, viewer)
        elif panel == "left":
            # `panel_show left menu` is not a file - it raises the widget page.
            # A tab reachable only by clicking would be the one thing in this
            # app an agent cannot do, and the whole point is that both reach
            # for the same commands.
            if file == "menu":
                self._show_left_menu()
            else:
                self._show_left_html(file)

    def _show_left_menu(self) -> None:
        pL = self.p_left
        if pL.stack is None:
            return
        pL.stack.setCurrentIndex(1)
        pL.menu.setChecked(True)

    def _show_left_html(self, file: str) -> None:
        if not os.path.isfile(file):
            return
        # A page swap has to lower the menu, or it would load behind it.
        if self.p_left.stack is not None:
            self.p_left.stack.setCurrentIndex(0)
        url = QUrl.fromLocalFile(file)
        base = os.path.basename(file)
        info_path_file = file
        self._left_load_ctr = getattr(self, "_left_load_ctr", 0) + 1
        # A viewer is `<name>.exe.html`, or `<name>.html` in a tree written
        # before that; both answer to the same name.
        stem = base.split(".")[0]
        if stem == "cmdlog":
            info_path_file = os.path.join(AppPaths.inst().dir_config(), "cmdlog.txt")
            q = f"role=parent&file={info_path_file}&_ts={self._left_load_ctr}"
        elif stem == "bookmarks":
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

        # A preselect belongs to one listing: it is the entry marked *in* this
        # directory. Stepping into a folder leaves it behind - and the one that
        # was left behind is usually the folder just entered, which would then
        # sit in the info row repeating the row's own last element. Drop
        # anything that does not live in the new listing.
        pre = str(CmdsChroma._preselects.get("dir", "") or "")
        if pre and os.path.dirname(os.path.normpath(pre)) != os.path.normpath(path):
            CmdsChroma._preselects.pop("dir", None)

        custom_viewer = vr.read_viewer_name(path)

        self.p_dir.custom.setVisible(bool(custom_viewer))
        self.p_dir.dflt.setVisible(bool(custom_viewer))
        if custom_viewer:
            self.p_dir.custom.setText(custom_viewer)
            self.p_dir.custom.setToolTip(f"viewer_switch dir {custom_viewer}")
            self.p_dir.dflt.setToolTip("viewer_switch dir dirs")

        root = self.bridge.allowed_dir_
        target_html = ""
        mode = "default"
        if custom_viewer:
            target_html = vr.find_viewer_html(path, root, custom_viewer)
            if target_html:
                mode = "custom"
        if not target_html:
            target_html = vr.find_viewer_html(path, root, "dirs")

        self._set_info_path(self.p_dir.info_path, path)
        if target_html:
            self._set_info_viewer(self.p_dir.info_viewer, target_html, is_native=False)
        else:
            self._set_info_viewer(self.p_dir.info_viewer, "", is_native=True)
            self.p_dir.info_viewer.setText("native")
        CmdsChroma.set_last_dir_viewer(target_html)

        parent_dir = os.path.dirname(path) or path
        self._set_info_path(self.p_left.info_path, parent_dir)

        if target_html:
            # Reload only when the VIEWER changes, not on every dir change.
            # Navigating between two dirs that share dirs.html keeps the same
            # page alive - dirs.html re-renders itself from bus.dirChanged on
            # the JS side. A full setUrl here would flash the panel and throw
            # away its scroll position on every step. Port of the C++
            # `if (*lastMidHtml == targetHtml) return;` guard.
            if self._last_dir_html != target_html:
                self._last_dir_html = target_html
                if mode == "custom":
                    self.p_dir.custom.setChecked(True)
                    self.p_dir.dflt.setChecked(False)
                else:
                    self.p_dir.dflt.setChecked(True)
                    self.p_dir.custom.setChecked(False)

                url = QUrl.fromLocalFile(target_html)
                key = "dir" if mode == "custom" else "start"
                url.setQuery(f"role=mid&{key}={path}")
                self.dir_view.setUrl(url)
        else:
            # No viewer anywhere in the walk-up: hand the raw dir to Chromium.
            # The URL *is* the path here, so every dir change must reload, and
            # the guard has to be cleared or a later viewer load would be skipped.
            self._last_dir_html = ""
            self.dir_view.setUrl(QUrl.fromLocalFile(path))


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
            self.dir_view.setUrl(url)

        CmdsChroma.set_viewer_switch_fn("dir", switch_fn)


    def _sync_copy_btn(self, label, visible: bool, line_visible: bool = False) -> None:
        # Labels that carry no path:line button simply have no such property,
        # so the second key is a no-op for them.
        for key, vis in (("copyBtn", visible), ("copyBtnLine", line_visible)):
            btn = label.property(key)
            if btn is not None:
                btn.setVisible(vis)

    # Which panel each path label belongs to, so the row can pick up the
    # selected line as well as the path. The left panel is not in the table -
    # it has no selection of its own.
    def _panel_of_info_path(self, label) -> str:
        for panel, p in (("dir", self.p_dir), ("p1", self.p_right),
                         ("p2", self.p_rm)):
            if p.info_path is label:
                return panel
        return ""

    def _set_info_path(self, label, abs_path: str) -> None:
        # One row now says what two used to. The bracket holds whatever counts
        # as "picked" in this panel: a position inside a document, or the entry
        # marked in a directory listing. The second copy button hands out the
        # addressable form of that same thing.
        panel = self._panel_of_info_path(label)
        if panel == "dir":
            # A directory has no line. What is selected in it is an entry, and
            # its bare name is enough on a row that already shows the folder.
            pre = str(CmdsChroma._preselects.get("dir", "") or "")
            # Same reason as in FsBridge: what is gone is not marked.
            if pre and not os.path.exists(pre):
                pre = ""
                CmdsChroma._preselects.pop("dir", None)
            tag = os.path.basename(pre)
            addressable = pre
        else:
            sel = CmdsChroma._sel_for(panel) if panel else None
            # The position belongs to the file it was picked in. A row just
            # handed a different file must not keep the previous one's.
            line = sel.line if sel is not None and sel.file == abs_path else 0
            tag = str(line) if line else ""
            addressable = f"{abs_path}:{line}" if line else ""

        short = _path_from_index(abs_path, self.root)
        label.setText(f"{short} [{tag}]" if tag else short)
        label.setToolTip(abs_path)
        label.setProperty("cmdPath", abs_path)
        label.setProperty("cmdPathLine", addressable)
        outside = _is_outside_sandbox(abs_path, self.root)
        base = "#f87171" if outside else "#f9fafb"
        # The path row never leads anywhere: it names what the panel is already
        # showing, so opening it would be opening what is open.
        set_label_clickable(label, False)
        label.setStyleSheet("QLabel { color: %s; font-weight: 700; }" % base)
        self._sync_copy_btn(label, bool(abs_path), bool(addressable))

    def _on_dir_changed(self, path: str) -> None:
        if path == CmdsChroma._last_dir:
            return
        self._load_dir(path)

    def _load_view_html(self, view: QWebEngineView, target: str, file: str,
                         role: str, line: int = 0, start: str = "") -> None:
        # Query is built the same way for a viewer HTML and for a native load
        # (target == file) - matches C++ loadDetail / loadRightmost, which never
        # branch on native either.
        host = {self.detail_view: self.p1_host, self.rm_view: self.p2_host}.get(view)
        if host is not None:
            if is_qt_target(target):
                # The page behind the Qt viewer would keep listening on the bus
                # and answer chroma_setline with a line of its own - empty it.
                view.setUrl(QUrl("about:blank"))
                host.show_qt(target[len(QT_PREFIX):], file, line)
                return
            host.show_web()
        url = QUrl.fromLocalFile(target)
        q = f"role={role}"
        if start:
            # Startup loads have no file yet, only the dir the app opened on -
            # same pair (role, start) C++ setupPanel_ puts on every panel URL.
            q += f"&start={start}"
        if file:
            q += f"&file={file}"
        if line > 0:
            q += f"&line={line}"
        if role == "rightmost":
            # Cache-buster: p2 reloads the same file repeatedly via
            # `chroma_setfile <path> --p2` and would otherwise be served the
            # cached page. C++ does the same with rmLoadCtr.
            self._rm_load_ctr = getattr(self, "_rm_load_ctr", 0) + 1
            q += f"&_ts={self._rm_load_ctr}"
        url.setQuery(q)
        view.setUrl(url)

    def _reload_dir(self) -> None:
        """Refresh the dir panel where it stands, not where it was opened.

        The panel's URL carries the dir it was loaded with (`?start=…`) and is
        then deliberately left alone: walking the tree only moves the JS side
        over the bus, so the page is not thrown away on every step. A plain
        `reload()` therefore serves that first dir again and the panel jumps
        back to the sandbox root. Rebuild the query from the dir the panel is
        actually on. `_ts` is the same cache-buster the rightmost panel uses -
        without it the identical URL comes back from cache and nothing moves.
        """
        path = CmdsChroma._last_dir
        if not path or not CmdsChroma._last_dir_viewer:
            self.dir_view.reload()   # native listing: the URL *is* the dir
            return
        url = self.dir_view.url()
        key = "dir" if "dir=" in url.query() else "start"
        self._dir_load_ctr = getattr(self, "_dir_load_ctr", 0) + 1
        url.setQuery(f"role=mid&{key}={path}&_ts={self._dir_load_ctr}")
        self.dir_view.setUrl(url)

    def _on_qt_selected(self, panel: str, path: str, record_no: int) -> None:
        """A Qt viewer picked a record - same effect as an HTML viewer calling
        fs.setSelectedFile / fs.setSelectedLine, so chroma_file and
        chroma_line answer it."""
        self.bridge.setSelectedFile(path)
        self.bridge.setSelectedLine(record_no)

    def _on_qt_line(self, host: ViewerHost, record_no: int) -> None:
        """chroma_setline into a Qt viewer. An HTML viewer publishes the line it
        was moved to; select() must not emit, so the line is published here."""
        if host.is_qt():
            host.select(record_no)
            self.bridge.setSelectedLine(record_no)

    def _on_qt_failed(self, msg: str) -> None:
        # The error is on screen in the panel; the viewer bar still offers txt.
        print(msg, file=sys.stderr)

    def _set_info_viewer(self, label, target: str, is_native: bool) -> None:
        if is_qt_target(target):
            # A Qt viewer has no HTML to step into; the tooltip says where its
            # code is (deployment config.t2l, `qt_viewer:`).
            file_, cls = qt_registry().get(target[len(QT_PREFIX):], ("", ""))
            label.setText(target)
            label.setToolTip(f"{file_}:{cls}")
            label.setProperty("cmdPath", file_)
            set_label_clickable(label, False)
            label.setStyleSheet("QLabel { color: #9ca3af; }" + HOVER_QSS)
            self._sync_copy_btn(label, bool(file_))
            return
        if is_native:
            label.setText("NATIVE")
            label.setToolTip("")
            label.setProperty("cmdPath", "")
        else:
            label.setText(_path_from_index(target, self.root))
            label.setToolTip(target)
            label.setProperty("cmdPath", target)
        # The viewer is a file like any other and has to be able to step into
        # the file's place and be shown. NATIVE names no separate file - the
        # document renders itself - so there is nothing to open.
        set_label_clickable(label, not is_native and os.path.isfile(target))
        label.setStyleSheet("QLabel { color: #9ca3af; }" + HOVER_QSS)
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
            target = f if viewer == "native" else vr.find_viewer_target(file_dir, self.root, viewer)
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
            target = f if viewer == "native" else vr.find_viewer_target(file_dir, self.root, viewer)
            if not target:
                return
            self._last_p2_html = ""
            load_fn(target, f)

        CmdsChroma.set_viewer_switch_fn("p2", switch_fn)
        rebuild_viewer_bar(self.p_rm.viewer_bar, path, self.root, load_fn, "", "p2")

    def _on_www_url_requested(self, url: QUrl, source: str) -> None:
        """A link leaves koumes - the panels show documents, not the web.

        There used to be a www tab next to the document; a browser inside a
        400px panel was worse at being a browser than the one the user already
        has. The URL goes out to the system default and the panel keeps the
        document it was showing.
        """
        subprocess.Popen(["xdg-open", url.toString()])

    def _on_selection_changed(self, panel: str, file: str, line: int) -> None:
        label = path_label = None
        if panel == "dir":
            label, path_label = self.p_dir.info_selection, self.p_dir.info_path
        elif panel == "p1":
            label, path_label = self.p_right.info_selection, self.p_right.info_path
        elif panel == "p2":
            label, path_label = self.p_rm.info_selection, self.p_rm.info_path
        if label is None:
            return

        # The path row carries the picked position too, so it has to be redrawn
        # here. In a document panel the selection is only about that row when it
        # names the file the row is showing; in the dir panel the selection is a
        # preselected entry, which the row reports whatever it points at.
        if path_label is not None:
            shown = str(path_label.property("cmdPath") or "")
            if shown and (panel == "dir" or shown == file):
                self._set_info_path(path_label, shown)

        # Selection == the panel's own current dir/file with no line is redundant
        # (info_path already shows it) -> clear the row instead of duplicating.
        sel = CmdsChroma._sel_for(panel)
        if sel is not None and line == 0 and file == sel.file:
            label.setText("")
            label.setToolTip("")
            label.setProperty("cmdPath", "")
            label.setProperty("cmdPathLine", "")
            self._sync_copy_btn(label, False)
            return

        short = _path_from_index(file, self.root) if file else ""
        # Brackets, not a colon: this row repeats info_path and the position is
        # the only thing it adds, so the eye can find it without a colour of
        # its own. The copy button hands out the colon form for pasting.
        text = f"{short} [{line}]" if line else short
        label.setText(text)
        label.setToolTip(file)
        label.setProperty("cmdPath", file)
        # Second copy button hands out the addressable form; without a line
        # there is nothing to add and the button stays hidden.
        label.setProperty("cmdPathLine", f"{file}:{line}" if line else "")
        outside = _is_outside_sandbox(file, self.root)
        label.setStyleSheet(
            ("QLabel { color: #f87171; font-weight: 400; }" if outside
             else "QLabel { color: #9ca3af; font-weight: 400; }")
        )
        self._sync_copy_btn(label, bool(file), bool(file) and line > 0)
