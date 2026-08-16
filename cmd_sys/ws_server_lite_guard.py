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
"""WsServerLiteGuard - broadcasts each executed command to all WS clients.

Python port of base2/mccp_com/WsServerLiteGuard.h.
"""

from typing import Optional

from .cmd_exe_guard import CmdExeGuard, Phase
from .cmd_sys import CMD_SYS
from .ws_server_lite import WsServerLite


class WsServerLiteGuard(CmdExeGuard):
    _instance: Optional["WsServerLiteGuard"] = None

    def __init__(self, server: WsServerLite):
        super().__init__(Phase.UPDATE)
        self.server_ = server
        CMD_SYS().reg_guard(self)

    @classmethod
    def inst(cls) -> "WsServerLiteGuard":
        if cls._instance is None:
            cls._instance = cls(WsServerLite.init())
        return cls._instance

    def command_executed(self) -> None:
        args = CMD_SYS().executing_args_
        if args is None:
            return
        output = args.to_string()
        self.server_.broadcast(output)
