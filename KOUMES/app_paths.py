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
"""AppPaths - resolves per-app filesystem paths.

Python adaptation of base2/app_common/AppPaths.h.

C++ version returned `<binary>/../config` for `dirConfig()` (self-contained
deployment layout). Python packaged apps use platform-standard user config
locations instead - via Qt's `QStandardPaths` if PyQt is present, or fallback
to XDG-style `~/.config/koumes/`.
"""

import os
from pathlib import Path
from typing import Optional


class AppPaths:
    _instance: Optional["AppPaths"] = None

    def __init__(self):
        self._dir_exe = str(Path(__file__).resolve().parent)
        self._dir_config = str(Path(self._dir_exe).parent / "config")

    @classmethod
    def inst(cls) -> "AppPaths":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def dir_exe(self) -> str:
        return self._dir_exe

    def dir_config(self) -> str:
        os.makedirs(self._dir_config, exist_ok=True)
        return self._dir_config
