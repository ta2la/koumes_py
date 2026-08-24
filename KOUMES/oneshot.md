# KOUMES - module reference

Desktop application (PyQt6) - the koumes editor / dir browser / t2l viewer / command console. Ported from `APPS/AI_T2LS/` C++ codebase.

## Module dependencies

- **[cmd_sys](../cmd_sys/oneshot.md)** - command parsing, registration, dispatch, guards, and WebSocket bridge. KOUMES imports it as its command backbone. See sibling directory `../cmd_sys/`. All external control of KOUMES (via WS, stdin, embedded UI actions) flows through `CmdSys.execute()`.
- **PyQt6** - Qt bindings (widgets, WebEngine, WebChannel, QSettings)
- **websockets** - transitive via `cmd_sys.WsServerLite`

## Package layout (planned)

```
KOUMES/
├── plan.md              this port plan
├── oneshot.md           this API reference (grows as classes get ported)
├── __init__.py          package exports
├── __main__.py          `python -m koumes` entry
├── main.py              `main()` bootstrap
├── app_paths.py         AppPaths
├── fs_bridge.py         FsBridge (QWebChannel bridge for JS)
├── chroma_page.py       ChromaPage (QWebEnginePage)
├── chroma_www_page.py   ChromaWwwPage
├── panel_bus.py         PanelBus (inter-panel signals)
├── window_persist.py    WindowPersist
├── cmds_chroma.py       Cmds_chroma
├── cmds_www.py          Cmds_www
└── dirview/             (later: package data - viewer HTMLs)
```

---

## Package metadata (pyproject.toml, README, .gitignore)

Installable package layout at the **repo root** (not inside `KOUMES/`), because the distribution ships both `KOUMES/` and `cmd_sys/` as top-level packages.

**Files:**
- `pyproject.toml` - PEP 621 metadata (build-backend = setuptools)
- `README.md` - short user-facing overview + install/run instructions
- `.gitignore` - Python artefacts (`__pycache__`, `dist`, `venv`, ...)

### pyproject.toml essentials

| Field | Value |
| --- | --- |
| `project.name` | `koumes` (lowercase - PyPI norm) |
| `project.version` | `0.1.0` |
| `requires-python` | `>=3.10` (uses `tomllib`, structural typing hints) |
| `dependencies` | `PyQt6>=6.5`, `PyQt6-WebEngine>=6.5`, `websockets>=11` |
| `project.scripts.koumes` | `KOUMES.main:main` (so `koumes` CLI works after install) |
| `tool.setuptools.packages.find.include` | `["cmd_sys*", "KOUMES*"]` |

### Install / run

```bash
pip install .              # in dev
pip install koumes         # later, from PyPI
koumes /some/root          # entry point
python -m KOUMES /some/root   # equivalent
```

**Import mismatch note:** the PyPI package is `koumes` (lowercase), but the Python import is `import KOUMES` (uppercase, matches the directory). This is deliberate to follow the CVZ convention (`APPS/UPPERCASE`) while keeping the pip name conventional. `import cmd_sys` is lowercase both ways.

---

## Main entry

Bootstrap and event loop entry for the app.

**Files:**
- `main.py` - `main()` function, arg parsing, bootstrap, run modes
- `__main__.py` - allows `python -m KOUMES ...`
- `__init__.py` - exports `AppPaths`, `main`

### CLI

```
koumes [--headless] [--port PORT] [root] [start_dir]
```

- `root` - sandbox root directory (default: cwd)
- `start_dir` - initial directory to open (default: same as root)
- `--headless` - skip GUI; only WS bridge + stdin monitor
- `--port PORT` - WebSocket port for external commands (default: **54325**, matches ai.t2ls)

### Functions
- `parse_args(argv: list) -> argparse.Namespace` - argparse wrapper
- `bootstrap(args) -> None` - one-time headless-safe init (no PyQt6 dep):
  1. `AppPaths.inst()` - create user config dir
  2. `CmdsCmdSys.register_cmds_()` - register 8 built-in commands
  3. `LogGuard(<dir_config>/cmdlog.txt)` - start command logging
  4. `WsServerLite.init(port=args.port)` - start WS server on **54325** (default; overridable via `--port`). Matches the ai.t2ls convention so external tools (chroma_setfile, etc.) work with either app.
  5. `CmdBridge.init()` - attach the broadcast guard (server already running)
  6. `StdinMonitor.init()` with `set_enabled(True)` - listen on stdin
- `register_gui_cmds() -> None` - **GUI-only** command registration (deferred import to keep headless mode PyQt-free):
  - `CmdsChroma.register_cmds()` - ~35 chroma commands
  - `CmdsWww.register_cmds()` - 9 www commands
- `run_gui(args) -> int`:
  1. Try `import PyQt6.QtWidgets.QApplication`; fall back to `run_headless` on ImportError
  2. `register_gui_cmds()`
  3. Create `MainWindow(root, start_dir)`, call `wire_toolbar(win)`, `WindowPersist.install(win, app)`
  4. `win.show()`, `app.exec()`
- `run_headless(args) -> int` - infinite sleep loop; WS + stdin are already live in daemon threads. Exit on Ctrl+C.
- `main(argv=None) -> int` - dispatch: bootstrap, then GUI or headless

**Current state:** GUI opens a real 4-panel `MainWindow` (`main_window.py`), wires all toolbar buttons through `wire_toolbar`, and installs `WindowPersist` for geometry save/restore. Chroma / www commands are registered inside `run_gui` (deferred import via `register_gui_cmds()` so headless mode never imports PyQt6).

---

## AppPaths

Resolves the two per-app filesystem paths KOUMES needs.

**File:** `app_paths.py`

### Construction
- `AppPaths.inst() -> AppPaths` - singleton accessor

### Methods
- `dir_exe() -> str` - package installation directory (the directory containing `app_paths.py`, resolved via `__file__`). Used for locating bundled read-only assets (viewer HTMLs, default configs, ...).
- `dir_config() -> str` - user-writable config directory. Auto-created on first access. Resolution order:
  1. `QStandardPaths.AppConfigLocation` if PyQt6 is importable
  2. `$XDG_CONFIG_HOME/koumes` if set
  3. `~/.config/koumes` (Linux/macOS default)

### Adaptation notes vs C++

The C++ `AppPaths::dirConfig()` returned `<binary>/../config` (self-contained deployment pattern: config folder shipped alongside the executable). Python packaged apps don't work that way - a pip-installed package lives inside `site-packages/`, which is not user-writable. The port replaces that with platform-standard user config location.

If a future deployment mode ships koumes as an AppImage/Flatpak/PyInstaller bundle where `<binary>/../config` makes sense again, add a runtime detection in `_resolve_config_dir()`.

---

## FsBridge

Sandboxed filesystem bridge + `[[link]]` resolver, exposed to embedded JS via `QWebChannel`. Every FS operation is gated by an `allowed_dir_` root; nothing outside can be read/written/trashed.

**File:** `fs_bridge.py`
**Requires:** `PyQt6` (inherits `QObject`)

### Construction
- `FsBridge(allowed_dir: str, parent: QObject = None)` - installs itself as `FsBridge._inst` (global singleton). Path is cleaned to absolute.

### Global handles
- `FsBridge.inst() -> FsBridge | None` - the singleton (set by the last constructed instance)
- `FsBridge.set_bus(bus) -> None` - inject a `PanelBus`-like object so `followLink` can notify the UI (`bus.notify_line_changed(n)` / `bus.notify_file_selected_for_browse(path, n)`). If not set, `followLink` is a silent no-op.

### JS-invokable methods (`@pyqtSlot`)
Reachable from embedded JS through the WebChannel-bound name (typically `__chroma.fs.<method>`):

- `allowedRoot() -> str` - sandbox root
- `list(path: str = "") -> list[str]` - directory entries, dirs first then files (both sorted). Empty result for missing or outside-sandbox path.
- `read(path: str) -> str` - UTF-8 file contents ("" on error or outside sandbox)
- `write(path: str, content: str) -> bool` - overwrite file with UTF-8 content
- `isDir(path: str) -> bool`
- `exists(path: str) -> bool`
- `trash(path: str) -> bool` - move to system trash via `gio trash --`. Refuses to trash the sandbox root itself.
- `setSelection(json: str)` - JS pushes DOM selection JSON here for later cmd_sys reads
- `setSelectedDir(p: str)` / `setSelectedFile(p: str)` / `setSelectedLine(n: int)` - HTML apps publish the currently-selected addressable unit (independent of what's actually rendered)
- `exec(cmdline: str)` - dispatch a CmdSys command line from JS (via `CMD_SYS().execute_thread_safe(..., "js", -1, "HTML")`)
- `followLink(link_arg: str, start_path: str)` - resolve `[[id]]` or `[[id::relpath]]` clicked in HTML; scrolls to the target unit or opens the target file at that unit (via injected bus)
- `validateLinks(file_path: str)` - scan all `[[...]]` in the file, verify each still resolves, rewrite with fresh `[[id::relpath]]` (or `[[id::???]]` when target is lost). Called BEFORE the viewer loads.

### Sandbox rules

- `_is_inside(path, dir)` - path must equal `dir` or start with `dir + sep`; both sides cleaned to absolute
- `set_allowed_root(new_root: str) -> bool` - **only widens**, never narrows. Rejects paths that aren't ancestors of the current root.

### `.t2l` id resolution

- `_find_id_ordinal_in_file(file_path, id) -> int` - line-by-line parser mirroring the JS `t2lplus.html parseT2l`: blank line ends record, `#` comments skipped, comment-only blocks don't count as records. Returns 1-based record ordinal or 0.
- `_resolve_id_in_tree(id, start_dir, root_abs) -> (abs_path, ord) | None` - BFS: walks up from `start_dir` to sandbox root; at each level adds the whole subtree (via `os.walk`), scans `*.t2l` for the id. Priority preserves "close first".
- `_rewrite_link_in_file(source_file, id, new_path) -> None` - regex replace on the whole `[[id]]` or `[[id::oldpath]]` bracket, then rewrites file.

### Adaptation notes vs C++
- `QObject` + `Q_INVOKABLE` -> `QObject` + `@pyqtSlot(...)` decorators
- `QDir::cleanPath / absolutePath` -> `os.path.normpath(os.path.abspath(...))`
- `QDirIterator(..., Subdirectories)` -> `os.walk(...)`
- `QRegularExpression` -> `re`
- `QProcess.start("gio", ...)` -> `subprocess.run(["gio", "trash", "--", ...], timeout=15)`
- `PanelBus* bus = Cmds_chroma::busRef_()` (a static global reference) -> `FsBridge._bus` (class attribute set via `FsBridge.set_bus(bus)`)

---

## ChromaPage

`QWebEnginePage` subclass for VIEW panels (local file access only). Any `http` / `https` navigation is rejected and re-routed to a www panel via injected `PanelBus`.

**File:** `chroma_page.py`
**Inheritance:** `PyQt6.QtWebEngineCore.QWebEnginePage`

### Construction
- `ChromaPage(role: str = "", parent=None)` - `role` is the source panel id (`"parent" / "mid" / "detail" / "rightmost"`), used by the router to pick the OPPOSITE tabbable panel when re-routing external URLs.

### Global handle
- `ChromaPage.set_bus(bus) -> None` - inject `PanelBus`-like object (must implement `notify_www_url_requested(url, role)`)

### Methods
- `set_role(role: str) -> None` / `role() -> str` - role getter/setter
- `acceptNavigationRequest(url, nav_type, is_main_frame) -> bool` - override: rejects `http`/`https` in main frame, dispatches to `bus.notify_www_url_requested(url, self._role)`. All other schemes pass through.
- `createWindow(window_type) -> QWebEnginePage` - `target="_blank"` / `window.open()`: returns child `ChromaPage` with the same role, so the same routing applies.

### Adaptation notes vs C++
- `QWebEnginePage` moved from `QtWebEngineWidgets` (Qt5) to `QtWebEngineCore` (Qt6).
- No `Q_OBJECT` macro needed - Python subclasses of `QObject` are already Qt-aware.
- No `using QWebEnginePage::QWebEnginePage;` (constructor inheritance is automatic in Python).

---

## ChromaWwwPage

`QWebEnginePage` subclass for WWW panels (external web only). Complement of `ChromaPage`: this one bans local schemes so a web page can never escape the isolated Chromium tab to reach the local filesystem.

**File:** `chroma_www_page.py`
**Inheritance:** `PyQt6.QtWebEngineCore.QWebEnginePage`

### Construction
- `ChromaWwwPage(parent=None)` - default; no role tracking (all www panels are equivalent from the page's POV)

### Methods
- `acceptNavigationRequest(url, nav_type, is_main_frame) -> bool`
  - **Sub-frames** (`is_main_frame == False`): allow everything (iframes serving http/https content).
  - **Main frame**: allow only `http`, `https`, `about` (last is used for `about:blank` initial state). Reject `file://`, `data:`, `javascript:`, `qrc://`, `chrome://`, etc.

### Recommended pairing

Instantiate with an **isolated `QWebEngineProfile`** so cookies/cache do not mix with the view panels' default profile:

```python
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineView

www_profile = QWebEngineProfile("koumes-www")
page = ChromaWwwPage(www_profile, parent=view)
view = QWebEngineView()
view.setPage(page)
```

---

## PanelBus

Simple pub/sub channel between HTML panels in chroma. Registered as `"bus"` in every WebChannel (left / mid / detail / rightmost). When one panel calls a `notify*` method, every panel that connected to the matching signal receives it. Each panel decides what to do based on its role.

**File:** `panel_bus.py`
**Inheritance:** `QObject`

### Signals (JS listens, Python emits)
- `dirChanged(str path)` - middle panel navigated into a new directory
- `fileSelected(str path)` - a file was picked (typically from the middle panel)
- `fileSelectedRightmost(str path)` - explicitly targeted at the rightmost (p2) view
- `fileSelectedForBrowse(str path, int line)` - opened via link-follow; viewer must support `sys__browse_support: true`, in-file directive ignored
- `sandboxChanged(str new_root)` - sandbox root widened at runtime (dir-up past edge); HTML apps that cached `fs.allowedRoot()` must re-read
- `lineChanged(int line)` - external caller wants the detail viewer to jump to a specific line
- `wwwUrlRequested(QUrl url, str source)` - view panel refused an http/https navigation; router picks the opposite tabbable panel (detail <-> rightmost)
- `selectionChanged(str panel, str file, int line)` - selection changed in a panel; `panel` in `{dir, p1, p2}`
- `panelShow(str panel, str file, str viewer)` - unified panel loader; `panel` in `{left, dir, p1, p2}`, `file` absolute path, `viewer` optional override

### Slots (JS calls, Python re-emits as signal)
Each signal has a matching `notifyX` slot (Q_INVOKABLE, exposed to JS through WebChannel):

- `notifyDirChange(str)` -> emits `dirChanged`
- `notifyFileSelected(str)` -> emits `fileSelected`
- `notifyFileSelectedRightmost(str)` -> emits `fileSelectedRightmost`
- `notifyFileSelectedForBrowse(str, int)` -> emits `fileSelectedForBrowse`
- `notifySandboxChanged(str)` -> emits `sandboxChanged`
- `notifyLineChanged(int)` -> emits `lineChanged`
- `notifyWwwUrlRequested(QUrl, str)` -> emits `wwwUrlRequested`
- `notifySelectionChanged(str, str, int)` -> emits `selectionChanged`
- `notifyPanelShow(str, str, str="")` -> emits `panelShow`

### Snake-case aliases (Python callers)

For Python callers (`FsBridge.followLink`, `ChromaPage.acceptNavigationRequest`, cmds_chroma) each `notifyX` method has a snake_case alias (`notify_x`) so the calling convention matches the surrounding Python code. Both call paths reach the same signal.

Example callers already ported:
- `ChromaPage.acceptNavigationRequest` -> `bus.notify_www_url_requested(url, role)`
- `FsBridge.followLink` -> `bus.notify_line_changed(ord)` / `bus.notify_file_selected_for_browse(path, ord)`

---

## CmdsChroma

Container class registering all chroma-specific CmdSys commands (~35 commands total). Also holds the shared UI state referenced by those commands (page/view refs, per-panel selection, callback dispatchers).

**File:** `cmds_chroma.py`
**Registration:** `CmdsChroma.register_cmds()`

### State setters (called by main window during setup)

- `set_page(p)`, `set_detail_page(p)`, `set_rightmost_page(p)` - `QWebEnginePage` refs (mid / detail / rightmost)
- `set_detail_view(v)`, `set_rightmost_view(v)` - `QWebEngineView` refs (needed for screenshot)
- `set_bus(b)` - the shared `PanelBus`
- `set_last_dir(p)`, `set_last_file(p)` - updated from bus handlers as user navigates
- `set_last_dir_viewer(v)`, `set_last_file_viewer(v)` - HTML viewer currently rendering the mid dir / detail file
- `set_viewer_switch_fn(panel, fn)`, `set_reload_fn(panel, fn)`, `set_toggle_fn(panel, fn)`, `set_tab_toggle_fn(panel, fn)` - per-panel callbacks registered by main window
- `set_sel_file(panel, file)` - update per-panel selection (resets `line` to 0, emits `selectionChanged`)

### Registered commands (category: `chroma`)

**Selection (2-stage: 1st click selects, 2nd click shows):**
- `select <dir|p1|p2> <line>` - set selection line inside panel
- `show <dir|p1|p2>` - if `line > 0` -> `bus.lineChanged`, else file -> `bus.fileSelected`
- `get_selection <panel>` -> `"<file>:<line>"`
- `preselect <panel> <path>` - 1st-click highlight (no navigation)

**Panel lifecycle:**
- `panel_show <panel> <file> [<viewer>]` - unified loader
- `tab_toggle <p1|p2>` - flip view/www tab
- `panel_toggle <left|p2>` - flip visibility
- `panel_reload <left|dir|p1|p2>` - reload web view
- `viewer_switch <panel> <viewer>` - change active viewer

**Shorthand readers** (added per-panel via loop): `dir_file`, `dir_line`, `dir_preselect`, `p1_file`, `p1_line`, `p1_preselect`, `p2_file`, `p2_line`, `p2_preselect`

**Chroma current state:**
- `chroma_selection` - last DOM selection JSON (from FsBridge)
- `chroma_dir` - selected dir OR viewed dir
- `chroma_file` - selected file OR viewed file
- `chroma_line` - selected line inside detail viewer
- `chroma_dir_viewer`, `chroma_file_viewer` - HTML viewer names
- `debug_follow <id> [--start <path>]` - invoke `FsBridge.followLink` and return the internal log
- `debug_follow_log` - return log from last `followLink` (no invocation)

**Chroma navigation:**
- `chroma_setdir <path>` - navigate mid panel
- `chroma_setfile <path> [--p2]` - open file in detail (default) or rightmost panel
- `chroma_setline <n>` - jump detail viewer to line N (1-based)

**Chroma introspection** (async web APIs, wrapped synchronously with `QEventLoop`):
- `chroma_html [--p2]` - full HTML of the target view (via `page.toHtml(callback)` + `QEventLoop.exec()`)
- `chroma_text [--p2]` - plain text of the target view (via `page.toPlainText(callback)`)
- `chroma_screenshot <path> [--p2]` - `view.grab().save(path, "PNG")`
- `chroma_window <path>` - `window.grab().save(path, "PNG")` - celé Qt okno včetně toolbarů a info barů. Jediná cesta k snapshotu pod Waylandem: X grabbery (`import`, `xwd`) na okno nedosáhnou, `wmctrl -l` nevrací nic.

**Panel navigation shortcuts:**
- `dir_up` - navigate to parent of `_last_dir`
- `reveal_dir` - navigate to parent of `_last_file`
- `chroma_openfm` - `xdg-open <dir>` (open in system file manager)
- `open_extern <target>` - smart: URL -> `google-chrome`, else -> `xdg-open`
- `chroma_reload` - reload mid page
- `chroma_reload_detail` - reload detail page

**JS DOM injection** (JavaScript executed via `page.runJavaScript`):
- `chroma_style "<css>"` - wrap current selection in `<span style="<css>">`
- `chroma_class "<className>"` - wrap current selection in `<span class="<className>">`
- `chroma_unwrap` - remove nearest wrapping `<span>` around cursor/selection

### Adaptation notes vs C++

- C++ static function refs (`static QWebEnginePage*& pageRef_() { static QWebEnginePage* p = nullptr; return p; }`) -> Python class attributes with `set_*` classmethods
- C++ `std::map<QString, std::function<...>>` -> Python `Dict[str, Callable[..., None]]`
- C++ `struct PanelSel { QString file; int line = 0; }` -> Python `@dataclass class PanelSel`
- Async `page.toHtml(callback)` -> synchronous wrapper via `QEventLoop` (same pattern the C++ uses)
- `QProcess.startDetached` -> `subprocess.Popen`
- `QWebEnginePage::Reload` (enum) -> `QWebEnginePage.WebAction.Reload` in PyQt6
- Static class attributes for FnDicts / PanelSels are **shared across all instances** (matches C++ static globals). This is fine since `CmdsChroma` is used only as a namespace (never instantiated).

---

## CmdsWww

Container class registering all www-panel CmdSys commands (~9 commands). Commands intentionally do not touch view panels (dir/file) - even name confusion is avoided by the `www_` prefix.

**File:** `cmds_www.py`
**Registration:** `CmdsWww.register_cmds()`

### State setters

- `set_detail_www(v)` - detail www view (`QWebEngineView`)
- `set_rightmost_www(v)` - rightmost www view (the www home)

### Target resolution

All commands accept an optional `--panel <name>` arg (default `right`):
- `detail` / `d` -> detail www view
- `right` / `r` -> rightmost www view (fallback / default)

### Registered commands (category: `www`)

- `www_open <url> [--panel detail|right]` - navigate; if `url` has no `://`, prepends `https://`
- `www_url [--panel ...]` - current URL
- `www_html [--panel ...]` - full HTML (async wrapped with `QEventLoop`)
- `www_text [--panel ...]` - plain text (async wrapped)
- `www_selection [--panel ...]` - JS `window.getSelection().toString()` (async wrapped)
- `www_screenshot <path> [--panel ...]` - `view.grab().save(path, "PNG")`
- `www_back [--panel ...]` - history back
- `www_forward [--panel ...]` - history forward
- `www_reload [--panel ...]` - reload current page

### Adaptation notes vs C++

- Same async wrapping pattern as `CmdsChroma` (`QEventLoop` for `toHtml`/`toPlainText`/`runJavaScript` callbacks)
- Callback signature for `runJavaScript` uses `QVariant` in C++; in Python it's a plain Python object, wrap with `str(r) if r is not None else ""`.

---

## Panel wrapper

One column of the 4-panel main window - toolbar + info bar + content stack.

**File:** `panel.py`
**Factory:** `wrap_panel(content: QWidget, www_view: QWebEngineView = None) -> Panel`

### Layout
```
+-------------------------------------------------+
| [tab] 🔄 □ ⬅ ⬈ 📂 □   ...   [viewer buttons]  |   toolbar (54px)
+-------------------------------------------------+
| 📋  <path label>                                |
| 📋  <selection label>                           |   info bar (76px, dark)
|                        <viewer label>  📋       |
| [ url input - only in www mode                ] |
+-------------------------------------------------+
|                                                 |
|              content (view / www)               |   remainder
|                                                 |
+-------------------------------------------------+
```

### Panel dataclass fields
- `wrap: QWidget` - the outer widget added to the splitter
- `custom`, `dflt`, `log: QPushButton` - legacy viewer switch buttons (hidden by default; `viewer_bar` supersedes them; `log` is left-panel-only)
- `viewer_bar: QWidget` - container that receives dynamic per-file viewer buttons (rebuilt by main window)
- `refresh, hide_parent, dir_up, fm, reveal_dir, hide_rightmost: QPushButton` - fixed toolbar buttons
- `tab_toggle: QPushButton | None` - view/www cycle button (present only on tabbable panels)
- `info_path, info_selection, info_viewer: QLabel` - 3-row info bar
- `copy_path, copy_selection, copy_viewer: QPushButton` - 📋 buttons; hidden until label has content
- `url_input: QLineEdit | None` - visible when www tab is active
- `info_bar: QWidget` - the whole info section (hideable)
- `stack: QStackedWidget | None` - swaps view <-> www when tabbable
- `www_view: QWebEngineView | None` - the www view instance

### Factory behavior
- **Tabbable panel** (`www_view is not None`): adds `tab_toggle` button, wraps `content + www_view` in a `QStackedWidget`, and adds an `url_input` line into the info bar.
- **Non-tabbable panel** (`www_view is None`): plain content widget, no stack, no `url_input`.
- All buttons carry the same emoji icons and styling as the C++ original (🔄 ⬅ ⬈ 📂 □).
- The `custom / dflt / log` legacy switch buttons stay in the tree for backward compat but start hidden; the main window can flip visibility per-panel role.

### Copy buttons
- `_make_copy_btn(parent, target_label)` wires each 📋 button to copy the target label's `cmdPath` property (falls back to tooltip). Button starts hidden - the main window shows/hides it as label content changes (matches the C++ `syncCopyBtn_` helper).

### Adaptation notes vs C++

- `Panel_` struct -> `@dataclass Panel` (mutable, default `None` on every widget slot)
- All `Qt::AlignLeft` / `Qt::TextSelectableByMouse` are now enum values under `Qt.AlignmentFlag.*` / `Qt.TextInteractionFlag.*` in PyQt6
- `lambda` connections in C++ (`QObject::connect(..., [](){})`) -> Python `btn.clicked.connect(fn)`
- Stylesheet strings are lifted to module-level constants to keep `wrap_panel` readable.
- `rebuildViewerBar` (~180 lines of dynamic per-file viewer button assembly) is **NOT ported yet** - it belongs to the main window (item #11), needs `readAllViewers_` / `findViewerHtml_` helpers that traverse `.t2l/config.t2l` chains. Coming in the main-window pass.

---

## MainWindow

The 4-panel splitter shell. Instantiates all views, wraps them in Panels, creates the FsBridge + PanelBus singletons, wires WebChannel bridges, sets `CmdsChroma` / `CmdsWww` refs, and hooks up basic bus handlers.

**File:** `main_window.py`
**Inheritance:** `QMainWindow`

### Layout
```
+--------------------+--------------------------+
|                    |                          |
|  parent | dir      |    detail  |  rightmost  |
|   (L)   | (D)      |    (P1)    |    (P2)     |
|                    |                          |
+--------------------+--------------------------+
```

Three nested `QSplitter`s (all horizontal):
- Left group: `p_left` + `p_mid`, min widths 150, startup 200/300
- Right group: `p_right` + `p_rm`, startup 500/500
- Outer: left group + right group, startup 500/1100

### Construction
- `MainWindow(root: str, start_dir: str | None = None)` - `root` = sandbox root; `start_dir` = initial dir OR file:
  - if `start_dir` is a directory -> loaded in the mid panel
  - if `start_dir` is a file -> parent dir loaded in mid panel; file loaded in detail panel (via `bus.notify_file_selected`)
  - if `start_dir` is outside `root` (would escape sandbox) -> falls back to `root`
  - if `start_dir` is `None` -> defaults to `root`

### Panels
- `left_view / mid_view / detail_view / rm_view: QWebEngineView` - 4 view widgets
- `right_www / rm_www: QWebEngineView` - the 2 www views (paired with detail and rightmost)
- `p_left / p_mid / p_right / p_rm: Panel` - the wrapped Panel dataclasses (from `wrap_panel`)

### Setup helpers (module-level)
- `www_profile() -> QWebEngineProfile` - lazy singleton isolated profile named `"koumes-www"` (cookies/cache separated from view panels' default profile)
- `setup_panel(view, role, bridge, bus) -> ChromaPage` - attaches a `ChromaPage(role)` to `view`, then wires a `QWebChannel` exposing three named objects to embedded JS:
  - `fs` -> the `FsBridge` singleton
  - `bus` -> the shared `PanelBus`
  - `panel` -> a tiny `_PanelInfo(role)` so viewers can query their own role
- Class `_PanelInfo` - one-method helper (`role() -> str`), exposed via WebChannel

### Bus wiring (baseline handlers)
- `dirChanged(path)` -> `_load_dir(path)` -> `mid_view.setUrl(file://path)`, updates `info_path`, tracks `_last_dir` on `CmdsChroma`
- `fileSelected(path)` -> loads `path` in `detail_view`, updates info bar, `set_sel_file("p1", path)`
- `fileSelectedRightmost(path)` -> loads in `rm_view`, `set_sel_file("p2", path)`
- `wwwUrlRequested(url, source)` -> loads url in `rm_www` when source is a view panel, else in `right_www`
- `selectionChanged(panel, file, line)` -> updates the corresponding `info_selection` label

### State propagation to command layer
After panels are built, `MainWindow` publishes refs to `CmdsChroma` / `CmdsWww`:
```
CmdsChroma.set_page(mid_view.page())
CmdsChroma.set_detail_page(detail_view.page())
CmdsChroma.set_rightmost_page(rm_view.page())
CmdsChroma.set_detail_view(detail_view)
CmdsChroma.set_rightmost_view(rm_view)
CmdsWww.set_detail_www(right_www)
CmdsWww.set_rightmost_www(rm_www)
```

so the already-registered chroma / www commands (`chroma_html`, `chroma_screenshot`, `www_open`, ...) can reach the live pages.

### Deferred to later steps
- **`rebuildViewerBar`** - dynamic viewer-switch buttons per file (needs `.t2l/config.t2l` walk-up)
- **`readAllViewers_` / `findViewerHtml_`** - viewer resolution helpers (item #18 - "Load viewer config")
- **Toolbar button click wiring** - the `refresh` / `dir_up` / `fm` / `reveal_dir` / `hide_parent` / `hide_rightmost` / `tab_toggle` buttons in each Panel currently have no handlers connected. Item #12 (Toolbar) will register them.
- **WindowPersist** - geometry / splitter sizes / panel visibility save/restore (item #13)
- **Startup viewer loading** - currently loads files directly via `file://` (the browser handles). Once viewer resolution lands, files get routed through the appropriate viewer HTML.

### Adaptation notes vs C++

- ~1500 lines of Main.cpp collapsed to ~150 lines of MainWindow class - the C++ inline lambdas for `updateCustom` / `updateDetail` / `updateRightmost` (~300 lines together) are placeholders for now; the file-loading logic they wrap is deferred until viewer resolution lands.
- `QWebEngineProfile("koumes-www")` uses named profile so subsequent lookups get the same isolated storage.
- Explicit enum access in PyQt6: `Qt.Orientation.Horizontal`, `Qt.AlignmentFlag.*`.

---

## wire_toolbar

Connects the Panel buttons to `CmdSys`. Every click goes through `CMD_SYS().execute_thread_safe(cmdline, "ui", -1, "TOOLBAR")` - never directly to the action - so:

1. The click is **logged** (`LogGuard`)
2. The click is **broadcast** to WS clients (`WsServerLiteGuard`)
3. The same action is triggerable **externally** via WS or stdin (`panel_reload dir`, `tab_toggle p1`, ...)

The actual action is a callback registered with `CmdsChroma` via `set_reload_fn` / `set_toggle_fn` / `set_tab_toggle_fn`.

**File:** `toolbar.py`
**Entry point:** `wire_toolbar(win: MainWindow) -> None`

### What gets wired

- **Refresh** (🔄, all 4 panels): registers reload callback for each panel; click -> `panel_reload <left|dir|p1|p2>`
- **Hide Parent** (□ in mid panel): toggle callback flips `p_left.wrap` visibility, updates button glyph (`□` -> `◧`); click -> `panel_toggle left`
- **Hide Rightmost** (□ in detail panel): toggle callback flips `p_rm.wrap` visibility (`□` -> `◨`); click -> `panel_toggle p2`
- **Tab toggle** (view/www, p1 & p2): flips `QStackedWidget` index between view (0) and www (1); shows/hides `url_input` and `info_path`/`info_viewer` accordingly; button text alternates `view` <-> `www`; click -> `tab_toggle <p1|p2>`
- **URL input** (in tabbable panels' info bar): Enter in field loads the URL into that panel's `www_view` (auto-prepends `https://` if missing)
- **Dir up** (⬅, mid panel only): click -> `dir_up`
- **Reveal dir** (📂, detail panel only): click -> `reveal_dir`
- **FM** (⬈, mid panel = open dir in system fm; detail panel = open file externally)

### Visibility rules

Buttons that don't apply to a given panel role are hidden after wiring:
- `dir_up` visible only on mid
- `reveal_dir` visible only on detail
- `hide_parent` hidden on left/right/rm panels (only mid has the toggle)
- `hide_rightmost` hidden on rm (would be self-close; redundant) and left/mid
- `fm` hidden on left / rm panels

### Adaptation notes vs C++

- `static int savedParentWidth = 200;` (function-static) -> Python nested closure state dict (`state = {"left_hidden": False}`)
- `[capture]() { ... }` lambdas -> nested Python defs with default-arg closure capture (`def cb(_=False, k=key): ...`)
- `setCmdTooltip_(w, cmdline)` (used a Q_PROPERTY) -> plain `setToolTip(cmdline)` - simpler and shows the same info on hover.
- **Splitter-size shuffle** on hide/show (C++ carefully moves pixels between panels using `split->sizes()`) is **simplified** in the port: setting `wrap.setVisible(False)` alone hides the panel and the splitter reflows; explicit pixel accounting can be added later if the reflow doesn't feel right.

---

## WindowPersist

Save / restore main window geometry across sessions via `<dir_config>/config.t2l`.

**File:** `window_persist.py`

### Line format written / read

```
set_window <x> <y> <w> <h> <screenIdx> <screenW> <screenH>
```

Coordinates are relative to the screen's origin. On restore, the saved `screenIdx` must exist and its `(screenW, screenH)` must match the current screen at that index - otherwise the line is skipped. This protects against monitor topology changes (docked / undocked / different setup).

If saving fails to resolve a screen index (rare - happens before window is shown), a short 4-arg form `set_window <x> <y> <w> <h>` is written and applied as absolute coords.

### Class method
- `WindowPersist.install(main_window: QWidget, app: QApplication) -> None`
  - Remembers `main_window` internally
  - Registers `set_window` and `save_window_position` CmdSys commands
  - Connects `app.aboutToQuit` -> save on shutdown

### Registered commands (category: `chroma`)

- `set_window <x> <y> <w> <h> [<screen> [<sw> <sh>]]` - restore geometry. Skips silently if screen mismatch. Named args (like `--USER`) are ignored - only positional args count as coordinates.
- `save_window_position` - immediately serialize current geometry and append/replace the `set_window ...` line in `config.t2l`.

### Config file helper (module-level)

- `replace_or_append_in_config(line: str) -> None` - reads `<dir_config>/config.t2l` (creates if missing), finds a line whose first word matches this line's first word, replaces it; if no match, appends. Writes the file back. Port of `AppUtility::replaceOrAppendInConfig`.

### Adaptation notes vs C++

- C++ `static QWidget*& mainWindowRef_()` (Meyers singleton pattern) -> Python class attribute `_main_window`
- C++ `QObject::connect(app, &QApplication::aboutToQuit, [](){ ... })` -> Python `app.aboutToQuit.connect(lambda: ...)`
- Only positional args count as coordinates (WS injects `--USER` etc.); matches C++ behavior
- File I/O uses plain Python `open()`; the config file lives in `AppPaths.inst().dir_config()` which was designed to be user-writable

---

## viewer_resolver

Resolve which viewer HTML renders a given file. Ported from the family of `readAllViewers_` / `findViewerHtml_` helpers in `APPS/AI_T2LS/Main.cpp`.

**File:** `viewer_resolver.py`
**Module-level functions (no class):**

### Resolution rules (highest precedence first)
1. **In-file directive** (only for `.t2l` files): the file itself contains `type: viewer / name: X`
2. **Walk-up `config.t2l`** from the file's directory toward the sandbox root; at each level check `.t2l/config.t2l` (new pattern) then plain `config.t2l` (backward compat). Each `type: viewer_ext / ext: <ext> / viewer: <name>` block that matches contributes a viewer name.

Duplicates removed (first occurrence wins).

### Public functions

- `find_viewer_html(dir_path, root, viewer_name) -> str` - walk up from `dir_path` toward `root`, look for `.t2l/<name>.html` first (new pattern) then `<name>.html` (backward compat). Returns absolute path or `""`.
- `read_viewer_from_t2l(file_path) -> str` - parse a `.t2l` file; return `name:` value from the first `type: viewer` record. `""` if none.
- `read_viewer_name(dir_path) -> str` - convenience: read `<dirname>/<basename>.t2l` for a dir-level viewer directive.
- `read_all_viewers_from_config(cfg_path, ext) -> list[str]` - viewers from all `viewer_ext` blocks matching `ext` in one config.t2l (in file order)
- `read_browse_viewers_from_config(cfg_path, ext) -> list[str]` - same but only where `sys__browse_support: true / 1 / yes`
- `read_browse_viewers(file_path, root) -> list[str]` - walk-up variant of `read_browse_viewers_from_config`
- `read_all_viewers(file_path, root) -> list[str]` - full precedence order (in-file + config walk-up), deduped
- `read_viewer_for_ext(file_path, root) -> str` - first result of `read_all_viewers`, or `""`

### `viewer_ext` block format

```
type: viewer_ext
ext: md
viewer: mdid
sys__browse_support: true    # optional
```

### Wiring in `MainWindow`

`MainWindow._resolve_view_url(file_path)` picks the highest-precedence viewer name via `read_viewer_for_ext`, resolves its HTML via `find_viewer_html`, and produces a `QUrl.fromLocalFile(html)` with a `?file=<abs>` query. The viewer HTML reads that query param and loads the file via the JS side (using `fs.read(path)` on the WebChannel bridge).

Falls back to `QUrl.fromLocalFile(file_path)` (browser handles the file directly) when no viewer is registered.

### Adaptation notes vs C++

- Six near-identical parser passes (`readAllViewersFromConfig_` / `readBrowseViewersFromConfig_` / etc.) collapsed to a single `_read_config_blocks(cfg_path, ext, require_browse=False)` with a flag - identical behavior, no code duplication.
- `QDir::cleanPath(QDir(x).absolutePath())` -> `os.path.normpath(os.path.abspath(x))`
- `QFileInfo(p).suffix()` -> `Path(p).suffix.lstrip(".")`
- `QFile.open()` -> plain `open(..., "r", encoding="utf-8")` inside `try/except OSError`

---

