# KOUMES_KONZOLE_APPS - recipe

A description precise enough to write the module again, in any language, and get the
same module: its parts, files, classes, functions, interfaces and the decisions behind
them. File names are given without an extension.

## What it is

Terminal apps that run in a tmux pane of the console, without curses except `pindani`:
alternate screen, own drawing with escape sequences, SGR mouse. One shared library.

## Decisions

- **One file per app.** It is started with paths as arguments and can run alone.
- **The app talks to the console through its pane:** `@role view`, `@file`, `@title`, and
  through `clmon` commands run by `tmux run-shell -b`, so they outlive the pane. `CLMON4_SOCKET`
  selects the tmux; a test without it writes into the live console.
- **A row is a string with its action.** `rows` and `acts` are parallel; a click on a row
  runs its action. A subclass fills them in `render` and redraws by `resized = True`.
- **`render` runs only when needed:** a size change, `resized`, or a change of `WATCH`. A change
  of the app's code needs a restart.
- **Optional programs are checked when used:** without rich md is not drawn, without chafa an
  image is a note, without pandoc html stays source.
- **External programs from `apps.bin_for`**, else `xdg-open`.
- **No machine data.** Places come from `config`; the module `KOUMES_KONZOLE` is added to the
  import path by `konzole_view`, or by the app itself when it does not use the library.
- **New text is English.** Older messages are Czech, translated gradually.

## Files

### `konzole_view`

Constants: `IMG_EXT`, `MD_EXT`, `HTML_EXT`, `IMG_TALL = 2000`, colors `DIM`, `BOLD`, `RST`,
`C_KEY`, `C_HEAD`, `C_CODE`, `C_BTN`, `C_URL`, `C_LINK`, `C_HOVER`, `C_DLG`, `C_DLG_BTN`;
`LINK_MARK = "▶▶▶ "`; `CONSOLE` = `../KOUMES_KONZOLE/clmon`, `SOCK`.

Functions:
- `tmux(*args) -> (rc, out)`, `popt(pane, name, value)`, `short(path)` (`~`), `fsize(path)`;
- `cwidth(s)`: terminal cells (combining and variation selectors 0, wide and emoji 2);
  `wrap_cells(s, width)`;
- `run_ext(app, arg)`, `xdg_open(arg)`, `open_image(path)`, `link_row(pre, label, post, kind, hover)`;
- `chafa_lines(path, width, height, fine=False)`: rows of a picture, `fine` = sextants, din99d;
  `img_path(src, base)`, `image_block(src, base, alt, width, height)`;
- `md_parts(text, width)`: md split into `("text", rows)` and `("img", src, alt)`; rich with
  a grid table without outer edges, a rule below h2; a block fenced ` ```monospace ` keeps its
  characters and spaces, no highlighting, a long row is cut, not wrapped, background `BG_MONO` across the width, on top a rule with the word monospace, escape sequences (SGR) apply; none without rich;
- `html_to_md(path)` through pandoc gfm-raw_html; `kind_of(path)`: img / md / html / text;
- `read_text(path, limit) -> (text, note)`; `arg_line(args)` takes `--line N` out.

**`Pane(path, line=0)`**. Class fields `MAX = 2000000`, `HOVER = False` (mouse motion 1003),
`STEP = 25`, `WATCH = ""`.
- constructor sets `@role view` and `@file`;
- console: `slot()`, `console(*args)`, `title(name, info)`;
- rows: `begin`, `add(row, act)`, `add_link`, `add_text` (first URL or existing relative html
  is a link), `add_image` (small at a third of the width, `[more]` / `[less]`), `add_md`,
  `add_rendered`, `cut_rows(start, n, arg, unit)`;
- for a subclass: `render(w, h)`, `more_less(arg, less)`, `action(what, arg)`, `key(k, h) -> bool`;
- dialog: `ask(text, choices, on_yes, image, value)`: `dlg = (text, choices, image)`, default
  yes / no, `dlg_buf` utf-8 bytes of the text field or none; `dlg_value()`; `dlg_draw(w, h)`
  centred box, `dlg_hits`; `dlg_input(k)`: click on a button, Enter = first, in a field keys
  append bytes and backspace removes a whole utf-8 character, else first letter;
- `poll_test()`: each second reads `@test`, `@test_msg`, `@test_img`; a dialog "Agent X is
  testing this app - hands off" with the avatar, the message, `[cancel]` clears `@test`;
- mouse: `hover_at(y, x)`, `click(y, x)` handles `img`, `open`, `ext`, `url`, `html`, `int`
  (`--open-right` pane target), `view` (with `--viewer`), `txt`, else `action`;
- terminal: `draw()`, `keys(timeout)` -> list of names, characters, `("click", y, x)`,
  `("move", y, x)`; `run()`: cbreak, alternate screen, no cursor, mouse; loop `poll_test`,
  `draw`, input with 1 s timeout; dialog takes all input.

### `viewer`

**`View(path, line=0)`** (a `Pane`). `kind()`, `text_rows(text, w)` (line numbers; colors for
t2l attribute names, headings and code), `render`, `top_line()`, `key`: s toggles source,
e runs `clmon --tp<n> <path> --edit --line <top>`.

### `git_list`

`STATE = "git_list.t2l"`, records `type: tick` / `file:`, `type: fold` / `dir:`, in the repo root.
`state_path`, `load_state`, `save_state`, `load_ticks`, `save_ticks`, `find_top(d)` through
`git rev-parse --show-toplevel`, `repo_key(root)`.

**`GitList(path)`** (a `Pane`), `HOVER = True`. `repo_dir()`, `render`: `git ls-files`, status,
ignored, deleted -> a tree, directories first, branches `├ └ │` with `⊟ ⊞`; legend paragraph on
top. An ignored directory is closed, a `fold` record means open for it; its content is read from disk one level at a time. `remote_check`, `_remote` in a thread: `git ls-remote`,
`rev-list --left-right`, title ↑ ↓, or a note that the remote is empty. `toggle(fs)`, `click`: zone of the
tick right after the name, zone of the fold in the branch, else the file to the right;
`hover_at`: dark ✔ on the tick spot only. Top row asks through `ask`.

### `git_diff`

**`GitDiff(path)`** (a `Pane`), `@file` = `diff:<path>`, `WATCH` for a file. `render`: menu row, `git diff -U<context> HEAD`,
messages for no repo, not in git, no changes. `show`: file name, rows on `BG_ADD`, `BG_DEL` padded to
the width, wrapped; `@@` becomes `gap`, the hidden lines from `RE_HUNK` in new numbering, the rest of
the file counted on disk. `STEP = 3`.
In `git_list` `diffs` and in `dirview` `Entry.mark_x` hold the column of 📝.

### `dirview`

Port of the C++ browser. Constants of buttons and virtual directories: `REPOS = "repos:"`,
`TIMEAXIS = "timeaxis:"`, `ESENCE = "esence:"`, `TIMEAXIS_STEP = 25`, `TIMEAXIS_DIR`.
Functions `cut`, `short`, `git_lines`, `module_tag`, `repo_icon(code, d)`, `is_file_list(path)`.
- **`CodeInfo(root)`**: `level(d)` ROOT / REPO / INSIDE / outside, `repo_kind`, `module`,
  `parse_pro`, `used_by(lib)`, `_dirs`.
- **`Entry`**, **`DirListing(code)`**: `load(d, filt)`, `index_of`, `_load`, `_list` (filelist),
  `_timeaxis`.
- **`TermUi(code)`**: `start`, `stop`, `write`, `size`, `run(line, user)`, `set_dir`, `set_line`,
  `reload`, `up`, `right`, `open`, `row_btn`, `view_repo`, `view_timeaxis`, `move`, `list_top`,
  `draw`, `tick`, `input`, `key`, `mouse`. Input goes through `run` as commands.
- **`CmdsDirview(ui)`** (a `cmd_sys.Cmds`, group `cppb`), commands as in the help.
- `main`: arguments, `start_ws(port)`, SIGTERM and SIGHUP end cleanly.
Default port `panel_port` from config, 54330.

### `aicom`

Used by `dirview` and from a shell. `AICOM_TIMEAXIS` replaces the timeaxis of config (trial runs).
Aicom = directory `MM_DD_name.AICOM` in `<year>_qN`. Item name `YYYY_MM_DD_HH_MM_SS_name.ext`, spaces
to `_`, a taken name gets `_2`. `root`, `dirs` oldest first, `new(name)` dated today, `last` newest or
new, `files(d)` of one aicom oldest first by name, `items(kind)` of the last one, none created, `target(name)`, `add(path, name)` moves, `write(name, text)`.
Clipboard: `clip_tools` wl-paste / wl-copy with `WAYLAND_DISPLAY`, then xclip; `clip_read` a picture
before text; `paste(name)`; `copy(path)` picture by extension, else text/plain, stdout of the tool
to null, it stays behind to serve the clipboard. `main`: one branch per command.

Kinds `AICOM`, `LINKS` (`.REMARKS`): functions take `kind`, `link(url, name, text, kind, clip)` writes one item from its parts; `files` leaves out a picture with the stem of an md.
In `dirview` `DATED` maps the mode `aicom:` to its kind; [remarks] opens `esence:` of the last remarks on the right. `Pane.add_md`: a row with a URL
gets the action `url`, with the whole URL from the source when rich wrapped it.

In `dirview`: `AICOM = "aicom:"`, `DirListing._aicom` opposite to `_timeaxis`: last
`timeaxis_count` items, oldest of them first, `[more]` as the first row. `set_dir` selects the
last row; `reload` stays on the last row when it was there. `view_aicom`, `aicom_paste`, `aicom_copy`.

### `stamp`

`target(rec, now)` `{monday}` in `file`; `where(lines, rec, now)` the line opening the next day, the
end of the file on the last day or without `section`, none when not found; `stamp(rec, now)` inserts
the block `type`, `datum`, `cas` and the other attributes with empty rows around it, keeps all other
lines, writes atomically. A missing file is an error, it is not created. `OWN` attributes are not copied.

### `repos`

**`Repos()`** (a `Pane`). `find` for `.git` under `tree`, pruning `node_modules`, `.venv`. Icon by
remark, name, dim path. `action`: first click opens the description, second `--show-dir`.

### `timeaxis_item_esence`

**`Esence(item)`** (a `Pane`). `render`: each file of the item as in the viewer, cut at
`STEP`, a rule between files; `more_less(f, less)`: +50 / back. `MORE = 50`. An item of an aicom
(`aicom.is_aicom`): files from `aicom.from_item`, newest first, above each a rule with `aicom.stamp`, two empty rows above the rule between items. A click on the rule: `aicom.toggle`; a shrunk item
is only its rule with its name. `aicom.STATE = "aicom.t2l"`, records `type: shrink` / `file: name`,
not an item; `aicom.shrunk(d)`.

### `pindani`

Curses. Read-only. `load_conf_names`, `load_agents(conf)` from `~/.claude/sessions/<pid>.json`,
**`Log`** reads `~/.claude/projects/<slug>/*.jsonl`: a sent message is a SendMessage call, a
received one a `<cross-session-message>`. `once(hours, limit)`, **`Tui`**, `main`. `CONFIG_FILE`,
`WORKERS_DIR` from config. Shares the first part of its code with `clmon` by copy.

## Order

Every app: import path, library, `Pane` constructor marks the pane, `run`. `dirview` starts
its WebSocket before the first draw.
