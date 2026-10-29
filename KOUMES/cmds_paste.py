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
"""paste_clipboard - drop whatever is on the clipboard into a file.

The point is the screenshot round trip: shoot, Ctrl+C, one click in koumes, and
the image is a file on disk with a path an agent can be pointed at.

Like every other action in koumes this is a command, not a button handler - the
toolbar button only sends `paste_clipboard`, so the same thing happens when it
arrives over the WS bridge, and either way it lands in the log.
"""

import os
import shutil
from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtGui import QGuiApplication

from cmd_sys import CMD_SYS


class CmdsPaste:
    _bus = None
    _root: str = ""
    _saved_fn: Optional[Callable[[str], None]] = None

    @classmethod
    def configure(cls, bus, root: str) -> None:
        cls._bus = bus
        cls._root = root

    @classmethod
    def set_saved_fn(cls, fn: Callable[[str], None]) -> None:
        """Called with the path after a successful paste (UI status line)."""
        cls._saved_fn = fn

    @classmethod
    def exchange_dir(cls) -> str:
        """Where pasted files land.

        `exchange_dir` in `other_config/config.t2l` wins. Without it: `<root>/exchange`
        if the tree has one - that is the drop box agents read, and the reason
        this button exists - then the machine's screenshot folder, and that one
        as a last resort even if it has to be created.
        """
        from .app_paths import AppPaths

        configured = AppPaths.inst().settings().get("exchange_dir", "")
        if configured:
            return os.path.expanduser(configured)

        exchange = os.path.join(cls._root, "exchange") if cls._root else ""
        if exchange and os.path.isdir(exchange):
            return exchange

        shots = os.path.expanduser("~/Pictures/Screenshots")
        return shots if os.path.isdir(shots) else (exchange or shots)

    @classmethod
    def _stamp(cls) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    @classmethod
    def _save(cls, target_dir: str) -> tuple:
        """Write the clipboard into target_dir. Returns (path, error)."""
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            return "", f"cannot create {target_dir}: {e}"

        cb = QGuiApplication.clipboard()
        if cb is None:
            return "", "no clipboard"
        mime = cb.mimeData()
        if mime is None:
            return "", "clipboard empty"

        if mime.hasImage():
            img = cb.image()
            if img.isNull():
                return "", "clipboard image is empty"
            path = os.path.join(target_dir, f"paste_{cls._stamp()}.png")
            if not img.save(path, "PNG"):
                return "", f"cannot write {path}"
            return path, ""

        # A copied file keeps its own name - renaming someone's file to
        # paste_<stamp> would lose the only thing that says what it is.
        if mime.hasUrls():
            for url in mime.urls():
                src = url.toLocalFile()
                if not src or not os.path.isfile(src):
                    continue
                path = os.path.join(target_dir, os.path.basename(src))
                try:
                    shutil.copyfile(src, path)
                except OSError as e:
                    return "", f"cannot copy {src}: {e}"
                return path, ""
            return "", "clipboard holds no local file"

        if mime.hasText() and cb.text().strip():
            path = os.path.join(target_dir, f"paste_{cls._stamp()}.txt")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(cb.text())
            except OSError as e:
                return "", f"cannot write {path}: {e}"
            return path, ""

        return "", "clipboard holds nothing pasteable"

    @classmethod
    def register_cmds(cls) -> None:
        sys_ = CMD_SYS()

        def first_positional(args) -> str:
            # Everything the user typed comes in unnamed; `--USER`, `--DIR` and
            # friends are appended by the system and the handlers around it, and
            # they sit in the same list. Reading get(1) blindly picked up
            # `--USER EXTERNAL_WS` and pasted into a directory called that.
            for i in range(1, args.count()):
                a = args.get(i)
                if not a.name:
                    return a.value
            return ""

        def paste_clipboard(args, data, ctx):
            target = first_positional(args) or cls.exchange_dir()
            path, err = cls._save(os.path.expanduser(target))
            if err:
                return args.append_error(f"paste_clipboard: {err}")
            if cls._saved_fn is not None:
                cls._saved_fn(path)
            args.append(path, "SAVED")
            return 0

        sys_.add("paste_clipboard", paste_clipboard, category="chroma")

        def exchange_dir(args, data, ctx):
            args.append(cls.exchange_dir(), "DIR")
            return 0

        sys_.add("exchange_dir", exchange_dir, category="chroma")

        def export_saved(args, data, ctx):
            """Log entry for a canvas export written by FsBridge.saveExport.

            The bytes are already on disk; this only puts the path in the log
            and lights up the same status line as a paste.
            """
            path = first_positional(args)
            if not path:
                return args.append_error("export_saved: usage: export_saved <path>")
            if cls._saved_fn is not None:
                cls._saved_fn(path)
            args.append(path, "SAVED")
            return 0

        sys_.add("export_saved", export_saved, category="chroma")
