# KOUMES - recipe

A description precise enough to write the app again, in any language, and get the same
app: its parts, files, classes, functions, interfaces and the decisions behind them. File
names are given without an extension.

## What it is

A desktop app (Qt with an embedded web engine) over a directory tree, the "sandbox":
four panels side by side, each showing a directory or a document through a viewer (an
HTML page or a Qt class). The command layer is `cmd_sys`: every action is a command, run
on the main thread, logged and broadcast over a WebSocket. Python port of the C++
`APPS/AI_T2LS`. Without a GUI it runs headless: commands from stdin and the WebSocket.

## Decisions

- **One interface for two users.** A human clicks, an agent sends the same command over
  the WebSocket; a button only sends a command. Everything is in the log.
- **Panels never reach into each other.** They meet on the bus (`PanelBus`): directory
  changed, file selected, line changed, panel show, selection changed.
- **Viewers are pages, not code of the app.** The app hands a viewer the path and a
  bridge (`window.__chroma`, `fs`, `bus`, `panel` over the web channel); the rest is the
  page's. A new viewer = an `.html` somewhere above the file, nothing recompiled.
- **The sandbox is a hard boundary.** The filesystem bridge reads and writes only inside
  the root; the boundary is a path separator, not a string prefix (`<root>_files` is
  outside).
- **`line` is the addressable unit:** a physical line in md and text, a record in t2l.
- **The state of one deployment is in its config** (`other_config/config.t2l`): port,
  colours of the info bar, window geometry, panels, `qt_viewer:` and `panel_button:`
  lines. It is never published.
- **Commands touching widgets run on the main thread**: lines from the WebSocket and
  stdin wait in the `CmdSys` queue; a timer drains it.
- **Wayland:** prefer XWayland (`xcb`) when both are available, otherwise a saved window
  position can never be restored; `KOUMES_QPA` overrides.
- English, no machine paths (public repo).

## Startup (`main`)

1. Parse arguments: `root` (default cwd), `start_dir` (default root), `--headless`,
   `--port`, `--dirview` (default: two levels above the package - the tree's `.t2l/`).
2. `bootstrap`: paths (`AppPaths`), built-in commands of `cmd_sys`, `LogGuard` into
   `<config>/cmdlog.txt` capped at `log_lines:` (default 300, 0 = no cap), port =
   `--port` or `ws_port:` or 54325, `WsServerLite` on it with `CmdBridge`, stdin monitor on.
3. Headless: print where it listens and sleep. GUI: prefer `xcb`; register the GUI
   commands (chroma, www, paste); viewer fallback dirs = `KOUMES_PY_APPS` (next to the
   package) and `--dirview`; Qt viewer names from the config; create the application,
   tooltip style, quit on SIGTERM / SIGINT (with a 200 ms timer so Python sees signals);
   `MainWindow(root, start_dir)`, `wire_toolbar`, `WindowPersist.install`, show, then
   `WindowPersist.restore()` (after show, otherwise the show fights the geometry).

## Files

The module breaks the rule one class = one file in a few places (marked *several*);
it is to be split when worked on.

### `app_paths` - **`AppPaths`** (singleton `inst()`)
`dir_exe()` = the package directory; `dir_config()` = `other_config` of the deployment
(created when missing); `settings()` = `key: value` lines of `config.t2l` as a dict;
`settings_list(key)` = all values of a repeated key.

### `main` - startup, see above. Constants `DEFAULT_WS_PORT = 54325`, `DEFAULT_LOG_LINES = 300`.

### `main_window` - **`MainWindow`** (+ `_PanelInfo`, *several*)
The four-panel splitter: `LeftPanel`, `DirPanel`, `DetailPanel` (p1), `RightmostPanel`
(p2), each with a web view (p1 / p2 inside a `ViewerHost`). Responsibilities, by method
group:
- **title and sizes:** `_window_title`, `set_title_short` (title = the sandbox only),
  `_apply_initial_sizes`, `splitter_state`, `restore_splitter(left, dir, p1, p2)`,
  `ensure_panel_width(which)`;
- **panel state:** `panel_state()` -> dir, p1 + viewer, p2 + viewer, active;
  `restore_panels(state)`;
- **startup content:** `_startup_html`, `_load_startup_detail`;
- **downloads:** `_wire_downloads`, `_on_download` (free name, flash on the panel);
- **wiring:** `_wire_infobar_clicks`, `_wire_dir_viewer_toggle`, `_wire_left_panel_tabs`,
  `_wire_bus`, `_drain_cmd_queue` (timer: run the queued commands on the main thread);
- **navigation:** `_load_dir(path)`, `_on_dir_changed`, `_reload_dir`, `_refresh_dir_up`,
  `_on_sandbox_changed(root)`; `_on_file_selected(path)` (p1),
  `_on_file_selected_rightmost` (p2), `_on_file_selected_for_browse(path, line)`,
  `_on_line_changed`, `_on_selection_changed(panel, file, line)`, `_on_panel_show`;
- **loading a viewer:** `_load_view_html(view, target, file, role, line, start)` - for a
  Qt target the host switches to the Qt page; else the web page loads the HTML with the
  file and line; `_set_info_viewer` shows which viewer, `NATIVE` when the browser renders
  the file itself;
- **info bar:** `_set_info_path(label, abs)` (path relative to the sandbox, full outside
  it), `_sync_copy_btn`, `_panel_of_info_path`;
- **left panel:** `_show_left_menu`, `_show_left_html`;
- **active panel:** `set_active_panel(key)`; `_mark_viewer_button(bar, name)`;
- **Qt viewers:** `_on_qt_selected(panel, path, record)`, `_on_qt_line`, `_on_qt_failed`.
- module functions: `setup_panel(view, role, bridge, bus)` - a `ChromaPage` with the
  role, a web channel exposing `fs`, `bus`, `panel`, the injected `__chroma` bootstrap
  and `qwebchannel.js` (read from the package, PyQt6 does not ship it);
  `_is_outside_sandbox`, `_path_from_index`.

### `panel` - **`Panel`** and its four kinds (*several*)
One column: toolbar, role bar, info bar, content. `LeftPanel` (four tabs: parent,
bookmarks, log, menu - `MenuPage`), `DirPanel` (owns navigation and the ◧ hiding left),
`DetailPanel` (p1; reveals the document's dir, carries ◨ hiding p2), `RightmostPanel` (p2).
Helpers: `icon_btn_qss`, `dir_up_qss` (`DIR_UP_COLOR = #16a34a`), `_info_bar_qss(bg,
border)` with `info_bg` / `info_border` (and `_left`) from the config, default
`#1f2937` / `#111827`; `_make_copy_btn`; `make_label_clickable` / `set_label_clickable`
(hand cursor, amber hover `#fbbf24`).

### `role_bar` - **`BaseRoleBar`**, `ContentRoleBar`, `ViewerRoleBar`, `DirRoleBar` (*several*)
The 26 px strip between toolbar and info bar: the panel's name on the left, a switch on
the right. Left: four fixed contents; p1 / p2: the viewers registered for the file on
screen; dir: the same plus custom / default. Buttons shrink to icons when there is no
room (`refit`), a hover peeks the full name and the command; the active panel's bar is
violet (`#ede9fe`, border `#6d28d9`).

### `viewer_bar` - `rebuild_viewer_bar(bar, file, root, load_fn, active, panel)`
One button per viewer the file has (`read_all_viewers`), plus `native`; `.pdf` starts
native.

### `viewer_resolver` - which viewer renders a file
- `viewer_file_names(name)` -> `name.exe.html`, `name.html`;
- `find_viewer_html(dir, root, name)`: walk up from `dir` to the filesystem root, at each
  level `.t2l/<file>` then `<file>`; then the extra fallback dirs;
- `ext_candidates(file)`: most specific first (`a.diag.t2l` -> `diag.t2l`, `t2l`);
- `read_viewer_from_t2l`, `read_viewer_name(dir)` (`<dirname>.t2l`, `type: viewer`);
- `read_all_viewers(file, root)` / `read_browse_viewers`: `viewer_ext` blocks of every
  `config.t2l` walking up (the first found is the default);
- `set_qt_viewers(names)`, `find_viewer_target(dir, root, name)` -> `qt:<name>` for a Qt
  viewer, else the HTML path; `read_viewer_for_ext`.

### `qt_viewer` - viewers that are classes
`registry()` = `qt_viewer:` lines -> `{name: (file, class)}`; `load_class(name)` once per
run; `is_qt_target` (`qt:` prefix). **`ViewerHost`** (a stacked widget): page 0 the web
view, page 1 a Qt viewer; `show_web`, `show_qt(name, path, line)`, `select(record)`;
watches the file (`_stat`, `_changed`, `_reload`).

### `help_resolver` - which document answers "what am I looking at"
`<name>.help.html` beats `<name>.help.md` at every level; bare `help.html` / `help.md` are
accepted. `find_help_for_file(file, root)`: the file's own sidecar, then the help of its
kind (`help_ext` blocks in `config.t2l`), then the place; `find_help_for_dir(dir, root)`:
this dir, else the nearest parent; `root_help_path(root)` where a new top help goes.

### `fs_bridge` - **`FsBridge`** (singleton; exposed to the pages as `fs`)
Sandboxed filesystem: `list`, `read`, `write`, `exists`, `isDir`, `trash` (`gio trash`),
`repoKind`, `viewers(path)`; selection reported by the pages: `setSelection`,
`setSelectedDir`, `setSelectedFile`, `setSelectedLine` and the `current_*` getters;
`[[link]]` resolution: `followLink(arg, start)` (id walked up through `index.t2l` /
records, rewriting a stale link), `validateLinks(file)`, `last_follow_log`;
`exec(cmdline)` runs a command; `saveInPlace(src, data_url)` (redline exports),
`origOf`. Allowed root: `set_allowed_root`, `allowedRoot`, `is_inside`.

### `panel_bus` - **`PanelBus`**
Signals (and `notify*` slots for the pages, `notify_*` for Python): dir change, file
selected (p1, p2, for browse with a line), sandbox changed, line changed (p1, p2), www
URL requested, selection changed, panel show.

### `chroma_page` / `chroma_www_page` - **`ChromaPage`**, **`ChromaWwwPage`**
Web pages of the view panels (local files only; role for the bootstrap; new windows
refused; feature permissions) and of the www panels (external web only).

### `cmds_chroma` - **`CmdsChroma`** (+ `PanelSel`, *several*)
The `chroma_*`, `panel_*`, `select` / `show` / `preselect` / `viewer_switch` /
`reveal_dir` / `dir_up` / `open_extern` / `title_toggle` / `debug_follow*` commands (the
list is in `KOUMES.help.md`). Holds the pages, views, hosts, window and bus it acts on
(`set_*`), the last dir / file / viewers, per-panel switch / reload / toggle functions;
HTML and text of a page are read synchronously (`_page_to_html_sync`).

### `cmds_www` - **`CmdsWww`**: `www_*` commands over the two web panels.
### `cmds_paste` - **`CmdsPaste`**: `paste_clipboard` (image or text into a timestamped file in the exchange dir), `exchange_dir`, `export_saved`.

### `window_persist` - **`WindowPersist`**
On exit writes into the config `set_window x y w h screen sw sh` (normal geometry, frame
offset corrected on X11), `set_panels --dir … --p1 … --p1v … --p2 … --p2v … --active …`
and `set_splitter`; on start the config is executed, so restore = the same commands.
Off-screen positions are pulled back, otherwise the window is centred on the primary
screen. `replace_or_append_in_config(line)` keys a line by its first word.

### `toolbar` - `wire_toolbar(win)`
Connects the buttons to commands: app bar, reload, hide toggles, active panel chip, tab
toggles, dir navigation, file manager, and one extra button per `panel_button:` line.

### `app_bar` - **`AppBar`**, `ClipPreview` (*several*)
The paste strip: what the clipboard holds (preview on hover: 200 px thumb or 200
characters), a click saves it; the status line shows the saved file for 12 s and opens it.

### `theme` - tooltip style (from `info_bg`) and `tinted(qss)`: the tint marking a panel of another category.

### `__init__`, `__main__` - the package and `python -m KOUMES`.

## Gaps of this recipe

Exact layouts and colours of every widget, the bootstrap JS (`__chroma`) and the link
resolution algorithm step by step are described only in outline; they are to be filled
in when the module is worked on.
