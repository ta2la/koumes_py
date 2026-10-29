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
"""Cmds - a group of commands of an application on its own CmdSys.

Like Cmds_cad in CAD or CmdsCmdSys here: the commands live in a class, not in
the mode queue. This base gives the plumbing; a subclass registers its
commands with `register(name, handler, description)`:

- a handler gets the unnamed arguments and returns None, an error (str) or
  [(value, name)] appended to the reply;
- every command runs under `lock` (e.g. a pool lock), errors never escape,
  each command is logged (line, ok); `mode()` (a hook, e.g. the active mode of
  the application's queue) is logged and appended to the reply;
- `<prefix>_help` lists the commands; `start_ws` opens a WebSocket connector,
  `drain` runs the lines waiting from it (on the main thread).
"""

import shlex
from collections import deque
from contextlib import nullcontext

from .cmd_sys import CmdSys
from .ws_server import WsServer, free_port


class Cmds:
    def __init__(self, prefix: str, lock=None):
        self.prefix = prefix
        self.lock = lock or nullcontext
        self.handlers = {}               # name -> (handler, description)
        self.log = deque(maxlen=500)     # executed commands: (line, ok)
        self.sys = CmdSys()
        self.sys.add("__not_implemented__", self._handler(None))
        self.ws = None
        self.register(prefix + "_help", self._cmd_help, "list of commands")

    def register(self, name, handler, description=""):
        self.handlers[name] = (handler, description)
        self.sys.add(name, self._handler(name), category=self.prefix)

    def run(self, line, user="USER"):
        """Run a command through the own CmdSys (logged, broadcast)."""
        self.sys.execute(line, "ui", -1, user)

    def start_ws(self, port=0, default=0):
        """WebSocket connector: `port` exactly, or the first free one from `default`."""
        if self.ws is None:
            self.ws = WsServer(self.sys, port or free_port(default))
        return self.ws.port

    def drain(self):
        while self.sys._deferred:
            a, sn, si, u = self.sys._deferred.popleft()
            self.sys.execute(a, sn, si, u)

    def changed(self):
        """Hook after every command (e.g. refresh the UI)."""

    def mode(self) -> str:
        """Hook: state reported with every command (e.g. the active mode)."""
        return ""

    #! @section Hidding
    def _cmd_help(self, args):
        return [("%s  %s" % (n, d), "CMD") for n, (_, d) in self.handlers.items()]

    def _log(self, name, vals, user, err):
        line = " ".join([name] + [shlex.quote(v) if " " in v else v for v in vals])
        mode = self.mode()
        if err:
            self.log.append(("%s  ! %s" % (line, err), False))
        else:
            self.log.append(("%s  > %s  (%s)" % (line, mode, user), True))
        self.changed()

    def _handler(self, name):
        def h(args, data, ctx):
            cmd = args.get(0).value
            vals = [args.get(i).value for i in range(1, args.count())
                    if args.get(i).name == ""]
            if name is None:
                err = "%s: unknown command (%s_help)" % (cmd, self.prefix)
            else:
                try:
                    with self.lock():
                        err = self.handlers[name][0](vals)
                except Exception as e:   # a command error must not take the app down
                    err = "%s: %s" % (name, e)
            out = err if isinstance(err, list) else []
            err = None if isinstance(err, list) else err
            user = args.get_by_name("USER").value
            self._log(cmd, vals, user, err)
            if err:
                args.append_error(err)
                return -1
            for value, key in out:
                args.append(value, key)
            if self.mode():
                args.append(self.mode(), "MODE")
            return 0
        return h
