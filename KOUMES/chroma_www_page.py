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
"""ChromaWwwPage - QWebEnginePage for WWW panels (external web only).

Python port of the C++ predecessor's ChromaWwwPage.h.

Rejects all local schemes (file://, data:, javascript:, qrc://, chrome://).
Sub-frames pass unrestricted (iframes serving http/https content).
Pair with an isolated QWebEngineProfile so cookies/cache do not mix with
the view panels' default profile.
"""

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEnginePage


class ChromaWwwPage(QWebEnginePage):
    def acceptNavigationRequest(
        self,
        url: QUrl,
        nav_type: "QWebEnginePage.NavigationType",
        is_main_frame: bool,
    ) -> bool:
        if not is_main_frame:
            return True
        scheme = url.scheme()
        return scheme in ("http", "https", "about")
