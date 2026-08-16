# KOUMES - port plan

Python port of `APPS/AI_T2LS/` (~3400 lines of C++/Qt) into a PyQt6 application.

Uses `cmd_sys` module (already ported, sibling in this repo) as its command backbone.

## Group 1 - Bootstrap / infrastructure

- [x] **1. AppPaths** - `app_paths.py`
- [x] **2. Main entry** - `main.py`, `__main__.py`, `__init__.py`
- [x] **3. pyproject.toml** - `pyproject.toml`, `README.md`, `.gitignore` (in repo root)

## Group 2 - Qt / Web bridge

- [x] **4. FsBridge** - `fs_bridge.py`
- [x] **5. ChromaPage** - `chroma_page.py`
- [x] **6. ChromaWwwPage** - `chroma_www_page.py`
- [x] **7. PanelBus** - `panel_bus.py`

## Group 3 - Commands

- [x] **8. Cmds_chroma** - `cmds_chroma.py` (~35 commands)
- [x] **9. Cmds_www** - `cmds_www.py` (9 commands)

## Group 4 - UI

- [x] **10. Panel wrapper** - `panel.py` (Panel dataclass + `wrap_panel` factory)
- [x] **11. Main window** - `main_window.py` (baseline; viewer resolution + toolbar wiring deferred)
- [x] **12. Toolbar** - `toolbar.py` (wire_toolbar function)
- [x] **13. WindowPersist** - `window_persist.py` (via config.t2l `set_window` cmd)

## Group 5 - Integration

- [x] **14. Register commands** - wired into `main.py` (headless: CmdsCmdSys; GUI: adds CmdsChroma + CmdsWww via lazy import)
- [x] **15. Bootstrap CmdBridge** - port 54325 (default) + `--port` override in `main.py`
- [x] **16. Bootstrap LogGuard** - wired in `main.py` bootstrap, verified end-to-end
- [x] **17. Load initial file/dir** - `MainWindow` accepts dir OR file, sandbox-checks, defaults to root
- [x] **18. Load viewer config** - `viewer_resolver.py` (walk-up + in-file directive), wired into `MainWindow._resolve_view_url`

## Group 6 - Viewer HTMLs (no port, reuse existing)

The existing dirview HTMLs in `APPS/AI_T2LS/dirview/` (dirs.html, t2lplus.html, mdid.html, txt.html) and `.t2l/*.html` viewers are **not ported** - they're plain HTML/JS and work as-is with the FsBridge. KOUMES just points its QWebEngineView at the same files. Long-term option: copy them into `koumes/dirview/` as package data.
