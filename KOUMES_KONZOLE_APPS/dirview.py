#!/usr/bin/env python3
"""dirview - terminalovy prohlizec adresaru pro konzoli (clmon), port CPPBROWSE do Pythonu.

Usage: dirview.py [adresar] [--port N] [--code <code_root>]
Ridi se commandy pres WebSocket (cmd_sys, default port 54330), klavesy a mys volaji totez.

Vypis jednoho adresare. Mimo code_root obycejny vypis (.., slozky, soubory).
Repo (adresar s .git) ma kdekoli ikonu: 🈴 C++ knihovny (remark cpp), 🅰️ appky (app), 🟥 ostatni.
V koreni code_root jen repa; v repu vse, C++ modul (adresar s .pro) ma 🧩. V git repu sloupec:
● v gitu, ✗ vyloucene z gitu (.gitignore), jinak prazdno; 📝 za jmenem = v gitu, ale zmenene
proti HEAD (slozka: aspon jeden soubor v ni).
Seznam souboru (.t2l s type: filelist) se ukazuje taky jako adresar: polozky jsou
`file: [[file:cesta]]`, `...]]:25` (radek) nebo `...]]:25:40` (usek radku).
[repos] = vsechna repa pod tree z config.t2l v prohlizeci konzole vpravo.
[timeaxis] = mod: polozky TIMEAXIS (MM_DD_nazev v <rok>_qN/) jako jeden seznam od nejnovejsi,
po 25, dole [more]; vybrana polozka = jeji esence v konzoli vpravo (esence:<cesta>);
[back] = zpet na adresar TIMEAXIS.
[remarks] = posledni *.REMARKS v esenci vpravo.
[aicom] = mod: polozky posledniho *.AICOM (aicom.py), nejnovejsi dole, naopak nez
timeaxis; [more] nahore starsi; [paste] schranka do posledniho aicom, [copy] vybrana do schranky.
"""

import os
import re
import select
import signal
import subprocess
import sys
import termios
import time
import unicodedata

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)                                  # KOUMES_PY: cmd_sys, .venv

# cmd_sys potrebuje websockets z .venv koumesu: pod jinym pythonem se pustit znovu pod nim
VENV = os.path.join(ROOT, ".venv")
if os.path.isdir(VENV) and os.path.realpath(sys.prefix) != os.path.realpath(VENV):
    py = os.path.join(VENV, "bin", "python")
    os.execv(py, [py, "-B", os.path.realpath(__file__)] + sys.argv[1:])

sys.dont_write_bytecode = True
sys.path.insert(0, ROOT)
from cmd_sys import Cmds  # noqa: E402

HOME = os.path.expanduser("~")
CONSOLE = os.path.join(ROOT, "KOUMES_KONZOLE", "clmon")        # konzole: --open-right

REPOS_BTN = "[repos]"
REPOS = "repos:"                  # pro konzoli: seznam vsech rep pod tree z config.t2l
TIMEAXIS_BTN = "[timeaxis]"
TIMEAXIS = "timeaxis:"            # "adresar" modu timeaxis
ESENCE = "esence:"                # pro konzoli: esence:<cesta> polozky TIMEAXIS
BACK_BTN = "[back]"               # v modu timeaxis: zpet na adresar TIMEAXIS
MORE = "[more]"                   # posledni polozka modu timeaxis: dalsich 25
TIMEAXIS_STEP = 25
AICOM_BTN = "[aicom]"
AICOM = "aicom:"                  # "adresar" modu aicom
WWW_BTN = "[remarks]"
PASTE_BTN = "[paste]"
COPY_BTN = "[copy]"
sys.path.insert(0, os.path.join(ROOT, "KOUMES_KONZOLE"))
import config as _config  # noqa: E402
import aicom  # noqa: E402
TIMEAXIS_DIR = aicom.root()
DATED = {AICOM: aicom.AICOM}                                  # "adresar" modu -> druh polozky

RST = "\x1b[0m"
DIM = "\x1b[2m"
SEL = "\x1b[48;5;238m"
CDIR = "\x1b[1;38;5;75m"
CTAG = "\x1b[38;5;244m"
CHEAD = "\x1b[1;38;5;252m"
CINFO = "\x1b[38;5;180m"
CGIT = "\x1b[38;5;244m"           # ● v gitu: stredne seda
CIGN = "\x1b[38;5;131m"           # ✗ vyloucene z gitu: tlumena cervena
CTYPE = "\x1b[1;38;5;214m"        # typ polozky TIMEAXIS (.ARTICLE)


# =============================================================================
def cut(s, cols):
    """Text oriznuty na `cols` sloupcu terminalu (siroke znaky a emoji maji 2): (text, sirka)."""
    out, w, prev = [], 0, 0
    for ch in s:
        o = ord(ch)
        if o == 0xFE0F:
            cw = 1 if prev == 1 else 0     # variacni selektor emoji: znak pred nim (🅰) na 2 sloupce
        elif unicodedata.combining(ch) or unicodedata.category(ch) in ("Me", "Mn", "Cf"):
            cw = 0
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            cw = 2
        else:
            cw = 1
        prev = cw
        if w + cw > cols:
            break
        out.append(ch)
        w += cw
    return "".join(out), w


def short(path):
    return "~" + path[len(HOME):] if path.startswith(HOME) else path


def git_lines(args, cwd):
    """Polozky z `git -C cwd <args> -z`; None, kdyz git selze (adresar neni v repu)."""
    try:
        r = subprocess.run(["git", "-C", cwd] + args, capture_output=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return [f.decode("utf-8", "replace") for f in r.stdout.split(b"\0") if f]


# =============================================================================
class CodeInfo:
    """Co dirview vi o C++ casti code_root: ktera repa jsou C++ (remark cpp/app v <repo>.t2l),
    ktere adresare v repu jsou moduly (maji .pro) a co ktery modul stavi a linkuje."""
    OUTSIDE, ROOT, REPO, INSIDE = range(4)
    RE_PRO = re.compile(r"^\s*(TEMPLATE|TARGET|DEPLIBS|T2LS|SUBDIRS)\s*(\+?=)\s*(\S+)")

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.users = None

    def level(self, d):
        d = os.path.abspath(d)
        if d == self.root:
            return self.ROOT
        if not d.startswith(self.root + "/"):
            return self.OUTSIDE
        return self.INSIDE if "/" in d[len(self.root) + 1:] else self.REPO

    def repo_kind(self, repo_dir):
        """<repo>/<repo>.t2l: record `type: remark` s `value: cpp|app`; jinak ""."""
        kind, typ = "", ""
        try:
            lines = open(os.path.join(repo_dir, os.path.basename(repo_dir) + ".t2l"),
                         encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            return kind
        for line in lines:
            line = line.strip()
            if not line:
                typ = ""
                continue
            if ":" not in line:
                continue
            key, value = (x.strip() for x in line.split(":", 1))
            if key == "type":
                typ = value
            elif typ == "remark" and key == "value" and value in ("cpp", "app"):
                kind = value
        return kind

    def module(self, mdir):
        """Hlavni .pro = <jmeno adresare>.pro (bez ohledu na velikost pismen), jinak prvni.
        Vraci dict pro/tmpl/target/links/builds, nebo None."""
        try:
            pros = sorted(n for n in os.listdir(mdir)
                          if n.endswith(".pro") and os.path.isfile(os.path.join(mdir, n)))
        except OSError:
            return None
        if not pros:
            return None
        name = os.path.basename(mdir).lower() + ".pro"
        pick = next((p for p in pros if p.lower() == name), pros[0])
        return self.parse_pro(os.path.join(mdir, pick))

    def parse_pro(self, path):
        m = {"pro": path, "tmpl": "", "target": "", "links": [], "builds": []}
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            return m
        for line in lines:
            hit = self.RE_PRO.match(line)
            if not hit:
                continue
            key, value = hit.group(1), hit.group(3)
            if key == "TEMPLATE" and not m["tmpl"]:
                m["tmpl"] = value
            elif key == "TARGET" and not m["target"]:
                m["target"] = value
            elif key == "DEPLIBS":
                parts = value.split(":")                          # repo:modul[:include]
                m["links"].append(parts[1] if len(parts) > 1 else "")
            elif key == "T2LS":
                m["links"].append(value)                          # base2 modul
            elif key == "SUBDIRS":
                parts = [p for p in value.split("/") if p]        # ../../../repo/modul
                if len(parts) >= 2:
                    m["builds"].append(parts[-2] + "/" + parts[-1])
        if not m["tmpl"]:
            m["tmpl"] = "app"                                     # qmake default
        return m

    def used_by(self, lib):
        """Kdo knihovnu `lib` linkuje: "repo/modul" app, ktere ji maji v DEPLIBS nebo T2LS."""
        if self.users is None:
            self.users = {}
            for r in sorted(self._dirs(self.root)):
                if not self.repo_kind(os.path.join(self.root, r)):
                    continue
                for md in sorted(self._dirs(os.path.join(self.root, r))):
                    m = self.module(os.path.join(self.root, r, md))
                    if m and m["tmpl"] == "app":
                        for l in m["links"]:
                            self.users.setdefault(l, []).append(r + "/" + md)
        return self.users.get(lib, [])

    @staticmethod
    def _dirs(d):
        try:
            return [n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))]
        except OSError:
            return []


def module_tag(m):
    if m["tmpl"] == "lib":
        return "lib  lib" + m["target"] + ".a"
    if m["tmpl"] == "app":
        return "app  " + m["target"]
    return m["tmpl"]


def repo_icon(code, d):
    """Repo = adresar s .git (kdekoli); C++ knihovny (remark cpp) 🈴, appky (app) 🅰️, ostatni 🟥."""
    if not os.path.exists(os.path.join(d, ".git")):
        return ""
    kind = code.repo_kind(d)
    return "🈴" if kind == "cpp" else "🅰️" if kind == "app" else "🟥"


def is_file_list(path):
    if not path.endswith(".t2l") or not os.path.isfile(path):
        return False
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line.startswith("type:"):
                return line[5:].strip() == "filelist"
    except OSError:
        pass
    return False


# =============================================================================
class Entry:
    def __init__(self, name, path, is_dir=False, icon="", tag=""):
        self.name, self.path, self.is_dir, self.icon, self.tag = name, path, is_dir, icon, tag
        self.in_git = False         # je v gitu (slozka: aspon jeden soubor v ni) - ● pred jmenem
        self.ignored = False        # vyloucene z gitu (.gitignore; slozka cela) - ✗ pred jmenem
        self.changed = False        # v gitu, ale zmenene proti HEAD - 📝 za jmenem


class DirListing:
    """Vypis jednoho adresare (nebo seznamu souboru, nebo modu timeaxis) a radky info nad nim."""
    RE_FILE = re.compile(r"^\[\[file:(.+?)\]\]((?::\d+){0,2})$")
    RE_Q = re.compile(r"^(\d{4})_q[1-4]$")
    RE_ITEM = re.compile(r"^(\d\d)_(\d\d)_.+")

    def __init__(self, code):
        self.code = code
        self.entries, self.info = [], []
        self.in_repo = False
        self.timeaxis_count = TIMEAXIS_STEP

    def load(self, d, filt):
        self.entries, self.info = [], []
        self.in_repo = False
        if d == TIMEAXIS:
            self._timeaxis()
            self.info.append(BACK_BTN + "  " + REPOS_BTN + "  " + AICOM_BTN + "  " + WWW_BTN)
            return
        if d in DATED:
            self._aicom(DATED[d])
            self.info.append(BACK_BTN + "  " + TIMEAXIS_BTN + "  " + PASTE_BTN + "  " + COPY_BTN)
            return
        self._load(d, filt)
        # posledni radek info: tlacitka (git list je prepinac ve stitku panelu)
        self.info.append(REPOS_BTN + ("  " + TIMEAXIS_BTN + "  " + AICOM_BTN + "  " + WWW_BTN if TIMEAXIS_DIR else ""))

    def index_of(self, name):
        return next((i for i, e in enumerate(self.entries) if e.name == name), -1)

    def _load(self, d, filt):
        if os.path.isfile(d):
            self._list(d)
            return
        code = self.code
        path = os.path.abspath(d)
        level = code.level(path)
        if path != "/":
            self.entries.append(Entry("..", os.path.dirname(path), True))
        tracked = git_lines(["ls-files", "-z"], path)
        self.in_repo = tracked is not None
        tracked = {f.split("/")[0] for f in tracked or []}
        ignored, changed = set(), set()
        if self.in_repo:
            # vyloucene: jen cele polozky prvni urovne (slozka cela = git ji vypise jako "jmeno/")
            for f in git_lines(["ls-files", "-z", "-o", "-i", "--exclude-standard", "--directory"],
                               path) or []:
                f = f.rstrip("/")
                if f and "/" not in f:
                    ignored.add(f)
            # zmenene proti HEAD (v pracovni kopii i pripravene)
            changed = {f.split("/")[0] for f in
                       git_lines(["diff", "--name-only", "-z", "--relative", "HEAD"], path) or []}
        try:
            names = os.listdir(path)
        except OSError:
            names = []
        isdir = {n: os.path.isdir(os.path.join(path, n)) for n in names}
        names.sort(key=lambda n: (not isdir[n], n.lower()))
        for n in names:
            full = os.path.join(path, n)
            e = Entry(n, full, isdir[n])
            e.in_git, e.ignored, e.changed = n in tracked, n in ignored, n in changed
            if e.is_dir:
                e.icon = repo_icon(code, full)
            if level == CodeInfo.ROOT:
                # v koreni code_root jen repa (vsechna, nejen C++)
                if not e.icon and filt:
                    continue
                if e.is_dir:
                    e.tag = code.repo_kind(full)
            elif level == CodeInfo.REPO:
                # v repu se nefiltruje; C++ modul (adresar s .pro) ma ikonu 🧩
                m = code.module(full) if e.is_dir else None
                if m:
                    e.icon, e.tag = "🧩", module_tag(m)
            self.entries.append(e)

        # co je tenhle adresar
        if level == CodeInfo.ROOT:
            self.info.append("repos  🈴 C++ libraries  🅰️ apps  🟥 other"
                             + ("" if filt else " · filter off"))
        elif level == CodeInfo.REPO:
            kind = code.repo_kind(path)
            self.info.append("%s repo · ● v gitu  📝 změněné  ✗ mimo git  🧩 C++ modul"
                             % ("🈴" if kind == "cpp" else "🅰️" if kind == "app" else "🟥"))
        elif level == CodeInfo.INSIDE:
            rel = path[len(code.root) + 1:]
            if rel.count("/") == 1:                                   # repo/modul
                m = code.module(path)
                if m:
                    self.info.append(module_tag(m))
                    if m["builds"]:
                        self.info.append("staví: " + ", ".join(m["builds"]))
                    if m["links"]:
                        self.info.append("linkuje: " + ", ".join(m["links"]))
                    if m["tmpl"] == "lib":
                        users = code.used_by(m["target"])
                        self.info.append("používají ji: " + (", ".join(users) if users else "nikdo"))

    def _list(self, file):
        """file: [[file:cesta]] | [[file:cesta]]:25 | [[file:cesta]]:25:40 ; cesta relativne
        k souboru se seznamem, absolutne nebo od ~."""
        base = os.path.dirname(os.path.abspath(file))
        self.entries.append(Entry("..", base, True))
        rid, co = "", []
        try:
            lines = open(file, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if ":" not in line:
                continue
            key, value = (x.strip() for x in line.split(":", 1))
            if key == "id" and not rid:
                rid = value
            elif key == "co":
                co.append(value)
            elif key == "file":
                m = self.RE_FILE.match(value)
                rel = m.group(1) if m else value
                rows = m.group(2) if m else ""
                if rel.startswith("~"):
                    rel = HOME + rel[1:]
                full = os.path.normpath(os.path.join(base, rel))
                # jmeno souboru, za nim radky a adresar (do uzkeho panelu se vejde to dulezite)
                e = Entry(os.path.basename(full), full + rows, os.path.isdir(full))
                e.tag = ("" if os.path.exists(full) else "chybí  ") \
                    + (rows[1:].replace(":", "-") + "  " if rows else "") + short(os.path.dirname(full))
                self.entries.append(e)
        self.info.append("seznam · " + (rid or os.path.basename(file)))
        self.info += co

    def _timeaxis(self):
        # polozka = soubor nebo adresar MM_DD_nazev v <rok>_qN/; rok je z ctvrtleti
        items = []
        for q in CodeInfo._dirs(TIMEAXIS_DIR):
            mq = self.RE_Q.match(q)
            if not mq:
                continue
            qd = os.path.join(TIMEAXIS_DIR, q)
            try:
                names = os.listdir(qd)
            except OSError:
                continue
            for n in names:
                mi = self.RE_ITEM.match(n)
                if mi:
                    full = os.path.join(qd, n)
                    items.append(("%s-%s-%s" % (mq.group(1), mi.group(1), mi.group(2)), n, full,
                                  os.path.isdir(full)))
        items.sort(key=lambda t: (t[0], t[1]), reverse=True)
        n = min(self.timeaxis_count, len(items))
        for i, (date, name, full, isd) in enumerate(items[:n]):
            self.entries.append(Entry(name, full, False, "[%d]" % (i + 1)))
        if n < len(items):
            self.entries.append(Entry(MORE, MORE, False, "", "%d z %d" % (n, len(items))))
        self.info.append("TIMEAXIS · %d položek od nejnovější · vybraná = esence vpravo" % len(items))

    def _aicom(self, kind):
        # naopak nez timeaxis: nejnovejsi dole, [more] nahore pridava starsi
        items = aicom.items(kind)
        n = min(self.timeaxis_count, len(items))
        if n < len(items):
            self.entries.append(Entry(MORE, MORE, False, "", "%d of %d" % (n, len(items))))
        for i, full in enumerate(items[len(items) - n:]):
            self.entries.append(Entry(os.path.basename(full), full, False, "[%d]" % (i + 1)))
        self.info.append("%s · %d items, newest at the bottom · selected = shown on the right"
                         % (kind[1:], len(items)))


# =============================================================================
class TermUi:
    """Kresleni do terminalu (ANSI) a vstup z nej. Nahore cesta a radky info, pod nimi
    seznam s jednim vybranym radkem. Klavesy a mys volaji tytez commandy jako WS."""
    RE_MOUSE = re.compile(rb"^\x1b\[<(\d+);(\d+);(\d+)([Mm])")
    SEQS = [(b"\x1b[A", "up"), (b"\x1bOA", "up"), (b"\x1b[B", "down"), (b"\x1bOB", "down"),
            (b"\x1b[C", "right"), (b"\x1bOC", "right"), (b"\x1b[D", "left"), (b"\x1bOD", "left"),
            (b"\x1b[5~", "pgup"), (b"\x1b[6~", "pgdn"), (b"\x1b[H", "home"), (b"\x1b[1~", "home"),
            (b"\x1b[F", "end"), (b"\x1b[4~", "end")]
    # klavesy jen preklada na commandy - jdou stejnou cestou jako z WS (log, broadcast)
    KEYS = {"up": "cppb_move -1", "k": "cppb_move -1", "down": "cppb_move +1", "j": "cppb_move +1",
            "pgup": "cppb_move pgup", "pgdn": "cppb_move pgdn",
            "home": "cppb_move home", "end": "cppb_move end",
            "\r": "cppb_open", "\n": "cppb_open", "right": "cppb_open",
            "left": "cppb_up", "\x7f": "cppb_up", "\b": "cppb_up", "h": "cppb_up",
            "f": "cppb_filter", "r": "panel_reload", "v": "cppb_view"}

    def __init__(self, code):
        self.cmds = None
        self.dir = ""
        self.list = DirListing(code)
        self.cur = self.top = 0
        self.filt = True
        self.buf = b""
        self.last_wh = (0, 0)
        self.last_list = 0.0
        self.saved = None

    # ---- terminal ------------------------------------------------------------
    def start(self, d):
        if os.isatty(0):
            self.saved = termios.tcgetattr(0)
            t = termios.tcgetattr(0)
            t[3] &= ~(termios.ICANON | termios.ECHO)
            t[6][termios.VMIN], t[6][termios.VTIME] = 0, 0
            termios.tcsetattr(0, termios.TCSANOW, t)
        # vlastni obrazovka, bez kurzoru, mys v citelnem tvaru (SGR)
        self.write("\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1006h")
        if not self.set_dir(d):
            self.set_dir(HOME)

    def stop(self):
        self.write("\x1b[?1000l\x1b[?1006l\x1b[?25h\x1b[?1049l")
        if self.saved:
            termios.tcsetattr(0, termios.TCSANOW, self.saved)
            self.saved = None

    @staticmethod
    def write(s):
        data = s.encode("utf-8")
        while data:
            try:
                n = os.write(1, data)
            except OSError:
                return
            if n <= 0:
                return
            data = data[n:]

    @staticmethod
    def size():
        try:
            s = os.get_terminal_size(1)
            return s.columns, s.lines
        except OSError:
            return 80, 24

    def run(self, line, user="TERMINAL"):
        self.cmds.run(line, user)

    # ---- stav ----------------------------------------------------------------
    def set_dir(self, path):
        if path == TIMEAXIS or path in DATED:
            # mod timeaxis, aicom nebo remarks: misto adresare seznam polozek
            self.dir = path
            self.list.load(self.dir, self.filt)
            self.cur = self.top = 0
            if path in DATED:
                self.cur = max(0, len(self.list.entries) - 1)     # nejnovejsi dole
            self.last_list = time.time()
            self.draw()
            return True
        p = HOME + path[1:] if path.startswith("~") else path
        # relativne k aktualnimu adresari; kdyz je otevreny seznam, k jeho adresari
        base = HOME if not self.dir else os.path.dirname(self.dir) if os.path.isfile(self.dir) else self.dir
        full = os.path.normpath(os.path.join(base, p))
        if os.path.isfile(full) and not is_file_list(full):
            # obycejny soubor: do jeho adresare a vybrat ho
            if not self.set_dir(os.path.dirname(full)):
                return False
            i = self.list.index_of(os.path.basename(full))
            if i >= 0:
                self.cur = i
                self.draw()
            return True
        if not os.path.isdir(full) and not is_file_list(full):
            return False
        frm, self.dir = self.dir, full
        self.list.load(self.dir, self.filt)
        self.cur = self.top = 0
        # o uroven vys: vyber zustane na adresari, ze ktereho se prislo
        if frm.startswith(self.dir.rstrip("/") + "/"):
            i = self.list.index_of(frm[len(self.dir.rstrip("/")) + 1:].split("/")[0])
            if i >= 0:
                self.cur = i
        elif len(self.list.entries) > 1:
            self.cur = 1                                          # prvni polozka za ..
        self.last_list = time.time()
        self.draw()
        return True

    def set_line(self, n):
        if n < 1 or n > len(self.list.entries):
            return False
        self.cur = n - 1
        self.draw()
        return True

    def reload(self):
        e = self.list.entries
        keep = e[self.cur].name if self.cur < len(e) else ""
        newest = self.dir in DATED and self.cur == len(e) - 1     # na konci: jde s novou polozkou
        self.list.load(self.dir, self.filt)
        # stejny soubor muze byt v seznamu vickrat (vic useku) - kdyz na miste vyberu
        # zustal ten samy, nechat ho tam
        n = self.list.entries
        i = self.cur if self.cur < len(n) and n[self.cur].name == keep else self.list.index_of(keep)
        self.cur = i if i >= 0 else min(self.cur, max(0, len(n) - 1))
        if newest:
            self.cur = max(0, len(n) - 1)
        self.last_list = time.time()
        self.draw()

    def up(self):
        if self.dir == TIMEAXIS or self.dir in DATED:
            self.set_dir(TIMEAXIS_DIR)                            # [back]
        elif os.path.isfile(self.dir):
            self.set_dir(os.path.dirname(self.dir))               # ze seznamu zpet
        elif self.dir != "/":
            self.set_dir("..")

    def right(self, path):
        """Soubor do panelu vpravo v konzoli (kdyz tam zadny neni, konzole ho zalozi)."""
        pane = os.environ.get("TMUX_PANE", "")
        if not pane:
            return False
        subprocess.Popen([CONSOLE, "--open-right", pane, path], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True

    def open(self):
        e = self.list.entries
        if not 0 <= self.cur < len(e):
            return
        en = e[self.cur]
        if self.dir == TIMEAXIS or self.dir in DATED:
            # [more] = dalsich 25; polozka = jeji esence v prohlizeci konzole vpravo
            if en.path == MORE:
                self.list.timeaxis_count += TIMEAXIS_STEP
                self.reload()
                return
            self.right(ESENCE + en.path)
            return
        if en.is_dir or is_file_list(en.path):
            self.set_dir(en.path)
            return
        # u seznamu muze mit :25 nebo :25:40 - konzole otevre na radku a usek vybere
        self.right(en.path)

    def row_btn(self):
        e = self.list.entries
        return self.list.in_repo and 0 <= self.cur < len(e) and e[self.cur].is_dir \
            and e[self.cur].name != ".."

    def view_repo(self, path=""):
        """[git list]: adresar v git repu jako strom vpravo; prazdna cesta = vybrana slozka,
        kdyz na ni tlacitko je, jinak aktualni adresar; .git = cele repo."""
        d = path or (self.list.entries[self.cur].path if self.row_btn() else self.dir)
        if not self.list.in_repo and not os.path.exists(os.path.join(d, ".git")):
            return False
        return self.right(d)

    def view_timeaxis(self):
        self.list.timeaxis_count = TIMEAXIS_STEP
        return self.set_dir(TIMEAXIS)

    def view_aicom(self, mode=AICOM):
        self.list.timeaxis_count = TIMEAXIS_STEP
        return self.set_dir(mode)

    def aicom_paste(self):
        """[paste]: schranka jako nova polozka posledniho aicom."""
        to = aicom.paste("clip", DATED.get(self.dir, aicom.AICOM))
        if to:
            self.reload()
        return to

    def aicom_copy(self):
        """[copy]: vybrana polozka do schranky."""
        e = self.list.entries
        if self.dir not in DATED or not 0 <= self.cur < len(e) or e[self.cur].path == MORE:
            return False
        return aicom.copy(e[self.cur].path)

    def move(self, how):
        page = max(1, self.size()[1] - self.list_top() - 1)
        n = len(self.list.entries)
        if not n:
            return False
        if how == "pgup":
            self.cur -= page
        elif how == "pgdn":
            self.cur += page
        elif how == "home":
            self.cur = 0
        elif how == "end":
            self.cur = n - 1
        else:
            try:
                self.cur += int(how.replace("+", ""))
            except ValueError:
                return False
        self.cur = max(0, min(self.cur, n - 1))
        self.draw()
        return True

    # ---- kresleni ------------------------------------------------------------
    def list_top(self):
        return 1 + len(self.list.info) + 1                        # cesta, info, cara

    def draw(self):
        w, h = self.size()
        self.last_wh = (w, h)
        out = ["\x1b[H"]
        row = [1]

        def line(text):
            if row[0] > h:
                return
            # \x1b[2K napred: po 🅰️ (s FE0F) terminal muze nechat bunku se starym znakem
            out.append("\x1b[%d;1H\x1b[2K%s\x1b[K%s" % (row[0], text, RST))
            row[0] += 1

        line(CHEAD + cut(" " + short(self.dir), w - 1)[0])
        for i in self.list.info:
            line(CINFO + cut(" " + i, w - 1)[0])
        line(DIM + "┈" * max(1, w - 1))

        e = self.list.entries
        lh = max(1, h - self.list_top())
        if self.cur < self.top:
            self.top = self.cur
        if self.cur >= self.top + lh:
            self.top = self.cur - lh + 1
        self.top = max(0, min(self.top, len(e) - lh))
        for i in range(self.top, len(e)):
            if row[0] > h:
                break
            en, sel = e[i], i == self.cur
            wr = w
            text = SEL + "› " if sel else "  "
            used = 2
            if self.list.in_repo:
                # sloupec pred ikonou: ● je v gitu, ✗ vyloucene z gitu, jinak prazdno
                text += CGIT + "●\x1b[39m " if en.in_git else CIGN + "✗\x1b[39m " if en.ignored else "  "
                used += 2
            if en.icon:
                s, u = cut(en.icon + " ", wr - 1 - used)
                text += s
                used += u
            name = en.name + "/" if en.is_dir else en.name
            color = CDIR if en.is_dir else DIM if en.name.startswith(".") else ""
            dot = en.name.rfind(".")
            if (self.dir == TIMEAXIS or self.dir in DATED) and dot > 0:
                # polozka TIMEAXIS: nazev, typ za posledni teckou zvyrazneny
                s, u = cut(en.name[:dot], wr - 1 - used)
                text += s
                used += u
                s, u = cut(en.name[dot:], wr - 1 - used)
                text += CTYPE + s + RST + (SEL if sel else "")
            else:
                s, u = cut(name, wr - 1 - used)
                text += color + s + RST + (SEL if sel else "")
            used += u
            if en.changed:
                s, u = cut(" 📝", wr - 1 - used)              # v gitu, ale zmenene proti HEAD
                text += s
                used += u
            if en.tag and used + 3 < wr - 1:
                s, u = cut(" " * max(2, 26 - used) + en.tag, wr - 1 - used)
                text += CTAG + s
                used += u
            line(text)                                    # \x1b[K v line() natahne podklad vyberu
        if not e or (len(e) == 1 and e[0].name == ".."):
            line(DIM + "  (prázdný adresář)")
        while row[0] <= h:
            line("")
        self.write("".join(out))

    # ---- vstup ---------------------------------------------------------------
    def tick(self):
        if self.size() != self.last_wh:
            self.draw()
            return
        # obsah adresare se mohl zmenit - jednou za 2 s nacist znovu
        if time.time() - self.last_list > 2:
            self.reload()

    def input(self):
        try:
            data = os.read(0, 1024)
        except OSError:
            return
        if not data:
            return
        self.buf += data
        while self.buf:
            b = self.buf
            if b.startswith(b"\x1b[<"):
                m = self.RE_MOUSE.match(b)
                if not m:
                    if len(b) < 32:
                        return                             # zbytek udalosti prijde priste
                    self.buf = b[3:]
                    continue
                self.mouse(int(m.group(1)), int(m.group(2)) - 1, int(m.group(3)) - 1, m.group(4) == b"M")
                self.buf = b[m.end():]
                continue
            hit = next((s for s in self.SEQS if b.startswith(s[0])), None)
            if hit:
                self.key(hit[1])
                self.buf = b[len(hit[0]):]
                continue
            if b[0] == 0x1b:
                j = 1                                      # jina sekvence - zahodit celou
                if len(b) > 1 and b[1] in b"[O":
                    j = 2
                    while j < len(b) and not 0x40 <= b[j] <= 0x7e:
                        j += 1
                    j += 1
                self.buf = b[j:]
                continue
            self.key(chr(b[0]))
            self.buf = b[1:]

    def key(self, k):
        cmd = self.KEYS.get(k)
        if cmd:
            self.run(cmd)

    def mouse(self, b, x, y, pressed):
        if b == 64:
            self.key("up")                                 # kolecko
            return
        if b == 65:
            self.key("down")
            return
        if not pressed or b & 3 or b & 32:
            return                                         # jen stisk leveho tlacitka
        if 1 <= y <= len(self.list.info):
            # radek info: tlacitka [repos], [timeaxis], [aicom], [paste], [copy] a [back]
            info = " " + self.list.info[y - 1]

            def hit(btn):
                at = info.find(btn)
                if at < 0:
                    return False
                frm = cut(info[:at], 1000)[1]
                return frm <= x < frm + len(btn)
            if hit(REPOS_BTN):
                self.run("cppb_repos")
            elif hit(TIMEAXIS_BTN):
                self.run("cppb_timeaxis")
            elif hit(AICOM_BTN):
                self.run("cppb_aicom")
            elif hit(WWW_BTN):
                self.run("cppb_remarks")
            elif hit(PASTE_BTN):
                self.run("cppb_paste")
            elif hit(COPY_BTN):
                self.run("cppb_copy")
            elif hit(BACK_BTN):
                self.run("cppb_up")
            return
        i = self.top + y - self.list_top()
        if y < self.list_top() or not 0 <= i < len(self.list.entries):
            return
        # jako v koumesu: klik jen vybere, klik na uz vybrany otevre (slozka = vlezt, soubor = vpravo)
        self.run("cppb_open" if i == self.cur else "chroma_setline %d" % (i + 1))


# =============================================================================
class CmdsDirview(Cmds):
    """Commandy dirview: jednotny protokol panelu (chroma_*) a vlastni (cppb_*)."""

    def __init__(self, ui):
        super().__init__("cppb")
        self.ui = ui
        for name, fn, desc in (
                ("chroma_dir", self._dir, "current directory"),
                ("chroma_setdir", self._setdir, "<path> - go to a directory (a file: select it)"),
                ("chroma_line", self._line, "selected line (1-based)"),
                ("chroma_setline", self._setline, "<n> - select line n"),
                ("cppb_open", self._open, "open the selected line"),
                ("cppb_view", self._view, "[path] - [git list]: the repo tree on the right"),
                ("cppb_repos", self._repos, "[repos]: all repos on the right"),
                ("cppb_timeaxis", self._timeaxis, "[timeaxis]: TIMEAXIS mode"),
                ("cppb_aicom", self._aicom, "[aicom]: AICOM mode"),
                ("cppb_remarks", self._www, "[remarks]: the last REMARKS on the right"),
                ("cppb_paste", self._paste, "[paste]: the clipboard as a new item of the last aicom"),
                ("cppb_copy", self._copy, "[copy]: the selected aicom item into the clipboard"),
                ("cppb_up", self._up, "one level up ([back] in TIMEAXIS and AICOM mode)"),
                ("cppb_move", self._move, "<-1|+1|pgup|pgdn|home|end> - move the selection"),
                ("panel_reload", self._reload, "read the directory again"),
                ("cppb_filter", self._filter, "[on|off] - filter of the code root")):
            self.register(name, fn, desc)

    def _dir(self, a):
        return [(self.ui.dir, "DIR")]

    def _setdir(self, a):
        if not a:
            return "chroma_setdir: usage: chroma_setdir <path>"
        if not self.ui.set_dir(a[0]):
            return "chroma_setdir: není adresář: " + a[0]
        return [(self.ui.dir, "DIR")]

    def _line(self, a):
        return [(str(self.ui.cur + 1), "LINE")]

    def _setline(self, a):
        if not a:
            return "chroma_setline: usage: chroma_setline <n>"
        try:
            ok = self.ui.set_line(int(a[0]))
        except ValueError:
            ok = False
        return None if ok else "chroma_setline: řádek mimo seznam"

    def _open(self, a):
        self.ui.open()

    def _view(self, a):
        if not self.ui.view_repo(a[0] if a else ""):
            return "cppb_view: adresar neni v git repu, nebo neni konzole"

    def _repos(self, a):
        if not self.ui.right(REPOS):
            return "cppb_repos: neni konzole"

    def _timeaxis(self, a):
        if not self.ui.view_timeaxis():
            return "cppb_timeaxis: nejde"

    def _aicom(self, a):
        if not self.ui.view_aicom():
            return "cppb_aicom: not possible"

    def _www(self, a):
        d = aicom.dirs(aicom.LINKS)
        if not d or not self.ui.right(ESENCE + d[-1]):
            return "cppb_remarks: no remarks, or no console"

    def _paste(self, a):
        to = self.ui.aicom_paste()
        return [(to, "FILE")] if to else "cppb_paste: the clipboard is empty"

    def _copy(self, a):
        if not self.ui.aicom_copy():
            return "cppb_copy: nothing went to the clipboard"

    def _up(self, a):
        self.ui.up()
        return [(self.ui.dir, "DIR")]

    def _move(self, a):
        if not a:
            return "cppb_move: usage: cppb_move <-1|+1|pgup|pgdn|home|end>"
        if not self.ui.move(a[0]):
            return "cppb_move: nevím kam: " + a[0]
        return [(str(self.ui.cur + 1), "LINE")]

    def _reload(self, a):
        self.ui.reload()

    def _filter(self, a):
        self.ui.filt = (not self.ui.filt) if not a else a[0] != "off"
        self.ui.reload()
        return [("on" if self.ui.filt else "off", "FILTER")]


# =============================================================================
def main():
    d, port, code = os.getcwd(), _config.number("panel_port", 54330), _config.place("code_root") or "/nonexistent"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 1
        elif args[i] == "--code" and i + 1 < len(args):
            code = args[i + 1]
            i += 1
        elif not args[i].startswith("--"):
            d = args[i]
        i += 1

    ui = TermUi(CodeInfo(code))
    cmds = ui.cmds = CmdsDirview(ui)
    cmds.start_ws(port)

    # SIGTERM / SIGHUP: ukoncit slusne, at se terminal vrati do puvodniho stavu
    def quit_(*_):
        raise SystemExit(0)
    for s in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, quit_)

    ui.start(d)
    last = 0.0
    try:
        while True:
            r, _, _ = select.select([0], [], [], 0.1)
            if r:
                ui.input()
            cmds.drain()                                   # commandy z WS na hlavnim vlakne
            if time.time() - last > 0.3:
                last = time.time()
                ui.tick()
    except KeyboardInterrupt:
        pass
    finally:
        ui.stop()


if __name__ == "__main__":
    main()
