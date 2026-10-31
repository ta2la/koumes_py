#!/usr/bin/env python3
"""stamp - one click writes a record with the exact time into a dated t2l file.

Records `type: stamp` in KOUMES_KONZOLE/config.t2l, each one is a button in the panel bar:
  id: label of the button
  file: target; {monday} = YY_MM_DD of this week's Monday. A missing file is an error.
  section: start of the line that opens a day, {day} = a word of days
  days: seven words, Monday first
  record: type of the written record
  anything else: copied to the record

The record goes to the end of today's section. Without section: to the end of the file.

Usage: stamp.py ID
"""

import datetime
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "KOUMES_KONZOLE"))
import config  # noqa: E402

OWN = ("type", "id", "file", "section", "days", "record", "origin")


def target(rec, now):
    monday = (now - datetime.timedelta(days=now.weekday())).strftime("%y_%m_%d")
    return config.expand(rec.get("file", "").replace("{monday}", monday))


def where(lines, rec, now):
    """Index to insert at; None = the section of the next day is not in the file."""
    days = rec.get("days", "").split()
    if not rec.get("section") or now.weekday() >= len(days) - 1:
        return len(lines)
    start = rec["section"].replace("{day}", days[now.weekday() + 1])
    return next((i for i, ln in enumerate(lines) if ln.startswith(start)), None)


def stamp(rec, now=None):
    """Writes the record; returns (True, time) or (False, what is wrong)."""
    now = now or datetime.datetime.now()
    path = target(rec, now)
    if not os.path.isfile(path):
        return False, "missing file: " + path
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if lines and not lines[-1]:
        lines.pop()                                  # konec posledniho radku, ne prazdny radek
    i = where(lines, rec, now)
    if i is None:
        return False, "section not found: " + path
    text = ["type: " + rec.get("record", "stamp"), "datum: " + now.strftime("%Y-%m-%d"),
            "cas: " + now.strftime("%H:%M:%S")]
    text += ["%s: %s" % (k, v) for k, v in rec.items() if k not in OWN]
    block = ([""] if i and lines[i - 1].strip() else []) + text + ([""] if i < len(lines) else [])
    lines[i:i] = block
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    return True, now.strftime("%H:%M:%S")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rec = next((r for r in config.records("stamp") if r.get("id") == sys.argv[1]), None)
    if not rec:
        sys.exit("stamp: no record " + sys.argv[1])
    ok, msg = stamp(rec)
    print("%s %s" % (rec["id"], msg) if ok else "stamp: " + msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
