#!/usr/bin/env python3
"""git_list - adresar v git repu jako strom pro konzoli (clmon), slozky napred.
Vydeleno z clmon (driv jeho prohlizec u adresare); zaklad je konzole_view.Pane.

Usage: git_list.py <adresar>     (cesta k .git = cele repo)
Strom s vetvemi ├─ └─ │.
● = v gitu, ⊗ = v gitu, ale na disku chybi, prazdno = neni; 📝 za jmenem = zmenene proti HEAD; ✗ = git ignoruje; klik na 📝 = zmeny vpravo. r = nacist znovu.
✔ za jmenem = fajfka (klik na misto ✔ za jmenem; znovu = pryc), u adresare vsechno pod nim,
u horniho radku (cele repo) po potvrzeni.
Adresar ma vetev ├⊟ (rozbaleny) / ├⊞ (sbaleny), klik na ni prepne; ignorovany je sbaleny, dokud
ho clovek nerozbali, jeho obsah se cte z disku az pak. Fajfky i sbaleni drzi git_list.t2l v rootu listovaneho repa.
V titulku stav proti githubu (origin): ↑ nepushnute commity, ↓ commity, ktere tu chybi.
Pousti ho konzole na adresar (prepinac ve stitku panelu). Klik na soubor = prohlizec vpravo.
"""

import os
import subprocess
import sys
import threading

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from konzole_view import DIM, HOME, RST, Pane, cwidth, short, wrap_cells  # noqa: E402

C_GIT, C_DIR = "\x1b[38;5;244m", "\x1b[1;34m"      # ● v gitu; adresar ve stromu repa
C_TREE = "\x1b[38;5;240m"                           # vetve stromu
C_MD = "\x1b[93m"                                   # .md zlute
C_MOD = "\x1b[38;5;198m"                            # popis modulu: <modul>.md / .recipe.md / .help.md
C_TICK = "\x1b[1;32m"                               # ✔ fajfka
C_HOV = "\x1b[38;5;238m"                            # ✔ pod mysi (jeste neni)
STATE = "git_list.t2l"                               # stav git listu, v rootu listovaneho repa


def state_path(root):
    return os.path.join(root, STATE)


def load_state(root):
    """Stav z <root>/git_list.t2l: fajfky {(repo, soubor)} a sbalene adresare {(repo, adresar)}."""
    key = repo_key(root)
    ticks, folds, rec = set(), set(), {}
    try:
        with open(state_path(root), encoding="utf-8") as f:
            lines = f.read().split("\n") + [""]
    except OSError:
        return ticks, folds
    for line in lines:
        k, _, v = line.partition(":")
        if not line.strip():
            if rec.get("type") == "tick" and rec.get("file"):
                ticks.add((key, rec["file"]))
            elif rec.get("type") == "fold" and rec.get("dir"):
                folds.add((key, rec["dir"]))
            rec = {}
        else:
            rec[k.strip()] = v.strip()
    return ticks, folds


def save_state(root, ticks, folds):
    key, path = repo_key(root), state_path(root)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("#: stav git_list.py - tick = zafajfkovany soubor, fold = sbaleny adresar\n\n")
        for rp, fp in sorted(ticks):
            if rp == key:
                f.write("type: tick\nfile: %s\n\n" % fp)
        for rp, dp in sorted(folds):
            if rp == key:
                f.write("type: fold\ndir: %s\n\n" % dp)
    os.replace(tmp, path)


def load_ticks(root):
    return load_state(root)[0]


def save_ticks(root, ticks):
    save_state(root, ticks, load_state(root)[1])


def find_top(d):
    """Root git repa, ve kterem adresar d lezi; None, kdyz v zadnem."""
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True,
                           text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def repo_key(root):
    return "~" + root[len(HOME):] if root.startswith(HOME + "/") else root


class GitList(Pane):
    HOVER = True                            # mys na miste fajfky: tmave sede ✔

    def __init__(self, path):
        super().__init__(os.path.abspath(path))
        d = os.path.dirname(self.path) if os.path.basename(self.path) == ".git" else self.path
        self.repo_top = find_top(d)         # repo, ve kterem adresar lezi (None = zadne)
        self.prefix = ""                    # ukazuje se vzdy cele repo od jeho rootu
        self.WATCH = state_path(self.repo_top) if self.repo_top else ""   # fajfky zmenene jinde
        self.ends, self.fileof = {}, {}     # radek -> sloupec konce jmena / soubory v repu pod nim
        self.plain = {}                     # radek -> (bez fajfky, s fajfkou) - k hoveru sede ✔
        self.top_row = None                 # radek celeho repa (fajfky jen po potvrzeni)
        self.remote = "github …"            # stav proti originu, pocita se na pozadi (sit)
        self.folds = {}                     # radek -> (od, do sloupce vetve, adresar)
        self.diffs = {}                     # radek -> (od, do sloupce 📝, cesta)
        self.remote_check()

    def repo_dir(self):
        """Co se listuje: cele repo, ve kterem zadany adresar lezi (at je kdekoli v nem)."""
        if getattr(self, "repo_top", None):
            return self.repo_top
        return os.path.dirname(self.path) if os.path.basename(self.path) == ".git" else self.path

    def render(self, w, h):
        root = self.repo_dir()
        if not self.repo_top:
            self.add(DIM + "Not a git repo: %s" % short(root) + RST)
            self.title(short(root), "git list · not a git repo")
            return
        key, pre = repo_key(self.repo_top), self.prefix
        # stav je od rootu repa, strom od adresare: jen co lezi pod nim, cesty bez prefixu
        t_all, f_all = load_state(self.repo_top)
        ticks = {(key, f[len(pre):]) for k, f in t_all if f.startswith(pre)}
        folds = {(key, f[len(pre):]) for k, f in f_all if f.startswith(pre)}
        collapsed = {d for rp, d in folds if rp == key}      # sbalene adresare (cesta s / na konci)
        self.ends, self.fileof, self.plain = {}, {}, {}
        self.folds, self.diffs = {}, {}
        self.hover = None
        self.top_row = None

        def ls(*opt):
            r = subprocess.run(["git", "-C", root, "ls-files", "-z"] + list(opt),
                               capture_output=True, timeout=10)
            if r.returncode:
                raise OSError(0, "není v git repu")
            return [f for f in r.stdout.decode("utf-8", "replace").split("\0") if f]
        try:
            tracked = set(ls())
            gone = set(ls("-d"))             # v gitu, na disku smazane
            try:                             # v gitu, ale zmenene proti HEAD (i pripravene ke commitu)
                d = subprocess.run(["git", "-C", root, "diff", "--name-only", "--relative", "-z", "HEAD"],
                                   capture_output=True, timeout=10)
                changed = {f for f in d.stdout.decode("utf-8", "replace").split("\0") if f}
            except (OSError, subprocess.SubprocessError):
                changed = set()
            # co git ignoruje: ignorovany adresar jako jedna polozka (ne jeho obsah)
            ign = ls("-o", "-i", "--exclude-standard", "--directory")
            ign_dirs = [d for d in ign if d.endswith("/")]
            ignored = {f for f in ign if not any(f != d and f.startswith(d) for d in ign_dirs)}
            tree = {}
            for f in tracked | set(ls("-o", "--exclude-standard")) | ignored:
                parts = f.rstrip("/").split("/")
                node = tree
                for part in parts[:-1]:
                    node = node.setdefault(part + "/", {})
                node[parts[-1] + ("/" if f.endswith("/") else "")] = f
        except (OSError, subprocess.SubprocessError):
            self.add(DIM + "Not a git repo: %s" % short(root) + RST)
            self.title(short(root), "")
            return

        def has_git(node):
            return any(has_git(v) if isinstance(v, dict) else v in tracked for v in node.values())

        def files(node):
            for v in node.values():
                if isinstance(v, dict):
                    yield from files(v)
                else:
                    yield v

        def mark(fs):
            """Fajfka za jmenem jen tehdy, kdyz jsou zafajfkovane vsechny soubory."""
            return " " + C_TICK + "✔" + RST if fs and all((key, f) in ticks for f in fs) else ""

        def disk(d):
            """Obsah ignorovaneho adresare z disku (git ho nezna), jedna uroven."""
            node = {}
            try:
                entries = list(os.scandir(os.path.join(root, d)))
            except OSError:
                return node
            for e in entries:
                name = e.name + "/" if e.is_dir(follow_symlinks=False) else e.name
                node[name] = d + name
                ignored.add(d + name)
            return node

        def walk(node, pre, path=""):
            """pre = vetve nad touhle urovni (│ kde se pokracuje, mezera kde ne);
            path = cesta adresare v repu."""
            keys = sorted(node, key=lambda k: (not isinstance(node[k], dict) and not k.endswith("/"),
                                               k.lower()))
            for i, k in enumerate(keys):
                v = node[k]
                sub = isinstance(v, dict)
                last = i == len(keys) - 1
                dot = (C_GIT + "● " + RST) if (has_git(v) if sub else v in tracked) else "  "
                if not sub and v in gone:
                    dot = C_GIT + "⊗ " + RST
                if not sub and v in ignored:
                    dot = C_GIT + "✗ " + RST                 # git ho ignoruje
                ign_dir = not sub and v.endswith("/")          # ignorovany adresar
                # sbaleny adresar: ├⊞; ignorovany naopak: sbaleny, zaznam ve stavu = rozbaleny
                fold = (path + k in collapsed) != ign_dir if sub or ign_dir else False
                branch = pre + ("└" if last else "├") + ("⊞ " if fold else "⊟ " if sub or ign_dir else "─ ")
                t = (wrap_cells(k, max(4, w - 4 - len(branch))) or [""])[0]   # dlouhe jmeno oriznout
                name = (C_DIR + t + RST) if sub else (DIM + t + RST if k.startswith(".") or v in gone
                                                      or v in ignored else t)
                if not sub and v not in gone and k.lower().endswith(".md"):
                    mod = os.path.basename(os.path.dirname(os.path.join(root, v)))
                    name = (C_MOD if k in (mod + ".md", mod + ".recipe.md", mod + ".help.md",
                                           mod + ".purpose.md")     # .purpose = starsi jmeno .md
                            else C_MD) + t + RST
                fs = list(files(v)) if sub else [v]
                ch = " 📝" if any(f in changed and f not in gone for f in fs) else ""   # zmenene proti HEAD
                out.append((C_TREE + branch + RST + dot + name + ch,      # ● tesne pred jmenem
                            None if sub or v in gone or v.endswith("/") else ("view", os.path.join(root, v)),
                            fs, cwidth(branch) + 2 + cwidth(t) + cwidth(ch), mark(fs),
                            (cwidth(pre), path + k) if sub or ign_dir else None,
                            (cwidth(branch) + 3 + cwidth(t), os.path.join(root, path + k if sub else v))
                            if ch else None))
                if sub and not fold:
                    walk(v, pre + ("   " if last else "│  "), path + k)
                elif ign_dir and not fold:
                    walk(disk(v), pre + ("   " if last else "│  "), v)
        out = []
        n_ign = len(ignored)                 # do pocitadla jen co hlasi git, ne rozbalene
        walk(tree, "")
        gut = len(str(len(out)))
        # horni radek: cele repo
        top = os.path.basename(root) + "/"
        everything = list(files(tree))
        legend = ("● in git · 📝 changed against HEAD · ⊗ in git, missing on disk · no mark = "
                  "not in git · ✗ ignored by git · ✔ ticked (click right of the name, again = off; a directory ticks "
                  "all under it, the top row the whole repo) · ⊟ / ⊞ click folds / unfolds a "
                  "directory · .md yellow, module descriptions (.md, .recipe.md, .help.md) magenta")
        line = ""                                                # vyklad znacek nad stromem, po slovech
        for word in legend.split(" "):
            if line and cwidth(line + " " + word) > max(20, w - 2):
                self.add(DIM + " " + line + RST)
                line = word
            else:
                line = (line + " " + word).strip()
        self.add(DIM + " " + line + RST)
        self.add("")
        self.top_row = len(self.rows)
        out.insert(0, (C_DIR + top + RST, None, everything, cwidth(top), mark(everything), None, None))
        for i, (row, act, fs, end, tick, fold, diff) in enumerate(out):
            if diff:
                x0 = gut + 1 + diff[0]
                self.diffs[len(self.rows)] = (x0, x0 + 1, diff[1])
            if fold:
                x0 = gut + 1 + fold[0]
                self.folds[len(self.rows)] = (x0, x0 + 1, fold[1])
            num = " " * gut if i == 0 else str(i).rjust(gut)
            line = DIM + num + RST + " " + row                    # cislo radku uplne vlevo
            self.ends[len(self.rows)] = gut + 1 + end
            self.fileof[len(self.rows)] = fs
            self.plain[len(self.rows)] = (line, line + tick)
            self.add(line + tick, act)
        n = len(tracked)
        self.title(short(root), "git list · %s · ● v gitu %d · 📝 změněné %d · ⊗ smazané %d · mimo git %d · ✗ %d · ✔ %d · r = znovu"
                   % (self.remote, n, len(changed - gone), len(gone),
                      sum(1 for _ in files(tree)) - n - n_ign, n_ign,
                      sum(1 for r, _ in ticks if r == key)))

    def remote_check(self):
        threading.Thread(target=self._remote, daemon=True).start()

    def _remote(self):
        """Kolik commitu je repo pred / za originem (github). Jen cte: ls-remote, zadny fetch."""
        root = self.repo_dir()

        def git(*a, timeout=5):
            return subprocess.run(["git", "-C", root] + list(a), capture_output=True, text=True,
                                  timeout=timeout, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        try:
            url = git("remote", "get-url", "origin").stdout.strip()
            if not url:
                self.remote = "bez originu"
                return
            name = "github" if "github.com" in url else "origin"
            branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
            ls = git("ls-remote", "origin", "refs/heads/" + branch, timeout=15)
            if ls.returncode:
                self.remote = name + " ?"
                return
            sha = ls.stdout.split()[0] if ls.stdout.split() else ""
            if not sha:
                n = git("rev-list", "--count", "HEAD").stdout.strip()
                self.remote = "%s ↑%s (%s je prázdný)" % (name, n, name)
            elif git("cat-file", "-e", sha + "^{commit}").returncode:
                self.remote = "%s ↓? (má commity, které tu nejsou)" % name
            else:
                a = git("rev-list", "--count", sha + "..HEAD").stdout.strip()
                b = git("rev-list", "--count", "HEAD.." + sha).stdout.strip()
                self.remote = "%s ↑%s ↓%s" % (name, a, b)
        except (OSError, subprocess.SubprocessError):
            self.remote = "github ?"
        finally:
            self.resized = True

    def key(self, k, h):
        if k in ("r", "R"):
            self.remote_check()             # r = znovu i stav proti githubu
        return False

    def toggle(self, fs):
        """Fajfky souboru fs: jsou-li vsechny, pryc; jinak vsem."""
        top = self.repo_top
        key = repo_key(top)
        ticks = load_ticks(top)
        mine = {(key, self.prefix + f) for f in fs}
        save_ticks(top, ticks - mine if mine <= ticks else ticks | mine)
        self.resized = True

    def click(self, y, x=0):
        """Klik na misto fajfky za jmenem = fajfka (adresar: vse pod nim, cele repo po potvrzeni);
        jinak jako v Pane (jmeno souboru = prohlizec)."""
        i = self.top + y
        if i in self.folds and self.folds[i][0] <= x <= self.folds[i][1]:   # vetev adresare
            top = self.repo_top
            ticks, folds = load_state(top)
            save_state(top, ticks, folds ^ {(repo_key(top), self.prefix + self.folds[i][2])})
            self.resized = True
            return
        if i in self.diffs and self.diffs[i][0] <= x <= self.diffs[i][1]:   # 📝: zmeny vpravo
            if self.pane:
                self.console("--open-right", self.pane, "diff:" + self.diffs[i][2])
            return
        if i in self.ends and self.ends[i] <= x <= self.ends[i] + 2:   # jen misto fajfky
            fs = self.fileof[i]
            if i == self.top_row:
                key = repo_key(self.repo_top)
                on = {(key, self.prefix + f) for f in fs} <= load_ticks(self.repo_top)
                self.ask("%s the whole repo (%d files)?" % ("Untick" if on else "Tick", len(fs)),
                         on_yes=lambda: self.toggle(fs))
            else:
                self.toggle(fs)
            return
        super().click(y, x)

    def hover_at(self, y, x=0):
        """Mys na miste fajfky: tam tmave sede ✔ misto fajfky - klik ji da nebo vezme."""
        i = self.top + y
        if not (i in self.ends and self.ends[i] <= x <= self.ends[i] + 2):
            i = None
        old = self.hover
        if i == old:
            return
        self.hover = i
        if old in self.plain and old < len(self.rows):
            self.rows[old] = self.plain[old][1]
        if i in self.plain:
            self.rows[i] = self.plain[i][0] + " " + C_HOV + "✔" + RST


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: git_list.py <adresar>")
    try:
        GitList(sys.argv[1]).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
