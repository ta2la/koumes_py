#!/usr/bin/env python3
"""config - where things are on this machine: paths of the console that no code may know.

config.t2l next to this file is not in git. When it is missing, config.py writes it empty:
one `places` record with nothing assigned. An empty value = the feature is off and its
button is not shown. The console runs without anything assigned, the app config_view
assigns the rest.

Records: `places` (one), `koumes` (one per instance, id = name of its button), `diag` (one).

Key of an assignment: `<attribute>` in places, `<id>.<attribute>` in koumes, `diag.<attribute>`.

Usage: config.py            (writes config.t2l when it is missing)
"""

import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
CONFIG_T2L = os.path.join(HERE, "config.t2l")
HOME = os.path.expanduser("~")

# (type of record, attribute, kind, what it is for as markdown); kind: dir, file, text
FIELDS = [
    ("places", "tree", "dir", """The directory tree you work in.

- **Used by:** [repos] searches it for git repos, [dir] opens dirview here
- **Not set:** your home directory; works, but [repos] searches all of it and can be slow
"""),
    ("places", "code_root", "dir", """The directory that holds your source repos.

- **Used by:** dirview only
- **In its root:** only the repos, with icons 🈴 C++, 🅰️ apps, 🟥 other
- **Inside a repo:** C++ modules (a directory with a .pro file) get 🧩 and show which other modules use them
- **Not set:** dirview is a plain directory listing, you lose only these marks
- **For whom:** a tree organized as repos of modules
"""),
    ("places", "agents", "file", """The list of agents, a file like projects.conf.

- **Format:** a block per agent with `path`, `name`, `icon`, optionally `cmd` (another command than claude)
- **Used by:** the agent list and [pindání]: names, icons, order
- **Rule:** only agents listed here can be started and switched
- **Not set:** the agent list is empty; panels and apps still work
"""),
    ("places", "timeaxis", "dir", """A directory of dated work items.

- **Format:** `<year>_qN/MM_DD_name`
- **Used by:** [timeax] shows them in dirview as one list, newest first, 25 at a time
- **Selected item:** opens in the panel to the right
- **Aicom:** items `MM_DD_name.AICOM` hold dated files shared with agents; [aicom] lists them, newest at the bottom
- **Not set:** no [timeax], [timeaxis] and [aicom] buttons
"""),
    ("places", "avatars", "dir", """Pictures of agents.

- **Format:** `<NAME>.png`, the name in capitals, e.g. `KOUMES.png`
- **Special:** `WORKERS.png` for T1 to T6, `PARTA.png` when no agent is shown
- **Used by:** the picture next to the agent list, the testing dialog of `--in_test`
- **Not set:** no pictures, nothing else changes
"""),
    ("places", "workers", "dir", """The directory with worker slots.

- **Format:** subdirectories `TEMP1` to `TEMP6`
- **What they are:** disposable agents T1 to T6, they start clean, without a previous context
- **Used by:** the agent list, after the named agents
- **Not set:** no workers
"""),
    ("places", "panel_port", "text", """The first port for programs in panels.

- **Used by:** dirview and other programs with a WebSocket take the first free port above it
- **Not set:** 54330
"""),
    ("places", "koumes_port", "text", """The port of a koumes that was started without `--port`.

- **Used by:** the console, to find out which port a running koumes listens on
- **Not set:** 54325
"""),
    ("koumes", "code", "dir", """The code of this koumes instance.

- **Format:** the directory with the module `KOUMES`
- **Why here:** it starts from this directory, so two instances can run different versions
"""),
    ("koumes", "root", "dir", """The tree this instance opens.

- **Sandbox:** koumes reads and writes only inside it
- **Same tree twice:** no second copy starts, the button only places the running window next to the terminal
"""),
    ("koumes", "port", "text", """Its WebSocket port, where commands are sent.

- **Rule:** each instance needs its own
- **Port taken:** the button only reports it
"""),
    ("koumes", "python", "file", """The python that runs this instance.

- **Typically:** `.venv/bin/python` in its code directory, koumes needs PyQt6
- **Empty:** the python of the console; works only if it has those libraries
"""),
    ("diag", "script", "file", """`diag_view.py`, the diagram viewer.

- **Runs:** in its own window beside the terminal, a change in its code does not restart koumes
- **Not set:** no [diag] button
"""),
    ("diag", "file", "file", """The diagram (`.diag.t2l`) that [diag] opens at start.
"""),
    ("diag", "python", "file", """The python that runs the viewer.

- **Needs:** PyQt6
- **Empty:** the python of the console
"""),
]
HEAD = ["#: Places of this machine. Not in git. Paths may start with ~.",
        "#: An empty value = the feature is off or the default applies.", ""]


def fields(typ):
    return [f for f in FIELDS if f[0] == typ]


def write(path=CONFIG_T2L):
    """Write the empty database."""
    out = HEAD + ["type: places"] + ["%s:" % f[1] for f in fields("places")] + ["origin: py", ""]
    _save(path, out)


def ensure(path=CONFIG_T2L):
    """config.t2l exists - when not, write it. True = it was written now."""
    if os.path.exists(path):
        return False
    write(path)
    return True


def _save(path, lines):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, path)


def load(path=CONFIG_T2L):
    """Records as dicts {attribute: value}; a missing database is written first."""
    ensure(path)
    recs, rec = [], {}
    try:
        lines = open(path, encoding="utf-8").read().split("\n") + [""]
    except OSError:
        return recs
    for line in lines:
        if not line.strip():
            if rec.get("type"):
                recs.append(rec)
            rec = {}
        elif not line.startswith("#"):
            k, _, v = line.partition(":")
            rec[k.strip()] = v.strip()
    return recs


def records(typ, path=CONFIG_T2L):
    return [r for r in load(path) if r.get("type") == typ]


def expand(value):
    return os.path.expanduser(value) if value else ""


def place(name, path=CONFIG_T2L):
    """Path assigned in the places record, expanded; "" when it is off."""
    rec = next(iter(records("places", path)), {})
    return expand(rec.get(name, ""))


def number(name, default, path=CONFIG_T2L):
    """Number assigned in the places record; default when none is."""
    v = place(name, path)
    return int(v) if v.isdigit() else default


def tree(path=CONFIG_T2L):
    """The tree to work in; the home directory when none is assigned."""
    return place("tree", path) or HOME


def _span(lines, typ, rid):
    """Line range [a, b) of the record of that type (and id, when given); None = not found."""
    a = 0
    for i in range(len(lines) + 1):
        if i == len(lines) or not lines[i].strip():
            block = lines[a:i]
            if ("type: %s" % typ) in block and (not rid or ("id: %s" % rid) in block):
                return a, i
            a = i + 1
    return None


def assign(key, value, path=CONFIG_T2L):
    """Assign a value by key; None = done, else what is wrong."""
    rid, _, attr = key.rpartition(".")
    typ = "places" if not rid else "diag" if rid == "diag" else "koumes"
    if attr not in [f[1] for f in fields(typ)]:
        return "unknown key: %s" % key
    ensure(path)
    lines = open(path, encoding="utf-8").read().split("\n")
    span = _span(lines, typ, "" if typ != "koumes" else rid)
    if span is None:
        return "no such record: %s" % rid
    a, b = span
    new = ("%s: %s" % (attr, value)) if value else "%s:" % attr
    hit = next((i for i in range(a, b) if lines[i].partition(":")[0].strip() == attr), None)
    if hit is None:
        lines.insert(b, new)
    else:
        lines[hit] = new
    for i in range(a, b):
        if lines[i] == "origin: py":
            lines[i] = "origin: user"              # assigned by hand from now on
    _save(path, lines)
    return None


def add(typ, rid="", path=CONFIG_T2L):
    """A new empty record of type koumes / diag; None = done, else what is wrong."""
    ensure(path)
    lines = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
    if _span(lines, typ, rid):
        return "already there: %s" % (rid or typ)
    rec = ["", "type: %s" % typ] + (["id: %s" % rid] if rid else [])
    _save(path, lines + rec + ["%s:" % f[1] for f in fields(typ)] + ["origin: user", ""])
    return None


if __name__ == "__main__":
    print("written" if ensure(sys.argv[1] if len(sys.argv) > 1 else CONFIG_T2L) else "exists")
