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
"""CmdContextIface - context accessor interface (reply channel + client data).

Python port of base2/cmd_sys/CmdContextIface.h.
"""

from typing import Optional

from .cmd_context_data_iface import CmdContextDataIface


class CmdContextIface:
    def __init__(self):
        self.client_data_: Optional[CmdContextDataIface] = None

    def reply(self, cmd: str, data: bytes = b"") -> None:
        raise NotImplementedError

    def reply_thread_safe(self, cmd: str, data: bytes = b"") -> None:
        raise NotImplementedError

    def get_as_client_context(self) -> Optional[object]:
        return None

    def force_disconnect(self) -> None:
        pass

    def log_cmd(self) -> bool:
        return False

    def unique_id(self) -> int:
        if self.client_data_ is None:
            return -1
        return self.client_data_.unique_id()

    def client_data(self) -> Optional[CmdContextDataIface]:
        return self.client_data_

    def client_data_set(self, data: CmdContextDataIface) -> None:
        assert self.client_data_ is None
        self.client_data_ = data
