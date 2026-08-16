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

Python port of the viewer-resolution helpers from APPS/AI_T2LS/Main.cpp
(findViewerHtml_, readViewerFromT2l_, readAllViewersFromConfig_, ...).

Resolution rules (highest precedence first):
  1. In-file directive (only for .t2l files): `type: viewer / name: X`
  2. Walk config.t2l up from file's dir toward sandbox root; at each level
     check `.t2l/config.t2l` (new pattern) then plain `config.t2l` (backward
     compat). Each `type: viewer_ext / ext: <ext> / viewer: <name>` block
     that matches contributes a viewer name.

Duplicates are removed (first occurrence wins).
"""

import os
from pathlib import Path
from typing import List


# Extra fallback search paths appended after the sandbox walk-up. Set from
# main.py so koumes can reuse the C++ ai.t2ls dirview/ HTMLs during transition.
_EXTRA_FALLBACK_DIRS: list = []


def set_extra_fallback_dirs(dirs: list) -> None:
    global _EXTRA_FALLBACK_DIRS
    _EXTRA_FALLBACK_DIRS = [os.path.normpath(os.path.abspath(d)) for d in dirs if os.path.isdir(d)]


def find_viewer_html(dir_path: str, root: str, viewer_name: str) -> str:
    """Walk up from dir_path to root, look for `.t2l/<name>.html` (new) or `<name>.html` (compat).
    Falls back to _EXTRA_FALLBACK_DIRS (e.g. C++ ai.t2ls dirview/) when walk-up fails."""
    if not viewer_name:
        return ""
    cur = os.path.normpath(os.path.abspath(dir_path))
    base = os.path.normpath(os.path.abspath(root))
    while True:
        in_hidden = os.path.join(cur, ".t2l", f"{viewer_name}.html")
        if os.path.isfile(in_hidden):
            return in_hidden
        candidate = os.path.join(cur, f"{viewer_name}.html")
        if os.path.isfile(candidate):
            return candidate
        if cur == base or not cur or cur == os.sep:
            break
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            break
        if not parent.startswith(base):
            break
        cur = parent

    for extra in _EXTRA_FALLBACK_DIRS:
        candidate = os.path.join(extra, f"{viewer_name}.html")
        if os.path.isfile(candidate):
            return candidate
        in_hidden = os.path.join(extra, ".t2l", f"{viewer_name}.html")
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


def _read_config_blocks(cfg_path: str, ext: str, require_browse: bool = False) -> List[str]:
    """Parse a config.t2l; return viewer names from viewer_ext blocks matching ext."""
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    out: List[str] = []
    in_block = False
    ext_matches = False
    browse_support = False
    viewer = ""

    def flush() -> None:
        nonlocal in_block, ext_matches, browse_support, viewer
        if in_block and ext_matches and viewer and (not require_browse or browse_support):
            out.append(viewer)
        in_block = False
        ext_matches = False
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
        if k == "ext" and v.lower() == ext:
            ext_matches = True
        if k == "viewer":
            viewer = v
        if k == "sys__browse_support" and v in ("true", "1", "yes"):
            browse_support = True
    flush()
    return out


def read_all_viewers_from_config(cfg_path: str, ext: str) -> List[str]:
    return _read_config_blocks(cfg_path, ext, require_browse=False)


def read_browse_viewers_from_config(cfg_path: str, ext: str) -> List[str]:
    return _read_config_blocks(cfg_path, ext, require_browse=True)


def _walk_up_configs(file_path: str, root: str, ext: str, require_browse: bool) -> List[str]:
    if not ext:
        return []
    root_c = os.path.normpath(os.path.abspath(root))
    dir_ = os.path.dirname(os.path.abspath(file_path))
    out: List[str] = []
    while dir_ and dir_.startswith(root_c):
        for cfg in (os.path.join(dir_, ".t2l", "config.t2l"), os.path.join(dir_, "config.t2l")):
            if os.path.isfile(cfg):
                for v in _read_config_blocks(cfg, ext, require_browse=require_browse):
                    if v not in out:
                        out.append(v)
        if dir_ == root_c:
            break
        parent = os.path.dirname(dir_)
        if not parent or parent == dir_:
            break
        dir_ = parent
    return out


def read_browse_viewers(file_path: str, root: str) -> List[str]:
    ext = Path(file_path).suffix.lstrip(".").lower()
    return _walk_up_configs(file_path, root, ext, require_browse=True)


def read_all_viewers(file_path: str, root: str) -> List[str]:
    out: List[str] = []
    if file_path.lower().endswith(".t2l"):
        in_file = read_viewer_from_t2l(file_path)
        if in_file:
            out.append(in_file)
    ext = Path(file_path).suffix.lstrip(".").lower()
    for v in _walk_up_configs(file_path, root, ext, require_browse=False):
        if v not in out:
            out.append(v)
    return out


def read_viewer_for_ext(file_path: str, root: str) -> str:
    all_ = read_all_viewers(file_path, root)
    return all_[0] if all_ else ""
