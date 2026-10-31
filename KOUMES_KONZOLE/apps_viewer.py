#!/usr/bin/env python3
"""apps_viewer - appky konzole (clmon), externi programy a externi prohlizece jako tabulky
z KOUMES_KONZOLE/apps.t2l (kdyz chybi, vytvori ho apps.py); stav instalace se zjistuje zivě.
Zaklad je konzole_view.Pane, tabulka se kresli jako v md (mrizka).

Lezi primo v KOUMES_KONZOLE (vyjimka: prehled appek patri ke konzoli), knihovnu
konzole_view bere z KOUMES_KONZOLE_APPS. Pousti ho [apps] v liste panelu.

Usage: apps_viewer.py [apps.t2l]
Soubor se hlida: po zmene se tabulka nakresli znovu.
"""

import os
import re
import shutil
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "KOUMES_KONZOLE_APPS"))   # konzole_view
from konzole_view import DIM, RST, Pane, short  # noqa: E402

sys.path.insert(0, HERE)
import apps  # noqa: E402

APPS = os.path.join(HERE, "apps.t2l")
ICON = {"app": "[ ]", "lib": "[ ]", "tool": "[ ]", "viewer_ext": "↗"}   # interni v panelu / externi v okne
RE_FILE = re.compile(r"^\[\[file:(.+?)\]\]$")


def load(path):
    """Recordy apps.t2l jako dicty; opakovany atribut (start:) jako seznam."""
    recs, cur = [], None
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return recs
    for line in lines + [""]:
        line = line.strip()
        if not line:
            if cur and cur.get("type"):
                recs.append(cur)
            cur = None
            continue
        if ":" not in line or line.startswith("#:"):
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        cur = cur or {}
        if k in ("start", "bin"):                        # opakovane atributy
            cur.setdefault(k, []).append(v)
        else:
            cur.setdefault(k, v)
    for r in recs:
        m = RE_FILE.match(r.get("file", ""))
        r["path"] = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1))) if m else ""
    return recs


def table_lines(rows, w):
    """Seznam jako tabulka rich (mrizka jako md v konzole_view): pripony pod sebou v bunce."""
    import io
    from rich import box
    from rich.console import Console
    from rich.table import Table
    grid = box.Box("    \n  │ \n ─┼ \n  │ \n ─┼ \n ─┼ \n  │ \n    \n")
    t = Table(box=grid, show_edge=False, show_lines=True, border_style="grey50")
    for c in ("kind", "name", "extensions", "file / binary", "installed"):
        t.add_column(c, style=None, header_style="bold")
    for icon, name, ext, fb, ok, _ in rows:
        t.add_row(icon, "[bold]%s[/]" % name.replace("[", "\\["), "\n".join(ext.split(", ")[:3] + (["…"] if len(ext.split(", ")) > 3 else [])) or "-",
                  fb.strip("`"), "✔" if ok else "✗")
    buf = io.StringIO()
    Console(file=buf, width=max(20, w - 1), force_terminal=True, color_system="truecolor",
            highlight=False).print(t)
    return buf.getvalue().rstrip("\n").split("\n")


def cell(t):
    return (t or "").replace("|", "\\|").replace("<", "\\<").replace("*", "\\*")


class AppList(Pane):
    def __init__(self, path):
        self.WATCH = path
        super().__init__(path)
        self.sel = None                  # vybrany radek seznamu (detail nahore)

    def entries(self, recs):
        """Radky seznamu: (ikona, jmeno, ext, soubor / binarka, nainstalovano, detail)."""
        out = []
        for r in recs:
            t = r["type"]
            if t == "app":                                     # knihovny do seznamu appek nepatri
                ok = bool(r["path"]) and os.path.exists(r["path"])      # soubor appky je na disku
                start = ", ".join(r.get("start", []))
                out.append((ICON[t], r.get("id", ""), r.get("ext", ""), os.path.basename(r["path"]) or "-", ok,
                            r.get("description", "") + (" · starts: " + start if start else "")))
            elif t == "tool":
                b = (r.get("bin") or [""])[0]
                out.append((ICON[t], r.get("id", ""), r.get("ext", ""), "`%s`" % b, bool(b and shutil.which(b)),
                            r.get("use", "")))
            elif t == "viewer_ext":                      # appka jeden radek, pripony pod sebou
                bins = r.get("bin") or []
                used = next((b for b in bins if shutil.which(b)), "")
                for b in bins:
                    out.append((ICON[t], b, r.get("ext", ""), "`%s`" % b, bool(shutil.which(b)),
                                r.get("use", "") + (" · used now" if b == used else
                                                    " · candidate, %s is used" % (used or "nothing"))))
        return out

    def render(self, w, h):
        if self.path == apps.APPS_T2L:
            apps.ensure()                                # chybi -> vytvorit z vychozich
        recs = load(self.path)
        rows = self.entries(recs)
        legend = ("[ ] internal - runs in a panel of the console · ↗ external - opens in its own window · "
                  "✔ installed · ✗ missing · click a row = what it does")
        md = [legend, ""]
        if self.sel is not None and self.sel < len(rows):          # detail vybraneho, pod nim cara
            e = rows[self.sel]
            md += ["**%s** - %s" % (cell(e[1]), cell(e[5])), ""]
            if len(e[2].split(", ")) > 3:
                md += ["extensions: " + cell(e[2]), ""]
            md += ["---", ""]
        start = len(self.rows)
        if not self.add_md("\n".join(md), os.path.dirname(self.path), w):
            self.add(DIM + "Without the rich library the list is not drawn." + RST)
            return
        self.add("")
        for line in table_lines(rows, w):
            self.add(line)
        # radky tabulky -> zaznam: radek zacinajici ikonou je novy zaznam, pokracovani do oddelovace
        icons, i, table = tuple(ICON.values()), -1, False      # od start: vyklad, detail, tabulka
        for j in range(start, len(self.rows)):
            plain = re.sub(r"\x1b\[[0-9;]*m", "", self.rows[j])
            if not table:                                # vyklad nahore taky zacina ikonou
                table = "│ name" in plain
                continue
            if plain.lstrip().startswith(icons):
                i += 1
            elif plain.startswith("─") or i < 0:
                continue
            self.acts[j] = ("sel", i)
            if i == self.sel:
                self.rows[j] = "\x1b[48;5;236m" + self.rows[j].replace(RST, RST + "\x1b[48;5;236m") + "\x1b[K" + RST
        missing = sum(1 for e in rows if not e[4])
        self.title(short(self.path), "%d rows · %d missing · watched" % (len(rows), missing))

    def action(self, what, i):
        if what == "sel":
            self.sel = None if self.sel == i else i
            self.resized = True


def main():
    try:
        AppList(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else apps.APPS_T2L).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
