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
"""CmdBridge - unified entry point for external command IO.

Python port of base2/mccp_com/CmdBridge.{h,cpp}.

The C++ version selects transport by build:
  - Native: starts WsServerLite via WsServerLiteGuard.inst()
  - WASM/Emscripten: EM_JS + DOM REPL + craseExec() export

Python has no WASM branch - always native. `init()` reduces to
starting the WS server via WsServerLiteGuard.
"""

from .ws_server_lite_guard import WsServerLiteGuard


class CmdBridge:
    @staticmethod
    def init() -> None:
        WsServerLiteGuard.inst()
