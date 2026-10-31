#!/usr/bin/env python3
"""repos - vsechna repa (adresare s .git) pod tree z config.t2l pro konzoli (clmon).
Vydeleno z clmon (driv `repos:` v jeho prohlizeci); zaklad je konzole_view.Pane.

Usage: repos.py
Ikona jako v dirview (🈴 remark cpp, 🅰️ remark app v <repo>/<repo>.t2l, jinak 🟥), jmeno,
slabe cesta. Klik = rozbalit popis repa (record description, radky co:), jine se zavre;
klik na rozbalene = otevrit v dirview v p1. r = nacist znovu.
Pousti ho dirview tlacitkem [repos] (panel vpravo).
"""

import os
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from konzole_view import DIM, RST, Pane, short, wrap_cells  # noqa: E402
import config as _config  # noqa: E402        # KOUMES_KONZOLE je v ceste od konzole_view

REPOS = "repos:"                                    # @file panelu: konzole tak pozna, co panel ukazuje
C_DIR = "\x1b[1;34m"
REV = "\x1b[48;5;238m"                              # rozbalene repo


class Repos(Pane):
    def __init__(self):
        super().__init__(REPOS)
        self.repos = None           # seznam rep, nacita se jednou; r = znovu
        self.open = ""              # rozbalene repo

    def key(self, k, h):
        if k in ("r", "R"):
            self.repos = None       # pak obnovi Pane (resized)
        return False

    def render(self, w, h):
        if self.repos is None:
            tree = _config.tree()
            try:
                r = subprocess.run(["find", tree, "-name", "node_modules", "-prune", "-o", "-name", ".venv",
                                    "-prune", "-o", "-name", ".git", "-print", "-prune"],
                                   capture_output=True, timeout=20)
            except (OSError, subprocess.SubprocessError) as e:
                self.add(DIM + "find nejde: %s" % e + RST)
                return
            self.repos = sorted((os.path.dirname(g) for g in
                                 r.stdout.decode("utf-8", "replace").split("\n") if g), key=str.lower)
        for d in self.repos:
            kind, desc = "", []
            try:
                with open(os.path.join(d, os.path.basename(d) + ".t2l"), encoding="utf-8") as f:
                    typ = ""
                    for line in f:
                        k, _, v = line.strip().partition(":")
                        k, v = k.strip(), v.strip()
                        if not line.strip():
                            typ = ""
                        elif k == "type":
                            typ = v
                        elif typ == "remark" and k == "value" and v in ("cpp", "app"):
                            kind = v
                        elif typ == "description" and k == "co":
                            desc.append(v)
            except OSError:
                pass
            icon = {"cpp": "🈴", "app": "🅰️"}.get(kind, "🟥")
            name = os.path.basename(d) + "/"
            pad = " " * max(2, 22 - len(name))
            on = d == self.open
            self.add((REV if on else "") + " " + icon + " " + C_DIR + name + RST
                     + (REV if on else "") + pad + DIM + short(d) + ("\x1b[K" if on else "") + RST, ("repo", d))
            if on:
                for t in desc or ["(popis chybí - record type: description, co: ... v %s.t2l)"
                                  % os.path.basename(d)]:
                    for part in wrap_cells(t, w - 6):
                        self.add("     " + part, ("repo", d))
                self.add(DIM + "     klik znovu = otevřít v dirview v p1" + RST, ("repo", d))
        self.title(short(_config.tree()), "%d rep · 🈴 C++  🅰️ appky  🟥 ostatní · klik = popis, znovu = dirview · r = znovu"
                   % len(self.repos))

    def action(self, what, d):
        if what != "repo":
            return
        if d == self.open:
            self.console("--show-dir", d)            # dirview v p1 vleze do repa
        else:
            self.open = d
            self.resized = True


def main():
    try:
        Repos().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
