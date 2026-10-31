#!/usr/bin/env python3
# clmon - Claude Monitor: kdo z agentu prave jede a co si mezi sebou pisou.
#
# Usage:
#   clmon              # zivy terminalovy pohled (curses)
#   clmon -H 48        # zpravy za poslednich 48 hodin (default 24)
#   clmon --once       # jednou vypsat jako text a skoncit (bez curses)
#   clmon --chat       # jen pindani, bez seznamu agentu (pouziva clmon2)
#   clmon -h           # help
#
# Odkud to bere:
#   ~/.claude/sessions/<pid>.json    - bezici sessions: jmeno, cwd, stav busy/idle, sessionId
#   ~/.claude/projects/<slug>/*.jsonl - prepisy konverzaci; odeslana zprava je tam volani
#                                      nastroje SendMessage, prijata je <cross-session-message>
#
# Nic nezapisuje a do zadne session nesaha - jen cte.

import curses
import glob
import json
import locale
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
SESS_DIR = os.path.join(HOME, ".claude", "sessions")
PROJ_DIR = os.path.join(HOME, ".claude", "projects")
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(SCRIPT_DIR), "KOUMES_KONZOLE"))
import config as _config  # noqa: E402
CONFIG_FILE = _config.place("agents")       # seznam agentu, "" = jen adresare
WORKERS_DIR = _config.place("workers")
TEMP_ICONS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]

RE_RECV = re.compile(r'<cross-session-message\b([^>]*)>\n?(.*?)</cross-session-message>', re.S)
RE_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
# velikost kontextu = vstup posledni odpovedi: novy vstup + cteni z cache + zapis do cache
RE_USAGE = re.compile(rb'"usage":\{(.{0,300})', re.S)
RE_TOK = {k: re.compile(b'"' + k + rb'":(\d+)') for k in
          (b"input_tokens", b"cache_read_input_tokens", b"cache_creation_input_tokens")}
RE_MODEL = re.compile(rb'"model":"([^"]+)"')


# ---- sirka znaku v terminalu ------------------------------------------------
# Emoji zabira dve bunky, variation selector a combining znaky zadnou. Znak
# nasledovany VS16 (U+FE0F) se kresli jako emoji, tedy na dve bunky (⚠️, 1️⃣).
def cwidth(s):
    w = 0
    chars = list(s)
    for i, ch in enumerate(chars):
        o = ord(ch)
        if o in (0xFE0F, 0xFE0E, 0x200D) or unicodedata.combining(ch) \
                or unicodedata.category(ch) in ("Me", "Mn", "Cf"):
            continue
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if nxt == "️":
            w += 2
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def cut(s, width):
    """Oriznout na danou sirku bunek; co se nevejde, konci znakem …"""
    if cwidth(s) <= width:
        return s
    out, w = "", 0
    for ch in s:
        cw = cwidth(out + ch) - w
        if w + cw > width - 1:
            break
        out += ch
        w += cw
    return out + "…"


def wrap(s, width):
    """Zalomit text na radky dane sirky, po slovech, dlouha slova natvrdo."""
    lines = []
    for para in s.split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = word if not cur else cur + " " + word
            if cwidth(cand) <= width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            while cwidth(word) > width:
                part = cut(word, width + 1)[:-1] or word[:1]
                lines.append(part)
                word = word[len(part):]
            cur = word
        lines.append(cur)
    return lines


# ---- jmena ------------------------------------------------------------------
def load_conf_names():
    """cesta -> '<ikona> <jmeno>' z projects.conf (stejne jako visacky v clswp)"""
    names = {}
    try:
        text = open(CONFIG_FILE, encoding="utf-8").read()
    except OSError:
        return names
    for block in re.split(r"\n\s*\n", text):
        kv = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
        if "path" in kv:
            p = os.path.expanduser(kv["path"]).rstrip("/")
            nm = kv.get("name") or os.path.basename(p)
            names[p] = (kv.get("icon", "") + " " + nm).strip()
    for i, ic in enumerate(TEMP_ICONS if WORKERS_DIR else [], 1):
        names[os.path.join(WORKERS_DIR, "TEMP%d" % i)] = "%s T%d" % (ic, i)
    return names


def slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def short_path(p):
    return "~" + p[len(HOME):] if p.startswith(HOME) else p


# ---- bezici sessions ----------------------------------------------------------
def alive(pid):
    try:
        cmd = open("/proc/%d/cmdline" % pid, "rb").read().split(b"\0")
    except OSError:
        return False
    # proces na pozadi si prepise jmeno na "claude bg-spare"
    return bool(cmd) and os.path.basename(cmd[0]).split(b" ")[0] == b"claude"


def load_agents(conf):
    sess = []
    for f in glob.glob(os.path.join(SESS_DIR, "*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = d.get("pid")
        if isinstance(pid, int) and alive(pid):
            sess.append(d)
    # Zaparkovana session: okno zustava, ale praci prevzal proces na pozadi (kind bg,
    # jobId = parkedJobId okna) a pise novy prepis. Stav, prepis a model brat z nej,
    # a proces na pozadi neukazovat jako dalsiho agenta.
    jobs = {d.get("jobId"): d for d in sess if d.get("kind") == "bg" and d.get("jobId")}
    parked = set()
    for d in sess:
        job = jobs.get(d.get("parkedJobId"))
        if job:
            parked.add(id(job))
            for k in ("sessionId", "status", "statusUpdatedAt"):
                if job.get(k):
                    d[k] = job[k]
    agents = []
    for d in sess:
        if id(d) in parked:
            continue
        pid = d.get("pid")
        cwd = d.get("cwd", "")
        name = d.get("name") or conf.get(cwd.rstrip("/")) or os.path.basename(cwd)
        tr = os.path.join(PROJ_DIR, slug(cwd), (d.get("sessionId") or "") + ".jsonl")
        if not os.path.exists(tr):
            hit = glob.glob(os.path.join(PROJ_DIR, "*", (d.get("sessionId") or "?") + ".jsonl"))
            tr = hit[0] if hit else ""
        agents.append({
            "pid": pid, "name": name, "cwd": cwd,
            "status": d.get("status", "?"),
            "since": (d.get("statusUpdatedAt") or 0) / 1000.0,
            "transcript": tr,
            "sock": d.get("messagingSocketPath") or "",
        })
    agents.sort(key=lambda a: a["name"])
    return agents


# ---- zpravy z prepisu -----------------------------------------------------------
def ts_of(d):
    t = d.get("timestamp")
    if not t:
        return 0.0
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


class Log:
    """Cte prepisy prirustkove: pamatuje si, kam v kazdem souboru dosel."""

    def __init__(self, hours):
        self.hours = hours
        self.offsets = {}
        self.owner = {}       # prepis -> jmeno session, ktera ho pise
        self.msgs = []        # dict(t, frm, to, text, sent, recv)
        self.addr = {}        # "uds:/.../<pid>.sock" -> jmeno session
        self.usage = {}       # prepis -> (kontext v tokenech, model) z posledni odpovedi

    def _usage(self, f, raw):
        """Posledni odpoved hlavniho vlakna nese, kolik tokenu slo na vstup."""
        if b'"type":"assistant"' not in raw or b'"isSidechain":true' in raw:
            return
        mu = RE_USAGE.search(raw)
        if not mu:
            return
        ctx = 0
        for rx in RE_TOK.values():
            mt = rx.search(mu.group(1))
            if mt:
                ctx += int(mt.group(1))
        mm = RE_MODEL.search(raw)
        model = mm.group(1).decode("utf-8", "replace") if mm else ""
        if ctx and model != "<synthetic>":
            self.usage[f] = (ctx, model)

    def name(self, who):
        """Odpoved jde na adresu socketu, ne na jmeno - prelozit, kdyz ho zname."""
        return self.addr.get(who, who)

    def files(self, agents):
        horizon = time.time() - self.hours * 3600
        out = {a["transcript"] for a in agents if a["transcript"]}
        for f in glob.glob(os.path.join(PROJ_DIR, "*", "*.jsonl")):
            try:
                if os.path.getmtime(f) >= horizon:
                    out.add(f)
            except OSError:
                pass
        return out

    def update(self, agents, conf):
        for a in agents:
            if a["transcript"]:
                self.owner[a["transcript"]] = a["name"]
            if a["sock"]:
                self.addr["uds:" + a["sock"]] = a["name"]
        horizon = time.time() - self.hours * 3600
        for f in self.files(agents):
            try:
                size = os.path.getsize(f)
            except OSError:
                continue
            off = self.offsets.get(f, 0)
            if size < off:
                off = 0
            if size == off:
                continue
            with open(f, "rb") as fh:
                fh.seek(off)
                chunk = fh.read()
            end = chunk.rfind(b"\n") + 1
            self.offsets[f] = off + end
            for raw in chunk[:end].splitlines():
                if b'"usage":{' in raw:
                    self._usage(f, raw)
                if b"SendMessage" not in raw and b"cross-session-message" not in raw:
                    continue
                try:
                    d = json.loads(raw)
                except ValueError:
                    continue
                t = ts_of(d)
                if t < horizon:
                    continue
                me = self.owner.get(f) or conf.get((d.get("cwd") or "").rstrip("/")) \
                    or os.path.basename(d.get("cwd") or "?")
                self._take(d, t, me)
        self.msgs.sort(key=lambda m: m["t"])

    def _take(self, d, t, me):
        m = d.get("message") or {}
        c = m.get("content")
        if d.get("type") == "assistant" and isinstance(c, list):
            for x in c:
                if x.get("type") == "tool_use" and x.get("name") == "SendMessage":
                    inp = x.get("input") or {}
                    text = inp.get("message") or ""
                    if not text:
                        continue
                    self._add(t, me, inp.get("to", "?"), text, sent=True)
        elif d.get("type") == "user":
            texts = [c] if isinstance(c, str) else \
                [x.get("text", "") for x in (c or []) if isinstance(x, dict)]
            for s in texts:
                for mm in RE_RECV.finditer(s or ""):
                    attrs = dict(RE_ATTR.findall(mm.group(1)))
                    frm = attrs.get("from-name") or attrs.get("from", "?")
                    if attrs.get("from") and attrs.get("from-name"):
                        self.addr[attrs["from"]] = attrs["from-name"]
                    self._add(t, frm, me, mm.group(2).strip(), sent=False)

    def _add(self, t, frm, to, text, sent):
        # Tataz zprava lezi u odesilatele i u prijemce. Sloucit, kdyz sedi
        # zacatek textu a cas je do deseti minut od sebe.
        key = text.strip()[:120]
        for m in self.msgs:
            # stejny text vic prijemcum (rozeslani vsem) jsou ruzne zpravy
            if m["key"] == key and abs(m["t"] - t) < 600 and self.name(m["to"]) == self.name(to):
                if sent:
                    m["sent"] = True
                    m["to"] = to
                    m["t"] = min(m["t"], t)
                else:
                    m["recv"] = True
                return
        self.msgs.append({"t": t, "frm": frm, "to": to, "text": text.strip(),
                          "key": key, "sent": sent, "recv": not sent})


# ---- spolecne formatovani ----------------------------------------------------------
def ago(sec):
    sec = max(0, int(sec))
    if sec < 60:
        return "%ds" % sec
    if sec < 3600:
        return "%dm" % (sec // 60)
    if sec < 86400:
        return "%dh" % (sec // 3600)
    return "%dd" % (sec // 86400)


def ktok(n):
    if n >= 1000000:
        return "%.1fM" % (n / 1000000.0)
    return "%dk" % round(n / 1000.0)


def fsize(path):
    try:
        n = os.path.getsize(path)
    except OSError:
        return "?"
    return "%.0f MB" % (n / 1e6) if n >= 1e6 else "%.0f kB" % (n / 1e3)


def second_line(a, log):
    """Druhy radek instance: model, velikost kontextu, prepis, pid."""
    ctx, model = log.usage.get(a["transcript"], (0, ""))
    parts = [model.replace("claude-", "") or "model ?",
             "kontext " + (ktok(ctx) if ctx else "?"),
             "přepis " + fsize(a["transcript"]),
             "pid %d" % a["pid"]]
    return " · ".join(parts)


def hhmm(t):
    lt = datetime.fromtimestamp(t)
    if lt.date() == datetime.now().date():
        return lt.strftime("%H:%M")
    return lt.strftime("%d.%m %H:%M")


def mark(m):
    # ✓ = videt u obou stran, → = jen odeslano, ← = jen prijato (odesilatel neznamy)
    if m["sent"] and m["recv"]:
        return "✓"
    return "→" if m["sent"] else "←"


# ---- textovy vystup ----------------------------------------------------------------
HOUR = 3600
SEP_TEXT = "──────── starší než hodina ────────"


def once(hours, limit=30):
    conf = load_conf_names()
    agents = load_agents(conf)
    log = Log(hours)
    log.update(agents, conf)
    now = time.time()
    print("AGENTI")
    for a in agents:
        dot = "●" if a["status"] == "busy" else "○"
        print("  %s %s  %s %s  %s" % (dot, a["name"], a["status"],
                                       ago(now - a["since"]), short_path(a["cwd"])))
        print("      " + second_line(a, log))
    print("\nPINDANI (poslednich %d h, %d zprav)" % (hours, len(log.msgs)))
    # nejnovejsi nahore; cara oddeluje posledni hodinu od starsich
    lined = False
    for m in reversed(log.msgs[-limit:]):
        if not lined and m["t"] < now - HOUR:
            print("  " + SEP_TEXT)
            lined = True
        first = m["text"].splitlines()[0] if m["text"] else ""
        print("  %s %s %s %s  %s" % (hhmm(m["t"]), m["frm"], mark(m), log.name(m["to"]), cut(first, 90)))


# ---- curses -------------------------------------------------------------------------
class Tui:
    HELP = " q konec · ↑↓ PgUp PgDn Home End listovat · e cele zpravy · r obnovit "

    def __init__(self, scr, hours, show_agents=True):
        self.scr = scr
        self.hours = hours
        self.show_agents = show_agents     # --chat: jen pindani, bez seznamu agentu
        self.conf = load_conf_names()
        self.log = Log(hours)
        self.agents = []
        self.expand = False
        self.scroll = 0          # 0 = prilepeno nahore, kde jsou nejnovejsi zpravy
        self.colors = {}
        curses.curs_set(0)
        curses.use_default_colors()
        self.palette = []
        if curses.has_colors():
            for i, c in enumerate([curses.COLOR_CYAN, curses.COLOR_YELLOW, curses.COLOR_GREEN,
                                   curses.COLOR_MAGENTA, curses.COLOR_BLUE, curses.COLOR_RED], 1):
                curses.init_pair(i, c, -1)
                self.palette.append(curses.color_pair(i))
            curses.init_pair(20, curses.COLOR_GREEN, -1)
            curses.init_pair(21, curses.COLOR_WHITE, -1)
        scr.timeout(1000)

    def color(self, name):
        if not self.palette:
            return 0
        if name not in self.colors:
            self.colors[name] = self.palette[sum(map(ord, name)) % len(self.palette)] | curses.A_BOLD
        return self.colors[name]

    def put(self, y, x, s, attr=0, maxw=None):
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x >= w - 1:
            return x
        room = w - 1 - x if maxw is None else min(maxw, w - 1 - x)
        s = cut(s, room)
        try:
            self.scr.addstr(y, x, s, attr)
        except curses.error:
            pass
        return x + cwidth(s)

    def box(self, y, x, h, w, title):
        if h < 2 or w < 4:
            return
        dim = curses.A_DIM
        self.put(y, x, "┌" + "─" * (w - 2) + "┐", dim)
        for i in range(1, h - 1):
            self.put(y + i, x, "│", dim)
            self.put(y + i, x + w - 1, "│", dim)
        self.put(y + h - 1, x, "└" + "─" * (w - 2) + "┘", dim)
        self.put(y, x + 2, " " + title + " ", curses.A_BOLD)

    def msg_lines(self, inner):
        """Vsechny zpravy jako radky: (segmenty [(text, attr)], ...)"""
        rows = []
        lined = False
        horizon = time.time() - HOUR
        # nejnovejsi nahore; cara oddeluje posledni hodinu od starsich
        for m in reversed(self.log.msgs):
            if not lined and m["t"] < horizon:
                pad = max(0, inner - cwidth(SEP_TEXT))
                rows.append([(SEP_TEXT + "─" * pad, curses.A_DIM)])
                lined = True
            head = [(hhmm(m["t"]) + " ", curses.A_DIM),
                    (m["frm"], self.color(m["frm"])),
                    (" " + mark(m) + " ", curses.A_DIM),
                    (self.log.name(m["to"]), self.color(self.log.name(m["to"]))),
                    ("  ", 0)]
            used = sum(cwidth(s) for s, _ in head)
            if not self.expand:
                first = m["text"].splitlines()[0] if m["text"] else ""
                rows.append(head + [(cut(first, max(4, inner - used)), 0)])
                continue
            rows.append(head)
            for ln in wrap(m["text"], max(10, inner - 4)):
                rows.append([("    " + ln, 0)])
            rows.append([("", 0)])
        return rows

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        now = time.time()
        # agenti
        # instance je na dva radky: nahore kdo a co dela, pod tim model a kontext
        shown = min(len(self.agents), max(1, (h // 2 - 2) // 2)) if self.show_agents else 0
        ah = 2 * shown + 2 if self.show_agents else 0
        if self.show_agents:
            self.box(0, 0, ah, w - 1, "agenti · %d" % len(self.agents))
        for i, a in enumerate(self.agents[:shown]):
            y = 1 + 2 * i
            busy = a["status"] == "busy"
            x = self.put(y, 2, "● " if busy else "○ ",
                         (curses.color_pair(20) | curses.A_BOLD) if busy else curses.A_DIM)
            x = self.put(y, x, a["name"], self.color(a["name"]))
            x = max(x, 18)
            x = self.put(y, x, " %-4s %4s " % (a["status"], ago(now - a["since"])),
                         curses.A_BOLD if busy else curses.A_DIM)
            self.put(y, x, " " + short_path(a["cwd"]), curses.A_DIM, maxw=w - 3 - x)
            self.put(y + 1, 6, second_line(a, self.log), curses.A_DIM, maxw=w - 8)
        # zpravy
        my = ah
        mh = h - ah - 1
        inner = w - 5
        rows = self.msg_lines(inner)
        view = mh - 2
        maxscroll = max(0, len(rows) - view)
        self.scroll = min(self.scroll, maxscroll)
        start = self.scroll
        title = "pindani · %d zprav · %d h · nejnovejsi nahore" % (len(self.log.msgs), self.hours)
        if self.scroll:
            title += " · ↓%d" % self.scroll
        self.box(my, 0, mh, w - 1, title)
        for i, segs in enumerate(rows[start:start + view]):
            x = 2
            for s, attr in segs:
                x = self.put(my + 1 + i, x, s, attr, maxw=w - 3 - x)
        if not rows:
            self.put(my + 1, 2, "zadne zpravy mezi sessions za poslednich %d h" % self.hours, curses.A_DIM)
        self.put(h - 1, 0, cut(self.HELP, w - 1), curses.A_REVERSE)
        scr.refresh()
        return view

    def refresh_data(self):
        self.agents = load_agents(self.conf)
        self.log.update(self.agents, self.conf)

    def run(self):
        last = 0
        view = 10
        while True:
            if time.time() - last >= 2:
                self.refresh_data()
                last = time.time()
            view = self.draw()
            k = self.scr.getch()
            if k in (ord("q"), ord("Q"), 27):
                return
            if k == curses.KEY_DOWN:
                self.scroll += 1
            elif k == curses.KEY_UP:
                self.scroll = max(0, self.scroll - 1)
            elif k == curses.KEY_NPAGE:
                self.scroll += max(1, view - 1)
            elif k == curses.KEY_PPAGE:
                self.scroll = max(0, self.scroll - max(1, view - 1))
            elif k == curses.KEY_END:
                self.scroll = 10 ** 9
            elif k == curses.KEY_HOME:
                self.scroll = 0
            elif k in (ord("e"), ord("E")):
                self.expand = not self.expand
                self.scroll = 0
            elif k in (ord("r"), ord("R")):
                last = 0


def main():
    args = sys.argv[1:]
    hours = 24
    if "-h" in args or "--help" in args:
        print(open(os.path.realpath(__file__), encoding="utf-8").read().split("\n\n")[0]
              .replace("#!/usr/bin/env python3\n", "").replace("# ", "").replace("#", ""))
        return
    if "-H" in args:
        i = args.index("-H")
        try:
            hours = max(1, int(args[i + 1]))
        except (IndexError, ValueError):
            sys.exit("clmon: -H chce pocet hodin")
    if "--once" in args or not sys.stdout.isatty():
        once(hours)
        return
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(lambda scr: Tui(scr, hours, "--chat" not in args).run())


if __name__ == "__main__":
    main()
