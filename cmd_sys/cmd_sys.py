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
"""CmdSys - command registry and dispatch (singleton).

Python port of base2/cmd_sys/CmdSys.{h,cpp}.
"""

import threading
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from .cmd import Cmd, CommandHandler
from .cmd_arg_col import CmdArgCol
from .cmd_context import CmdContext
from .cmd_context_iface import CmdContextIface
from .cmd_exe_filter import CmdExeFilter
from .cmd_exe_guard import CmdExeGuard, Phase


class CmdSys:
    _instance: Optional["CmdSys"] = None

    def __init__(self):
        self.cmds_: Dict[str, Cmd] = {}
        self.guards_: List[CmdExeGuard] = []
        self.filters_: List[CmdExeFilter] = []
        self.executing_args_: Optional[CmdArgCol] = None
        self.running_index_: int = -1
        self.main_thread_: bool = True
        self._deferred: Deque[Tuple[str, str, int, str]] = deque()
        self._lock = threading.RLock()

    @classmethod
    def inst(cls) -> "CmdSys":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add(
        self,
        name: str,
        handler: CommandHandler,
        exclude_exe_rec: bool = False,
        exclude_update: bool = False,
        category: str = "common",
    ) -> None:
        self.cmds_[name] = Cmd(name, handler, exclude_exe_rec, exclude_update, category)

    def get(self, name: str) -> Optional[Cmd]:
        return self.cmds_.get(name)

    def reg_guard(self, guard: CmdExeGuard) -> None:
        if guard.phase() == Phase.RECORD:
            self.guards_.insert(0, guard)
        else:
            self.guards_.append(guard)

    def reg_filter(self, filter_: CmdExeFilter) -> None:
        self.filters_.append(filter_)

    def set_main_thread(self, value: bool) -> None:
        self.main_thread_ = value

    def execute(
        self,
        args: str,
        source_name: str = "",
        source_index: int = -1,
        user: str = "UNKNOWN",
    ) -> int:
        if self.executing_args_ is not None and not self.executing_args_.is_null():
            self.execute_thread_safe(args, source_name, source_index, user)
            return 0

        self.executing_args_ = CmdArgCol(args)
        self.executing_args_.append(user, "USER")

        try:
            self._execute(
                self.executing_args_,
                None,
                CmdContext.inst(),
                source_name,
                source_index,
            )
        finally:
            self.executing_args_ = None

        while self._deferred:
            a, sn, si, u = self._deferred.popleft()
            self.execute(a, sn, si, u)

        return 0

    def execute_thread_safe(
        self,
        args: str,
        source_name: str = "",
        source_index: int = -1,
        user: str = "internal",
    ) -> None:
        with self._lock:
            self._deferred.append((args, source_name, source_index, user))

    def _execute(
        self,
        args: CmdArgCol,
        data: Optional[bytearray],
        context: CmdContextIface,
        source_name: str,
        source_index: int,
    ) -> int:
        if args.count() == 0:
            return -1

        self.running_index_ += 1

        for f in self.filters_:
            if f.pass_(args):
                return 0

        name = args.get(0).value
        cmd = self.get(name)
        if cmd is None:
            cmd = self.get("__not_implemented__")
            if cmd is None:
                return -1

        result = cmd.execute(args, data, context)

        if not cmd.exclude_update():
            for g in self.guards_:
                g.command_executed()

        return result


def CMD_SYS() -> CmdSys:
    return CmdSys.inst()
