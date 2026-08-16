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
"""StdoutCmdOutput - guard that echoes each executed command to stdout.

Python port of base2/cmd_sys/StdoutCmdOutput.{h,cpp}.

Disabled by default - when enabled and running inside a shell that pipes stdout
back to stdin (e.g. Qt Creator), you get an echo loop. Enable only for pipe/bridge
setups (e.g. STDIO_BRIDGE).
"""

import sys
from typing import Optional

from .cmd_exe_guard import CmdExeGuard, Phase


class StdoutCmdOutput(CmdExeGuard):
    _instance: Optional["StdoutCmdOutput"] = None

    def __init__(self):
        super().__init__(Phase.UPDATE)
        self.enabled_: bool = False
        from .cmd_sys import CMD_SYS
        CMD_SYS().reg_guard(self)

    @classmethod
    def inst(cls) -> "StdoutCmdOutput":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_enabled(self, value: bool) -> None:
        self.enabled_ = value

    def is_enabled(self) -> bool:
        return self.enabled_

    def command_executed(self) -> None:
        if not self.enabled_:
            return
        from .cmd_sys import CMD_SYS
        args = CMD_SYS().executing_args_
        if args is None:
            return
        sys.stdout.write(args.to_string() + "\n")
        sys.stdout.flush()
