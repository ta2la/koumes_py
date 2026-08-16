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
"""Cmds_chroma - CmdSys commands specific to the chroma UI.

Python port of APPS/AI_T2LS/Cmds_chroma.h.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from PyQt6.QtCore import QEventLoop
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

from cmd_sys import CMD_SYS
from .fs_bridge import FsBridge
from .panel_bus import PanelBus


@dataclass
class PanelSel:
    file: str = ""
    line: int = 0


class CmdsChroma:
    _page: Optional[QWebEnginePage] = None
    _detail_page: Optional[QWebEnginePage] = None
    _rightmost_page: Optional[QWebEnginePage] = None
    _detail_view: Optional[QWebEngineView] = None
    _rightmost_view: Optional[QWebEngineView] = None

    _last_dir: str = ""
    _last_file: str = ""
    _last_dir_viewer: str = ""
    _last_file_viewer: str = ""

    _bus: Optional[PanelBus] = None

    _sel_dir = PanelSel()
    _sel_p1 = PanelSel()
    _sel_p2 = PanelSel()

    _switch_fns: Dict[str, Callable[[str], None]] = {}
    _reload_fns: Dict[str, Callable[[], None]] = {}
    _toggle_fns: Dict[str, Callable[[], None]] = {}
    _tab_toggle_fns: Dict[str, Callable[[], None]] = {}
    _preselects: Dict[str, str] = {}

    @classmethod
    def set_page(cls, p: QWebEnginePage) -> None:
        cls._page = p

    @classmethod
    def set_detail_page(cls, p: QWebEnginePage) -> None:
        cls._detail_page = p

    @classmethod
    def set_rightmost_page(cls, p: QWebEnginePage) -> None:
        cls._rightmost_page = p

    @classmethod
    def set_detail_view(cls, v: QWebEngineView) -> None:
        cls._detail_view = v

    @classmethod
    def set_rightmost_view(cls, v: QWebEngineView) -> None:
        cls._rightmost_view = v

    @classmethod
    def set_bus(cls, b: PanelBus) -> None:
        cls._bus = b

    @classmethod
    def set_last_dir(cls, p: str) -> None:
        cls._last_dir = p

    @classmethod
    def set_last_file(cls, p: str) -> None:
        cls._last_file = p

    @classmethod
    def set_last_dir_viewer(cls, p: str) -> None:
        cls._last_dir_viewer = p

    @classmethod
    def set_last_file_viewer(cls, p: str) -> None:
        cls._last_file_viewer = p

    @classmethod
    def set_viewer_switch_fn(cls, panel: str, fn: Callable[[str], None]) -> None:
        cls._switch_fns[panel] = fn

    @classmethod
    def set_reload_fn(cls, panel: str, fn: Callable[[], None]) -> None:
        cls._reload_fns[panel] = fn

    @classmethod
    def set_toggle_fn(cls, panel: str, fn: Callable[[], None]) -> None:
        cls._toggle_fns[panel] = fn

    @classmethod
    def set_tab_toggle_fn(cls, panel: str, fn: Callable[[], None]) -> None:
        cls._tab_toggle_fns[panel] = fn

    @classmethod
    def _sel_for(cls, p: str) -> Optional[PanelSel]:
        if p == "dir":
            return cls._sel_dir
        if p == "p1":
            return cls._sel_p1
        if p == "p2":
            return cls._sel_p2
        return None

    @classmethod
    def set_sel_file(cls, panel: str, file: str) -> None:
        s = cls._sel_for(panel)
        if s is None:
            return
        s.file = file
        s.line = 0
        if cls._bus is not None:
            cls._bus.notify_selection_changed(panel, file, 0)

    @classmethod
    def _target_page(cls, args) -> Optional[QWebEnginePage]:
        return cls._rightmost_page if args.get_arg("p2") is not None else cls._detail_page

    @classmethod
    def _target_view(cls, args) -> Optional[QWebEngineView]:
        return cls._rightmost_view if args.get_arg("p2") is not None else cls._detail_view

    @staticmethod
    def _page_to_html_sync(page: QWebEnginePage) -> str:
        result = [""]
        loop = QEventLoop()

        def cb(s: str) -> None:
            result[0] = s
            loop.quit()

        page.toHtml(cb)
        loop.exec()
        return result[0]

    @staticmethod
    def _page_to_text_sync(page: QWebEnginePage) -> str:
        result = [""]
        loop = QEventLoop()

        def cb(s: str) -> None:
            result[0] = s
            loop.quit()

        page.toPlainText(cb)
        loop.exec()
        return result[0]

    @classmethod
    def register_cmds(cls) -> None:
        sys_ = CMD_SYS()

        def select(args, data, ctx):
            if args.count() < 3:
                return args.append_error("select: usage: select <dir|p1|p2> <line>")
            panel = args.get(1).value
            s = cls._sel_for(panel)
            if s is None:
                return args.append_error("select: panel must be dir|p1|p2")
            line = int(args.get(2).value or 0)
            s.line = line
            if cls._bus is not None:
                cls._bus.notify_selection_changed(panel, s.file, line)
            args.append(f"{s.file}:{line}", "SEL")
            return 0
        sys_.add("select", select, category="chroma")

        def show(args, data, ctx):
            if args.count() < 2:
                return args.append_error("show: usage: show <dir|p1|p2>")
            panel = args.get(1).value
            s = cls._sel_for(panel)
            if s is None:
                return args.append_error("show: panel must be dir|p1|p2")
            if cls._bus is None:
                return args.append_error("show: bus not set")
            if s.line > 0:
                cls._bus.notify_line_changed(s.line)
                args.append(f"line {s.line}", "SHOW")
            elif s.file:
                cls._bus.notify_file_selected(s.file)
                args.append(s.file, "SHOW")
            return 0
        sys_.add("show", show, category="chroma")

        def get_selection(args, data, ctx):
            if args.count() < 2:
                return args.append_error("get_selection: usage: get_selection <panel>")
            panel = args.get(1).value
            s = cls._sel_for(panel)
            if s is None:
                return args.append_error("get_selection: panel must be dir|p1|p2")
            args.append(f"{s.file}:{s.line}", "SEL")
            return 0
        sys_.add("get_selection", get_selection, category="chroma")

        def preselect(args, data, ctx):
            if args.count() < 3:
                return args.append_error("preselect: usage: preselect <panel> <path>")
            panel = args.get(1).value
            path = args.get(2).value
            cls._preselects[panel] = path
            if cls._bus is not None:
                cls._bus.notify_selection_changed(panel, path, 0)
            args.append(f"{panel} {path}", "PRE")
            return 0
        sys_.add("preselect", preselect, category="chroma")

        def panel_show(args, data, ctx):
            if args.count() < 3:
                return args.append_error("panel_show: usage: panel_show <left|dir|p1|p2> <file> [<viewer>]")
            panel = args.get(1).value
            file = args.get(2).value
            viewer = args.get(3).value if args.count() >= 4 else ""
            if panel not in ("left", "dir", "p1", "p2"):
                return args.append_error("panel_show: panel must be left|dir|p1|p2")
            if cls._bus is None:
                return args.append_error("panel_show: bus not set")
            cls._bus.notify_panel_show(panel, file, viewer)
            tail = f" [{viewer}]" if viewer else ""
            args.append(f"{panel} {file}{tail}", "SHOW")
            return 0
        sys_.add("panel_show", panel_show, category="chroma")

        def tab_toggle(args, data, ctx):
            if args.count() < 2:
                return args.append_error("tab_toggle: usage: tab_toggle <p1|p2>")
            panel = args.get(1).value
            fn = cls._tab_toggle_fns.get(panel)
            if fn is None:
                return args.append_error(f"tab_toggle: no handler for panel {panel}")
            fn()
            args.append(panel, "TABBED")
            return 0
        sys_.add("tab_toggle", tab_toggle, category="chroma")

        def panel_toggle(args, data, ctx):
            if args.count() < 2:
                return args.append_error("panel_toggle: usage: panel_toggle <left|p2>")
            panel = args.get(1).value
            fn = cls._toggle_fns.get(panel)
            if fn is None:
                return args.append_error(f"panel_toggle: no handler for panel {panel}")
            fn()
            args.append(panel, "TOGGLED")
            return 0
        sys_.add("panel_toggle", panel_toggle, category="chroma")

        def panel_reload(args, data, ctx):
            if args.count() < 2:
                return args.append_error("panel_reload: usage: panel_reload <left|dir|p1|p2>")
            panel = args.get(1).value
            fn = cls._reload_fns.get(panel)
            if fn is None:
                return args.append_error(f"panel_reload: no handler for panel {panel}")
            fn()
            args.append(panel, "RELOADED")
            return 0
        sys_.add("panel_reload", panel_reload, category="chroma")

        def viewer_switch(args, data, ctx):
            if args.count() < 3:
                return args.append_error("viewer_switch: usage: viewer_switch <panel> <viewer>")
            panel = args.get(1).value
            viewer = args.get(2).value
            fn = cls._switch_fns.get(panel)
            if fn is None:
                return args.append_error(f"viewer_switch: no handler for panel {panel}")
            fn(viewer)
            args.append(f"{panel} {viewer}", "SWITCH")
            return 0
        sys_.add("viewer_switch", viewer_switch, category="chroma")

        for panel, sel in (("dir", cls._sel_dir), ("p1", cls._sel_p1), ("p2", cls._sel_p2)):
            def make_file(sel_=sel):
                def h(args, data, ctx):
                    args.append(sel_.file, "VALUE")
                    return 0
                return h

            def make_line(sel_=sel):
                def h(args, data, ctx):
                    args.append(str(sel_.line), "VALUE")
                    return 0
                return h

            def make_pre(panel_=panel):
                def h(args, data, ctx):
                    args.append(cls._preselects.get(panel_, ""), "VALUE")
                    return 0
                return h

            sys_.add(f"{panel}_file", make_file(), category="chroma")
            sys_.add(f"{panel}_line", make_line(), category="chroma")
            sys_.add(f"{panel}_preselect", make_pre(), category="chroma")

        def chroma_selection(args, data, ctx):
            fs = FsBridge.inst()
            if fs is None:
                return args.append_error("chroma_selection: FsBridge not initialised")
            args.append(fs.current_selection(), "SELECTION")
            return 0
        sys_.add("chroma_selection", chroma_selection, category="chroma")

        def chroma_dir(args, data, ctx):
            fs = FsBridge.inst()
            sel = fs.current_selected_dir() if fs else ""
            args.append(sel or cls._last_dir, "DIR")
            return 0
        sys_.add("chroma_dir", chroma_dir, category="chroma")

        def chroma_file(args, data, ctx):
            fs = FsBridge.inst()
            sel = fs.current_selected_file() if fs else ""
            args.append(sel or cls._last_file, "FILE")
            return 0
        sys_.add("chroma_file", chroma_file, category="chroma")

        def chroma_line(args, data, ctx):
            fs = FsBridge.inst()
            n = fs.current_selected_line() if fs else 0
            args.append(str(n), "LINE")
            return 0
        sys_.add("chroma_line", chroma_line, category="chroma")

        def debug_follow(args, data, ctx):
            fs = FsBridge.inst()
            if fs is None:
                return args.append_error("debug_follow: FsBridge not initialised")
            if args.count() < 2:
                return args.append_error("debug_follow: usage <id> [--start <path>]")
            id_ = args.get(1).value
            a_start = args.get_arg("start")
            start = a_start.value if a_start else ""
            if not start:
                start = fs.current_selected_file()
            if not start:
                start = cls._last_file
            fs.followLink(id_, start)
            args.append(fs.last_follow_log(), "LOG")
            return 0
        sys_.add("debug_follow", debug_follow, category="chroma")

        def debug_follow_log(args, data, ctx):
            fs = FsBridge.inst()
            if fs is None:
                return args.append_error("debug_follow_log: FsBridge not initialised")
            args.append(fs.last_follow_log(), "LOG")
            return 0
        sys_.add("debug_follow_log", debug_follow_log, category="chroma")

        def chroma_dir_viewer(args, data, ctx):
            args.append(cls._last_dir_viewer, "VIEWER")
            return 0
        sys_.add("chroma_dir_viewer", chroma_dir_viewer, category="chroma")

        def chroma_file_viewer(args, data, ctx):
            args.append(cls._last_file_viewer, "VIEWER")
            return 0
        sys_.add("chroma_file_viewer", chroma_file_viewer, category="chroma")

        def chroma_setdir(args, data, ctx):
            if args.count() < 2:
                return args.append_error("chroma_setdir: usage <path>")
            if cls._bus is None:
                return args.append_error("chroma_setdir: bus not set")
            path = args.get(1).value
            if not path:
                return args.append_error("chroma_setdir: empty path")
            cls._bus.notify_dir_change(path)
            args.append(path, "DIR")
            return 0
        sys_.add("chroma_setdir", chroma_setdir, category="chroma")

        def chroma_setfile(args, data, ctx):
            if args.count() < 2:
                return args.append_error("chroma_setfile: usage <path> [--p2]")
            if cls._bus is None:
                return args.append_error("chroma_setfile: bus not set")
            path = args.get(1).value
            if not path:
                return args.append_error("chroma_setfile: empty path")
            to_p2 = args.get_arg("p2") is not None
            if to_p2:
                cls._bus.notify_file_selected_rightmost(path)
            else:
                cls._bus.notify_file_selected(path)
            args.append(path, "FILE")
            args.append("p2" if to_p2 else "detail", "PANEL")
            return 0
        sys_.add("chroma_setfile", chroma_setfile, category="chroma")

        def chroma_setline(args, data, ctx):
            if args.count() < 2:
                return args.append_error("chroma_setline: usage <line>")
            if cls._bus is None:
                return args.append_error("chroma_setline: bus not set")
            try:
                line = int(args.get(1).value)
            except ValueError:
                return args.append_error("chroma_setline: line must be integer")
            if line < 1:
                return args.append_error("chroma_setline: line must be >= 1")
            cls._bus.notify_line_changed(line)
            args.append(str(line), "LINE")
            return 0
        sys_.add("chroma_setline", chroma_setline, category="chroma")

        def chroma_html(args, data, ctx):
            p = cls._target_page(args)
            if p is None:
                return args.append_error("chroma_html: target page not set")
            args.append(cls._page_to_html_sync(p), "HTML")
            return 0
        sys_.add("chroma_html", chroma_html, category="chroma")

        def chroma_text(args, data, ctx):
            p = cls._target_page(args)
            if p is None:
                return args.append_error("chroma_text: target page not set")
            args.append(cls._page_to_text_sync(p), "TEXT")
            return 0
        sys_.add("chroma_text", chroma_text, category="chroma")

        def chroma_screenshot(args, data, ctx):
            if args.count() < 2:
                return args.append_error("chroma_screenshot: usage <path> [--p2]")
            v = cls._target_view(args)
            if v is None:
                return args.append_error("chroma_screenshot: target view not set")
            path = args.get(1).value
            px = v.grab()
            if not px.save(path, "PNG"):
                return args.append_error("chroma_screenshot: save failed")
            args.append(path, "PATH")
            return 0
        sys_.add("chroma_screenshot", chroma_screenshot, category="chroma")

        def _widen_if_needed(parent: str) -> bool:
            fs = FsBridge.inst()
            if fs is None:
                return True
            if fs.is_inside(parent, fs.allowed_dir_):
                return True
            if not fs.set_allowed_root(parent):
                return False
            if cls._bus is not None:
                cls._bus.notify_sandbox_changed(fs.allowed_dir_)
            return True

        def dir_up(args, data, ctx):
            d = cls._last_dir
            if not d:
                return args.append_error("dir_up: no dir yet")
            parent = os.path.dirname(os.path.abspath(d))
            if not parent or parent == d:
                return args.append_error("dir_up: already at root")
            if cls._bus is None:
                return args.append_error("dir_up: bus not set")
            if not _widen_if_needed(parent):
                return args.append_error(f"dir_up: cannot widen sandbox to {parent}")
            cls._bus.notify_dir_change(parent)
            args.append(parent, "DIR")
            return 0
        sys_.add("dir_up", dir_up, category="chroma")

        def reveal_dir(args, data, ctx):
            f = cls._last_file
            if not f:
                return args.append_error("reveal_dir: no file in p1")
            parent = os.path.dirname(os.path.abspath(f))
            if not parent:
                return args.append_error("reveal_dir: no parent")
            if cls._bus is None:
                return args.append_error("reveal_dir: bus not set")
            if not _widen_if_needed(parent):
                return args.append_error(f"reveal_dir: cannot widen sandbox to {parent}")
            cls._bus.notify_dir_change(parent)
            args.append(parent, "DIR")
            return 0
        sys_.add("reveal_dir", reveal_dir, category="chroma")

        def chroma_openfm(args, data, ctx):
            d = cls._last_dir
            if not d:
                return args.append_error("chroma_openfm: no dir yet")
            subprocess.Popen(["xdg-open", d])
            args.append(d, "OPENED")
            return 0
        sys_.add("chroma_openfm", chroma_openfm, category="chroma")

        def open_extern(args, data, ctx):
            if args.count() < 2:
                return args.append_error("open_extern: usage: open_extern <target>")
            t = args.get(1).value
            is_url = t.startswith("http://") or t.startswith("https://")
            if is_url:
                subprocess.Popen(["google-chrome", t])
            else:
                subprocess.Popen(["xdg-open", t])
            args.append(t, "URL" if is_url else "FILE")
            return 0
        sys_.add("open_extern", open_extern, category="chroma")

        def chroma_reload(args, data, ctx):
            p = cls._page
            if p is None:
                return args.append_error("chroma_reload: page not set")
            p.triggerAction(QWebEnginePage.WebAction.Reload)
            return 0
        sys_.add("chroma_reload", chroma_reload, category="chroma")

        def chroma_reload_detail(args, data, ctx):
            p = cls._detail_page
            if p is None:
                return args.append_error("chroma_reload_detail: detail page not set")
            p.triggerAction(QWebEnginePage.WebAction.Reload)
            return 0
        sys_.add("chroma_reload_detail", chroma_reload_detail, category="chroma")

        _JS_STYLE = r"""
            (function () {
                var s = window.getSelection();
                if (!s || !s.rangeCount) return;
                var r = s.getRangeAt(0);
                if (r.collapsed) return;
                var span = document.createElement('span');
                span.setAttribute('style', '%s');
                try { r.surroundContents(span); }
                catch (e) {
                    var frag = r.extractContents();
                    span.appendChild(frag);
                    r.insertNode(span);
                }
            })();
        """

        _JS_UNWRAP = r"""
            (function () {
                var s = window.getSelection();
                if (!s || !s.rangeCount) return;
                var node = s.getRangeAt(0).commonAncestorContainer;
                if (node && node.nodeType === 3) node = node.parentElement;
                var span = null;
                for (var n = node; n; n = n.parentElement) {
                    if (n.tagName === 'SPAN') { span = n; break; }
                }
                if (!span) return;
                var parent = span.parentNode;
                while (span.firstChild) parent.insertBefore(span.firstChild, span);
                parent.removeChild(span);
                parent.normalize();
            })();
        """

        _JS_CLASS = r"""
            (function () {
                var s = window.getSelection();
                if (!s || !s.rangeCount) return;
                var r = s.getRangeAt(0);
                if (r.collapsed) return;
                var span = document.createElement('span');
                span.setAttribute('class', '%s');
                try { r.surroundContents(span); }
                catch (e) {
                    var frag = r.extractContents();
                    span.appendChild(frag);
                    r.insertNode(span);
                }
            })();
        """

        def chroma_style(args, data, ctx):
            p = cls._page
            if p is None:
                return args.append_error("chroma_style: page not set")
            if args.count() < 2:
                return args.append_error("chroma_style: usage <css>")
            css = args.get(1).value
            if not css:
                return args.append_error("chroma_style: missing css arg")
            esc = css.replace("\\", "\\\\").replace("'", "\\'")
            p.runJavaScript(_JS_STYLE % esc)
            return 0
        sys_.add("chroma_style", chroma_style, category="chroma")

        def chroma_unwrap(args, data, ctx):
            p = cls._page
            if p is None:
                return args.append_error("chroma_unwrap: page not set")
            p.runJavaScript(_JS_UNWRAP)
            return 0
        sys_.add("chroma_unwrap", chroma_unwrap, category="chroma")

        def chroma_class(args, data, ctx):
            p = cls._page
            if p is None:
                return args.append_error("chroma_class: page not set")
            if args.count() < 2:
                return args.append_error("chroma_class: usage <className>")
            c = args.get(1).value
            if not c:
                return args.append_error("chroma_class: missing class arg")
            esc = c.replace("\\", "\\\\").replace("'", "\\'")
            p.runJavaScript(_JS_CLASS % esc)
            return 0
        sys_.add("chroma_class", chroma_class, category="chroma")
