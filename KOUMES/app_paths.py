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
        self._dir_config = str(Path(self._dir_exe).parent / "other_config")
        self._settings: Optional[dict] = None

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

    def settings(self) -> dict:
        """Attribute lines of `other_config/config.t2l` as a flat dict (last wins).

        Deployment-local knobs - WS port, info bar colours, exchange dir. They
        live in the same file as the startup commands: `config.t2l` is a t2l
        file that happens to hold commands, so an attribute line is at home in
        it and `WindowPersist.restore()` steps over it. A line counts as an
        attribute when its **first word** ends with a colon - that is the same
        test restore() uses, and it keeps `set_panels --p1 "C:/x"` a command.

        Missing file or an unreadable one is not an error: the caller falls
        back to defaults.
        """
        if self._settings is None:
            self._settings = {}
            path = os.path.join(self.dir_config(), "config.t2l")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        head = line.split(" ", 1)[0]
                        if not head.endswith(":"):
                            continue
                        self._settings[head[:-1].strip()] = line[len(head):].strip()
            except OSError:
                pass
        return self._settings

    def settings_list(self, key: str) -> list:
        """All values of a repeated attribute, in file order - `settings()`
        keeps only the last. A t2l attribute may repeat, one thing per line;
        `qt_viewer:` does, one viewer per line."""
        out = []
        path = os.path.join(self.dir_config(), "config.t2l")
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    head = line.split(" ", 1)[0]
                    if head == key + ":":
                        out.append(line[len(head):].strip())
        except OSError:
            pass
        return out
