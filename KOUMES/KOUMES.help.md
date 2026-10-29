# KOUMES - how to use it

For a person who uses the window and for an agent who drives it by commands.

```bash
python -m KOUMES <root> [start_dir] [--port N] [--headless] [--dirview DIR]
```

`root` is the sandbox: the app reads and writes only inside it. The port comes from
`--port`, else `ws_port:` in `other_config/config.t2l`, else 54325.

## Panels

| panel | what it's for |
|---|---|
| `left` | parent directory, bookmarks, log, menu (four tabs) |
| `dir` | main directory browsing |
| `p1` | the open document (or a webpage, `view` / `www` toggle) |
| `p2` | a second document, target of `chroma_setfile … --p2` |

**Panels never reach into each other.** A click on a button sends a command, it runs,
gets logged and broadcast - which is why an agent can repeat everything a person does
with the mouse.

## Commands

Over the WebSocket, one per line, e.g. `echo 'chroma_dir' | websocat -n1 ws://127.0.0.1:54325`.
Replies carry the output as `--NAME value`, an error as `--ERROR`.

### Where the user is

| command | reply |
|---|---|
| `chroma_dir` | `--DIR` the directory in `dir` |
| `chroma_file` | `--FILE` the selected file |
| `chroma_line` | `--LINE` the selected line (md / text: physical line, t2l: record) |
| `chroma_selection` | the last DOM selection (JSON) |
| `chroma_dir_viewer`, `chroma_file_viewer` | `--VIEWER` what renders the directory / the file |
| `get_selection <panel>` | file and line selected in a panel |
| `panel_active [p1\|p2]` | which document panel an unaddressed file opens in; with an argument switches it |

### Showing the user where to look

| command | what it does |
|---|---|
| `chroma_setdir <path>` | `dir` goes to the directory |
| `chroma_setfile <path> [--p1\|--p2]` | opens the file in p1 (or p2) |
| `chroma_setline <n> [--p2]` | scrolls to line n and selects it |
| `select <dir\|p1\|p2> <line>` | selects a line in a panel |
| `show <dir\|p1\|p2>` | brings the panel into view |
| `preselect <panel> <path>` | selects a file without opening it |
| `panel_show <left\|dir\|p1\|p2\|active> <file> [viewer]` | shows a file in a panel, optionally with a given viewer |
| `viewer_switch <panel> <viewer>` | switches the viewer of a panel |
| `reveal_dir [p1\|p2]` | `dir` goes to the directory of the panel's document |
| `dir_up` | `dir` one level up |

### Panels and the window

| command | what it does |
|---|---|
| `panel_reload <left\|dir\|p1\|p2>` | reloads a panel (scrolls to the top; restore with `chroma_setline`) |
| `chroma_reload`, `chroma_reload_detail` | reloads the whole page / p1 |
| `panel_toggle <left\|p2>` | hides / shows the panel |
| `tab_toggle <p1\|p2>` | switches `view` / `www` |
| `title_toggle [short\|full]` | window title |
| `chroma_openfm` | the file manager on the current directory |
| `open_extern <target>` | opens a file or URL outside the app |
| `set_window <x> <y> <w> <h> [screen [sw sh]]`, `set_splitter <left> <dir> <p1> <p2>`, `set_panels …`, `save_window_position` | window geometry (written to the config on exit) |

### Looking at the screen

| command | what it does |
|---|---|
| `chroma_html [--p2]`, `chroma_text [--p2]` | HTML / plain text of a document panel |
| `chroma_screenshot <png> [--p2]` | snapshot of a document panel |
| `chroma_window <png>` | snapshot of the whole window (on Wayland the only one that works) |
| `chroma_style <css>`, `chroma_class <cls>`, `chroma_unwrap` | style / class / unwrap the current DOM selection |

### Web panels

| command | what it does |
|---|---|
| `www_open <url> [--panel detail\|right]` | opens a URL in a web panel |
| `www_url`, `www_html`, `www_text`, `www_selection` | what the web panel shows |
| `www_screenshot <png>` | its snapshot |
| `www_back`, `www_forward`, `www_reload` | navigation |

### Clipboard and links

| command | what it does |
|---|---|
| `paste_clipboard` | saves the clipboard (image or text) into a file in the exchange directory |
| `exchange_dir` | where pasted files go |
| `export_saved <path>` | log entry for a canvas export already written |
| `debug_follow <id> [--start <path>]`, `debug_follow_log` | resolves a `[[link]]` and shows how |

Plus the commands of `cmd_sys` (`cmd_help`, `cmds_list`, `execute_script`, ...), see
`cmd_sys/cmd_sys.help.md`.

## Viewers

Which viewer a file gets: walking up from the file's directory, `.t2l/<name>.html` and
`<name>.html`, chosen by `type: viewer_ext` records in `config.t2l` files and by
`<dirname>.t2l`; then `KOUMES_PY_APPS/`; then `--dirview`. A `qt_viewer:` line in the
deployment config makes a Qt class a viewer. The role bar of a panel shows the viewers
the file has and switches between them.

Files of the module: [KOUMES.md](KOUMES.md). How the module is built: `KOUMES.recipe.md`.
