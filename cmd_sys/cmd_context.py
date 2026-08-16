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
"""CmdContext - concrete singleton implementation of CmdContextIface.

Python port of base2/cmd_sys/CmdContext.h.
"""

from typing import Optional

from .cmd_context_iface import CmdContextIface


class CmdContext(CmdContextIface):
    _instance: Optional["CmdContext"] = None

    @classmethod
    def inst(cls) -> "CmdContext":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reply(self, cmd: str, data: bytes = b"") -> None:
        pass


def CMD_CONTEXT() -> CmdContext:
    return CmdContext.inst()
