"""konzole_view - spolecny zaklad prohlizecu konzole (viewer.py, timeaxis_item_esence.py).

Pane: panel, ktery listuje hotovy barevny text (rows) a ke kazdemu radku muze mit akci
kliku (acts). Podtrida v render() plni radky pres add / add_link / add_text / add_image.

- obrazek: maly, pod nim [more] = zvetsit, [less] = zpet; klik na obrazek = samostatny
  prohlizec obrazku (eog, ...) v plne kvalite
- text: [more] / [less] pod nim, kdyz ho podtrida zkracuje (hook more_less)
- odkazy: URL modre, soubor s ▶▶▶ pred jmenem; pod mysi fialove; klik = otevrit
- obrazky pres chafa (barevne znaky, jdou i v tmuxu), md pres rich, html pres pandoc

S konzoli mluvi pres volby panelu v jejim tmuxu (@role view, @file, @title) - z nich
konzole kresli listu a stitek panelu; editor, zavreni panelu a panel vpravo pousti
prikazem konzole.
"""

import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import time
import unicodedata

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.realpath(__file__))
CONSOLE = os.path.join(os.path.dirname(HERE), "KOUMES_KONZOLE", "clmon")
SOCK = os.environ.get("CLMON4_SOCKET", "clmon4")          # tmux konzole

IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tif", ".tiff", ".ico")
MD_EXT = (".md", ".markdown")
HTML_EXT = (".html", ".htm")
IMG_TALL = 2000      # strop vysky obrazku v radcich - prakticky zadny, ridi se sirkou
DIM, BOLD, RST = "\x1b[2m", "\x1b[1m", "\x1b[0m"
C_KEY, C_HEAD, C_CODE = "\x1b[36m", "\x1b[1;35m", "\x1b[32m"
C_BTN = "\x1b[1;33m"                                # [more] [less]
C_URL = "\x1b[4;38;5;39m"                           # externi odkaz (URL): modre, podtrzene
C_LINK = "\x1b[4m"                                  # odkaz na soubor: podtrzene, pred nim ▶▶▶
C_HOVER = "\x1b[48;5;97m\x1b[97m"                   # odkaz pod mysi: fialove
C_DLG = "\x1b[48;5;237m\x1b[97m"                     # dialog (ask): ramecek a text
C_DLG_BTN = "\x1b[48;5;237m\x1b[1;33m"               # tlacitka dialogu
BG_MONO = "#0a0a0a"               # pozadi bloku ```monospace
LINK_MARK = "▶▶▶ "                                  # interni odkaz a externi dokument
RE_SGR = re.compile(r"\x1b\[[0-9;:]*m")
RE_URL = re.compile(r"https?://[^\s)\]>\"']+")
RE_HTML = re.compile(r"(?<![\w/:.-])((?:\.{1,2}/)?[\w./-]*\w\.html?)\b")
RE_IMG_MD = re.compile(r'^\s*!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)\s*$')
RE_IMG_HTML = re.compile(r'^\s*<img\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\'][^>]*>\s*$', re.I)
RE_ALT = re.compile(r'\balt\s*=\s*["\']([^"\']*)["\']', re.I)
RE_MOUSE = re.compile(rb"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
RE_PART = re.compile(rb"\x1b\[<[\d;]*$")              # zacatek sekvence mysi, zbytek jeste neprisel
READ_SIZE = 4096
KEY_NAMES = {b"\x1b[A": "up", b"\x1bOA": "up", b"\x1b[B": "down", b"\x1bOB": "down",
             b"\x1b[5~": "pgup", b"\x1b[6~": "pgdn", b"\x1b[H": "home", b"\x1b[1~": "home",
             b"\x1bOH": "home", b"\x1b[F": "end", b"\x1b[4~": "end", b"\x1bOF": "end"}


# ---- pomucky -----------------------------------------------------------------------------
def tmux(*args):
    r = subprocess.run(["tmux", "-L", SOCK] + [str(a) for a in args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout.rstrip("\n")


def popt(pane_id, name, value):
    tmux("set-option", "-p", "-t", pane_id, name, value)


def short(path):
    return "~" + path[len(HOME):] if path.startswith(HOME) else path


def fsize(path):
    try:
        n = os.path.getsize(path)
    except OSError:
        return "?"
    return "%.0f MB" % (n / 1e6) if n >= 1e6 else "%.0f kB" % (n / 1e3)


def cwidth(s):
    if s.isascii():
        return len(s)
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


def wrap_cells(s, width):
    """Rozdelit radek na kusy siroke nejvys `width` bunek terminalu."""
    if width < 4:
        width = 4
    if s.isascii():
        return [s[i:i + width] for i in range(0, len(s), width)] or [""]
    out, cur, w = [], "", 0
    for ch in s:
        cw = cwidth(cur[-1:] + ch) - cwidth(cur[-1:])      # sirka zavisi jen na sousednim znaku
        if w + cw > width and cur:
            out.append(cur)
            cur, w = "", 0
            cw = cwidth(ch)
        cur += ch
        w += cw
    out.append(cur)
    return out


sys.path.insert(0, os.path.join(os.path.dirname(HERE), "KOUMES_KONZOLE"))
try:
    import apps as _apps          # databaze konzole: kterym programem se co otevre (apps.t2l)
except ImportError:
    _apps = None


def run_ext(app, arg):
    subprocess.Popen([app, arg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def xdg_open(arg):
    """Otevrit externe (soubor, adresar, URL): program podle vyctu pripon v apps.t2l
    (record viewer_ext), jinak vychozi program systemu (xdg-open)."""
    run_ext((_apps and _apps.bin_for(arg)) or "xdg-open", arg)


def open_image(path):
    """Obrazek v plne kvalite v samostatnem prohlizeci obrazku (zoom, posun)."""
    xdg_open(path)


def link_row(pre, label, post, kind, hover):
    """Radek s odkazem: URL modre, soubor s ▶▶▶ pred jmenem; pod mysi fialove."""
    mark = "" if kind == "url" else LINK_MARK
    color = C_HOVER if hover else (C_URL if kind == "url" else C_LINK)
    return pre + color + mark + label + RST + post


# ---- obrazky, md, html -------------------------------------------------------------------
def chafa_lines(path, width, height, fine=False):
    """Obrazek jako radky barevnych znaku. None, kdyz to nejde. fine = jemneji a pomaleji:
    sextanty (2x3 body v bunce), nejvyssi kvalita, barvy v DIN99d."""
    if not shutil.which("chafa"):
        return None
    extra = ["--symbols", "block+border+sextant+wedge+quad+half", "--work", "9",
             "--color-space", "din99d", "--dither", "none"] if fine else []
    try:
        r = subprocess.run(["chafa", "--format", "symbols", "--colors", "full", "--polite", "on",
                            "--animate", "off", "--size", "%dx%d" % (max(8, width), max(4, height))]
                           + extra + [path], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = r.stdout.decode("utf-8", "replace").rstrip("\n")
    return [l + RST for l in out.split("\n")] if out else None


def img_path(src, base):
    """Cesta k obrazku z md / html; None u obrazku z webu."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I) and not src.startswith("file:"):
        return None
    path = src[7:] if src.startswith("file://") else src
    return path if os.path.isabs(path) else os.path.join(base, path)


def image_block(src, base, alt, width, height):
    """Radky pro jeden obrazek: vykresleny obrazek a pod nim popisek."""
    path = img_path(src, base)
    if path is None:
        return [DIM + "[obrázek z webu, nestahuje se: %s]" % src + RST]
    if not os.path.isfile(path):
        return [DIM + "[obrázek nenalezen: %s]" % src + RST]
    lines = chafa_lines(path, width, height)
    if lines is None:
        return [DIM + "[obrázek nejde vykreslit: %s]" % src + RST]
    cap = alt or os.path.basename(path)
    try:
        from PIL import Image
        with Image.open(path) as im:
            cap += "  %dx%d" % im.size
    except Exception:
        pass
    return lines + [DIM + cap + RST]


def md_parts(text, width):
    """Markdown rozdeleny na text (radky pres rich) a obrazky na samostatnem radku:
    [("text", radky)] / [("img", src, alt)]. None, kdyz rich neni."""
    try:
        import io
        from rich.console import Console
        from rich import box
        from rich.markdown import CodeBlock, Heading, Markdown, TableElement
        from rich.table import Table
        from rich.rule import Rule
        from rich.text import Text
        from rich.theme import Theme
    except ImportError:
        return None

    class Heading2(Heading):
        """Nadpis; pod ## tenka seda cara pres sirku."""
        def __rich_console__(self, console, options):
            yield from super().__rich_console__(console, options)
            if self.tag == "h2":
                yield Rule(style="grey50", characters="─")

    # tabulka: svisle cary mezi sloupci a vodorovne mezi radky, bez okraju po stranach
    GRID = box.Box("    \n"
                   "  │ \n"
                   " ─┼ \n"
                   "  │ \n"
                   " ─┼ \n"
                   " ─┼ \n"
                   "  │ \n"
                   "    \n")

    class Table2(TableElement):
        def __rich_console__(self, console, options):
            table = Table(box=GRID, show_edge=False, show_lines=True, border_style="grey50")
            if self.header is not None and self.header.row is not None:
                for column in self.header.row.cells:
                    table.add_column(column.content)
            if self.body is not None:
                for row in self.body.rows:
                    table.add_row(*[element.content for element in row.cells])
            yield table

    class Code2(CodeBlock):
        """Blok ```monospace: vystup konzole nebo diagram; znaky a mezery beze zmeny, bez zvyrazneni,
        delsi radek se orizne, nezalamuje; o neco svetlejsi pozadi pres celou sirku."""
        def __rich_console__(self, console, options):
            if self.lexer_name != "monospace":
                yield from super().__rich_console__(console, options)
                return
            # escape sekvence (SGR) plati: barvy a styly; sirku pocita rich bez nich
            out = Text(style="on " + BG_MONO, no_wrap=True, overflow="crop")
            out.append(("── monospace ").ljust(options.max_width, "─") + "\n", style="grey50")
            rows = str(self.text).rstrip("\n").split("\n")
            for i, r in enumerate(rows):
                row = Text.from_ansi(r) if "\x1b" in r else Text(r)
                row.truncate(options.max_width, overflow="crop", pad=True)
                out.append_text(row)
                if i < len(rows) - 1:
                    out.append("\n")
            yield out

    class Md(Markdown):
        elements = {**Markdown.elements, "heading_open": Heading2, "table_open": Table2,
                    "fence": Code2, "code_block": Code2}

    def rich_part(src):
        if not src.strip():
            return []
        buf = io.StringIO()
        con = Console(file=buf, width=max(20, width), force_terminal=True,
                      color_system="truecolor", legacy_windows=False, highlight=False,
                      theme=Theme({"markdown.h2": "bold"}))        # ## bez podtrzeni, cara je pod nim
        con.print(Md(src, hyperlinks=False))
        return buf.getvalue().rstrip("\n").split("\n")

    out, chunk, fence = [], [], False
    for line in text.split("\n"):
        s = line.lstrip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = not fence
        m = None if fence else RE_IMG_MD.match(line)
        h = None if fence or m else RE_IMG_HTML.match(line)
        if not m and not h:
            chunk.append(line)
            continue
        out.append(("text", rich_part("\n".join(chunk))))
        chunk = []
        if m:
            out.append(("img", m.group(2), m.group(1)))
        else:
            a = RE_ALT.search(line)
            out.append(("img", h.group(1), a.group(1) if a else ""))
    out.append(("text", rich_part("\n".join(chunk))))
    return out


def html_to_md(path):
    """HTML na markdown pres pandoc (obrazky zustanou jako ![..](..)). None, kdyz to nejde."""
    if not shutil.which("pandoc"):
        return None
    try:
        r = subprocess.run(["pandoc", "-f", "html", "-t", "gfm-raw_html", "--wrap=none", path],
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def kind_of(path):
    """Druh souboru podle pripony: img / md / html / text."""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMG_EXT:
        return "img"
    if ext in MD_EXT:
        return "md"
    if ext in HTML_EXT:
        return "html"
    return "text"


def read_text(path, limit=2000000):
    """(text, poznamka) - poznamka je duvod, proc text neni (None) nebo neni cely."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            data = f.read(limit)
    except OSError as e:
        return None, "Nejde číst: %s" % e.strerror
    if b"\0" in data[:8192]:
        return None, "Binární soubor, %s. Text v něm není." % fsize(path)
    text = data.decode("utf-8", "replace").replace("\r\n", "\n")
    note = ""
    if size > limit:
        note = "… zobrazeny první %d MB z %s" % (limit // 1000000, fsize(path))
    return text, note


# ---- panel -------------------------------------------------------------------------------
class Pane:
    """Panel konzole, ktery listuje radky s akcemi kliku. Podtrida plni radky v render()."""
    MAX = 2000000      # vic se z jednoho souboru necte
    HOVER = False      # pohyb mysi (1003): odkaz pod mysi se obarvi
    STEP = 25          # cut_rows: kolik radku napred, [less] se vraci sem
    WATCH = ""         # soubor, ktery se hlida: po zmene se panel nakresli znovu

    def __init__(self, path, line=0):
        self.path = path
        self.pane = os.environ.get("TMUX_PANE", "")
        self.rows, self.acts, self.links = [], [], {}
        self.hover = None
        self.top = 0
        self.size = (0, 0)
        self.resized = True
        self.big = set()           # obrazky zvetsene pres [more]
        self.wide = False          # w = vsechny obrazky na celou sirku
        self.goto = line
        self.goto_row = None
        self.jump = line > 0
        self.fd = sys.stdin.fileno()
        self.pending = b""                  # zacatek sekvence, kterou cteni rozetlo
        self.dlg = None            # otevreny dialog (ask): (text, [(popisek, fn)])
        self.dlg_buf = None        # textove pole dialogu (bajty utf-8); None = neni
        self.dlg_hits = []         # tlacitka dialogu na obrazovce: (y, x0, x1, index)
        self.testing = ("", "")    # (kdo, co) na appce testuje (konzole --in_test, @test, @test_msg)
        self._test_t = 0.0
        if self.pane:
            popt(self.pane, "@role", "view")
            popt(self.pane, "@file", self.path)

    # -- konzole --
    def slot(self):
        """Cislo panelu pN, ve kterem prohlizec bezi (0 = nevi)."""
        if not self.pane:
            return 0
        v = tmux("show-options", "-pqv", "-t", self.pane, "@slot")[1]
        return int(v) if v.isdigit() else 0

    def console(self, *args):
        """Prikaz konzole (editor, zavreni panelu, panel vpravo); spousti ho tmux zvenci."""
        tmux("run-shell", "-b", " ".join([shlex.quote(CONSOLE)] + [shlex.quote(str(a)) for a in args]))

    def title(self, name, info):
        if self.pane:
            popt(self.pane, "@title", name + (" · " + info if info else ""))

    # -- radky --
    def begin(self):
        self.rows, self.acts, self.links = [], [], {}
        self.hover = None

    def add(self, row, act=None):
        self.rows.append(row)
        self.acts.append(act)

    def add_link(self, pre, label, post, act):
        """Radek s odkazem: ▶▶▶ pred souborem, modre URL; pod mysi fialove."""
        self.links[len(self.rows)] = (pre, label, post, act[0])
        self.add(link_row(pre, label, post, act[0], False), act)

    def add_text(self, part, base):
        """Radek textu; prvni URL nebo relativni html v nem je odkaz."""
        m = RE_URL.search(part)
        if m:
            return self.add_link(part[:m.start()], m.group(0), part[m.end():], ("url", m.group(0)))
        for m in RE_HTML.finditer(part):
            target = os.path.normpath(os.path.join(base, m.group(1)))
            if os.path.isfile(target):
                return self.add_link(part[:m.start()], m.group(1), part[m.end():], ("html", target))
        self.add(part)

    def add_image(self, src, base, alt, w, small_w, small_h):
        """Obrazek: maly (small_w x small_h), [more] = na celou sirku, [less] = zpet;
        klik na obrazek = otevrit externe."""
        path = img_path(src, base)
        big = (path in self.big) != self.wide
        lines = image_block(src, base, alt, (w - 1) if big else small_w, IMG_TALL if big else small_h)
        if len(lines) < 2:                         # z webu, nenalezen, nejde vykreslit
            self.add(lines[0])
            return
        for r in lines[:-1]:
            self.add(r, ("open", path))
        self.add(lines[-1])                        # popisek
        self.add(" " + C_BTN + ("[less]" if big else "[more]") + RST, ("img", path))

    def add_md(self, text, base, w):
        """Markdown: text pres rich, obrazky pres add_image (tretina sirky). False = rich neni."""
        parts = md_parts(text, w - 1)
        if parts is None:
            return False
        for p in parts:
            if p[0] == "text":
                for r in p[1]:
                    # URL v radku je aktivni; zalomena ma zbytek v textu, odkaz je cely
                    m = RE_URL.search(RE_SGR.sub("", r))
                    url = m and next((u for u in RE_URL.findall(text) if u.startswith(m.group(0))),
                                     m.group(0))
                    self.add(r, ("url", url) if url else None)
            else:
                if self.rows:
                    self.add("")
                self.add_image(p[1], base, p[2], w, max(12, (w - 1) // 3), IMG_TALL)
                self.add("")
        return True

    def add_rendered(self, path, w):
        """md nebo html vykreslene jako ve vieweru (text pres rich, obrazky pres add_image).
        False = nejde (neni md / html, rich, pandoc) - pak ukazat zdroj."""
        kind, base = kind_of(path), os.path.dirname(path)
        if kind == "md":
            text = read_text(path, self.MAX)[0]
            return text is not None and self.add_md(text, base, w)
        if kind == "html":
            md = html_to_md(path)
            return md is not None and self.add_md(md, base, w)
        return False

    def cut_rows(self, start, n, arg, unit):
        """Radky od `start` nad prvnich n schovat a pod ne [more] / [less] (akce "txt" arg)."""
        total = len(self.rows) - start
        if total > n:
            del self.rows[start + n:]
            del self.acts[start + n:]
            for j in [j for j in self.links if j >= start + n]:
                del self.links[j]
        btn = []
        if n < total:
            btn.append(C_BTN + "[more]" + RST)
        if n > self.STEP:
            btn.append(C_BTN + "[less]" + RST)
        if btn:
            self.add(" " + "  ".join(btn) + DIM + "  %d z %d %s" % (min(n, total), total, unit) + RST,
                     ("txt", arg))

    # -- obsah: podtrida --
    def render(self, w, h):
        """Naplnit radky (begin, add...) a nastavit titulek."""

    def more_less(self, arg, less):
        """Klik na [more] / [less] pod textem (akce "txt")."""

    # -- dialog --
    def ask(self, text, choices=None, on_yes=None, image=None, value=None):
        """Dialog uprostred panelu: text a tlacitka. choices = [(popisek, fn)], fn None = jen
        zavrit; bez choices [ano] [ne] a ano zavola on_yes. image = (radky, sirka) obrazku
        nad textem (chafa_lines). Klik na tlacitko, nebo klavesa: Enter = prvni tlacitko,
        jinak prvni pismeno popisku. value = textove pole s touto hodnotou: klavesy pisou do
        nej, Enter = prvni tlacitko; tlacitko si text vezme pres dlg_value()."""
        self.dlg = (text, choices or [("ano", on_yes), ("ne", None)], image)
        self.dlg_buf = None if value is None else value.encode("utf-8")

    def dlg_value(self):
        """Text pole dialogu."""
        return (self.dlg_buf or b"").decode("utf-8", "ignore")

    def dlg_draw(self, w, h):
        """Dialog pres panel: retezec escape sekvenci, plni dlg_hits."""
        text, choices, image = self.dlg
        if self.dlg_buf is not None:
            text += "\n> " + self.dlg_value() + "█"
        lines = [part for t in text.split("\n") for part in (wrap_cells(t, max(10, min(w - 6, 56))) or [""])]
        btns = ["[%s]" % c[0] for c in choices]
        img, iw = image if image else ([], 0)
        inner = max([cwidth(t) for t in lines] + [iw, sum(len(b) for b in btns) + 2 * (len(btns) - 1)])
        body = [(" " * ((inner - iw) // 2) + l + C_DLG, (inner - iw) // 2 + iw) for l in img] \
            + [(t, cwidth(t)) for t in lines] + [("", 0)]          # obrazek na stred, pod nim text
        bw, bh = inner + 4, len(body) + 3
        x0, y0 = max(0, (w - bw) // 2), max(0, (h - bh) // 2)
        out = ["%s\x1b[%d;%dH┌%s┐" % (C_DLG, y0 + 1, x0 + 1, "─" * (bw - 2))]
        for j, (t, tw) in enumerate(body):
            out.append("\x1b[%d;%dH│ %s%s │" % (y0 + 2 + j, x0 + 1, t, " " * (inner - tw)))
        y = y0 + 2 + len(body)
        bx = x0 + 2 + (inner - (sum(len(b) for b in btns) + 2 * (len(btns) - 1))) // 2
        row = "\x1b[%d;%dH│%s" % (y, x0 + 1, " " * (bx - x0 - 1))
        self.dlg_hits = []
        for j, b in enumerate(btns):
            self.dlg_hits.append((y - 1, bx, bx + len(b) - 1, j))
            row += C_DLG_BTN + b + C_DLG + ("  " if j < len(btns) - 1 else "")
            bx += len(b) + 2
        out.append(row + " " * max(0, x0 + bw - 1 - (bx - 2)) + "\x1b[%d;%dH│" % (y, x0 + bw))
        out.append("\x1b[%d;%dH└%s┘%s" % (y + 1, x0 + 1, "─" * (bw - 2), RST))
        return "".join(out)

    def dlg_input(self, k):
        """Vstup, kdyz je otevreny dialog: jen jeho tlacitka, ostatni se zahodi."""
        text, choices = self.dlg[:2]
        pick = None
        if isinstance(k, tuple):
            if k[0] == "click":
                pick = next((j for y, a, b, j in self.dlg_hits if y == k[1] and a <= k[2] <= b), None)
        elif k in ("\r", "\n"):
            pick = 0
        elif self.dlg_buf is not None:
            if k in ("\x7f", "\x08"):                  # bajty znaku utf-8 pryc vsechny
                while self.dlg_buf and self.dlg_buf[-1] & 0xC0 == 0x80:
                    self.dlg_buf = self.dlg_buf[:-1]
                self.dlg_buf = self.dlg_buf[:-1]
            elif isinstance(k, str) and len(k) == 1 and k >= " ":
                self.dlg_buf += k.encode("latin-1")     # keys() dava bajty po jednom
            return
        elif isinstance(k, str) and len(k) == 1:
            pick = next((j for j, c in enumerate(choices) if c[0][:1].lower() == k.lower()), None)
        if pick is None:
            return
        self.dlg = None
        self.resized = True
        fn = choices[pick][1]
        if fn:
            fn()

    def poll_test(self):
        """Konzole --in_test pN <agent>: volba panelu @test = agent, ktery testuje, @test_img
        jeho obrazek, @test_msg co testuje (\\n = novy radek, napr. checklist). Okynko nad
        appkou s [cancel]; cancel volbu smaze, off okynko zavre, nova zprava ho prekresli."""
        if not self.pane or time.time() - self._test_t < 1:
            return
        self._test_t = time.time()
        who = tmux("show-options", "-pqv", "-t", self.pane, "@test")[1].strip()
        msg = tmux("show-options", "-pqv", "-t", self.pane, "@test_msg")[1].strip() if who else ""
        if (who, msg) == self.testing:
            return
        self.testing = (who, msg)
        if who:
            img = tmux("show-options", "-pqv", "-t", self.pane, "@test_img")[1].strip()
            lines = chafa_lines(img, 16, 8, fine=True) if img and os.path.isfile(img) else None
            self.ask("Agent %s is testing this app - hands off" % who
                     + ("\n\n" + msg.replace("\\n", "\n") if msg else ""),
                     [("cancel", lambda: popt(self.pane, "@test", ""))],
                     image=(lines, max(cwidth(re.sub(r"\x1b\[[0-9;]*m", "", l)) for l in lines))
                     if lines else None)
        elif self.dlg and self.dlg[0].startswith("🧪"):
            self.dlg = None
        self.resized = True

    # -- mys --
    def hover_at(self, y, x=0):
        """Mys nad radkem y (sloupec x) obrazovky: odkaz na nem fialove, predchozi zpet."""
        i = self.top + y
        old = self.hover
        if i == old:
            return
        self.hover = i
        for j, on in ((old, False), (i, True)):
            if j is not None and j in self.links and j < len(self.rows):
                pre, label, post, kind = self.links[j]
                self.rows[j] = link_row(pre, label, post, kind, on)

    def click(self, y, x=0):
        """Klik na radek y obrazovky (0 = nahore)."""
        i = self.top + y
        act = self.acts[i] if 0 <= i < len(self.acts) else None
        if not act:
            return
        what, arg = act
        if what == "img":
            self.big ^= {arg}
        elif what == "open":
            open_image(arg)                        # obrazek: samostatny prohlizec obrazku
            return
        elif what in ("ext", "url", "html"):
            xdg_open(arg)
            return
        elif what == "int":
            if self.pane:
                self.console("--open-right", self.pane, arg)        # soubor do panelu vpravo
            return
        elif what == "view":
            if self.pane:
                self.console("--open-right", self.pane, arg, "--viewer")   # do prohlizece vpravo
            return
        elif what == "txt":
            # [more] [less] na jednom radku: less je vpravo od more, kdyz jsou oba
            row = self.rows[i]
            self.more_less(arg, "[less]" in row and ("[more]" not in row or x > 9))
        else:
            self.action(what, arg)
            return
        self.resized = True

    def action(self, what, arg):
        """Dalsi akce kliku podtridy."""

    # -- terminal --
    def draw(self):
        w, h = shutil.get_terminal_size((80, 24))
        if self.WATCH:
            try:
                st = os.path.getmtime(self.WATCH)
            except OSError:
                st = None
            if st != getattr(self, "_watched", None):
                self._watched, self.resized = st, True
        if self.resized or (w, h) != self.size:
            self.resized = False
            self.goto_row = None
            self.begin()
            self.render(w, h)
            self.size = (w, h)
            if self.goto_row is not None and self.jump:
                self.top = max(0, self.goto_row - h // 3)      # ukazany radek do horni tretiny
                self.jump = False
        self.top = max(0, min(self.top, len(self.rows) - h))
        out = ["\x1b[H"]
        for y in range(h):
            i = self.top + y
            out.append("\x1b[%d;1H%s%s\x1b[K" % (y + 1, self.rows[i] if i < len(self.rows) else "", RST))
        if self.dlg:
            out.append(self.dlg_draw(w, h))
        os.write(sys.stdout.fileno(), "".join(out).encode("utf-8", "replace"))
        return h

    def keys(self, timeout):
        """Vstup jako seznam: 'up', 'down', 'pgup', ..., znak, ("click", y, x), ("move", y, x)."""
        try:
            r, _, _ = select.select([self.fd], [], [], timeout)
        except (InterruptedError, OSError):
            return None
        if not r:
            return None
        chunk = os.read(self.fd, READ_SIZE)
        if not chunk:
            raise SystemExit(0)
        data, self.pending = self.pending + chunk, b""
        keys = []
        while data:
            if RE_PART.fullmatch(data) or (len(chunk) == READ_SIZE and data in (b"\x1b", b"\x1b[")):
                self.pending = data                # cteni sekvenci rozetlo: dokonci se priste
                break
            m = RE_MOUSE.match(data)
            if m:
                b = int(m.group(1))
                if b == 64:
                    keys.append("up")
                elif b == 65:
                    keys.append("down")
                elif b == 0 and m.group(4) == b"M":
                    keys.append(("click", int(m.group(3)) - 1, int(m.group(2)) - 1))
                elif b & 32 and m.group(4) == b"M":
                    keys.append(("move", int(m.group(3)) - 1, int(m.group(2)) - 1))
                data = data[m.end():]
                continue
            hit = next((k for k in KEY_NAMES if data.startswith(k)), None)
            if hit:
                keys.append(KEY_NAMES[hit])
                data = data[len(hit):]
            elif data[:1] == b"\x1b":
                data = data[1:]
                while data and not (64 <= data[0] <= 126 and data[:1] != b"["):
                    data = data[1:]        # neznama sekvence - zahodit az po koncovy znak
                data = data[1:]
            else:
                keys.append(data[:1].decode("latin-1"))
                data = data[1:]
        last = max((i for i, k in enumerate(keys) if isinstance(k, tuple) and k[0] == "move"), default=-1)
        return [k for i, k in enumerate(keys)            # z pohybu mysi plati jen posledni
                if i == last or not (isinstance(k, tuple) and k[0] == "move")]

    def key(self, k, h):
        """Klavesa navic podtridy; True = zpracovana."""
        return False

    def run(self):
        import termios
        import tty
        old = termios.tcgetattr(self.fd)
        signal.signal(signal.SIGWINCH, lambda *a: setattr(self, "resized", True))
        out = sys.stdout.fileno()
        mouse = b"\x1b[?1000h\x1b[?1006h" + (b"\x1b[?1003h" if self.HOVER else b"")
        os.write(out, b"\x1b[?1049h\x1b[?25l" + mouse)     # vlastni obrazovka, bez kurzoru, mys
        try:
            tty.setcbreak(self.fd)
            while True:
                self.poll_test()
                h = self.draw()
                for k in self.keys(1.0) or []:
                    if self.dlg:
                        self.dlg_input(k)
                    elif isinstance(k, tuple) and k[0] == "move":
                        self.hover_at(k[1], k[2])
                    elif isinstance(k, tuple):
                        self.click(k[1], k[2])
                    elif self.key(k, h):
                        pass
                    elif k in ("q", "Q") and self.slot():
                        self.console("--tx%d" % self.slot())
                    elif k in ("up", "k"):
                        self.top -= 1
                    elif k in ("down", "j"):
                        self.top += 1
                    elif k in ("pgup", "b"):
                        self.top -= max(1, h - 1)
                    elif k in ("pgdn", " "):
                        self.top += max(1, h - 1)
                    elif k in ("home", "g"):
                        self.top = 0
                    elif k in ("end", "G"):
                        self.top = len(self.rows)
                    elif k in ("w", "W"):
                        self.wide = not self.wide
                        self.big = set()
                        self.resized = True
                    elif k in ("r", "R"):
                        self.resized = True
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, old)
            os.write(out, b"\x1b[?1003l\x1b[?1006l\x1b[?1000l\x1b[?25h\x1b[?1049l")


def arg_line(args):
    """`--line N` z argumentu (a pryc z nich); 0, kdyz neni."""
    line = 0
    if "--line" in args:
        i = args.index("--line")
        try:
            line = int(args[i + 1])
        except (IndexError, ValueError):
            pass
        del args[i:i + 2]
    return line
