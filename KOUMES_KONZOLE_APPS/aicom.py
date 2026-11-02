#!/usr/bin/env python3
"""aicom - shared channel of a person and an agent, kept in the timeaxis.

An aicom is a timeaxis item <year>_qN/MM_DD_name.AICOM. Its items are files named
YYYY_MM_DD_HH_MM_SS_name.ext: md, pictures, anything. Writing goes to the last aicom.
remarks is the same thing with items MM_DD_name.REMARKS: --remarks selects it.

Usage: aicom.py [--remarks] last | find | list | new [NAME] | add FILE [NAME] | write NAME (text on stdin)
       | paste [NAME] | copy [FILE] | link URL [NAME] [--clip] (text on stdin, optional)
"""

import datetime
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "KOUMES_KONZOLE"))
import config  # noqa: E402

STATE = "aicom.t2l"               # in the aicom: records type: shrink / file: name of an item
WHOLE = "."                       # that record with this name: the whole aicom differs from its default
RE_Q = re.compile(r"^(\d{4})_q[1-4]$")
AICOM = ".AICOM"
LINKS = ".REMARKS"
RE_AICOM = re.compile(r"^\d\d_\d\d_.+(\.AICOM|\.REMARKS)$")
RE_STAMP = re.compile(r"^(\d{4})_(\d\d)_(\d\d)_(\d\d)_(\d\d)_(\d\d)_")
IMG_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif"}
MIME_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


# =============================================================================
def root():
    """AICOM_TIMEAXIS replaces the timeaxis of config (trial runs)."""
    return os.environ.get("AICOM_TIMEAXIS") or config.place("timeaxis")


def dirs(kind=AICOM):
    """All aicoms of a kind, oldest first."""
    out = []
    base = root()
    if not base or not os.path.isdir(base):
        return out
    for q in os.listdir(base):
        if not RE_Q.match(q) or not os.path.isdir(os.path.join(base, q)):
            continue
        for n in os.listdir(os.path.join(base, q)):
            if RE_AICOM.match(n) and n.endswith(kind) and os.path.isdir(os.path.join(base, q, n)):
                out.append((q, n))
    return [os.path.join(base, q, n) for q, n in sorted(out)]


def new(name="", kind=AICOM):
    """A new aicom dated today; the one that already exists is returned."""
    base = root()
    if not base:
        raise OSError("timeaxis is not set in config")
    now = datetime.datetime.now()
    d = os.path.join(base, "%d_q%d" % (now.year, (now.month - 1) // 3 + 1),
                     "%02d_%02d_%s%s" % (now.month, now.day, name or kind[1:].lower(), kind))
    os.makedirs(d, exist_ok=True)
    return d


def last(kind=AICOM):
    """The aicom to write to: the newest one, a new one when there is none."""
    d = dirs(kind)
    return d[-1] if d else new("", kind)


def older(d, n):
    """Up to n aicoms of the kind of d older than d, newest first."""
    kind = AICOM if d.endswith(AICOM) else LINKS
    all_ = dirs(kind)
    return all_[:all_.index(d)][::-1][:n] if d in all_ else []


def files(d):
    """All items of one aicom, oldest first. A picture of an md item is part of that item."""
    names = set(os.listdir(d))
    return [os.path.join(d, n) for n in sorted(names)
            if not n.startswith(".") and n != STATE and os.path.isfile(os.path.join(d, n))
            and not (os.path.splitext(n)[1].lower() in IMG_MIME
                     and os.path.splitext(n)[0] + ".md" in names)]


def items(kind=AICOM):
    """The items of the last aicom of a kind; nothing is created."""
    d = dirs(kind)
    return files(d[-1]) if d else []


def is_aicom(path):
    """Is the path an aicom, or a file in one?"""
    d = path if os.path.isdir(path) else os.path.dirname(path)
    return bool(RE_AICOM.match(os.path.basename(d)))


def stamp(path):
    """Date and time of an item from its name: 2026-10-31 15:33:49; "" when it has none."""
    m = RE_STAMP.match(os.path.basename(path))
    return "%s-%s-%s %s:%s:%s" % m.groups() if m else ""


def from_item(path):
    """Items of its aicom from this one to the oldest, newest first; an aicom: from the newest."""
    d = path if os.path.isdir(path) else os.path.dirname(path)
    all_ = files(d)[::-1]
    return all_[all_.index(path):] if path in all_ else all_


def shrunk(d):
    """Names of the items of aicom d shown shrunk."""
    try:
        with open(os.path.join(d, STATE), encoding="utf-8") as f:
            return {ln.split(":", 1)[1].strip() for ln in f if ln.startswith("file:")}
    except OSError:
        return set()


def toggle(path):
    """Shrinks or expands an item, kept in the t2l of its aicom."""
    d, name = os.path.split(path)
    names = shrunk(d) ^ {name}
    tmp = os.path.join(d, STATE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("".join("type: shrink\nfile: %s\n\n" % n for n in sorted(names)))
    os.replace(tmp, os.path.join(d, STATE))


def target(name, kind=AICOM):
    """A free path in the last aicom, the name prepended with date and time."""
    base = os.path.basename(name).replace(" ", "_")
    stem, ext = os.path.splitext(base)
    d = last(kind)
    now = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    path = os.path.join(d, "%s_%s%s" % (now, stem, ext))
    i = 2
    while os.path.exists(path):
        path = os.path.join(d, "%s_%s_%d%s" % (now, stem, i, ext))
        i += 1
    return path


def add(path, name="", kind=AICOM):
    """Moves a file into the last aicom."""
    to = target(name + os.path.splitext(path)[1] if name else path, kind)
    shutil.move(path, to)
    return to


def write(name, text, kind=AICOM):
    """A new md item in the last aicom."""
    to = target(name if os.path.splitext(name)[1] else name + ".md", kind)
    with open(to, "w", encoding="utf-8") as f:
        f.write(text)
    return to


# =============================================================================
def clip_tools():
    """(types, read of a type, write of a type); Wayland first, xclip when it does not answer."""
    out = []
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        out.append((["wl-paste", "--list-types"], ["wl-paste", "--no-newline", "--type"],
                    ["wl-copy", "--type"]))
    if shutil.which("xclip"):
        out.append((["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                    ["xclip", "-selection", "clipboard", "-o", "-t"],
                    ["xclip", "-selection", "clipboard", "-i", "-t"]))
    return out


def clip_read():
    """What is in the clipboard: (type, bytes), a picture before text; none when empty."""
    for types, read, _ in clip_tools():
        try:
            r = subprocess.run(types, capture_output=True, timeout=5)
            if r.returncode:
                continue
            have = r.stdout.decode("utf-8", "replace").split()
            mime = next((m for m in MIME_EXT if m in have), None) \
                or next((m for m in ("text/plain;charset=utf-8", "UTF8_STRING", "text/plain")
                         if m in have), None)
            if not mime:
                continue
            r = subprocess.run(read + [mime], capture_output=True, timeout=5)
            if r.returncode == 0 and r.stdout:
                return mime, r.stdout
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def link(url, name="", text="", kind=LINKS, clip=False):
    """One item from its parts: a link, text and the clipboard; the name defaults to the host.
    A picture from the clipboard lies next to the md under the same name."""
    host = re.sub(r"^\w+://(www\.)?", "", url).split("/")[0]
    body = url + "\n" + ("\n" + text if text else "")
    to = write(name or host.replace(".", "_"), body, kind)
    got = clip_read() if clip else None
    if got:
        mime, data = got
        if mime in MIME_EXT:
            pic = os.path.splitext(to)[0] + MIME_EXT[mime]
            with open(pic, "wb") as f:
                f.write(data)
            body += "\n![](%s)\n" % os.path.basename(pic)
        else:
            body += "\n" + data.decode("utf-8", "replace") + "\n"
        with open(to, "w", encoding="utf-8") as f:
            f.write(body)
    return to


def paste(name="clip", kind=AICOM):
    """The clipboard as a new item: text = md, picture = its format. Returns its path."""
    got = clip_read()
    if not got:
        return None
    mime, data = got
    to = target((name or "clip") + MIME_EXT.get(mime, ".md"), kind)
    with open(to, "wb") as f:
        f.write(data)
    return to


def copy(path):
    """An item into the clipboard: a picture as a picture, anything else as text."""
    mime = IMG_MIME.get(os.path.splitext(path)[1].lower(), "text/plain")
    for _, _, put in clip_tools():
        try:
            with open(path, "rb") as f:
                # the tool stays behind to serve the clipboard: its output must not hold a pipe
                r = subprocess.run(put + [mime], stdin=f, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=5)
            if r.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


# =============================================================================
def main():
    a = sys.argv[1:]
    kind = LINKS if "--remarks" in a else AICOM
    clip = "--clip" in a
    a = [x for x in a if x not in ("--remarks", "--clip")]
    cmd = a[0] if a else ""
    arg = a[1] if len(a) > 1 else ""
    if cmd == "last":
        print(last(kind))
    elif cmd == "find":
        print("\n".join(dirs(kind)[-1:]))
    elif cmd == "list":
        print("\n".join(items(kind)))
    elif cmd == "new":
        print(new(arg, kind))
    elif cmd == "add" and arg:
        print(add(arg, a[2] if len(a) > 2 else "", kind))
    elif cmd == "write" and arg:
        print(write(arg, sys.stdin.read(), kind))
    elif cmd == "link" and arg:
        print(link(arg, a[2] if len(a) > 2 else "", "" if sys.stdin.isatty() else sys.stdin.read(), LINKS, clip))
    elif cmd == "paste":
        to = paste(arg, kind)
        if not to:
            sys.exit("aicom: the clipboard is empty")
        print(to)
    elif cmd == "copy":
        all_ = items(kind)
        path = arg or (all_[-1] if all_ else "")
        if not path or not copy(path):
            sys.exit("aicom: nothing went to the clipboard")
        print(path)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
