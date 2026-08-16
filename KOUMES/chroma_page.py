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
"""ChromaPage - QWebEnginePage for VIEW panels (local file access only).

Python port of APPS/AI_T2LS/ChromaPage.h.

http/https navigation is rejected and re-routed to a www panel via PanelBus.
"""

from typing import Optional

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage


class ChromaPage(QWebEnginePage):
    _bus = None

    def __init__(self, role: str = "", parent=None):
        super().__init__(parent)
        self._role: str = role

    @classmethod
    def set_bus(cls, bus) -> None:
        cls._bus = bus

    def set_role(self, role: str) -> None:
        self._role = role

    def role(self) -> str:
        return self._role

    def acceptNavigationRequest(
        self,
        url: QUrl,
        nav_type: "QWebEnginePage.NavigationType",
        is_main_frame: bool,
    ) -> bool:
        if is_main_frame:
            scheme = url.scheme()
            if scheme in ("http", "https"):
                if ChromaPage._bus is not None:
                    ChromaPage._bus.notify_www_url_requested(url, self._role)
                return False
        return True

    def createWindow(self, window_type: "QWebEnginePage.WebWindowType") -> Optional[QWebEnginePage]:
        return ChromaPage(self._role, self)
