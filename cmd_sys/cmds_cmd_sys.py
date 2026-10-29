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
"""Cmds_cmd_sys - built-in commands of CmdSys.

Python port of base2/cmd_sys/Cmds_cmd_sys.{h,cpp}.
"""

import os
from typing import Optional

from .cmd_arg_col import CmdArgCol
from .cmd_context_iface import CmdContextIface
from .cmd_sys import CMD_SYS
from .cmd_utils import CmdUtils


NOT_DOCUMENTED = "No documentation available for this command."
HELP_FILE = os.path.join(os.path.dirname(__file__), "cmd_sys.help.md")


def command_help(name: str) -> str:
    """Text of section `### <name>` in cmd_sys.help.md (without the heading); NOT_DOCUMENTED if none."""
    try:
        with open(HELP_FILE, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")
    except OSError:
        return NOT_DOCUMENTED
    out, inside = [], False
    for line in lines:
        if line.startswith("### "):
            if inside:
                break
            inside = line[4:].strip().strip("`") == name
        elif line.startswith("## ") or line.startswith("# "):
            if inside:
                break
        elif inside:
            out.append(line)
    return "\n".join(out).strip() or NOT_DOCUMENTED

class CmdsCmdSys:
    @staticmethod
    def register_cmds_() -> bool:
        sys_ = CMD_SYS()

        def voidcmd(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            return 0
        sys_.add("voidcmd", voidcmd, category="cmd_sys")

        def logcmd(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            return 0
        sys_.add("logcmd", logcmd, category="cmd_sys")

        def not_implemented(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            name = args.get(0).value
            args.append_error(f"command not implemented: {name}")
            return 1
        sys_.add("__not_implemented__", not_implemented, category="__cmd_sys_core__")

        def cmds_execute_script(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            path = args.get(1).value.strip()
            if not path:
                return args.append_error("cmds_from_file: missing file path")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    script = f.read()
            except OSError as e:
                return args.append_error(f"cmds_from_file: cannot open file: {path} ({e})")
            commands = CmdUtils.mine_commands_from_script(script)
            executed = CmdUtils.execute_commands(commands)
            args.append(f"executed {executed} command(s)", "INFO")
            return 0
        sys_.add("cmds_execute_script", cmds_execute_script, category="cmd_sys")

        def cmd_help(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            if args.count() < 2:
                return args.append_error("usage: cmd_help <command_name>")
            name = args.get(1).value
            text = command_help(name)
            lines = text.split("\n") if text else []
            while lines and lines[0].strip().startswith("--"):
                flag = lines.pop(0).strip()
                if flag.startswith("--"):
                    flag = flag[2:]
                args.append("", flag)
            args.append("\n".join(lines).strip(), "HELP")
            return 0
        sys_.add("cmd_help", cmd_help, category="cmd_sys")

        def cmds_categories(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            cats = set()
            for cmd in sys_.cmds_.values():
                cats.add(cmd.category())
            for cat in sorted(cats):
                args.append(cat, "CATEGORY")
            return 0
        sys_.add("cmds_categories", cmds_categories, category="cmd_sys")

        def cmds_list(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            filters = []
            for i in range(1, args.count()):
                a = args.get(i)
                if a.name == "type":
                    filters.append(a.value)
            by_category: dict = {}
            for name, cmd in sys_.cmds_.items():
                by_category.setdefault(cmd.category(), []).append(name)
            for cat in sorted(by_category.keys()):
                if filters and cat not in filters:
                    continue
                args.append(f"{cat} : {' '.join(sorted(by_category[cat]))}", "CATEGORY")
            return 0
        sys_.add("cmds_list", cmds_list, category="cmd_sys")

        def execute_script(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int:
            if args.count() < 2:
                return args.append_error("usage: execute_init_script <file>")
            file_name = args.get(1).value
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    for raw in f:
                        line = raw.strip()
                        if not line:
                            continue
                        if line.startswith("#"):
                            continue
                        sys_.execute_thread_safe(line, "", -1, "SCRIPT")
            except OSError as e:
                return args.append_error(f"cannot open file: {file_name} ({e})")
            args.append(file_name, "INIT_OK")
            return 0
        sys_.add("execute_script", execute_script, category="cmd_sys")

        return True
