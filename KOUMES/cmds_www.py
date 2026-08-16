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
"""Cmds_www - CmdSys commands for the WWW (external web) panels.

Python port of APPS/AI_T2LS/Cmds_www.h.

All commands accept an optional --panel arg (default "right"). Panel names:
"detail" / "d" -> detail www view; "right" / "r" -> rightmost www view.
"""

from typing import Optional

from PyQt6.QtCore import QEventLoop, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

from cmd_sys import CMD_SYS


class CmdsWww:
    _detail: Optional[QWebEngineView] = None
    _rightmost: Optional[QWebEngineView] = None

    @classmethod
    def set_detail_www(cls, v: QWebEngineView) -> None:
        cls._detail = v

    @classmethod
    def set_rightmost_www(cls, v: QWebEngineView) -> None:
        cls._rightmost = v

    @classmethod
    def _target(cls, args) -> Optional[QWebEngineView]:
        p = args.get_arg("panel")
        panel = p.value if p else "right"
        if panel in ("detail", "d"):
            return cls._detail
        return cls._rightmost

    @staticmethod
    def _page_to_html_sync(page) -> str:
        result = [""]
        loop = QEventLoop()

        def cb(s: str) -> None:
            result[0] = s
            loop.quit()

        page.toHtml(cb)
        loop.exec()
        return result[0]

    @staticmethod
    def _page_to_text_sync(page) -> str:
        result = [""]
        loop = QEventLoop()

        def cb(s: str) -> None:
            result[0] = s
            loop.quit()

        page.toPlainText(cb)
        loop.exec()
        return result[0]

    @staticmethod
    def _page_js_sync(page, js: str) -> str:
        result = [""]
        loop = QEventLoop()

        def cb(r) -> None:
            result[0] = str(r) if r is not None else ""
            loop.quit()

        page.runJavaScript(js, cb)
        loop.exec()
        return result[0]

    @classmethod
    def register_cmds(cls) -> None:
        sys_ = CMD_SYS()

        def www_open(args, data, ctx):
            if args.count() < 2:
                return args.append_error("www_open: usage <url> [--panel detail|right]")
            v = cls._target(args)
            if v is None:
                return args.append_error("www_open: target view not set")
            s = args.get(1).value
            if not s:
                return args.append_error("www_open: empty url")
            if "://" not in s:
                s = "https://" + s
            v.setUrl(QUrl(s))
            args.append(s, "URL")
            return 0
        sys_.add("www_open", www_open, category="www")

        def www_url(args, data, ctx):
            v = cls._target(args)
            if v is None:
                return args.append_error("www_url: target view not set")
            args.append(v.url().toString(), "URL")
            return 0
        sys_.add("www_url", www_url, category="www")

        def www_html(args, data, ctx):
            v = cls._target(args)
            if v is None or v.page() is None:
                return args.append_error("www_html: target view not set")
            args.append(cls._page_to_html_sync(v.page()), "HTML")
            return 0
        sys_.add("www_html", www_html, category="www")

        def www_text(args, data, ctx):
            v = cls._target(args)
            if v is None or v.page() is None:
                return args.append_error("www_text: target view not set")
            args.append(cls._page_to_text_sync(v.page()), "TEXT")
            return 0
        sys_.add("www_text", www_text, category="www")

        def www_selection(args, data, ctx):
            v = cls._target(args)
            if v is None or v.page() is None:
                return args.append_error("www_selection: target view not set")
            sel = cls._page_js_sync(v.page(), "window.getSelection().toString()")
            args.append(sel, "SELECTION")
            return 0
        sys_.add("www_selection", www_selection, category="www")

        def www_screenshot(args, data, ctx):
            if args.count() < 2:
                return args.append_error("www_screenshot: usage <path>")
            v = cls._target(args)
            if v is None:
                return args.append_error("www_screenshot: target view not set")
            path = args.get(1).value
            px = v.grab()
            if not px.save(path, "PNG"):
                return args.append_error("www_screenshot: save failed")
            args.append(path, "PATH")
            return 0
        sys_.add("www_screenshot", www_screenshot, category="www")

        def www_back(args, data, ctx):
            v = cls._target(args)
            if v is None or v.page() is None:
                return args.append_error("www_back: target view not set")
            v.back()
            return 0
        sys_.add("www_back", www_back, category="www")

        def www_forward(args, data, ctx):
            v = cls._target(args)
            if v is None or v.page() is None:
                return args.append_error("www_forward: target view not set")
            v.forward()
            return 0
        sys_.add("www_forward", www_forward, category="www")

        def www_reload(args, data, ctx):
            v = cls._target(args)
            if v is None:
                return args.append_error("www_reload: target view not set")
            v.reload()
            return 0
        sys_.add("www_reload", www_reload, category="www")
