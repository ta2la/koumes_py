#!/usr/bin/env python3
"""git_diff - uncommitted changes of a file or directory against HEAD, one column.

Usage: git_diff.py <path>
Runs git diff HEAD, so changes in the stage count too. A file not in git has no diff: it says so.
Added and removed rows have a background. [- less] [+ more], keys - +: lines around a change.
Between changes a rule says how many lines are hidden.
"""

import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from konzole_view import BOLD, C_BTN, DIM, RST, Pane, cwidth, short, wrap_cells  # noqa: E402

DIFF = "diff:"                 # @file panelu: konzole tak pozna, co panel ukazuje
BG_ADD = "\x1b[48;2;0;58;20m"   # pridane radky
BG_DEL = "\x1b[48;2;160;0;18m"  # odmazane radky
RE_HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")
LESS, MORE = "[- less]", "[+ more]"
STEP = 3                       # o kolik radku menu pridava a ubira


class GitDiff(Pane):
    def __init__(self, path):
        self.target = os.path.abspath(path)
        super().__init__(DIFF + self.target)
        self.context = 3               # radku kolem zmeny
        self.menu_row = 0
        if os.path.isfile(self.target):
            self.WATCH = self.target

    def git(self, *a):
        d = self.target if os.path.isdir(self.target) else os.path.dirname(self.target)
        return subprocess.run(["git", "-C", d] + list(a), capture_output=True, timeout=15)

    def render(self, w, h):
        self.title(short(self.target), "uncommitted changes · r = again")
        self.menu_row = len(self.rows)
        self.add("%s  %s  %s" % (C_BTN + LESS + RST, C_BTN + MORE + RST,
                                 DIM + "%d lines around a change" % self.context + RST))
        self.add("")
        try:
            known = self.git("ls-files", "--error-unmatch", "--", self.target).returncode == 0 \
                or self.git("cat-file", "-e", "HEAD:./" + os.path.basename(self.target)).returncode == 0
            r = self.git("diff", "--no-color", "-U%d" % self.context, "HEAD", "--", self.target)
            top = self.git("rev-parse", "--show-toplevel").stdout.decode("utf-8", "replace").strip()
        except (OSError, subprocess.SubprocessError) as e:
            self.add(DIM + str(e) + RST)
            return
        if r.returncode:
            self.add(DIM + "Not a git repo: %s" % short(self.target) + RST)
        elif not known and os.path.isfile(self.target):
            self.add(DIM + "Not in git yet, there is nothing to compare it with." + RST)
        elif not r.stdout.strip():
            self.add(DIM + "No uncommitted changes." + RST)
        else:
            self.show(r.stdout.decode("utf-8", "replace").split("\n"), top, w)

    def show(self, lines, top, w):
        """Radky pozadim, jmeno souboru, mezi useky pocet nezobrazenych radku."""
        name, seen = "", 0                  # soubor; kam az v nem dosel posledni usek (nove cislovani)

        def rest():
            """Nezobrazene radky za poslednim usekem souboru."""
            try:
                with open(os.path.join(top, name), "rb") as f:
                    self.gap(sum(1 for _ in f) - seen, w)
            except OSError:
                pass
        for ln in lines:
            if ln.startswith("diff --git"):
                if name:
                    rest()
                name, seen = "", 0
            elif ln.startswith("+++ "):
                name = ln[6:] if ln[4:] != "/dev/null" else ""
                if name:
                    self.add(BOLD + name + RST)
            elif ln.startswith(("index ", "--- ", "new file", "deleted file", "similarity", "rename ")):
                continue
            elif ln.startswith("@@"):
                m = RE_HUNK.match(ln)
                if m:
                    start, n = int(m.group(1)), int(m.group(2) or 1)
                    self.gap(start - seen - (1 if n else 0), w)
                    seen = start + n - 1 if n else start
            else:
                bg = BG_ADD if ln[:1] == "+" else BG_DEL if ln[:1] == "-" else ""
                for part in wrap_cells(ln.expandtabs(4), w - 1) or [""]:
                    self.add(bg + part + " " * max(0, w - 1 - cwidth(part)) + RST if bg else part)
        if name:
            rest()

    def gap(self, n, w):
        """Mezi useky: kolik radku neni videt."""
        if n > 0:
            head = "── %d lines " % n
            self.add(DIM + head + "─" * max(1, w - 1 - cwidth(head)) + RST)

    def step(self, by):
        self.context = max(0, self.context + by)
        self.resized = True

    def click(self, y, x=0):
        if self.top + y == self.menu_row:
            if x <= len(LESS):
                self.step(-STEP)
            elif x <= len(LESS) + 2 + len(MORE):
                self.step(STEP)
            return
        super().click(y, x)

    def key(self, k, h):
        if k in ("+", "-"):
            self.step(STEP if k == "+" else -STEP)
            return True
        return False


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: git_diff.py <path>")
    try:
        GitDiff(sys.argv[1]).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
