#!/usr/bin/env python3
"""viewer - prohlizec souboru pro konzoli (clmon): text s cisly radku, markdown vykresleny
pres rich, obrazky pres chafa (i vlozene v md) a HTML prevedene pandocem na markdown.
Vydeleno z clmon (driv `clmon --view`); zaklad je konzole_view.Pane.

Usage: viewer.py <soubor> [--line N]
Klavesy: sipky / j k, PgUp PgDn / b mezera, g G = zacatek / konec, s = vykreslene / zdroj,
w = obrazky na celou sirku, e = editor na radku nahore, q = zavrit panel, r = obnovit.
Mys: obrazek [more] = zvetsit, [less] = zpet, klik na obrazek = otevrit externe.
"""

import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from konzole_view import (C_CODE, C_HEAD, C_KEY, DIM, MD_EXT, RST, Pane, arg_line,  # noqa: E402
                          kind_of, read_text, short, wrap_cells)


class View(Pane):
    def __init__(self, path, line=0):
        super().__init__(os.path.abspath(path) if path else "", line)
        # s = prepnout vykresleny obsah / zdroj s cisly radku. Kdyz se ma ukazat
        # konkretni radek, otevira se zdroj - cislo radku plati pro nej.
        self.source = line > 0

    def kind(self):
        return kind_of(self.path)

    def text_rows(self, text, w):
        """Zdroj s cisly fyzickych radku; md a t2l lehce obarvene."""
        lines = [l.expandtabs(4) for l in text.split("\n")]
        if len(lines) > 1 and lines[-1] == "":
            lines.pop()
        ext = os.path.splitext(self.path)[1].lower()
        gut = len(str(max(1, len(lines)))) + 1
        fence = False
        for i, line in enumerate(lines):
            s = line.lstrip()
            color = ""
            if ext in MD_EXT:
                if s.startswith("```") or s.startswith("~~~"):
                    fence, color = not fence, DIM
                elif fence:
                    color = C_CODE
                elif s.startswith("#"):
                    color = C_HEAD
                elif s.startswith(">"):
                    color = DIM
            elif ext == ".t2l":
                if s.startswith("#"):
                    color = DIM
                elif s.startswith("type:"):
                    color = C_HEAD
            if i + 1 == self.goto:
                self.goto_row = len(self.rows)
            mark = "\x1b[1;33m" if i + 1 == self.goto else DIM          # ukazany radek vyrazne
            for j, part in enumerate(wrap_cells(line, w - gut - 2)):
                num = (mark + str(i + 1).rjust(gut - 1) + RST) if j == 0 else " " * (gut - 1)
                c = part.find(":")
                if ext == ".t2l" and not color and j == 0 and c > 0:
                    body = C_KEY + part[:c + 1] + RST + part[c + 1:]      # klic: hodnota
                else:
                    body = color + part + RST
                self.add(num + "  " + body)
        return len(lines)

    def render(self, w, h):
        name = short(self.path) if self.path else "prázdný panel"
        note, info = "", ""
        if not self.path:
            note = "Prázdný panel. Soubor sem dá clmon --tp%d SOUBOR." % (self.slot() or 1)
        elif os.path.isdir(self.path):
            note = "To je adresář."
        elif not os.path.exists(self.path):
            note = "Soubor není: %s" % name
        else:
            kind = self.kind()
            base = os.path.dirname(self.path)
            if kind == "img":
                # samotny obrazek: nejdriv cely do panelu, [more] / w = na celou sirku s listovanim
                self.add_image(self.path, base, "", w, w - 1, h - 3)
                info = "obrázek · [more] / w = celá šířka · klik = otevřít"
            else:
                text, note = read_text(self.path, self.MAX)
                if text is not None:
                    done = not self.source and self.add_rendered(self.path, w)
                    if done:
                        info = ("md · s = zdroj · e = editor" if kind == "md" else "html jako text · s = zdroj") \
                            + " · obrázky [more] / w, klik = otevřít"
                    else:
                        self.begin()
                        n = self.text_rows(text, w)
                        info = "%d řádků" % n + (" · s = vykreslit" if kind in ("md", "html") else "") \
                            + " · e = editor"
        if note:
            if self.rows:
                self.add("")
            self.add(DIM + note + RST)
        self.title(name, info)

    def top_line(self):
        """Cislo radku zdroje, ktery je prave nahore (ve zdrojovem zobrazeni)."""
        for row in self.rows[self.top:self.top + 40]:
            m = re.match(r"(?:\x1b\[[0-9;]*m)*\s*(\d+)", row)
            if m:
                return int(m.group(1))
        return 0

    def key(self, k, h):
        if k in ("s", "S"):
            self.source = not self.source
            self.top = 0
            self.resized = True
        elif k in ("e", "E") and self.path and self.kind() != "img":
            # editor na radku, ktery je prave nahore
            line = self.top_line() if self.source or self.kind() == "text" else 0
            self.console("--tp%d" % (self.slot() or 1), self.path, "--edit", "--line", line)
        else:
            return False
        return True


def main():
    args = sys.argv[1:]
    line = arg_line(args)
    try:
        View(args[0] if args else "", line).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
