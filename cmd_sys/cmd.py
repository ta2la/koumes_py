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
"""Cmd - single registered command (name + callback + flags).

Python port of base2/cmd_sys/Cmd.h.
"""

from typing import Callable, Optional

from .cmd_arg_col import CmdArgCol
from .cmd_context_iface import CmdContextIface


CommandHandler = Callable[[CmdArgCol, Optional[bytearray], CmdContextIface], int]


class Cmd:
    def __init__(
        self,
        name: str,
        handler: CommandHandler,
        exclude_exe_rec: bool = False,
        exclude_update: bool = False,
        category: str = "common",
    ):
        self.name_ = name
        self.handler_ = handler
        self.exclude_exe_rec_ = exclude_exe_rec
        self.exclude_update_ = exclude_update
        self.category_ = category

    def execute(
        self,
        args: CmdArgCol,
        data: Optional[bytearray],
        context: CmdContextIface,
    ) -> int:
        return self.handler_(args, data, context)

    def name(self) -> str:
        return self.name_

    def category(self) -> str:
        return self.category_

    def exclude_exe_rec(self) -> bool:
        return self.exclude_exe_rec_

    def exclude_update(self) -> bool:
        return self.exclude_update_
