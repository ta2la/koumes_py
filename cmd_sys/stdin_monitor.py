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
"""StdinMonitor - reads commands from stdin in a background thread.

Python port of base2/cmd_sys/StdinMonitor.h.
"""

import sys
import threading
from typing import Optional


class StdinMonitor(threading.Thread):
    _instance: Optional["StdinMonitor"] = None

    def __init__(self):
        super().__init__(daemon=True, name="StdinMonitor")
        self.enabled_: bool = False
        self._stop_event = threading.Event()

    @classmethod
    def init(cls) -> "StdinMonitor":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.start()
        return cls._instance

    def set_enabled(self, value: bool) -> None:
        self.enabled_ = value

    def is_enabled(self) -> bool:
        return self.enabled_

    def request_interruption(self) -> None:
        self._stop_event.set()

    def process_line(self, line: str) -> None:
        if not self.enabled_:
            return
        if line.startswith("qt."):
            return
        from .cmd_sys import CMD_SYS
        CMD_SYS().execute_thread_safe(line, "stdin", -1, "EXTERNAL_STD")

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                raw = sys.stdin.readline()
            except (OSError, ValueError):
                break
            if not raw:
                break
            line = raw.strip()
            if line:
                self.process_line(line)
