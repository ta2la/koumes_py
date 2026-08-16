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
"""WsServerLite - lightweight WebSocket server that turns incoming lines into commands.

Python port of base2/mccp_com/WsServerLite.h.

Requires the `websockets` package. Install: `pip install websockets`.
"""

import asyncio
import threading
from typing import Optional, Set

try:
    import websockets
except ImportError:
    websockets = None


class WsServerLite:
    _instance: Optional["WsServerLite"] = None

    def __init__(self, port: int = 12345):
        self.port_: int = port
        self._clients: Set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._started: bool = False

    @classmethod
    def init(cls, port: int = 12345) -> "WsServerLite":
        if cls._instance is None:
            cls._instance = cls(port)
        if not cls._instance._started:
            cls._instance._started = True
            cls._instance._thread = threading.Thread(
                target=cls._instance._run_loop,
                name="WsServerLite",
                daemon=True,
            )
            cls._instance._thread.start()
        return cls._instance

    def broadcast(self, text: str) -> None:
        if self._loop is None or not self._loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception:
            pass

    async def _serve(self) -> None:
        if websockets is None:
            return
        self._server = await websockets.serve(self._handler, "127.0.0.1", self.port_)
        await self._server.wait_closed()

    async def _handler(self, websocket) -> None:
        self._clients.add(websocket)
        try:
            async for message in websocket:
                for line in str(message).split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    from .cmd_sys import CMD_SYS
                    CMD_SYS().execute_thread_safe(line, "ws", -1, "EXTERNAL_WS")
        except Exception:
            pass
        finally:
            self._clients.discard(websocket)

    async def _broadcast(self, text: str) -> None:
        for client in list(self._clients):
            try:
                await client.send(text)
            except Exception:
                self._clients.discard(client)
