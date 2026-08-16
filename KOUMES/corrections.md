# KOUMES - opravy po konverzi (reconstruction reference)

Chronologický seznam fixů provedených po initial commitu (kompletní one-shot port z C++). Každá položka: co bylo špatně, kde přesně, jak vypadalo před a po. Detail dostatečný pro rekonstrukci fixu ze scratch.

Konvence oneshot.md přenesena: **File, Problem, Before/After, Notes**.

---

## 1. `WsServerLite.broadcast` - RuntimeWarning bez `websockets`

**File:** `cmd_sys/ws_server_lite.py`

**Problem:** Bez nainstalovaného `websockets` package `_serve()` vrátí okamžitě (import selhal, `websockets is None`) → asyncio loop stopne. `broadcast()` ale dál schedulovala coroutine na už-stopped loop:
```
RuntimeWarning: coroutine 'WsServerLite._broadcast' was never awaited
```

**Before:**
```python
def broadcast(self, text: str) -> None:
    if self._loop is None:
        return
    asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)
```

**After:**
```python
def broadcast(self, text: str) -> None:
    if self._loop is None or not self._loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)
```

**Notes:** `is_running()` check zajistí graceful degradation když WS server neběží (bud kvůli missing dep, nebo protože se ještě nespustil).

---

## 2. `_PanelInfo` musel být QObject

**File:** `KOUMES/main_window.py`

**Problem:** `_PanelInfo` byla plain Python třída. `channel.registerObject("panel", _PanelInfo(role))` selhalo s:
```
TypeError: registerObject(self, id: str|None, object: QObject|None):
    argument 2 has unexpected type '_PanelInfo'
```

**Before:**
```python
class _PanelInfo:
    def __init__(self, role: str):
        self._role = role

    def role(self) -> str:
        return self._role
```

**After:**
```python
from PyQt6.QtCore import QObject, pyqtSlot

class _PanelInfo(QObject):
    def __init__(self, role: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._role = role

    @pyqtSlot(result=str)
    def role(self) -> str:
        return self._role
```

**Notes:** QWebChannel vyžaduje QObject dědiče. `@pyqtSlot(result=str)` decorator exponuje `role()` metodu do JS. Parent set na `page` v `setup_panel` (lifecycle management).

---

## 3. `AppPaths.dir_config` - špatná cesta bez QApplication

**File:** `KOUMES/app_paths.py`

**Problem:** Bez `QApplication.setOrganizationName()` / `setApplicationName()`, `QStandardPaths.AppConfigLocation` vrací jen base directory `~/.config`. Moje logika stripovala parent → `Path('~/.config').parent / 'koumes'` = `~/koumes`. Log soubory šly na `~/koumes/cmdlog.txt` místo `~/.config/koumes/cmdlog.txt`.

**Before:**
```python
if base:
    path = str(Path(base).parent / "koumes") if os.path.basename(base) != "koumes" else base
    return path
```

**After:**
```python
if base:
    p = Path(base)
    return str(p if p.name == "koumes" else p / "koumes")
```

**Notes:** Nová logika: pokud `base` už končí na `koumes` (např. když QApplication má org/app jméno), použij as-is; jinak přidej `koumes` jako subdirectory. Nikdy nestripovat parent.

---

## 4. Deferred queue drain pod Qt event loopem

**File:** `KOUMES/main_window.py`

**Problem:** `CmdSys.execute_thread_safe(cmd, ...)` pushne command do `_deferred` deque (thread-safe). Drén probíhá jen když někdo zavolá `execute()` na main threadu (nakonec drain loop). Ale pod Qt event loopem nic periodicky nedrenuje - WS commands se hromadily bez reakce, kliky se neregistrovaly.

**Fix:** V `MainWindow.__init__` přidán QTimer s 50ms intervalem:
```python
from PyQt6.QtCore import QTimer

# v __init__ po self._wire_bus():
self._drain_timer = QTimer(self)
self._drain_timer.setInterval(50)
self._drain_timer.timeout.connect(self._drain_cmd_queue)
self._drain_timer.start()

def _drain_cmd_queue(self) -> None:
    sys_ = CMD_SYS()
    while sys_._deferred:
        a, sn, si, u = sys_._deferred.popleft()
        sys_.execute(a, sn, si, u)
```

**Notes:** 50ms je kompromis - dost rychlé aby UI cítilo responsive, dost pomalé aby se šetřilo CPU. Alternative by byl asyncio bridge nebo Qt signal from WS thread; QTimer je nejjednodušší.

---

## 5. iris → koumes branding v dirs.html + spol.

**Files:** `KOUMES/dirview/{dirs,help,md-viewer}.html`

**Problem:** `APPS/AI_T2LS/dirview/dirs.html` má hardcoded "Iris" v title, h1, picker text, HOTDIRS. Když je koumes načte (via C++ dirview fallback), zobrazí se "👁 Iris" místo koumes brandingu.

**Fix:** Zkopírováno + edit v koumes dirview:

`dirs.html`:
```
- <title>Iris</title>                             → <title>koumes</title>
- <h1>👁 Iris</h1>                                → <h1>🦝 koumes</h1>
- 'Pick root directory for Iris.'                 → '...for koumes.'
- 'CODE_ROOT/iris/main' (HOTDIRS)       → 'CODE_ROOT/koumes_py'
- 'Wipe all iris storage'                         → 'Wipe all koumes storage'
- 'Pick root directory for Iris:' (2nd occurrence)→ '...for koumes:'
```

`help.html`:
```
- <title>Iris Help</title>       → <title>koumes Help</title>
- <h1>ai.t2ls.com</h1>           → <h1>koumes.com</h1>
```

`md-viewer.html`: nic (žádný iris string).

**Nezasaženo (záměrně):** `DB_NAME='iris'` (IndexedDB storage key), `iris-state.json` filename, `irisTab=iris-preview` query param. Tyto jsou tech identifikátory sdílené s ai.t2ls - state (last dir, last file) se sdílí mezi oběma appkami.

---

## 6. Fallback dirs pro viewery + `--dirview` CLI

**Files:** `KOUMES/viewer_resolver.py`, `KOUMES/main.py`

**Problem:** `dirs.html` neexistuje v `.t2l/` chainu (`TREE/.t2l/` má jen md/t2l/cmdlog viewery, ne dirs). Walk-up ho nenajde → panel bez viewer padne na `file://` fallback (raw Chromium directory listing).

**Fix:**

`viewer_resolver.py` - přidán module-level global + setter + fallback search:
```python
_EXTRA_FALLBACK_DIRS: list = []

def set_extra_fallback_dirs(dirs: list) -> None:
    global _EXTRA_FALLBACK_DIRS
    _EXTRA_FALLBACK_DIRS = [os.path.normpath(os.path.abspath(d)) for d in dirs if os.path.isdir(d)]

# ...v find_viewer_html po walk-up failu:
for extra in _EXTRA_FALLBACK_DIRS:
    candidate = os.path.join(extra, f"{viewer_name}.html")
    if os.path.isfile(candidate):
        return candidate
    in_hidden = os.path.join(extra, ".t2l", f"{viewer_name}.html")
    if os.path.isfile(in_hidden):
        return in_hidden
return ""
```

`main.py` - `DEFAULT_DIRVIEW` + `--dirview` CLI arg + set při run_gui:
```python
DEFAULT_DIRVIEW = "CODE_ROOT/APPS/AI_T2LS/dirview"

# parse_args:
p.add_argument("--dirview", default=DEFAULT_DIRVIEW,
               help=f"Fallback dir for viewer HTMLs (default: {DEFAULT_DIRVIEW})")

# run_gui - po register_gui_cmds():
from . import viewer_resolver as vr
from .app_paths import AppPaths as _AP
koumes_dirview = os.path.join(_AP.inst().dir_exe(), "dirview")
vr.set_extra_fallback_dirs([koumes_dirview, args.dirview])
```

**Notes:** koumes/dirview má **vyšší priority** než C++ - koumes-branded soubory vyhrají, C++ jen jako fallback.

---

## 7. QWebEngineScript `__chroma` bootstrap injection

**File:** `KOUMES/main_window.py`, `KOUMES/qwebchannel.js` (bundled)

**Problem:** dirs.html čeká na `window.__chroma.ready` Promise:
```js
if (window.__chroma && window.__chroma.ready) {
    window.__chroma.ready.then(resolve);
    return;
}
```
C++ ai.t2ls injectuje bootstrap script před load. Koumes neinjectovala → dirs.html Promise nikdy neresolne, JS padne do picker/iris fallback módu.

**Fix:**

Bundlován `KOUMES/qwebchannel.js` (16KB copy z `~/Qt/6.11.0/gcc_64/share/qt6/webchannel/qwebchannel.js`). PyQt6 tenhle JS neexponuje jako Qt resource `:/qtwebchannel/qwebchannel.js` (jako C++), takže ho musíme bundlovat.

V `main_window.py`:
```python
from PyQt6.QtWebEngineCore import QWebEngineScript

_QWEBCHANNEL_JS: Optional[str] = None

def _load_qwebchannel_js() -> str:
    global _QWEBCHANNEL_JS
    if _QWEBCHANNEL_JS is not None:
        return _QWEBCHANNEL_JS
    bundled = os.path.join(os.path.dirname(__file__), "qwebchannel.js")
    try:
        with open(bundled, "r", encoding="utf-8") as f:
            _QWEBCHANNEL_JS = f.read()
    except OSError:
        _QWEBCHANNEL_JS = ""
    return _QWEBCHANNEL_JS

_CHROMA_BOOTSTRAP_JS = r"""
window.__chroma = window.__chroma || {};
window.__chroma.role = (function () {
    var p = new URLSearchParams(location.search);
    return p.get('role') || 'mid';
})();
window.__chroma.ready = new Promise(function (resolve) {
    new QWebChannel(qt.webChannelTransport, function (channel) {
        window.__chroma.fs  = channel.objects.fs;
        window.__chroma.bus = channel.objects.bus;
        resolve(channel.objects.fs);
    });
});
window.__chroma.ready.then(function (fs) {
    document.addEventListener('selectionchange', function () {
        // ... selection JSON push via fs.setSelection(...)
    });
});
"""

# V setup_panel() po page.setWebChannel(channel):
inject_src = _load_qwebchannel_js() + _CHROMA_BOOTSTRAP_JS
script = QWebEngineScript()
script.setName(f"chroma-inject-{role}")
script.setSourceCode(inject_src)
script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
script.setRunsOnSubFrames(False)
page.scripts().insert(script)
```

**Notes:**
- Injection point nejdřív `DocumentReady`, pak změněno na **`DocumentCreation`** aby `__chroma` bylo dostupné dřív než dirs.html scripts běží (jinak vidí `undefined`, padne do polling loopu, viditelný flicker).
- Skript má oba díly: qwebchannel.js (nutný pro `QWebChannel` konstruktor) + custom bootstrap.

---

## 8. `role` param v URL query

**File:** `KOUMES/main_window.py`

**Problem:** dirs.html rozlišuje chování podle `?role=` (mid = active listing, parent = shows parent-of-mid, detail = shows one file). Bez toho JS spadl do default 'mid' pro všechny panely → parent panel se choval jako mid, layout selhal.

**Before:**
```python
url.setQuery(f"start={path}")  # in _load_dir
url.setQuery(f"file={file_path}")  # in _resolve_view_url
```

**After:**
```python
# _load_dir - mid:
url.setQuery(f"start={path}&role=mid")

# _load_dir - left:
purl.setQuery(f"start={parent}&role=parent")

# _resolve_view_url:
def _resolve_view_url(self, file_path: str, role: str = "detail") -> QUrl:
    ...
    url.setQuery(f"file={file_path}&role={role}")

# Volání:
self.detail_view.setUrl(self._resolve_view_url(path, role="detail"))
self.rm_view.setUrl(self._resolve_view_url(path, role="rightmost"))
```

**Notes:** dirs.html JS reads `role` z `URLSearchParams` a větví `if (role === 'mid') { ... } else if (role === 'parent') { ... }`. Přidání role param umožnilo správné chování všech panelů.

---

## 9. Endless flicker loop mid ↔ Python

**File:** `KOUMES/main_window.py`

**Problem:** dirs.html v role='mid' po každém `render()` publikuje `bus.notifyDirChange(abs)` (aby ostatní panely věděly kde je). Python `_on_dir_changed` → `_load_dir(path)` → `mid_view.setUrl(...)` = **RELOAD** dirs.html. Nová instance se nastartuje, publikuje dirChanged, Python reloaduje... **endless loop**. Vizuálně: dir panel bliká mezi "🦝 koumes" initial state a proper dir content.

**Fix:** Loop guard v obou bus handlerech:

**Before:**
```python
def _on_dir_changed(self, path: str) -> None:
    self._load_dir(path)

def _on_file_selected(self, path: str) -> None:
    if not os.path.isfile(path):
        return
    CmdsChroma.set_last_file(path)
    ...
```

**After:**
```python
def _on_dir_changed(self, path: str) -> None:
    if path == CmdsChroma._last_dir:
        return
    self._load_dir(path)

def _on_file_selected(self, path: str) -> None:
    if not os.path.isfile(path):
        return
    if path == CmdsChroma._last_file:
        return
    CmdsChroma.set_last_file(path)
    ...
```

**Notes:**
- JS strana má vlastní loop-guard (`if (newAbs === currentAbsDir()) return;`) ale chrání jen JS-side re-render, ne full-page reload z Pythonu.
- Python-side guard je nutný - full setUrl vytváří novou dirs.html instanci bez paměti "už jsem tam byl".
- `_last_dir` je updated `_load_dir` PŘED setUrl, takže loop-guard uvidí novou hodnotu při druhé notifikaci.

---

## 10. Left panel byl prázdný

**File:** `KOUMES/main_window.py`

**Problem:** `MainWindow.__init__` volal `_load_dir(self.start_dir)` jen pro mid. `left_view` nikdy nedostal setUrl → zůstal blank.

**Fix:** V `_load_dir` po mid_view.setUrl přidán load left_view:
```python
if html:
    parent = os.path.dirname(path) or path
    purl = QUrl.fromLocalFile(html)
    purl.setQuery(f"start={parent}&role=parent")
    self.left_view.setUrl(purl)
    self._set_info_path(self.p_left.info_path, parent)
    self.p_left.info_viewer.setText("dirs")
```

**Notes:**
- Původně jsem měl guard `if html and self.left_view.url().isEmpty()` (jen první load), ale left panel se pak neaktualizoval při navigaci mid. Odstraněno → left se aktualizuje při každém `_on_dir_changed`.
- dirs.html v role='parent' má vlastní `bus.dirChanged` listener který updates path bez reloadu, ale Python-side full reload je pojistka (loop-guard chrání proti hyperreloadu).

---

## 11. `dir_up` sandbox widen (matching C++)

**File:** `KOUMES/cmds_chroma.py`

**Problem:** Když je uživatel na sandbox root a klikne `⬅ dir_up`, parent je mimo sandbox → `bus.notify_dir_change(parent)` fires, `_load_dir` se pokusí načíst dirs.html, ale dirs.html přes `fs.list()` nedostane obsah (sandbox check refuse) → panel zamrzne. C++ ai.t2ls klikací handler PŘED dispatch rozšířil sandbox.

**Before:**
```python
def dir_up(args, data, ctx):
    d = cls._last_dir
    if not d:
        return args.append_error("dir_up: no dir yet")
    parent = os.path.dirname(os.path.abspath(d))
    if not parent or parent == d:
        return args.append_error("dir_up: already at root")
    if cls._bus is None:
        return args.append_error("dir_up: bus not set")
    cls._bus.notify_dir_change(parent)
    args.append(parent, "DIR")
    return 0
```

**After:**
```python
def _widen_if_needed(parent: str) -> bool:
    fs = FsBridge.inst()
    if fs is None:
        return True
    if fs.is_inside(parent, fs.allowed_dir_):
        return True
    if not fs.set_allowed_root(parent):
        return False
    if cls._bus is not None:
        cls._bus.notify_sandbox_changed(fs.allowed_dir_)
    return True

def dir_up(args, data, ctx):
    d = cls._last_dir
    if not d:
        return args.append_error("dir_up: no dir yet")
    parent = os.path.dirname(os.path.abspath(d))
    if not parent or parent == d:
        return args.append_error("dir_up: already at root")
    if cls._bus is None:
        return args.append_error("dir_up: bus not set")
    if not _widen_if_needed(parent):
        return args.append_error(f"dir_up: cannot widen sandbox to {parent}")
    cls._bus.notify_dir_change(parent)
    args.append(parent, "DIR")
    return 0

# Stejný _widen_if_needed použit v reveal_dir handleru.
```

**Notes:**
- `FsBridge.set_allowed_root` už z principu **jen rozšíří** sandbox (nikdy neomezuje - kontrola že new_root je ancestor current allowed_dir_).
- `bus.notify_sandbox_changed(new_root)` triggeruje `bus.sandboxChanged` signal, na který dirs.html JS reaguje (re-inituje `rootAbsPath`, re-renderuje).

---

## 12. Path display: shorten k sandboxu + red pro outside

**File:** `KOUMES/main_window.py`

**Problem:** Info-bar labely (`info_path`) zobrazovaly plnou absolutní cestu:
```
CODE_ROOT/APPS/AI_T2LS/dirview/dirs.html
```
C++ ai.t2ls zkracuje na:
```
CODE_ROOT/APPS/AI_T2LS/dirview/dirs.html
```
(prefix = sandbox basename, rest = relative). Když je cesta mimo sandbox, styling červeně.

**Fix:** Module-level helpers + method:

```python
def _path_from_index(abs_: str, root: str) -> str:
    """Shorten abs to '<sandbox>/rel'. Outside sandbox -> full abs path."""
    if not abs_:
        return abs_
    abs_c = os.path.normpath(os.path.abspath(abs_))
    root_c = os.path.normpath(os.path.abspath(root))
    if not abs_c.startswith(root_c):
        return abs_c
    root_base = os.path.basename(root_c) or root_c
    rel = abs_c[len(root_c):].lstrip(os.sep)
    return root_base if not rel else f"{root_base}/{rel}"


def _is_outside_sandbox(abs_: str, root: str) -> bool:
    if not abs_:
        return False
    abs_c = os.path.normpath(os.path.abspath(abs_))
    root_c = os.path.normpath(os.path.abspath(root))
    return not abs_c.startswith(root_c)


# V MainWindow:
def _set_info_path(self, label, abs_path: str) -> None:
    label.setText(_path_from_index(abs_path, self.root))
    label.setToolTip(abs_path)
    outside = _is_outside_sandbox(abs_path, self.root)
    label.setStyleSheet(
        "color: #f87171; font-weight: 700;" if outside
        else "color: #f9fafb; font-weight: 700;"
    )
```

Aplikováno v `_load_dir` (mid + left), `_on_file_selected` (right), `_on_file_selected_rightmost` (rm). Nahrazuje přímé `label.setText(path)`.

**Notes:**
- Tooltip drží plnou absolutní cestu (copy button ji čte).
- Barvy: `#f9fafb` (bílá) inside, `#f87171` (světle červená) outside. Font-weight 700 (bold) pro info_path.

---

## 13. `info_selection` label - stejné shorten

**File:** `KOUMES/main_window.py`

**Problem:** `_on_selection_changed` psal full path do `info_selection` (middle row info baru). Stejný problem jako #12 pro selection labels.

**Before:**
```python
def _on_selection_changed(self, panel: str, file: str, line: int) -> None:
    text = f"{file}:{line}" if line else file
    if panel == "dir":
        self.p_mid.info_selection.setText(text)
    elif panel == "p1":
        self.p_right.info_selection.setText(text)
    elif panel == "p2":
        self.p_rm.info_selection.setText(text)
```

**After:**
```python
def _on_selection_changed(self, panel: str, file: str, line: int) -> None:
    short = _path_from_index(file, self.root) if file else ""
    text = f"{short}:{line}" if line else short
    label = None
    if panel == "dir":
        label = self.p_mid.info_selection
    elif panel == "p1":
        label = self.p_right.info_selection
    elif panel == "p2":
        label = self.p_rm.info_selection
    if label is None:
        return
    label.setText(text)
    label.setToolTip(file)
    outside = _is_outside_sandbox(file, self.root)
    label.setStyleSheet(
        "color: #f87171; font-weight: 400;" if outside
        else "color: #9ca3af; font-weight: 400;"
    )
```

**Notes:**
- Palette pro selection: `#9ca3af` (dim gray) inside (info_selection je secondary informace, ne primary), `#f87171` outside.
- Font-weight 400 (regular) - není bold jako info_path.
- Refaktor: dispatch label via if/elif do proměnné, pak jedna větev pro `setText + setToolTip + setStyleSheet` - méně opakování.
