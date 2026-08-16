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
"""LogGuard - CmdExeGuard that appends every executed command line to a text file.

Python port of base2/cmd_sys_display/LogGuard.{h,cpp}.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from .cmd_exe_guard import CmdExeGuard, Phase
from .cmd_sys import CMD_SYS


class LogGuard(CmdExeGuard):
    def __init__(self, path: str = "config/cmdlog.txt"):
        super().__init__(Phase.UPDATE)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.file_: Optional[TextIO] = None
        try:
            self.file_ = open(p, "a", encoding="utf-8")
        except OSError:
            self.file_ = None
        CMD_SYS().reg_guard(self)

    def __del__(self):
        if self.file_ is not None and not self.file_.closed:
            try:
                self.file_.close()
            except Exception:
                pass

    def command_executed(self) -> None:
        if self.file_ is None or self.file_.closed:
            return
        args = CMD_SYS().executing_args_
        if args is None:
            return
        stamp = datetime.now().strftime("%H:%M:%S ")
        self.file_.write(stamp + args.to_string() + "\n")
        self.file_.flush()
