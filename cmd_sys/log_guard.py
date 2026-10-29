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


#: how far the file may run past its limit before it is rewritten. Trimming
#: means reading the whole log back and writing it out again, so doing it on
#: every single command would be silly - this buys one rewrite per SLACK
#: commands and the file is never more than SLACK lines over the mark.
_SLACK = 50


class LogGuard(CmdExeGuard):
    """Appends every executed command to a text file, optionally capped.

    `max_lines` 0 means the file grows forever - the behaviour this had before
    anyone asked for a cap. Anything else keeps the last `max_lines` commands:
    a log is for looking at what just happened, and the tail is the part that
    answers that. The limit comes from the deployment's `config.t2l`
    (`log_lines:`), so a machine that wants a long memory can have one.
    """

    def __init__(self, path: str = "other_config/cmdlog.txt", max_lines: int = 0):
        super().__init__(Phase.UPDATE)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.path_ = p
        self.max_lines_ = max(0, int(max_lines))
        self.lines_ = 0
        self.file_: Optional[TextIO] = None
        if self.max_lines_:
            # A log left over from a run without a cap (or with a bigger one)
            # is cut here, not at some later write - otherwise the setting
            # would look like it did nothing until the file grew again.
            self.lines_ = self._trim()
        try:
            self.file_ = open(p, "a", encoding="utf-8")
        except OSError:
            self.file_ = None
        CMD_SYS().reg_guard(self)

    def _trim(self) -> int:
        """Rewrite the file with its last `max_lines_` lines; return the count.

        Written to a neighbouring file and renamed, so a reader never catches a
        half-written log - the same atomic swap the t2l index scripts use.
        """
        try:
            with open(self.path_, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            return 0
        if len(lines) <= self.max_lines_:
            return len(lines)
        keep = lines[-self.max_lines_:]
        tmp = self.path_.with_suffix(self.path_.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(keep)
            tmp.replace(self.path_)
        except OSError:
            return len(lines)
        return len(keep)

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
        if not self.max_lines_:
            return
        self.lines_ += 1
        if self.lines_ <= self.max_lines_ + _SLACK:
            return
        # The handle has to let go before the file underneath it is replaced,
        # or the reopened log would keep writing into the unlinked old one.
        try:
            self.file_.close()
        except OSError:
            pass
        self.lines_ = self._trim()
        try:
            self.file_ = open(self.path_, "a", encoding="utf-8")
        except OSError:
            self.file_ = None
