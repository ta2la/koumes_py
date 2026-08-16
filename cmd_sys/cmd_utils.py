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
"""CmdUtils - helper static functions for scripts and batch execution.

Python port of base2/cmd_sys/CmdUtils.h.
"""

from typing import List


class CmdUtils:
    @staticmethod
    def mine_commands_from_script(input_: str) -> List[str]:
        text = input_.replace("\r\n", "\n").replace("\r", "\n")

        result: List[str] = []
        current_lines: List[str] = []

        def flush_block() -> None:
            parts: List[str] = []
            for line in current_lines:
                s = line.strip()
                if not s:
                    continue
                parts.append(s)
            current_lines.clear()

            if parts:
                result.append(" ".join(parts))

        pos = 0
        while pos <= len(text):
            eol = text.find("\n", pos)
            if eol == -1:
                eol = len(text)

            line = text[pos:eol]

            if not line.strip():
                flush_block()
            else:
                current_lines.append(line)

            pos = eol + 1
            if eol == len(text):
                break

        flush_block()
        return result

    @staticmethod
    def execute_commands(commands: List[str]) -> int:
        from .cmd_sys import CMD_SYS
        executed = 0
        for cmd in commands:
            if not cmd.strip():
                continue
            CMD_SYS().execute_thread_safe(cmd, "", -1, "SCRIPT")
            executed += 1
        return executed
