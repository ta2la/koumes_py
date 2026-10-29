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
"""FsBridge - sandboxed filesystem + [[link]] resolver, exposed to JS via QWebChannel.

Python port of the C++ predecessor's FsBridge.{h,cpp}.
"""

import base64
import binascii
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSlot

from cmd_sys import CMD_SYS


def _clean_abs(p: str) -> str:
    return os.path.normpath(os.path.abspath(p))


def _is_inside(path: str, dir_: str) -> bool:
    abs_dir = _clean_abs(dir_)
    abs_path = _clean_abs(path)
    return abs_path == abs_dir or abs_path.startswith(abs_dir + os.sep)


def _find_id_ordinal_in_file(file_path: str, id_: str) -> int:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return 0
    n = 0
    has_attr = False
    cur_id = ""
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            if has_attr:
                n += 1
                if cur_id == id_:
                    return n
            has_attr = False
            cur_id = ""
            continue
        if line.startswith("#"):
            continue
        c = line.find(":")
        if c < 0:
            continue
        has_attr = True
        if line[:c].strip() == "id":
            cur_id = line[c + 1:].strip()
    if has_attr:
        n += 1
        if cur_id == id_:
            return n
    return 0


def _rewrite_link_in_file(source_file: str, id_: str, new_path: str) -> None:
    try:
        with open(source_file, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return
    esc_id = re.escape(id_)
    rx = re.compile(r"\[\[" + esc_id + r"(::[^\]]*)?\]\]")
    replacement = f"[[{id_}::{new_path}]]"
    new_text = rx.sub(replacement, text)
    if new_text == text:
        return
    try:
        with open(source_file, "w", encoding="utf-8") as fw:
            fw.write(new_text)
    except OSError:
        pass


def _resolve_id_in_tree(id_: str, start_dir: str, root_abs: str) -> Optional[tuple]:
    visited = set()
    dirs_to_scan = []

    def add_subtree(root: str) -> None:
        dirs_to_scan.append(root)
        for sub, _, _ in os.walk(root):
            if sub != root:
                dirs_to_scan.append(sub)

    cur = start_dir
    while cur and _is_inside(cur, root_abs):
        if cur not in visited:
            visited.add(cur)
            add_subtree(cur)
        if cur == root_abs:
            break
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            break
        cur = parent

    for d in dirs_to_scan:
        try:
            for fn in os.listdir(d):
                if not fn.endswith(".t2l"):
                    continue
                abs_ = os.path.join(d, fn)
                if not os.path.isfile(abs_):
                    continue
                ord_ = _find_id_ordinal_in_file(abs_, id_)
                if ord_ > 0:
                    return (abs_, ord_)
        except OSError:
            continue
    return None


class FsBridge(QObject):
    _inst: Optional["FsBridge"] = None
    _bus = None

    def __init__(self, allowed_dir: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.allowed_dir_: str = _clean_abs(allowed_dir)
        self.selection_: str = ""
        self.selected_dir_: str = ""
        self.selected_file_: str = ""
        self.selected_line_: int = 0
        self.last_follow_log_: str = ""
        FsBridge._inst = self

    @classmethod
    def inst(cls) -> Optional["FsBridge"]:
        return cls._inst

    @classmethod
    def set_bus(cls, bus) -> None:
        cls._bus = bus

    @staticmethod
    def is_inside(path: str, dir_: str) -> bool:
        return _is_inside(path, dir_)

    def _is_allowed(self, path: str) -> bool:
        """Gate for browsing and for everything that changes the disk."""
        if not path:
            return True
        if _is_inside(path, self.allowed_dir_):
            return True
        try:
            from .app_paths import AppPaths
            if _is_inside(path, AppPaths.inst().dir_config()):
                return True
        except Exception:
            pass
        return False

    def _is_readable(self, path: str) -> bool:
        """Gate for showing a file. Wider than `_is_allowed` on purpose.

        The sandbox says where koumes browses and what it may change, not what
        it may render: a panel pointed at a file outside it already loads that
        file straight from disk, because Chromium does not come through this
        bridge. Refusing the read here did not keep the file out of sight - it
        only broke the viewer that was supposed to render it, so the sandbox
        edge showed up as an empty page instead of as a boundary.
        """
        return True

    def set_allowed_root(self, new_root: str) -> bool:
        cleaned = _clean_abs(new_root)
        if not cleaned or cleaned == self.allowed_dir_:
            return False
        if not _is_inside(self.allowed_dir_, cleaned):
            return False
        self.allowed_dir_ = cleaned
        return True

    @pyqtSlot(result=str)
    def allowedRoot(self) -> str:
        return self.allowed_dir_

    @pyqtSlot(str, result="QStringList")
    def list(self, path: str = "") -> List[str]:
        p = path if path else self.allowed_dir_
        if not self._is_allowed(p):
            return []
        if not os.path.isdir(p):
            return []
        try:
            entries = os.listdir(p)
        except OSError:
            return []
        dirs = sorted(e for e in entries if os.path.isdir(os.path.join(p, e)))
        files = sorted(e for e in entries if not os.path.isdir(os.path.join(p, e)))
        return dirs + files

    @pyqtSlot(str, result="QStringList")
    def viewers(self, path: str) -> List[str]:
        """Viewer names a file can be shown with, best first.

        The same list the viewer bar over a document offers: an in-file
        `type: viewer` directive, then the walk-up `config.t2l` mapping for the
        extension. Only names that actually resolve to an html on disk get
        through - offering a viewer that is not there would be a dead button.
        `native` is not in it: that is the panel handing the file to Chromium,
        not a viewer the tree provides.
        """
        if not self._is_readable(path) or not os.path.isfile(path):
            return []
        from . import viewer_resolver as vr
        out: List[str] = []
        for name in vr.read_all_viewers(path, self.allowed_dir_):
            if vr.find_viewer_target(os.path.dirname(path), self.allowed_dir_, name):
                out.append(name)
        return out

    @pyqtSlot(str, result=str)
    def read(self, path: str) -> str:
        if not self._is_readable(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            # A binary (pdf, zip, docx) is not text. Uncaught, the error
            # escapes the pyqtSlot and PyQt aborts the whole process.
            return ""

    @pyqtSlot(str, str, result=bool)
    def write(self, path: str, content: str) -> bool:
        if not self._is_allowed(path):
            return False
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except OSError:
            return False

    @pyqtSlot(str, result=str)
    def repoKind(self, path: str) -> str:
        """A repo is a dir with `.git`; its kind is the `remark` value cpp|app in
        `<repo>/<repo>.t2l`, anything else is `other`. Not a repo: empty - same
        rule as the dirview (CPPBROWSE)."""
        if not self._is_readable(path) or not os.path.exists(os.path.join(path, ".git")):
            return ""
        kind, typ = "other", ""
        try:
            with open(os.path.join(path, os.path.basename(path.rstrip("/")) + ".t2l"),
                      encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        typ = ""
                        continue
                    key, sep, value = line.partition(":")
                    key, value = key.strip(), value.strip()
                    if key == "type":
                        typ = value
                    elif typ == "remark" and key == "value" and value in ("cpp", "app"):
                        kind = value
        except OSError:
            pass
        return kind

    @pyqtSlot(str, result=bool)
    def isDir(self, path: str) -> bool:
        if not self._is_allowed(path):
            return False
        return os.path.isdir(path)

    @pyqtSlot(str, result=bool)
    def exists(self, path: str) -> bool:
        if not self._is_allowed(path):
            return False
        return os.path.exists(path)

    @pyqtSlot(str, result=bool)
    def trash(self, path: str) -> bool:
        if not self._is_allowed(path):
            return False
        if not os.path.exists(path):
            return False
        abs_ = _clean_abs(path)
        if abs_ == self.allowed_dir_:
            return False
        try:
            r = subprocess.run(
                ["gio", "trash", "--", abs_],
                timeout=15,
                capture_output=True,
            )
            return r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    @pyqtSlot(str)
    def setSelection(self, json_: str) -> None:
        self.selection_ = json_

    def current_selection(self) -> str:
        return self.selection_

    @pyqtSlot(str)
    def setSelectedDir(self, p: str) -> None:
        self.selected_dir_ = p

    @pyqtSlot(str)
    def setSelectedFile(self, p: str) -> None:
        self.selected_file_ = p

    @pyqtSlot(int)
    def setSelectedLine(self, n: int) -> None:
        self.selected_line_ = n

    # A selection outlives what it points at: rename or delete the file and the
    # viewer has no reason to publish anything new, so the old path would be
    # answered to `chroma_file` and painted in the info bar forever. A selection
    # that no longer exists is no selection.
    def current_selected_dir(self) -> str:
        if self.selected_dir_ and not os.path.isdir(self.selected_dir_):
            self.selected_dir_ = ""
        return self.selected_dir_

    def current_selected_file(self) -> str:
        if self.selected_file_ and not os.path.isfile(self.selected_file_):
            self.selected_file_ = ""
        return self.selected_file_

    def current_selected_line(self) -> int:
        return self.selected_line_

    def last_follow_log(self) -> str:
        return self.last_follow_log_

    @pyqtSlot(str, str)
    def followLink(self, link_arg: str, start_path: str) -> None:
        self.last_follow_log_ = f"followLink linkArg={link_arg} startPath={start_path}"
        bus = FsBridge._bus
        if bus is None or not link_arg:
            return

        id_ = link_arg
        hint_path = ""
        sep = link_arg.find("::")
        if sep >= 0:
            id_ = link_arg[:sep]
            hint_path = link_arg[sep + 2:]
        if not id_ or id_ == "???":
            return

        start_dir = os.path.dirname(os.path.abspath(start_path))
        root_abs = _clean_abs(self.allowed_dir_)
        start_abs = _clean_abs(start_path)

        def open_target(target_abs: str, ord_: int) -> None:
            if _clean_abs(target_abs) == start_abs:
                bus.notify_line_changed(ord_)
            else:
                bus.notify_file_selected_for_browse(target_abs, ord_)

        if hint_path and hint_path != "???":
            abs_ = _clean_abs(os.path.join(start_dir, hint_path))
            if os.path.exists(abs_) and _is_inside(abs_, root_abs):
                ord_ = _find_id_ordinal_in_file(abs_, id_)
                if ord_ > 0:
                    self.last_follow_log_ += f" | HINT_HIT abs={abs_} ord={ord_}"
                    open_target(abs_, ord_)
                    return

        # Rewriting the link is a write to disk, so the same gate as `write` applies.
        # Navigating to the target is not held back - that is only a read.
        may_write = self._is_allowed(start_abs)
        note = "" if may_write else " | NO_WRITE (start file outside sandbox)"

        found = _resolve_id_in_tree(id_, start_dir, root_abs)
        if found:
            found_abs, found_ord = found
            rel_path = os.path.relpath(found_abs, start_dir)
            if may_write:
                _rewrite_link_in_file(start_path, id_, rel_path)
            self.last_follow_log_ += f" | SCAN_HIT abs={found_abs} ord={found_ord} rel={rel_path}{note}"
            open_target(found_abs, found_ord)
        else:
            if may_write:
                _rewrite_link_in_file(start_path, id_, "???")
            self.last_follow_log_ += f" | NOT_FOUND{note}"

    @pyqtSlot(str)
    def validateLinks(self, file_path: str) -> None:
        self.last_follow_log_ = f"validateLinks file={file_path}"
        # The whole operation mutates the file, so it has no business outside the sandbox.
        if not self._is_allowed(file_path):
            self.last_follow_log_ += " | ABORT (outside sandbox)"
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            self.last_follow_log_ += " | ABORT (open failed)"
            return

        start_dir = os.path.dirname(os.path.abspath(file_path))
        root_abs = _clean_abs(self.allowed_dir_)

        rx = re.compile(r"\[\[([^\]]+)\]\]")
        changed = kept = broken = 0

        def substitute(m: re.Match) -> str:
            nonlocal changed, kept, broken
            raw = m.group(1)
            if raw.startswith("file:"):
                return m.group(0)
            id_ = raw
            hint_path = ""
            sep = raw.find("::")
            if sep >= 0:
                id_ = raw[:sep]
                hint_path = raw[sep + 2:]
            if not id_ or id_ == "???":
                return m.group(0)

            resolved = ""
            if hint_path and hint_path != "???":
                abs_ = _clean_abs(os.path.join(start_dir, hint_path))
                if os.path.exists(abs_) and _is_inside(abs_, root_abs):
                    if _find_id_ordinal_in_file(abs_, id_) > 0:
                        resolved = hint_path
            if not resolved:
                found = _resolve_id_in_tree(id_, start_dir, root_abs)
                if found:
                    resolved = os.path.relpath(found[0], start_dir)

            new_inner = f"[[{id_}::???]]" if not resolved else f"[[{id_}::{resolved}]]"
            if new_inner == m.group(0):
                kept += 1
            elif not resolved:
                broken += 1
            else:
                changed += 1
            return new_inner

        out = rx.sub(substitute, text)
        self.last_follow_log_ += f" | changed={changed} kept={kept} broken={broken}"

        if out == text:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as fw:
                fw.write(out)
        except OSError:
            pass

    @pyqtSlot(str)
    def exec(self, cmdline: str) -> None:
        CMD_SYS().execute_thread_safe(cmdline, "js", -1, "HTML")

    @pyqtSlot(str, str, result=str)
    def saveInPlace(self, src_path: str, data_url: str) -> str:
        """Overwrite `src_path` with the composite - but copy it aside first.

        Every save puts what the picture was until now next to it under a free
        name: `foo.copy.png`, then `foo.copy01.png`, `foo.copy02.png`, ... The
        working path keeps its name, so whatever points at the picture keeps
        pointing at the current version, and no save destroys the one before.

        The very first copy is therefore the picture as it came - untouched by
        any markup - and that is what the viewer draws over (see `origOf`);
        otherwise the shapes would stack on their own baked-in copies.

        Base64 goes through its own slot rather than `write()` (that one is
        text-only) and rather than a command (a megabyte of base64 in the
        command log helps nobody). Returns the path written, or "" on failure.
        """
        marker = ";base64,"
        i = data_url.find(marker)
        if i < 0:
            return ""
        try:
            blob = base64.b64decode(data_url[i + len(marker):])
        except (ValueError, binascii.Error):
            return ""

        prev = self._free_copy_name(src_path)
        if not prev:
            return ""
        try:
            shutil.copy2(src_path, prev)
            with open(src_path, "wb") as f:
                f.write(blob)
        except OSError:
            return ""

        CMD_SYS().execute_thread_safe(f'export_saved "{src_path}"', "js", -1, "HTML")
        return src_path

    @staticmethod
    def _free_copy_name(src_path: str) -> str:
        """`foo.png` -> first free of `foo.copy.png`, `foo.copy01.png`, ...

        The suffix goes before the extension on purpose: the copy is still a
        picture and has to open like one, in the same viewer as the original.
        """
        base, ext = os.path.splitext(src_path)
        first = base + ".copy" + ext
        if not os.path.exists(first):
            return first
        for n in range(1, 100):
            cand = base + ".copy%02d" % n + ext
            if not os.path.exists(cand):
                return cand
        return ""

    @pyqtSlot(str, result=str)
    def origOf(self, src_path: str) -> str:
        """Return the untouched picture, when a copy of it survives.

        The redline viewer draws over a background. Once a save has overwritten
        the picture with a composite, drawing over `src_path` again would stack
        the shapes on top of their baked-in copies. Loading the first copy
        instead keeps the composition idempotent. `.orig` is the older name for
        the same thing and still wins where it exists.
        """
        backup = src_path + ".orig"
        if os.path.exists(backup):
            return backup
        # Since saves copy aside instead of taking one `.orig`, the untouched
        # picture is the *first* copy ever made - the one without a number.
        base, ext = os.path.splitext(src_path)
        first = base + ".copy" + ext
        return first if os.path.exists(first) else src_path
