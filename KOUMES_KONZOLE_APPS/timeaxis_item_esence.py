#!/usr/bin/env python3
"""timeaxis_item_esence - esence polozky TIMEAXIS v jednom okne konzole (clmon).
Vydeleno z clmon (driv `esence:<cesta>` v jeho prohlizeci); zaklad je konzole_view.Pane.

Usage: timeaxis_item_esence.py <polozka>
Polozka je soubor sam, nebo adresar - pak jeho soubory za sebou, mezi soubory cara.
Soubor se kresli jako ve vieweru (spolecny kod konzole_view): md a html vykreslene,
obrazky pres chafa. Prvnich 25 radku, [more] dalsich 50, [less] zpet; obrazek maly,
[more] zvetseny, [less] zpet, klik na obrazek = otevrit externe. Binarky, URL a relativni
html v textu jsou odkazy (klik = otevrit externe), jmeno souboru je odkaz do panelu vpravo.
Polozka aicomu: vsechny polozky od ni ke starsim (od nejnovejsi, kdyz je vybrana ta), nad
kazdou cara s datem a casem; ⊟ / ⊞ na zacatku cary polozku sbali a rozbali, pamatuje si to
aicom.t2l v jejim aicomu. Nad polozkami radek aicomu, ⊟ / ⊞ sbali a rozbali cely; pod nim az OLDER
starsich aicomu stejneho druhu, sbalene.
"""

import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import aicom  # noqa: E402
from konzole_view import BOLD, DIM, RST, Pane, cwidth, kind_of, read_text, short, wrap_cells  # noqa: E402

ESENCE = "esence:"       # @file panelu: konzole tak pozna, co panel ukazuje
MORE = 50                # radku navic na [more]
OLDER = 8                # kolik starsich aicomu pod otevrenym


class Esence(Pane):
    HOVER = True

    def __init__(self, item):
        self.item = os.path.abspath(item)
        super().__init__(ESENCE + self.item)
        self.lines = {}          # soubor -> kolik radku textu je videt

    def render(self, w, h):
        root = self.item
        if aicom.is_aicom(root):
            d = root if os.path.isdir(root) else os.path.dirname(root)
            self.show_dir(d, False, aicom.from_item(root), w, h)
            for o in aicom.older(d, OLDER):
                self.add("")
                self.show_dir(o, True, aicom.files(o)[::-1], w, h)
            self.title(short(root), "esence · [more] / [less] · klik na obrázek = otevřít")
            return
        if os.path.isdir(root):
            try:
                names = sorted(os.listdir(root), key=str.lower)
            except OSError as e:
                self.add(DIM + str(e) + RST)
                return
            files = [os.path.join(root, n) for n in names
                     if not n.startswith(".") and os.path.isfile(os.path.join(root, n))]
        else:
            files = [root]
        self.show(files, root, False, w, h)
        self.title(short(root), "esence · [more] / [less] · klik na obrázek = otevřít")

    def show_dir(self, d, older, files, w, h):
        """Radek aicomu a pod nim jeho polozky; starsi je sbaleny, zaznam ve stavu to obraci."""
        small = (aicom.WHOLE in aicom.shrunk(d)) != older
        head = "%s %s " % ("⊞" if small else "⊟", os.path.basename(d))
        self.add(BOLD + head + RST + DIM + "═" * max(1, w - 1 - cwidth(head)) + RST, ("fold_dir", d))
        if not small:
            self.show(files, d, True, w, h)

    def show(self, files, root, dated, w, h):
        for k, f in enumerate(files):
            kind = kind_of(f)
            if dated:
                if k:
                    self.add("")
                    self.add("")
                # cara s datem a casem; klik = sbalit, rozbalit
                small = os.path.basename(f) in aicom.shrunk(os.path.dirname(f))
                head = "%s %s " % ("⊞" if small else "⊟", aicom.stamp(f) or os.path.basename(f))
                if small:
                    head += os.path.basename(f) + " "
                self.add(BOLD + head[0] + RST + DIM + head[1:]
                         + "─" * max(1, w - 1 - cwidth(head)) + RST, ("fold", f))
                if small:
                    continue
            elif k:
                self.add(DIM + "─" * max(1, w - 1) + RST)          # mezi soubory cara
            text = None if kind == "img" else read_text(f, self.MAX)[0]
            if kind != "img" and text is None:
                # binarka (externi dokument): jen jmeno jako odkaz; klik = otevrit externe
                self.add_link(" ", os.path.basename(f), "", ("ext", f))
                continue
            if len(files) > 1:
                self.add_link("", os.path.basename(f), "", ("int", f))      # jmeno = interni odkaz
            if kind == "img":
                self.add_image(f, root, "", w, max(12, (w - 1) // 3), max(4, h // 3))
                continue
            start = len(self.rows)
            if not self.add_rendered(f, w):                     # md / html jako ve vieweru
                for ln in text.splitlines():
                    for part in wrap_cells(ln.expandtabs(4), w - 1) or [""]:
                        self.add_text(part, os.path.dirname(f))
            self.cut_rows(start, self.lines.get(f, self.STEP), f, "řádků")

    def action(self, what, arg):
        if what == "fold":
            aicom.toggle(arg)
            self.resized = True
        elif what == "fold_dir":
            aicom.toggle(os.path.join(arg, aicom.WHOLE))
            self.resized = True

    def more_less(self, f, less):
        self.lines[f] = self.STEP if less else self.lines.get(f, self.STEP) + MORE


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: timeaxis_item_esence.py <polozka>")
    try:
        Esence(sys.argv[1]).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
