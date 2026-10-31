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
"""WsServer - WebSocket connector for any CmdSys instance.

Unlike WsServerLite (bound to the CMD_SYS() singleton) it serves the CmdSys it
is given, so an application with its own command system has its own port.
Lines from clients wait in that CmdSys's deferred queue; the owner drains
them on its main thread. Every executed command is broadcast to all clients.
"""

import asyncio
import socket
import threading

from .cmd_exe_guard import CmdExeGuard, Phase

try:
    import websockets
except ImportError:
    websockets = None


class WsServer(CmdExeGuard):
    def __init__(self, cmd_sys, port: int):
        super().__init__(Phase.UPDATE)
        self.sys, self.port = cmd_sys, port
        self.clients = set()
        self.loop = None
        cmd_sys.reg_guard(self)
        threading.Thread(target=self._run, name="WsServer", daemon=True).start()

    def command_executed(self) -> None:
        args = self.sys.executing_args_
        if args is not None and self.loop is not None and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send(args.to_string()), self.loop)

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except Exception:
            pass

    async def _serve(self) -> None:
        server = await websockets.serve(self._client, "127.0.0.1", self.port,
                                        origins=[None])    # prohlizec ma Origin vzdy: web se nedostane
        await server.wait_closed()

    async def _client(self, ws) -> None:
        self.clients.add(ws)
        try:
            async for msg in ws:
                for line in str(msg).split("\n"):
                    if line.strip():
                        self.sys.execute_thread_safe(line.strip(), "ws", -1, "EXTERNAL_WS")
        except Exception:
            pass
        finally:
            self.clients.discard(ws)

    async def _send(self, text: str) -> None:
        for c in list(self.clients):
            try:
                await c.send(text)
            except Exception:
                self.clients.discard(c)


def free_port(port: int) -> int:
    """First port from `port` that can be bound; TIME_WAIT of a previous run is fine."""
    for p in range(port, port + 20):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return port
