#!/usr/bin/env python3
"""apps - the default database of the console: its apps, the external programs it calls
and the external viewers it opens files in.

apps.t2l next to this file is the database itself. When it is missing, apps.py writes it
from DEFAULTS; every record it writes carries `origin: py`. Records a user adds carry
`origin: user` (or nothing) and apps.py never touches them. Whether a program is
installed is not stored - the reader (apps_viewer) asks the system each time.

Attribute ext: = what a record takes, comma separated (extensions, or a directory, a repo, ...); - = nothing.

Usage: apps.py            (writes apps.t2l when it is missing)
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
APPS_T2L = os.path.join(HERE, "apps.t2l")

# (type, [(attribute, value), ...]); repeated attributes are repeated pairs
DEFAULTS = [
    # --- apps of the console ---------------------------------------------------------
    ("app", [("id", "konzole"), ("ext", "-"), ("file", "[[file:clmon]]"), ("start", "clmon"),
             ("description", "panels, tmux, menu; starts the other apps")]),
    ("app", [("id", "dirview"), ("ext", "directory"), ("file", "[[file:../KOUMES_KONZOLE_APPS/dirview.py]]"),
             ("start", "[dir]"), ("start", "[timeax] in the panel bar"), ("start", "--tp1 --run"),
             ("description", "directory browser: git ● ✗ 📝, repos, C++ modules, timeaxis mode; WS cmd_sys")]),
    ("app", [("id", "pindani"), ("ext", "-"), ("file", "[[file:../KOUMES_KONZOLE_APPS/pindani.py]]"),
             ("start", "[pindání]"),
             ("description", "messages between agents (SendMessage) from the transcripts")]),
    ("app", [("id", "apps_viewer"), ("ext", "apps.t2l"), ("file", "[[file:apps_viewer.py]]"), ("start", "[apps] in the panel bar"),
             ("description", "this list: apps, programs, external viewers; watches apps.t2l")]),
    ("app", [("id", "config_view"), ("ext", "config.t2l"), ("file", "[[file:config_view.py]]"), ("start", "[config] in the menu"),
             ("description", "assigns where things are on this machine; watches config.t2l")]),
    ("app", [("id", "viewer"), ("ext", "txt, md, html, png, jpg, svg"), ("file", "[[file:../KOUMES_KONZOLE_APPS/viewer.py]]"),
             ("start", "--tpN <file>"),
             ("description", "file viewer: text with line numbers, md, html; images [more] / [less], click = open")]),
    ("app", [("id", "timeaxis_item_esence"), ("ext", "TIMEAXIS item"), ("file", "[[file:../KOUMES_KONZOLE_APPS/timeaxis_item_esence.py]]"),
             ("start", "dirview in timeaxis mode"),
             ("description", "a TIMEAXIS item in one window: files as in the viewer, [more] / [less], links")]),
    ("app", [("id", "git_list"), ("ext", "directory"), ("file", "[[file:../KOUMES_KONZOLE_APPS/git_list.py]]"),
             ("start", "[git_list] on the panel label"), ("start", "a directory into the viewer"),
             ("description", "a git repo as a tree: ● in git, 📝 changed, ⊗ deleted, ✗ ignored; ✔ ticks, ⊟ / ⊞ folds")]),
    ("app", [("id", "repos"), ("ext", "-"), ("file", "[[file:../KOUMES_KONZOLE_APPS/repos.py]]"),
             ("start", "[repos] in the panel bar"), ("start", "[repos] in dirview"),
             ("description", "all repos of the tree; click = description, again = dirview in p1")]),
    # --- external programs the user works in (not internals the apps call) ----------
    ("tool", [("id", "helix"), ("ext", "*"), ("bin", "hx"), ("use", "editor of every non-binary file (e, --hx)")]),
    # --- external viewers: the first installed one of a kind is used -----------------
    ("viewer_ext", [("kind", "image"), ("ext", "png, jpg, jpeg, gif, webp, bmp, svg, tif, tiff, ico"), ("bin", "eog"), ("use", "an image in full quality")]),
    ("viewer_ext", [("kind", "pdf"), ("ext", "pdf"), ("bin", "evince"),
                    ("use", "a pdf")]),
    ("viewer_ext", [("kind", "web"), ("ext", "html, htm, http, https"), ("bin", "chromium"),
                    ("use", "html and URLs")]),
    ("viewer_ext", [("kind", "video"), ("ext", "mp4, mkv, webm, avi, mov"), ("bin", "vlc"), ("use", "a video")]),
    ("viewer_ext", [("kind", "directory"), ("ext", "directory"), ("bin", "nautilus"),
                    ("use", "a directory in the GNOME file manager")]),
    ("viewer_ext", [("kind", "other"), ("ext", "*"), ("bin", "xdg-open"), ("use", "anything else: the system default")]),
]


def write(path=APPS_T2L):
    """Write the database from DEFAULTS (every record `origin: py`)."""
    out = ["#: Database of the console: apps, external programs, external viewers.",
           "#: origin: py = written by apps.py from its defaults; origin: user = added by hand.",
           "#: Paths are relative to this file.", ""]
    for typ, attrs in DEFAULTS:
        out.append("type: %s" % typ)
        out += ["%s: %s" % kv for kv in attrs]
        out += ["origin: py", ""]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    os.replace(tmp, path)


def ensure(path=APPS_T2L):
    """apps.t2l exists - when not, write it. True = it was written now."""
    if os.path.exists(path):
        return False
    write(path)
    return True


def load(path=APPS_T2L):
    """Records of the database as dicts {attribute: [values]}; missing database = written first."""
    ensure(path)
    recs, rec = [], {}
    try:
        lines = open(path, encoding="utf-8").read().split("\n") + [""]
    except OSError:
        return recs
    for line in lines:
        k, _, v = line.partition(":")
        if not line.strip():
            if rec.get("type"):
                recs.append(rec)
            rec = {}
        elif not line.startswith("#"):
            rec.setdefault(k.strip(), []).append(v.strip())
    return recs


def _exts(rec):
    return [e.strip().lower() for e in ", ".join(rec.get("ext", [])).split(",") if e.strip()]


def bin_for(target, path=APPS_T2L):
    """External viewer for a file, a directory or a URL by the extension list of the
    viewer_ext records: the first installed binary of the record that lists it, else of
    the record with `*`. None when nothing fits."""
    low = target.lower()
    if os.path.isdir(target):
        want = "directory"
    elif "://" in low:
        want = low.split("://", 1)[0]                        # http, https
    else:
        want = os.path.splitext(low)[1].lstrip(".")
    recs = [r for r in load(path) if r.get("type") == ["viewer_ext"]]
    for star in (False, True):
        for r in recs:
            if (want in _exts(r)) if not star else ("*" in _exts(r)):
                b = next((b for b in r.get("bin", []) if shutil.which(b)), None)
                if b:
                    return b
    return None


def editor(path=APPS_T2L):
    """The editor of non-binary files: the tool record with ext `*`, first installed binary."""
    for r in load(path):
        if r.get("type") == ["tool"] and "*" in _exts(r):
            b = next((b for b in r.get("bin", []) if shutil.which(b)), None)
            if b:
                return b
    return None


if __name__ == "__main__":
    print("written" if ensure(sys.argv[1] if len(sys.argv) > 1 else APPS_T2L) else "exists")
