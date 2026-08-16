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
"""CmdArgColParser - parses command line to CmdArgCol.

Python port of base2/base2/CmdArgCol_parser.{h,cpp}.

Handles:
  - positional args (space-separated)
  - named args (--name value)
  - quoted strings ("...")
  - JSON blobs ({...})
  - backslash escapes (\\\\ -> \\, \\" -> ")
"""

from typing import List, Tuple

from .cmd_arg_col import CmdArgCol


class CmdArgColParser:
    @staticmethod
    def _is_json_quote(ch: str) -> bool:
        return ch in ('"', "'")

    @staticmethod
    def split_custom_append(result: List[str], current: str, is_noname: bool) -> Tuple[str, bool]:
        current = current.strip()
        if not current:
            return "", is_noname

        if current.startswith("--"):
            is_noname = False
            space_index = current.find(' ')
            if space_index != -1:
                result.append(current[:space_index])
                current = current[space_index + 1:]

        if is_noname and current and current[0] != '{' and ' ' in current:
            parts = current.split(' ')
            for part in parts:
                if part:
                    result.append(part)
        else:
            result.append(current)

        return "", is_noname

    @staticmethod
    def split_custom(input_: str, result: List[str]) -> None:
        current = ""
        in_escape = False
        in_quotes = False
        brace_depth = 0
        name_level = 0
        in_noname = True

        for c in input_:
            if in_escape:
                if c == '\\':
                    current += '\\'
                elif c == '"':
                    current += '"'
                else:
                    current += '\\' + c
                in_escape = False
                continue

            if in_quotes:
                if c == '"':
                    current, in_noname = CmdArgColParser.split_custom_append(result, current, in_noname)
                    in_quotes = False
                    continue
                current += c
                continue

            if brace_depth > 0:
                if c == '}':
                    brace_depth -= 1
                elif c == '{':
                    brace_depth += 1
                current += c
                if brace_depth == 0:
                    current, in_noname = CmdArgColParser.split_custom_append(result, current, in_noname)
                continue

            if c == '\\':
                in_escape = True
                continue

            # nameLevel state machine: detect " --" (space, dash, dash)
            if name_level == 0 and c == ' ':
                name_level += 1
            elif name_level == 1 and c == '-':
                name_level += 1
            elif name_level == 2 and c == '-':
                name_level += 1
            else:
                name_level = 0
                if c == ' ':
                    name_level += 1

            if name_level == 3:
                name_level = 0
                # chopped(1).trimmed().isEmpty() -> True if content before this dash is only whitespace
                if current[:-1].strip() == "":
                    current += c
                    continue
                else:
                    current = current[:-1]  # chop last char (the '-' just added)
                    current, in_noname = CmdArgColParser.split_custom_append(result, current, in_noname)
                    current = "--"
                    continue

            current0 = ""
            if c == '{':
                current0 = '{'
                brace_depth += 1
            elif c == '"':
                current0 = '"'
                in_quotes = True
            else:
                current += c
                continue

            if current:
                current, in_noname = CmdArgColParser.split_custom_append(result, current, in_noname)
                current = current0

        if current:
            CmdArgColParser.split_custom_append(result, current, in_noname)

    @staticmethod
    def create_list(divided: List[str], args: CmdArgCol) -> None:
        name = ""
        value = ""

        while divided:
            current = divided.pop(0).strip()

            if current.startswith("--"):
                if name:
                    args.append(value, name)
                name = current[2:]
                value = ""
                continue

            if current.startswith('"'):
                current = current[1:]

            if not name:
                args.append(current)
            else:
                if value:
                    value += " "
                value += current

        if name:
            args.append(value, name)
