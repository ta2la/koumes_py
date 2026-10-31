#!/usr/bin/env python3
"""config_view - assigns where things are on this machine: an app over config.t2l.

Click a row = what it is for and [choose] [type] [clear]. [choose] walks the directories,
[type] asks for the text. The file is watched; the console reads it again by itself, so a
button appears without a restart.

Lives directly in KOUMES_KONZOLE, next to the console; [config] in the menu starts it.

Usage: config_view.py [config.t2l]
"""

import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "KOUMES_KONZOLE_APPS"))   # konzole_view
from konzole_view import BOLD, C_BTN, DIM, RST, Pane, short  # noqa: E402

sys.path.insert(0, HERE)
import config  # noqa: E402

SEL = "\x1b[48;5;236m"
KEY_W = 12


class ConfigView(Pane):
    def __init__(self, path):
        self.WATCH = path
        config.ensure(path)
        super().__init__(path)
        self.sel = None            # selected key
        self.walk = None           # [choose]: directory being walked
        self.kind = "dir"          # what [choose] takes: dir / file

    def state(self, value, kind):
        if not value:
            return DIM + "-" + RST
        if kind == "text":
            return "✔"
        return "✔" if os.path.exists(config.expand(value)) else "\x1b[31m✗" + RST

    def buttons(self, row, x, labels):
        """Buttons on one row: action by column, see click()."""
        spans = []
        for name, label in labels:
            spans.append((x, x + len(label) - 1, name))
            row += C_BTN + label + RST + "  "
            x += len(label) + 2
        self.spans[len(self.rows)] = spans
        self.add(row, ("btn", 0))

    def field(self, key, attr, value, kind, what):
        """One row, under the selected one what it is for and its buttons."""
        on = key == self.sel
        text = " %s%s%s  %s" % (attr, " " * (KEY_W - len(attr)), self.state(value, kind), value or DIM + "not set" + RST)
        self.add((SEL + text.replace(RST, RST + SEL) + "\x1b[K" + RST) if on else text, ("sel", key))
        if on:
            start = len(self.rows)
            if not self.add_md(what, HERE, self.size_w - 4):
                self.add(what)
            self.add("")
            for j in range(start, len(self.rows)):
                self.rows[j] = "    " + self.rows[j]
            labels = ([("choose", "[choose]")] if kind != "text" else []) + [("type", "[type]"), ("clear", "[clear]")]
            self.buttons("    ", 4, labels)
            self.kind = kind

    def render(self, w, h):
        self.spans = {}
        self.size_w = w
        if self.walk:
            return self.render_walk(w)
        self.add("Where things are on this machine. An empty row = the feature is off and its button "[:w - 1])
        self.add("is not shown. ✔ exists · ✗ does not exist · click a row = what it is for"[:w - 1])
        self.add("")
        recs = config.load(self.path)
        for rec in recs:
            typ = rec.get("type", "")
            if typ == "places":
                self.add(BOLD + "places" + RST)
            elif typ == "koumes":
                self.add("")
                self.add(BOLD + "koumes " + rec.get("id", "") + RST)
            elif typ == "diag":
                self.add("")
                self.add(BOLD + "diag" + RST)
            else:
                continue
            for _, attr, kind, what in config.fields(typ):
                key = attr if typ == "places" else "diag." + attr if typ == "diag" else "%s.%s" % (rec.get("id", ""), attr)
                self.field(key, attr, rec.get(attr, ""), kind, what)
        self.add("")
        self.buttons(" ", 1, [("add_koumes", "[+ koumes]")]
                     + ([] if config.records("diag", self.path) else [("add_diag", "[+ diag]")]))
        self.title(short(self.path), "watched")

    def render_walk(self, w):
        """[choose]: subdirectories, for a file also files; click = go in, on a file = take it."""
        self.add(BOLD + short(self.walk) + RST)
        self.buttons(" ", 1, ([("use", "[use this directory]")] if self.kind == "dir" else [])
                     + [("cancel", "[cancel]")])
        self.add("")
        self.add(" ..", ("go", os.path.dirname(self.walk)))
        try:
            names = sorted(os.listdir(self.walk), key=str.lower)
        except OSError as e:
            self.add(DIM + " cannot read: %s" % e.strerror + RST)
            names = []
        for n in names:
            full = os.path.join(self.walk, n)
            if os.path.isdir(full):
                self.add(" " + n + "/", ("go", full))
        if self.kind == "file":
            for n in names:
                full = os.path.join(self.walk, n)
                if os.path.isfile(full):
                    self.add(" " + DIM + n + RST, ("take", full))
        self.title(short(self.path), "choose for " + (self.sel or ""))

    def put(self, value):
        """Assign to the selected key; paths under home are written with ~."""
        err = config.assign(self.sel, short(value) if value.startswith("/") else value, self.path)
        if err:
            self.ask(err, [("ok", None)])
        self.walk = None
        self.resized = True

    def start_walk(self):
        rec = self.value()
        d = config.expand(rec)
        d = d if os.path.isdir(d) else os.path.dirname(d)
        self.walk = d if d and os.path.isdir(d) else config.tree(self.path)
        self.resized = True

    def value(self):
        """Current value of the selected key."""
        rid, _, attr = self.sel.rpartition(".")
        for r in config.load(self.path):
            if (not rid and r.get("type") == "places") or (rid == "diag" and r.get("type") == "diag") \
                    or (rid and r.get("id") == rid):
                return r.get(attr, "")
        return ""

    def do_button(self, name):
        if name == "choose":
            self.start_walk()
        elif name == "type":
            self.ask("%s:" % self.sel, [("ok", lambda: self.put(self.dlg_value())), ("cancel", None)],
                     value=self.value())
        elif name == "clear":
            self.put("")
        elif name == "use":
            self.put(self.walk)
        elif name == "cancel":
            self.walk = None
            self.resized = True
        elif name == "add_koumes":
            self.ask("Name of the new koumes button:", [("ok", self.add_koumes), ("cancel", None)], value="")
        elif name == "add_diag":
            config.add("diag", path=self.path)
            self.resized = True

    def add_koumes(self):
        name = self.dlg_value().strip()
        err = config.add("koumes", name, self.path) if name else None
        if err:
            self.ask(err, [("ok", None)])
        self.resized = True

    def click(self, y, x=0):
        i = self.top + y
        act = self.acts[i] if 0 <= i < len(self.acts) else None
        if act and act[0] == "btn":
            hit = next((n for a, b, n in self.spans.get(i, []) if a <= x <= b), None)
            if hit:
                self.do_button(hit)
            return
        super().click(y, x)

    def action(self, what, arg):
        if what == "sel":
            self.sel = None if self.sel == arg else arg
        elif what == "go":
            self.walk = arg
            self.top = 0
        elif what == "take":
            return self.put(arg)
        self.resized = True


def main():
    try:
        ConfigView(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else config.CONFIG_T2L).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
