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
"""Help resolution - which document answers "what am I looking at".

One name for both cases: `<jmeno>.help.md` lies next to the thing it explains,
and for a directory "next to" means inside it - the same shape the info system
already uses for `JOBS/JOBS.t2l`.

    08_27_idea_platform/
    |-- 08_27_idea_platform.help.md   <- help of the directory
    |-- status.t2l
    `-- status.t2l.help.md            <- help of the file

Three layers, narrowest first:

  1. the file    `<name.ext>.help.md` beside it
  2. its kind    `type: help_ext / ext: <ext> / help: <file>` in a config.t2l,
                 walked up exactly like viewers - one document then answers
                 "what is a .t2l file" for the whole tree
  3. the place   `<dir>/<dirname>.help.md`, walked up to the sandbox root

`.help.html` beats `.help.md` at every level: an HTML page is something somebody
built on purpose, markdown is what gets written by hand.

A bare `help.md` in a directory is still honoured, one step after the named
form - trees written before this convention keep working, the same way viewer
resolution keeps reading plain `config.t2l` next to `.t2l/config.t2l`.
"""

import os
from pathlib import Path
from typing import List

#: HTML first - see module docstring.
_SUFFIXES = (".help.html", ".help.md")

#: The pre-convention name, accepted at every level after the named form.
_LEGACY = ("help.html", "help.md")


def _first_file(candidates) -> str:
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return ""


def _sidecar_of(base_path: str) -> str:
    """`/x/status.t2l` -> `/x/status.t2l.help.md` (or .help.html)."""
    return _first_file(base_path + s for s in _SUFFIXES)


def help_of_dir(dir_path: str) -> str:
    """The one directory's own help, without walking anywhere."""
    d = os.path.normpath(os.path.abspath(dir_path))
    name = os.path.basename(d)
    named = [os.path.join(d, name + s) for s in _SUFFIXES] if name else []
    return _first_file(named + [os.path.join(d, l) for l in _LEGACY])


def _walk_up_dirs(start_dir: str, root: str) -> List[str]:
    """start_dir, its parents, up to and including the sandbox root."""
    cur = os.path.normpath(os.path.abspath(start_dir))
    base = os.path.normpath(os.path.abspath(root))
    out: List[str] = []
    while cur and cur.startswith(base):
        out.append(cur)
        if cur == base:
            break
        parent = os.path.dirname(cur)
        if not parent or parent == cur:
            break
        cur = parent
    return out


def _read_help_ext_blocks(cfg_path: str, ext: str) -> List[str]:
    """Parse a config.t2l; return `help:` values from help_ext blocks for ext.

    Deliberately a twin of viewer_resolver._read_config_blocks rather than a
    generalisation of it: the two answer different questions and the day one
    grows a field the other must not have, a shared parser is in the way.
    """
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    out: List[str] = []
    in_block = False
    ext_matches = False
    help_file = ""

    def flush() -> None:
        nonlocal in_block, ext_matches, help_file
        if in_block and ext_matches and help_file:
            out.append(help_file)
        in_block = False
        ext_matches = False
        help_file = ""

    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            flush()          # empty line ends a record - see t2l format
            continue
        if line.startswith("#"):
            continue
        c = line.find(":")
        if c < 0:
            continue
        k = line[:c].strip()
        v = line[c + 1:].strip()
        if k == "type" and v == "help_ext":
            flush()
            in_block = True
            continue
        if not in_block:
            continue
        if k == "ext" and v.lstrip(".").lower() == ext:
            ext_matches = True
        if k == "help":
            help_file = v
    flush()
    return out


def help_of_ext(file_path: str, root: str) -> str:
    """Help for the file's kind, from the nearest config.t2l that names one."""
    ext = Path(file_path).suffix.lstrip(".").lower()
    if not ext:
        return ""
    for d in _walk_up_dirs(os.path.dirname(os.path.abspath(file_path)), root):
        for cfg in (os.path.join(d, ".t2l", "config.t2l"),
                    os.path.join(d, "config.t2l")):
            if not os.path.isfile(cfg):
                continue
            for value in _read_help_ext_blocks(cfg, ext):
                if os.path.isabs(value):
                    hit = _first_file([value])
                else:
                    # Relative to the config's own level, hidden dir included -
                    # a help kept next to config.t2l is kept in `.t2l/` too.
                    hit = _first_file([os.path.join(d, value),
                                       os.path.join(d, ".t2l", value)])
                if hit:
                    return hit
    return ""


def find_help_for_dir(dir_path: str, root: str) -> str:
    """Help of a place: this directory, else the nearest parent that has one."""
    for d in _walk_up_dirs(dir_path, root):
        hit = help_of_dir(d)
        if hit:
            return hit
    return ""


def find_help_for_file(file_path: str, root: str) -> str:
    """Help of a document: itself, then its kind, then the place it lies in."""
    if not file_path:
        return ""
    return (_sidecar_of(file_path)
            or help_of_ext(file_path, root)
            or find_help_for_dir(os.path.dirname(os.path.abspath(file_path)),
                                 root))


def root_help_path(root: str) -> str:
    """Where a tree's top-level help belongs when it has to be created."""
    r = os.path.normpath(os.path.abspath(root))
    return os.path.join(r, os.path.basename(r) + ".help.md")
