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
"""CmdArgCol - collection of CmdArg (parsed command line).

Python port of base2/base2/CmdArgCol.{h,cpp}.
"""

from enum import Enum
from typing import List, Optional

from .cmd_arg import CmdArg


class Style(Enum):
    NORMAL = 0
    FORMATTED = 1
    JSON = 2


class CmdArgCol:
    def __init__(self, args: Optional[str] = None):
        self._args: List[CmdArg] = []
        if args:
            from .cmd_arg_col_parser import CmdArgColParser
            divided: List[str] = []
            CmdArgColParser.split_custom(args, divided)
            CmdArgColParser.create_list(divided, self)

    def append(self, value: str, name: str = "") -> int:
        self._args.append(CmdArg(name=name, value=value))
        return 1

    def append_error(self, text: str) -> int:
        return self.append(text, "ERROR")

    def append_warning(self, text: str) -> int:
        return self.append(text, "WARNING")

    def count(self) -> int:
        return len(self._args)

    def __len__(self) -> int:
        return len(self._args)

    def get(self, index: int) -> CmdArg:
        if index >= self.count():
            return CmdArg()
        return self._args[index]

    def get_by_name(self, name: str, implicit_value: str = "", index: int = 0) -> CmdArg:
        for arg in self._args:
            if arg.name != name:
                continue
            if index == 0:
                return arg
            index -= 1
        return CmdArg(name=name, value=implicit_value)

    def get_arg(self, name: str, index: int = 0) -> Optional[CmdArg]:
        for arg in self._args:
            if arg.name != name:
                continue
            if index == 0:
                return arg
            index -= 1
        return None

    def to_string(self, style: Style = Style.NORMAL, last: int = 0) -> str:
        from_ = 0
        to = self.count()
        if last > 0:
            from_ = to - last
        if from_ < 0:
            from_ = 0
        if last < 0:
            to += last
        if to > self.count():
            to = self.count()

        if style == Style.FORMATTED:
            parts = []
            for i in range(from_, to):
                arg = self.get(i)
                s = f"&nbsp;&nbsp;&nbsp;&nbsp;[{i}] "
                if arg.name:
                    s += arg.name
                s += ":" + arg.value.replace(" ", "&#9617;")
                parts.append(s)
            return "<br/>".join(parts)

        if style == Style.JSON:
            result = "[\n"
            for i in range(from_, to):
                arg = self.get(i)
                result += f'["{arg.name}", "{arg.value}"],\n'
            result += "]"
            return result

        parts = []
        for i in range(from_, to):
            arg = self.get(i)
            s = ""
            if arg.name:
                s = "--" + arg.name
                if arg.value:
                    s += " "
            s += arg.value
            parts.append(s)
        return " ".join(parts)

    def size_occupied(self) -> int:
        return sum(len(arg.name) + len(arg.value) for arg in self._args)

    def is_null(self) -> bool:
        return not self._args
