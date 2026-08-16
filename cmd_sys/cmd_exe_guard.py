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
"""CmdExeGuard - abstract base for objects observing command execution.

Python port of base2/cmd_sys/CmdExeGuard.h.
"""

from enum import IntEnum


class Phase(IntEnum):
    RECORD = 0
    UPDATE = 100


class CmdExeGuard:
    def __init__(self, phase: Phase = Phase.RECORD):
        self.phase_ = phase

    def phase(self) -> Phase:
        return self.phase_

    def command_executed(self) -> None:
        raise NotImplementedError
