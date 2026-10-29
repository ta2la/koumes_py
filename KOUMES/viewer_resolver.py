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
"""viewer_resolver - resolve which viewer HTML renders a file.

Python port of the viewer-resolution helpers from the C++ predecessor's Main.cpp
(findViewerHtml_, readViewerFromT2l_, readAllViewersFromConfig_, ...).

Resolution rules (highest precedence first):
  1. In-file directive (only for .t2l files): `type: viewer / name: X`
  2. Walk config.t2l up from file's dir to the filesystem root; at each level
     check `.t2l/config.t2l` (new pattern) then plain `config.t2l` (backward
     compat). Each `type: viewer_ext / ext: <ext> / viewer: <name>` block
     that matches contributes a viewer name.

Duplicates are removed (first occurrence wins).

The walk does not stop at the sandbox root. The sandbox says which files the
app hands out; it does not say where the rules for rendering them live. Those
sit in `.t2l/` dirs of the info-system tree, typically above any one sandbox -
a file opened outside the sandbox still gets the viewer its tree prescribes.
"""

import os
from typing import List


# Extra fallback search paths appended after the sandbox walk-up. Set from
# main.py so koumes can reuse the C++ predecessor's dirview/ HTMLs during transition.
_EXTRA_FALLBACK_DIRS: list = []


def set_extra_fallback_dirs(dirs: list) -> None:
    global _EXTRA_FALLBACK_DIRS
    _EXTRA_FALLBACK_DIRS = [os.path.normpath(os.path.abspath(d)) for d in dirs if os.path.isdir(d)]


def _walk_up_dirs(start_dir: str):
    """Yield start_dir and every parent up to the filesystem root."""
    cur = os.path.normpath(os.path.abspath(start_dir))
    while cur:
        yield cur
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            break
        cur = parent


#: A viewer is a program, not a page to read, and its name says so: `txt` lives
#: in `txt.exe.html`. The plain `<name>.html` is tried second so trees written
#: before the convention keep working - same two-step as `.t2l/config.t2l` and
#: plain `config.t2l`.
VIEWER_SUFFIXES = (".exe.html", ".html")


def viewer_file_names(viewer_name: str) -> List[str]:
    """`txt` -> ['txt.exe.html', 'txt.html'], in the order they are tried."""
    return [viewer_name + suffix for suffix in VIEWER_SUFFIXES]


def find_viewer_html(dir_path: str, root: str, viewer_name: str) -> str:
    """Walk up from dir_path to the filesystem root, look for `.t2l/<name>` (new)
    or `<name>` (compat). `root` is not a cutoff - see the module docstring.
    Falls back to _EXTRA_FALLBACK_DIRS (e.g. the C++ predecessor's dirview/) when walk-up fails."""
    if not viewer_name:
        return ""
    names = viewer_file_names(viewer_name)
    for cur in _walk_up_dirs(dir_path):
        # The hidden dir wins over the plain one on the same level, and the
        # `.exe.html` name wins over the bare one in the same dir.
        for name in names:
            in_hidden = os.path.join(cur, ".t2l", name)
            if os.path.isfile(in_hidden):
                return in_hidden
        for name in names:
            candidate = os.path.join(cur, name)
            if os.path.isfile(candidate):
                return candidate

    for extra in _EXTRA_FALLBACK_DIRS:
        for name in names:
            candidate = os.path.join(extra, name)
            if os.path.isfile(candidate):
                return candidate
            in_hidden = os.path.join(extra, ".t2l", name)
            if os.path.isfile(in_hidden):
                return in_hidden

    return ""


def read_viewer_from_t2l(file_path: str) -> str:
    """Parse a `.t2l` file; return `name:` value from the first `type: viewer` record."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    in_viewer = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            in_viewer = False
            continue
        if line.startswith("#"):
            continue
        c = line.find(":")
        if c < 0:
            continue
        key = line[:c].strip()
        val = line[c + 1:].strip()
        if key == "type" and val == "viewer":
            in_viewer = True
            continue
        if in_viewer and key == "name":
            return val
    return ""


def read_viewer_name(dir_path: str) -> str:
    """Read `<dirname>.t2l` for a dir-level viewer directive."""
    base = os.path.basename(os.path.normpath(dir_path))
    if not base:
        return ""
    return read_viewer_from_t2l(os.path.join(dir_path, f"{base}.t2l"))


def ext_candidates(file_path: str) -> List[str]:
    """Extensions a file answers to, most specific first: `a.diag.t2l` ->
    ['diag.t2l', 't2l']. A config may name the double one (`ext: diag.t2l`)
    to give a kind of t2l file its own viewer without a directive inside."""
    # A leading dot is a hidden name, not an extension (`.bashrc` has none).
    parts = os.path.basename(file_path).lower().lstrip(".").split(".")[1:]
    return [".".join(parts[i:]) for i in range(len(parts)) if parts[i]]


def _read_config_blocks(cfg_path: str, ext, require_browse: bool = False) -> List[str]:
    """Parse a config.t2l; return viewer names from viewer_ext blocks matching ext.

    `ext` is one extension or a list from `ext_candidates()`; with a list, the
    blocks for the more specific extension come first."""
    exts = [ext] if isinstance(ext, str) else list(ext)
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    found: List[tuple] = []
    in_block = False
    ext_matches = -1
    browse_support = False
    viewer = ""

    def flush() -> None:
        nonlocal in_block, ext_matches, browse_support, viewer
        if in_block and ext_matches >= 0 and viewer and (not require_browse or browse_support):
            found.append((ext_matches, viewer))
        in_block = False
        ext_matches = -1
        browse_support = False
        viewer = ""

    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("#"):
            continue
        c = line.find(":")
        if c < 0:
            continue
        k = line[:c].strip()
        v = line[c + 1:].strip()
        if k == "type" and v == "viewer_ext":
            flush()
            in_block = True
            continue
        if not in_block:
            continue
        if k == "ext" and v.lower() in exts:
            i = exts.index(v.lower())
            ext_matches = i if ext_matches < 0 else min(ext_matches, i)
        if k == "viewer":
            viewer = v
        if k == "sys__browse_support" and v in ("true", "1", "yes"):
            browse_support = True
    flush()
    found.sort(key=lambda t: t[0])   # stable: file order within one extension
    return [v for _, v in found]


def read_all_viewers_from_config(cfg_path: str, ext: str) -> List[str]:
    return _read_config_blocks(cfg_path, ext, require_browse=False)


def read_browse_viewers_from_config(cfg_path: str, ext: str) -> List[str]:
    return _read_config_blocks(cfg_path, ext, require_browse=True)


def _walk_up_configs(file_path: str, root: str, ext, require_browse: bool) -> List[str]:
    """`root` is not a cutoff - the walk goes to the filesystem root, see the
    module docstring. It stays in the signature because callers pass the
    sandbox root and the nearest config still wins."""
    if not ext:
        return []
    out: List[str] = []
    for dir_ in _walk_up_dirs(os.path.dirname(os.path.abspath(file_path))):
        for cfg in (os.path.join(dir_, ".t2l", "config.t2l"), os.path.join(dir_, "config.t2l")):
            if os.path.isfile(cfg):
                for v in _read_config_blocks(cfg, ext, require_browse=require_browse):
                    if v not in out:
                        out.append(v)
    return out


def read_browse_viewers(file_path: str, root: str) -> List[str]:
    return _walk_up_configs(file_path, root, ext_candidates(file_path), require_browse=True)


def read_all_viewers(file_path: str, root: str) -> List[str]:
    out: List[str] = []
    if file_path.lower().endswith(".t2l"):
        in_file = read_viewer_from_t2l(file_path)
        if in_file:
            out.append(in_file)
    for v in _walk_up_configs(file_path, root, ext_candidates(file_path), require_browse=False):
        if v not in out:
            out.append(v)
    return out


#: Names of Qt viewers from the deployment config (see qt_viewer.py). Set from
#: main.py; kept here as plain names so this module stays free of Qt.
_QT_VIEWERS: set = set()


def set_qt_viewers(names) -> None:
    global _QT_VIEWERS
    _QT_VIEWERS = set(names)


def find_viewer_target(dir_path: str, root: str, viewer_name: str) -> str:
    """What a document panel loads for viewer `viewer_name`: `qt:<name>` for a
    Qt viewer, else the HTML from find_viewer_html(). Only p1 / p2 host a Qt
    viewer, so only their paths call this; dir and left keep the HTML lookup."""
    if viewer_name in _QT_VIEWERS:
        return "qt:" + viewer_name
    return find_viewer_html(dir_path, root, viewer_name)


def read_viewer_for_ext(file_path: str, root: str) -> str:
    all_ = read_all_viewers(file_path, root)
    return all_[0] if all_ else ""
