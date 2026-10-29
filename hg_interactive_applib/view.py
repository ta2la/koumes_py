"""hg_interactive_app.view - Qt view of an interactive application.

DiagCanvas draws the entities of the view's scene and the dynamics on top;
InteractiveView holds the canvas, the floating panel (cmd / files / log) and
turns the mouse into the application's commands. An application subclasses
InteractiveView and supplies APP, SOURCE, TOOLBAR, ICONS, SUFFIX.
"""

import html
import os

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QIcon, QImage, QPainter,
                         QPen, QPixmap, QTextDocument)
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListView, QListWidget,
                             QListWidgetItem, QToolButton, QVBoxLayout, QWidget)

from hg_pool_py import POOL, SELSET, SOURCES, Sel

from .entities import C_BG, EntityBox, EntityCircle, EntityText, on_screen
from .panel import FloatPanel, FlowLayout
from .scene import RefColScene, ents_bound, paint_ents

C_DYN = QColor("#2b7bd9")      # dynamika - nahled behem modu


#=============================================================================
class DiagCanvas(QWidget):
#! Platno: kresli entity view (display list) a navrch dynamiku. Meritko a posun;
#! kolecko = zoom k mysi; posun obrazu je mod (AppMode_pan), ne tady.
#=============================================================================
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.scale, self.off = 1.0, QPointF(0, 0)    # obrazovka = scena * scale + off
        self.setMouseTracking(True)

    def to_scene(self, p):
        return QPointF((p.x() - self.off.x()) / self.scale, (p.y() - self.off.y()) / self.scale)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), C_BG)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self.off)
        p.scale(self.scale, self.scale)
        paint_ents(p, self.view.scene.entities() + self.view.err + self.view.dyn, self.scale)
        if self.view.cross:
            # agent na diagu pracuje (testy, restarty): kriz pres cely obraz
            p.resetTransform()
            pen = QPen(QColor(200, 40, 40, 150), 6)
            p.setPen(pen)
            r = self.rect()
            p.drawLine(r.topLeft(), r.bottomRight())
            p.drawLine(r.topRight(), r.bottomLeft())
            f = QFont("Sans")
            f.setPointSize(16)
            f.setBold(True)
            p.setFont(f)
            p.drawText(r.adjusted(0, 0, 0, -r.height() // 3), Qt.AlignmentFlag.AlignCenter,
                       "pracuje agent - " + self.view.cross)
        p.end()

    def fit(self, r, max_scale=1.0):
        if r.isEmpty() or self.width() < 2:
            return
        self.scale = min(self.width() / r.width(), self.height() / r.height(), max_scale)
        c = r.center()
        self.off = QPointF(self.width() / 2 - c.x() * self.scale,
                           self.height() / 2 - c.y() * self.scale)
        self.update()

    def ensure_visible(self, r, margin=40):
        a = QPointF(r.left() * self.scale + self.off.x(), r.top() * self.scale + self.off.y())
        b = QPointF(r.right() * self.scale + self.off.x(), r.bottom() * self.scale + self.off.y())
        dx = margin - a.x() if a.x() < margin else min(0, self.width() - margin - b.x())
        dy = margin - a.y() if a.y() < margin else min(0, self.height() - margin - b.y())
        self.off += QPointF(dx, dy)
        self.update()

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        m = ev.position()
        s = self.to_scene(m)
        self.scale *= f
        self.off = QPointF(m.x() - s.x() * self.scale, m.y() - s.y() * self.scale)
        self.update()

    def pan_by(self, dx, dy):
        """Posunout obraz o (dx, dy) jednotek sceny."""
        self.off += QPointF(dx * self.scale, dy * self.scale)
        self.update()



#=============================================================================
class InteractiveView(QWidget):
#! View interaktivni appky: platno se scenou, plovouci panel (cmd / files / log),
#! mys jako commandy appky. Appka dodá APP, SOURCE, TOOLBAR, ICONS, SUFFIX.
#=============================================================================
    APP = None               # koren appky (InteractiveApp)
    SOURCE = None            # trida zdroje souboru (SourceFile), ma THUMB a THUMB_DIR
    TOOLBAR = ()             # (tip, command, ikona, mod) tlacitek modu
    ICONS = ""               # adresar ikon
    SUFFIX = ""              # pripona souboru appky (tab files)
    GRID = 10
    DRAG_PX = 4              # od kolika pixelu je stisk tazeni, ne klik

    selected = pyqtSignal(int)
    opened = pyqtSignal(str)     # otevren jiny soubor (tab files, diag_open)

    def __init__(self, path: str, parent: QWidget = None):
        super().__init__(parent)
        # view kresli svou scenu (RefColScene), dokument nedrzi; soubory jsou v SOURCES.
        # Zatim jeden otevreny: nacteni noveho odnacte predchozi (SOURCES.open)
        self.path = os.path.realpath(path)          # = id zdroje
        SOURCES.open(self.SOURCE(self.path))
        self.dyn = []              # entity dynamiky (nahled behem modu), kresli se navrch
        self.err = []              # hlaska, kdyz soubor nejde precist
        self.cross = ""            # kdo na diagu prave pracuje (kriz pres obraz), "" = nikdo
        self._quiet = False        # pri prestavbe a select() neemitovat
        self._need_fit = False     # prvni zobrazeni: cely diagram do okna

        self.canvas = DiagCanvas(self)
        self.canvas.installEventFilter(self)
        self._press = None         # (bod sceny, bod viewportu) stisku leveho tlacitka
        self._ctrl = False         # ctrl pri stisku (multiselekt)
        self._shift = False        # shift pri stisku (vyber obdelnikem: 2 body)
        self._dragging = False

        # toolbar s mody a pod nim dialog aktivniho modu
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas)

        # plovouci okno nad diagramem (uvnitr appky): tab "cmd" = toolbar modu,
        # jmeno a hint aktivniho modu, jeho tlacitka; dalsi taby pribudou
        self.panel = FloatPanel(self)
        self._log = QListWidget()
        self._log.setWordWrap(True)
        self._log.setStyleSheet("font-family: monospace; font-size: 9px;")
        self._log_n = 0
        # tab cmd: ikony modu tecou jako slova v odstavci, pod nimi jmeno a hint
        # aktivniho modu, oddelovac a tlacitka modu (taky tecou)
        cmd_tab = QWidget()
        cl = QVBoxLayout(cmd_tab)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(4)
        icons = QWidget()
        il = FlowLayout(icons)
        self._mode_btns = {}
        for tip, cmd, icon, mode in self.TOOLBAR:
            b = QToolButton()
            b.setIcon(QIcon(os.path.join(self.ICONS, icon)))
            b.setIconSize(QSize(22, 22))
            b.setToolTip("%s (%s)" % (tip, cmd))
            b.setCheckable(mode is not None)
            b.clicked.connect(lambda _=False, c=cmd: self.APP.execute(c, self))
            il.addWidget(b)
            if mode is None:             # save: za nim pocet neulozenych zmen
                self._changes_lbl = QLabel()
                self._changes_lbl.setStyleSheet("color: #55606b; padding-right: 6px;")
                # radek flow layoutu zarovnava nahoru - stejna vyska jako tlacitko, text na stred
                self._changes_lbl.setFixedHeight(b.sizeHint().height())
                self._changes_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                il.addWidget(self._changes_lbl)
                continue
            self._mode_btns[mode] = b
        cl.addWidget(icons)
        self._hint = QLabel()
        self._hint.setWordWrap(True)
        cl.addWidget(self._hint)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #c3cad1;")
        cl.addWidget(sep)
        dlg = QWidget()
        self._dlg = FlowLayout(dlg)
        cl.addWidget(dlg)
        cl.addStretch()
        self.panel.add_tab(cmd_tab, "cmd")
        self.panel.tabs.addTab(self._files_tab(), "files")
        self.panel.tabs.addTab(self._log, "log")
        self.panel.tabs.setCurrentIndex(0)            # vychozi je cmd

        self.APP.views.add(self)
        self.APP.view = self          # posledni otevreny view bere i commandy agenta
        # WS konektor diagu (vlastni cmd_sys); radky z WS provadi hlavni vlakno
        self.ws_port = self.APP.start_ws()     # standalone ho uz pustil main() s --port
        self._drain = QTimer(self)
        self._drain.timeout.connect(self.APP.drain)
        self._drain.start(30)
        # scena = kolekce refu s filtrem (zatim vse); vyber = kolekce vybranych (SELSET)
        self.scene = RefColScene()
        self.scene.listeners.append(self.canvas.update)
        SELSET.listeners.append(self.sel_changed)
        POOL.add_refcol(self.scene)
        self.destroyed.connect(lambda _=None, sc=self.scene: POOL.remove_refcol(sc))
        SOURCES.find(self.path).load()
        self._show_error()
        self._need_fit = True
        self._fit()
        self.refresh_bar()

    # tab files: aktualni adresar, nahledy diagramu z .thumbnails, nic jineho

    def _files_tab(self):
        tab = QWidget()
        fl = QVBoxLayout(tab)
        fl.setContentsMargins(4, 4, 4, 4)
        fl.setSpacing(4)
        row = QHBoxLayout()
        # cesta: kazda cast je odkaz, klik prepne prochazeny adresar
        self._dir_lbl = QLabel()
        self._dir_lbl.setStyleSheet("font-size: 12px;")
        self._dir_lbl.setWordWrap(True)
        self._dir_lbl.linkActivated.connect(self.browse)
        row.addWidget(self._dir_lbl, 1)
        fm = QToolButton()
        fm.setText("📂")
        fm.setToolTip("otevřít adresář ve správci souborů")
        fm.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._browse)))
        row.addWidget(fm)
        fl.addLayout(row)
        self._files = QListWidget()
        self._files.setViewMode(QListView.ViewMode.IconMode)
        self._files.setResizeMode(QListView.ResizeMode.Adjust)
        self._files.setMovement(QListView.Movement.Static)
        self._files.setIconSize(QSize(self.SOURCE.THUMB[0] // 2, self.SOURCE.THUMB[1] // 2))
        self._files.setWordWrap(True)
        self._files.setGridSize(QSize(self.SOURCE.THUMB[0] // 2 + 16, self.SOURCE.THUMB[1] // 2 + 30))
        self._files.itemClicked.connect(self._file_clicked)
        # druhy klik v case dvojkliku Qt hlasi jen jako dvojklik, ne jako klik;
        # u adresare ne - do toho uz vesel prvni klik
        self._files.itemDoubleClicked.connect(
            lambda it: os.path.isdir(it.data(Qt.ItemDataRole.UserRole) or "") or self._file_clicked(it))
        self._file_sel = None                         # naposled kliknuta polozka
        self._browse = os.path.dirname(self.path)     # prochazeny adresar
        fl.addWidget(self._files, 1)
        self.panel.tabs.currentChanged.connect(lambda _i: self.refresh_files())
        return tab

    def browse(self, d):
        """Prepnout prochazeny adresar tabu files (soubor ve vieweru zustava)."""
        if os.path.isdir(d):
            self._browse = d
            self.refresh_files()

    def _file_clicked(self, it):
        """Adresar: klik do nej vejde. Diagram: prvni klik vybere, dalsi klik na
        vybrany ho otevre (command diag_open)."""
        path = it.data(Qt.ItemDataRole.UserRole)
        if path and os.path.isdir(path):
            self.browse(path)
        elif path and it is self._file_sel:
            self.APP.execute('%s_open "%s"' % (self.APP.prefix, path), self)
        self._file_sel = it

    def open_file(self, path):
        """Otevrit jiny soubor v tomhle view; predchozi se odnacte (zatim jeden otevreny)."""
        if self.APP.view is self:
            self.APP.queue.active().enter_reset(self)   # mod drzi objekty, ktere zmizi
        self.dyn = []
        self.path = os.path.realpath(path)
        doc = self.SOURCE(self.path)
        SOURCES.open(doc)
        doc.load()
        self._show_error()
        self._need_fit = True
        self._fit()
        self.refresh_bar()
        self.opened.emit(path)

    def refresh_files(self):
        self._file_sel = None
        d = self._browse
        parts, acc = [], ""
        for p in d.strip(os.sep).split(os.sep):
            acc += os.sep + p
            parts.append('<a href="%s" style="color:#2b5d9a; text-decoration:none">%s</a>'
                         % (html.escape(acc, quote=True), html.escape(p)))
        self._dir_lbl.setText(os.sep + (" " + os.sep + " ").join(parts))
        self._files.clear()
        try:
            names = sorted(os.listdir(d))
        except OSError:
            names = []
        # adresare (bez skrytych), za nimi diagramy; nic jineho
        dirs = [n for n in names if not n.startswith(".") and os.path.isdir(os.path.join(d, n))]
        diags = [n for n in names if n.endswith(self.SUFFIX)]
        for name in dirs:
            it = QListWidgetItem(self._tile(QPixmap(os.path.join(self.ICONS, "dir.png"))), name)
            it.setData(Qt.ItemDataRole.UserRole, os.path.join(d, name))
            self._files.addItem(it)
        for name in diags:
            it = QListWidgetItem(name[:-len(self.SUFFIX)])
            it.setToolTip(name)
            pm = QPixmap(os.path.join(d, self.SOURCE.THUMB_DIR, name + ".png"))
            if pm.isNull():          # jeste neulozeny - genericky nahled z kodu
                pm = QPixmap(os.path.join(self.ICONS, "thumb_generic.png"))
            it.setIcon(self._tile(pm))
            it.setData(Qt.ItemDataRole.UserRole, os.path.join(d, name))
            self._files.addItem(it)

    def _tile(self, pm):
        """Dlazdice tabu files: obdelnik s kulatymi rohy stale velikosti, obsah vpisany doprostred."""
        w, h = self.SOURCE.THUMB[0] // 2, self.SOURCE.THUMB[1] // 2
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        frame = QRectF(0.5, 0.5, w - 1, h - 1)
        p.setPen(QPen(QColor("#c3cad1"), 1))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawRoundedRect(frame, 6, 6)
        if not pm.isNull():
            inner = frame.adjusted(5, 5, -5, -5)
            k = min(inner.width() / pm.width(), inner.height() / pm.height())
            pw, ph = pm.width() * k, pm.height() * k
            p.drawPixmap(QRectF(inner.center().x() - pw / 2, inner.center().y() - ph / 2, pw, ph),
                         pm, QRectF(pm.rect()))
        p.end()
        return QIcon(QPixmap.fromImage(img))

    def saved(self):
        """Dokument se ulozil - novy nahled v tabu files."""
        if self.panel.tabs.tabText(self.panel.tabs.currentIndex()) == "files":
            self.refresh_files()

    #! @section Methods
    def select(self, record_no: int):
        """Zvyraznit record a najet na nej; selected se neemituje."""
        it = next((o for o in self.scene.objs()
                   if o.source == self.path and o.key == record_no), None)
        self._quiet = True
        try:
            SELSET.clear()
            if it is not None:
                SELSET.set(it, Sel.SEL)
                ref = self.scene.ref_of(it)
                if ref is not None:
                    self.canvas.ensure_visible(ents_bound(ref.ents))
        finally:
            self._quiet = False

    def reload(self):
        """Soubor se zmenil na disku: dokument se nacte znovu, pohled a vyber zustanou."""
        doc = SOURCES.find(self.path)
        if doc is None:
            return
        sel = self._selected_no()
        if self.APP.view is self:
            self.APP.queue.active().enter_reset(self)   # mod drzi objekty, ktere zmizi
        self.dyn = []
        if not doc.reload():
            return
        self._show_error()
        if sel:
            self.select(sel)

    #! @section Display
    def _show_error(self):
        self.err = []
        doc = SOURCES.find(self.path)
        if doc is not None and doc.error:
            t = QTextDocument()
            t.setPlainText(doc.error)
            self.err = [EntityText(t, QPointF(0, 0))]
        self.canvas.update()

    def pick(self, x, y, kind=None):
        """Objekt pod bodem: objekty odshora (posledni nakresleny je navrchu), kazdy
        se trefi sam ze svych dat."""
        tol = 5 / self.canvas.scale
        for obj in reversed(self.scene.ordered()):
            if (kind is None or obj.kind == kind) and obj.hit(x, y, tol):
                return obj
        return None

    def sel_changed(self):
        """Vyber se zmenil: hlaseni vybraneho recordu (koumes)."""
        if self._quiet:
            return
        no = self._selected_no()
        if no:
            self.selected.emit(no)

    def snap(self, x, y):
        return round(x / self.GRID) * self.GRID, round(y / self.GRID) * self.GRID

    def hover_room(self):
        """(radku, znaku) textu pod mysi, ktere se vejdou do plovouciho panelu."""
        top = self._hint.mapTo(self.panel, self._hint.rect().topLeft()).y()
        return max(3, (self.panel.height() - top - 60) // 13), max(20, (self.panel.width() - 20) // 6)

    def refresh_bar(self):
        """Radek pod toolbarem: jmeno a hint aktivniho modu, jeho tlacitka."""
        while self._dlg.count():
            w = self._dlg.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        self._refresh_log()
        cmd = self.APP.queue.active()
        base = self.APP.queue.stack[0].name         # spodni mod (drag navrchu ho nezhasne)
        for mode, b in self._mode_btns.items():
            b.setChecked(mode == base)
        self._hint.setText("<b>%s</b>: %s" % (cmd.name, cmd.hint()))
        doc = SOURCES.find(self.path)
        self._changes_lbl.setText("%d changes" % (doc.changes if doc else 0))
        for text, line in cmd.dialog():
            b = QToolButton()
            b.setText(text)
            b.clicked.connect(lambda _=False, c=line: self.APP.execute(c, self))
            self._dlg.addWidget(b)

    def _refresh_log(self):
        """Tab log: provedene commandy diag_* (kdo, vysledny mod, chyba cervene)."""
        if len(self.APP.cmds.log) == self._log_n and self._log_n < self.APP.cmds.log.maxlen:
            return
        self._log.clear()
        for line, ok in self.APP.cmds.log:
            it = QListWidgetItem(line)
            if not ok:
                it.setForeground(QColor("#c0392b"))
            self._log.addItem(it)
        self._log_n = len(self.APP.cmds.log)
        self._log.scrollToBottom()

    def pan_by(self, dx, dy):
        self.canvas.pan_by(dx, dy)

    def ratio(self):
        """Proporce okna sirka / vyska (zoom obdelnikem je drzi)."""
        return self.canvas.width() / max(1, self.canvas.height())

    def extent(self, kind=None):
        """Obdelnik sceny, ve kterem lezi objekty (kind = jen ten druh, napr. "node");
        prazdny, kdyz nic neni."""
        r = QRectF()
        for ref in self.scene.refs:
            if ref.ents and (kind is None or ref.obj.kind == kind):
                r = r.united(ents_bound(ref.ents))
        return r

    def zoom_to(self, box):
        """Obdelnik sceny (x1, y1, x2, y2) do okna, meritko bez omezeni."""
        x1, y1, x2, y2 = box
        self.canvas.fit(QRectF(QPointF(x1, y1), QPointF(x2, y2)).normalized(), float("inf"))

    def set_cross(self, who):
        """Kriz pres obraz: na appce pracuje agent (who), "" = zase uzivatelova."""
        self.cross = who
        self.canvas.update()

    #! @section Dynamics
    def dyn_clear(self):
        self.dyn = []
        self.canvas.update()

    def dyn_add(self, ent):
        self.dyn += on_screen([ent])
        self.canvas.update()

    def dyn_box(self, a, b):
        """Nahled obdelniku mezi dvema body (rect vyber)."""
        self.dyn_add(EntityBox(QRectF(QPointF(*a), QPointF(*b)).normalized(), C_DYN, 1.4,
                               style="dash"))

    def dyn_dot(self, a):
        """Puntik v bode a (prvni bod modu)."""
        self.dyn_add(EntityCircle(QPointF(*a), 3, C_DYN, 1, fill=C_DYN))

    def objs_in(self, a, b):
        """Objekty sceny, jejichz kresba lezi cela v obdelniku mezi dvema body."""
        r = QRectF(QPointF(*a), QPointF(*b)).normalized()
        return [ref.obj for ref in self.scene.refs if ref.ents and r.contains(ents_bound(ref.ents))]

    def dyn_rect(self, r):
        self.dyn_add(EntityBox(r, C_DYN, 1.4, style="dash"))

    def eventFilter(self, obj, ev):
        """Mys ve viewportu jde jen do fronty modu - zadne drag & drop eventy.
        Klik = diag_xy; shift = diag_xy .. shift (2 body obdelniku); tazeni = diag_cmd_drag | _resize | _pan + diag_xy zacatku + diag_xy konce."""
        t = ev.type()
        if t not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
                     QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            return False
        vp = ev.position().toPoint()
        p = self.canvas.to_scene(ev.position())
        if t == QEvent.Type.MouseButtonPress:
            if ev.button() == Qt.MouseButton.LeftButton:
                self._press, self._dragging = (p, vp), False
                self._ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
                self._shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            elif ev.button() == Qt.MouseButton.RightButton:
                self.APP.reset(self)
        elif t == QEvent.Type.MouseMove:
            if self._press is not None and not self._dragging \
                    and (vp - self._press[1]).manhattanLength() > self.DRAG_PX:
                self._dragging = True
                if self._shift:          # tah se shiftem = 2 body obdelniku
                    self.APP.point(self._press[0].x(), self._press[0].y(), self, ("shift",))
                else:
                    self.APP.drag_begin(self._press[0].x(), self._press[0].y(), self)
            self.APP.move(p.x(), p.y(), self)
        elif t == QEvent.Type.MouseButtonRelease and ev.button() == Qt.MouseButton.LeftButton:
            if self._press is not None:
                q = p if self._dragging else self._press[0]
                mods = ("shift",) if self._shift else \
                    ("ctrl",) if self._ctrl and not self._dragging else ()
                self.APP.point(q.x(), q.y(), self, mods)
            self._press, self._dragging = None, False
        return True

    def _selected_no(self):
        sel = [o for o in SELSET.items() if o.source == self.path]
        return sel[0].key if sel else 0

    def _fit(self):
        """Cely diagram do okna, ale nezvetsovat nad 1:1. Dokud widget nema
        skutecnou velikost, pocka na resizeEvent."""
        if not self._need_fit or not self.scene.refs or not self.isVisible() \
                or self.canvas.width() < 2:
            return
        self.canvas.fit(self.extent().adjusted(-40, -40, 40, 40))
        self._need_fit = False

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.panel.keep_inside()
        self._fit()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.panel.keep_inside()
        self._fit()

