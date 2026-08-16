# KOUMES C++ ↔ Python diff

Systematický průchod `APPS/AI_T2LS/Main.cpp` (1780 řádků) vs `KOUMES/`.
Značky: ✅ = ported, ⚠️ = partial, ❌ = missing, 🚫 = intentionally skipped.

---

## Main.cpp static helpers (top-of-file)

| # | C++ (line, name)                                | LOC | Python location                             | Status |
|---|-------------------------------------------------|-----|---------------------------------------------|--------|
| 1 | `wwwProfile_()` (65)                            | 15  | `main_window.py::www_profile()`             | ✅     |
| 2 | `setupPanel_()` (81)                            | 40  | `main_window.py::setup_panel()`             | ⚠️ (simplified) |
| 3 | `findViewerHtml_()` (126)                       | 20  | `viewer_resolver.py::find_viewer_html()`    | ✅ + fallback dirs |
| 4 | `readViewerFromT2l_()` (151)                    | 22  | `viewer_resolver.py::read_viewer_from_t2l()`| ✅     |
| 5 | `readViewerName_()` (177)                       | 8   | `viewer_resolver.py::read_viewer_name()`    | ✅     |
| 6 | `readAllViewersFromConfig_()` (190)             | 30  | `viewer_resolver.py::_read_config_blocks()` | ✅ (dedup s browse) |
| 7 | `readBrowseViewersFromConfig_()` (224)          | 30  | `viewer_resolver.py::_read_config_blocks(require_browse=True)` | ✅ |
| 8 | `readBrowseViewers_()` (260)                    | 22  | `viewer_resolver.py::read_browse_viewers()` | ✅     |
| 9 | `readAllViewers_()` (290)                       | 30  | `viewer_resolver.py::read_all_viewers()`    | ✅     |
| 10| `readViewerForExt_()` (326)                     | 8   | `viewer_resolver.py::read_viewer_for_ext()` | ✅     |
| 11| `fileHasLinks_()` (337)                         | 12  | -                                           | ❌     |
| 12| `dirHasLinks_()` (348)                          | 18  | -                                           | ❌     |
| 13| `pathFromIndex_()` (366)                        | 15  | `main_window.py::_path_from_index()`        | ✅     |
| 14| `isOutsideSandbox_()` (382)                     | 8   | `main_window.py::_is_outside_sandbox()`     | ✅     |
| 15| `setCmdTooltip_()` (408)                        | 42  | (via `setToolTip(cmdline)` v `toolbar.py`)  | ⚠️ (no Q_PROPERTY handshake, no visual style) |
| 16| `makeLabelClickable_()` (449)                   | 15  | -                                           | ❌     |
| 17| `syncCopyBtn_()` (463)                          | 8   | -                                           | ❌ (copy button always hidden) |
| 18| `setInfoPath_()` (470)                          | 22  | `main_window.py::_set_info_path()`          | ✅ (přidán po výtce) |
| 19| `setInfoViewer_()` (491)                        | 20  | -                                           | ❌ (info_viewer se nastavuje plain `setText`) |
| 20| `wrapPanel_()` (543)                            | 210 | `panel.py::wrap_panel()`                    | ✅ (bez cmdTooltip handshake) |
| 21| `rebuildViewerBar()` (753)                      | 70  | -                                           | ❌ **KRITICKÉ** - viewer switch buttony |

---

## Main.cpp `int main()` inline lambdas (830-1780)

| # | C++ (line, name)                                | LOC | Python location                             | Status |
|---|-------------------------------------------------|-----|---------------------------------------------|--------|
| 22| Injected JS `injectSrc` (937)                   | 90  | `main_window.py::_CHROMA_BOOTSTRAP_JS`      | ⚠️ (jen minimum bez linkify) |
| 23| `[[id]] linkify helper` (990)                   | 60  | -                                           | ❌ (chybí window.__chroma.linkify) |
| 24| Initial viewer HTML resolution (1054)           | 20  | v `_load_dir()` + `_resolve_view_url()`     | ⚠️ (bez `readViewerName_` in-file directive lookup pro **dir**) |
| 25| `wireTabs` lambda (1328)                        | 30  | `toolbar.py::_wire_tab_toggles()`           | ✅     |
| 26| `updateCustom` lambda (1387)                    | 50  | `main_window.py::_load_dir()`               | ⚠️ (chybí custom viewer switch, refresh info bars) |
| 27| Bus.dirChanged wire + init (1434)               | 5   | `main_window.py::_wire_bus()`               | ✅     |
| 28| Viewer switch handler (setViewerSwitchFn) (1445)| 15  | -                                           | ❌ (CmdsChroma.set_viewer_switch_fn nikdy nevoláno) |
| 29| `refreshDirUp` lambda (1499)                    | 15  | -                                           | ❌ (červené tlačítko když outside/at-root) |
| 30| `wireTabs(pR/pRm)` (1354-55)                    | 5   | `toolbar.py::_wire_tab_toggles()`           | ✅     |
| 31| WWW URL routing (1357+)                         | 20  | `main_window.py::_on_www_url_requested()`   | ✅     |
| 32| Left/p2 hide toggle handlers (1245, 1304)       | 40  | `toolbar.py::_wire_hide_toggles()`          | ⚠️ (bez pixel-precise splitter shuffle) |
| 33| selectionChanged handler (1277)                 | 25  | `main_window.py::_on_selection_changed()`   | ✅ (bez syncCopyBtn) |
| 34| dirUp button click + sandbox widen (1517)       | 15  | `toolbar.py::_wire_dir_navigation()` + `cmds_chroma.dir_up` widen | ✅ |
| 35| refresh button handlers (1532-1546)             | 15  | `toolbar.py::_wire_reload()`                | ✅     |
| 36| revealDir button (1552)                         | 10  | `toolbar.py::_wire_dir_navigation()` + `cmds_chroma.reveal_dir` widen | ✅ |
| 37| `updateDetail` lambda (1583)                    | 40  | `main_window.py::_on_file_selected()` + `_resolve_view_url()` | ⚠️ (chybí `rebuildViewerBar` call, `browse_support` viewer resolution, native fallback) |
| 38| Bus.fileSelected wire (1622)                    | 2   | `main_window.py::_wire_bus()`               | ✅     |
| 39| Detail viewer switch handler (1640+)            | 15  | -                                           | ❌ |
| 40| `updateRightmost` lambda (1687)                 | 40  | `main_window.py::_on_file_selected_rightmost()` | ⚠️ (viz #37) |
| 41| bus.fileSelectedRightmost wire (1728)           | 2   | `main_window.py::_wire_bus()`               | ✅     |
| 42| Rightmost viewer switch handler                 | 15  | -                                           | ❌ |
| 43| bus.panelShow router (registered 2025)          | 20  | `main_window.py::_on_panel_show()`          | ✅ (přidáno po výtce) |
| 44| bus.sandboxChanged handler                      | 10  | -                                           | ❌ (chybí propagace do dirs.html re-init) |
| 45| WsServerLite start (main)                       | 5   | `main.py::bootstrap()` `WsServerLite.init`  | ✅     |
| 46| CmdBridge init                                  | 2   | `main.py::bootstrap()` `CmdBridge.init()`   | ✅     |
| 47| StdinMonitor init                               | 2   | `main.py::bootstrap()`                      | ✅     |
| 48| LogGuard init                                   | 5   | `main.py::bootstrap()`                      | ✅     |
| 49| CmdsCmdSys register                             | 2   | `main.py::bootstrap()`                      | ✅     |
| 50| Cmds_chroma/Cmds_www register                   | 4   | `main.py::register_gui_cmds()`              | ✅     |
| 51| WindowPersist install                           | 5   | `main.py::run_gui()`                        | ✅     |
| 52| set_window restore at startup                   | 5   | (via WindowPersist)                         | ✅     |

---

## Statistika

- **Ported ✅:** 30 položek
- **Partial ⚠️:** 8 položek (existují ale zjednodušeně)
- **Missing ❌:** 14 položek

**Nejkritičtější missing:**
1. **`rebuildViewerBar`** (#21) - dynamické viewer switch buttony per file
2. **`readViewerName_` dir-level directive** (#24) - když dir má vlastní `type: viewer / name: X` v `<dirname>.t2l`
3. **`refreshDirUp`** (#29) - červené dir_up tlačítko na sandbox edge
4. **`[[id]] linkify helper`** (#23) - window.__chroma.linkify pro chroma-link tokens
5. **`updateCustom` custom viewer switch** (#26) - custom/default toggle pro dir
6. **`updateDetail`/`updateRightmost` full flow** (#37, #40) - viewer bar rebuild, browse_support handling, native fallback
7. **`setInfoViewer_`** (#19) - viewer label styling (červená pro native)
8. **`sandboxChanged` handler** (#44) - propagace do dirs.html JS
9. **`syncCopyBtn_`** (#17) - copy button show/hide based on label content
10. **`fileHasLinks_`/`dirHasLinks_`** (#11-12) - hint pro linkify aktivaci
11. **`makeLabelClickable_`** (#16) - clickable info labels

**Nejnaléhavější (u user complaints):** #21 rebuildViewerBar (viewer buttony na p1/p2).

---

## Doporučené pořadí opravy

1. **#21 rebuildViewerBar** - user explicit poptávka; viewer switching
2. **#24 readViewerName_** - dir-level in-file viewer directive
3. **#29 refreshDirUp** - UX na sandbox root
4. **#37/#40 updateDetail/Rightmost full** - stavební kámen pro viewer switch
5. **#44 sandboxChanged handler** - dirs.html re-init po widen
6. **#23 linkify** - [[id]] tokens v mdid/t2lplus viewer
7. **#19 setInfoViewer_** - červená pro native viewer (cosmetic)
8. **#17 syncCopyBtn_** - copy button visibility (cosmetic)
9. **#11/#12 fileHasLinks_/dirHasLinks_** - hint pro linkify (optimization)
10. **#16 makeLabelClickable_** - clickable info bar labels (cosmetic)
