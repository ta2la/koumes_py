# KOUMES_KONZOLE - recipe

A description precise enough to write the module again, in any language, and get the
same module: its parts, files, functions, interfaces and the decisions behind them. File
names are given without an extension.

## What it is

Several terminal programs that cooperate inside one tmux server and form one application:
a left column with a menu, a list of agents and the terminal of the selected agent, and
to the right numbered panels running anything. Standard library plus tmux; everything
optional is detected.

## Decisions

- **State lives in tmux.** Panes carry options (`@role`, `@slot`, `@file`, `@run`, `@lock`,
  `@port`, `@agent`, `@title`, `@test`, `@test_img`, `@test_msg`), the server carries `@panels`, `@chat`,
  `@msg`, `@msg_t`, `@idle`, `@busy`. Every pane sees the same state, no process owns it.
- **Everything is a command.** A click, a key and an agent all run `clmon --something` as a
  separate process, so the menu never blocks and an agent can repeat what a person does.
- **Minimal core, views are apps.** A view of something is a program in
  `KOUMES_KONZOLE_APPS`, it talks to the console through pane options and `clmon` commands.
- **No machine in the code.** Paths and ports come from `config.t2l`, programs from `apps.t2l`.
  Empty value = the feature is off and its button is absent, or a default applies. Nothing
  is detected: `config` writes an empty file and `config_view` lets the user assign it.
- **No width is remembered or computed.** An edge changes only its two neighbours; the outer
  edge of the window changes only the outer column, past the minimum it takes from the next
  one inwards. Minimum MIN_PX. A new panel has P1_W columns and the window grows by it.
- **A file is not watched** by the viewer; [🔃] reloads. Exception: an app sets `WATCH`.
- **A loop process ends when the program file changes** and the shell loop around it starts
  it again, so a code change reaches menu, bars, labels and list without a restart.
- **Text the user sees is English** for new code; older messages are Czech and are translated
  gradually. No personal data, no machine paths: the repo is public.

## Constants of `clmon`

`SOCK` tmux socket, default `clmon4`, env `CLMON4_SOCKET`; `CLMON4_CONF` replaces the agent
list and `CLMON4_AGENT_CMD` the agent command, `CLMON4_FAKE_HERE` makes a pane look like a
running agent (trial runs). `SEP = "|~|"`, `P1_W = 90`, `PANEL_MAX = 9`, `MIN_PX = 100`,
`TBAR_H = 2`, `STITEK_H = 2`, `PANEL_ROLES = view, chat, edit, hx, run, sh`,
`PANEL_PORT = 54330`, `KOUMES_PORT = 54325`, `WS_RUN = CPPBROWSE, dirview.py`,
`CTX_WARN = 200000`, `CTX_HIGH = 400000`, `TIP_SECS = 2.5`, `ARM_LABEL = " /exit "`,
`EDITOR = micro`, `HX = hx`. `REFRESH`: view = key r; edit = C-e reopen Enter; hx = Escape
:reload Enter. `REFRESH_RUN`: programs -> keys.

## Files

### `config`

The places of this machine. `FIELDS`: (record type, attribute, kind dir / file / text,
description in markdown). Record types `places` (one), `koumes` (many, `id` = button),
`diag` (one).
- `fields(typ)`, `write(path)` empty `places` with `origin: py`, `ensure(path) -> bool`;
- `load(path)`: records as dicts, a missing file is written first;
- `records(typ)`, `expand(value)`, `place(name)` expanded or "", `number(name, default)`,
  `tree()` = `place("tree")` or the home directory;
- `assign(key, value) -> error or none`: key `attr`, `<id>.attr`, `diag.attr`; replaces or
  inserts the line in the record, `origin: py` becomes `origin: user`; text preserved;
- `add(typ, rid) -> error or none`: appends an empty record;
- writes are atomic: `<path>.tmp`, then replace.

### `config_view`

**`ConfigView(path)`** (a `Pane`), `WATCH = path`. Fields `sel` (selected key), `walk`
(directory of [choose], none = the list), `kind`, `spans` (row -> buttons by column).
- `render`: two lines of legend, then per record a bold heading and a row per field;
  `render_walk` instead when `walk` is set;
- `field(key, attr, value, kind, what)`: row ` attr  state  value`, state `✔`, red `✗`,
  dim `-`; a selected row has a background and below it the description through `add_md`
  (indented 4) and buttons;
- `buttons(row, x, labels)`, `click`: a click on a button row finds the button by column;
- `do_button`: choose, type (`ask` with `value=`), clear, use, cancel, add_koumes, add_diag;
- `put(value)`: `config.assign`; paths under home are written with `~`;
- `start_walk`, `value()`, `action`: sel, go, take.

### `apps`

`DEFAULTS` (type, attributes): `app`, `tool`, `viewer_ext`. `write`, `ensure`, `load` as
in `config`, repeated attributes as lists. `bin_for(target)`: directory / URL scheme /
extension -> the first installed binary of the `viewer_ext` record listing it, else of
the record with `*`. `editor()`: the `tool` with ext `*`, first installed binary.

### `apps_viewer`

**`AppList(path)`** (a `Pane`), `WATCH = path`. `load`, `table_lines(rows, w)` (a rich table:
kind, name, extensions, file / binary, installed; at most 3 extensions, then `…`),
`entries(recs)` -> (icon, name, ext, file or binary, installed, detail): `[ ]` internal,
`↗` external. A click selects, the detail goes on top with a rule below. Rows of the table
are mapped to records by the icon starting a row.

### `clmon`

One file, sections in this order.

**Agents and transcripts.** `load_conf_names()` {path: label} from the agent list, workers
TEMP1..6 under `WORKERS_DIR`; `load_agents`, class **`Log(hours)`** (`update`, `files`,
`name`, reads messages between agents, usage): `cwidth`, `cut`, `wrap`, `slug`, `short_path`,
`alive`, `ts_of`, `ago`, `ktok`, `fsize`, `second_line`, `hhmm`, `mark`.

**tmux.** `tmux(*args)`, `server_up`, `gopt`, `popt`, `panes()` (list-panes with SEP),
`lay(ps)` -> `{list, main, panels, menu, tb, tbars, st, stitky, avatar}`, a bar and a label
belong to the panel starting on the same column; `panel(L, n)`, `free_slot(L)`.

**Clipboard and messages.** `copy_join`, `copy_cli`, `paste_cli`, `status_refresh`, `say`.

**State of agents.** `entries()` named first, workers after; `in_our_tmux(pid)`, `conf_cmd`,
`is_remote` (a `cmd:` starting with ssh), `agent_inner`, `agent_cmd`, `chat_cmd`, `pane_of`,
codex: `codex_transcript`, `codex_usage`, `codex_status`, `codex_limits`; `pane_busy`,
`state_of` -> here / jinde / shell / off, `rows_state`, `running`, `stopped`, `usage_parts`,
`idle_layout`, `idle_data`, `idle_bar`, `wake`.

**Window and widths.** `xrun`, `active_window`, `window_width`, `our_window`, `grow`, `touch`,
`want_w`, `cell_px`, `min_cols`, `columns`, `saved_cols`, `save_cols`, `apply_cols`, `edge_fit`,
`window_x`, `busy`, `fit` (hook client-resized), `clamp` (MouseDragEnd1Border and every second).

**Panels.** `ensure_main`, `active_path`, `add_panel`, `drop_panel`, `ensure_tbars`; bar
`tbar()`, label `stitek()` with `panel_app`, `is_binary`, `switch_options`, `switch_panel`,
`copy_path`; `menu()`; `open_panel(n, role, cmd, path, run) -> (error, n)`, `close_panel`,
`leave_editor`, `edit_cmd`, `hx_cmd`, `view_cmd`, `split_lines`, `hx_select`,
`tp(n, path, line, edit, run, hx, last) -> error`, `refresh_panel`, `sh_dir`, `toggle_sh`,
`show_dir`, `panel_port`, `move_panel`, `unlocked_right`, `open_right`, `where`.
A locked panel passes its content to the next unlocked one on the right, or a new one.

**Menu.** Two rows; the second starts at [dir]. Buttons: `[close]` when `@busy` is empty, else
`[exit actual]`; `[config]`; one per `KOUMES_ROOTS`; `[dir]`; `[diag]` with `DIAG_SCRIPT`;
`[pindání]`; open panels orange, the next free one grey. Yellow = that app is running.
`state` of redrawing includes the size, options, live apps and config; `use_config(mtime)`
each pass. `ListUi` writes the number of running agents to `@busy`.

**koumes and diag.** `port_busy`, `koumes_port(root)` from `/proc/*/cmdline` (`--port`, else
`KOUMES_PORT`), `koumes_live` (2 s cache), `_wgeom`, `_extents`, `_koumes_win`, `koumes_place`,
`_monitor_at`, `win_place`, `koumes_start(name)`, `dir_start`, `diag_running`, `_diag_win`,
`diag_start`.

**Dispatch.** `toggle(name)`: koumes names, diag, dir, config, exit_actual, `a<i>`, and
`(p|x|chat|lock|refresh|updir|copy|sh|mvl|mvr|repos|timeax|aicom|remarks|apps)<n>`. `launch`, `free_worker`,
`start_cli`, `snapshot(what)` (capture-pane -e into a monospace block, a fence of four when the text holds three), `show`, `dblclick`, `close_all` (refuses while an agent runs), `exit_actual`,
`icon_col`, `on_icon`, `deactivate`, `list_click`, `number`, `bind_keys`.

**Curses.** Class **`Ui(scr)`** (`put`, `title`, `close`), avatar: `avatar_path(label)`
(`<NAME>.png`, T1-6 = `WORKERS`, none = `PARTA`), `ensure_avatar`, `avatar`. Class **`ListUi`**
(`code_stamp`, `refresh_data`, `sizes_of`, `draw`, `act`, `step`, `events`, `on_mouse`, `run`,
`loop`).

**Built-in viewer.** Class **`View(path, line)`** and its helpers (`link_row`, `virtual`,
`wrap_cells`, `chafa_lines`, `image_block`, `md_lines`, `html_to_md`) behind `--view`, now only for an empty
panel; a file goes to `viewer`, a directory to `git_list`, repos to `repos`, an item to
`timeaxis_item_esence` (see `view_cmd`).

**Start.** `zoom`, `focus`, `idle`, `start`, `kill`, `arg_after`, `use_apps_config`,
`use_config(seen) -> mtime` (config into the module constants, `KOUMES_*` dicts, `DIAG_*`,
ports; `CLMON4_CONF` wins), `main`: reads `-h`, then one branch per option.

### `clmon.tmux`

Prefix F12, mouse on, copy through xclip, status off, own socket only; keys are generated
by `bind_keys` into `KEYS_CONF` at start.

## Order of start

`clmon` without arguments: refuse inside tmux; start the server with `clmon.tmux`, window with
the list; `ListUi` creates menu, avatar, bars, labels and panels. `apps.ensure`, `config.ensure`
in every process.
