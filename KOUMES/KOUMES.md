# KOUMES

The desktop app of koumes (PyQt6): a window with four panels over a directory tree -
parent / bookmarks / log, the directory, and two document panels - and a bridge between
them and the command layer. Everything a person does with the mouse is a command, so an
agent can do the same over the WebSocket.

Why it exists: one interface for two users. A human browses, reads and points at lines;
an agent asks where the human is (`chroma_dir`, `chroma_file`, `chroma_line`) and shows
them where to look (`chroma_setdir`, `chroma_setfile`, `chroma_setline`). The content is
drawn by HTML viewers (`KOUMES_PY_APPS`, `.t2l/` in the tree) or by Qt viewer classes.

Python port of the C++ `APPS/AI_T2LS`.

## Files

| file | what it is | what it does |
|---|---|---|
| `__main__` | entry point | `python -m KOUMES` |
| `main` | startup | arguments, command layer, log, WebSocket, then the window or headless |
| `app_paths` | paths | package dir, deployment config dir, `config.t2l` settings |
| `main_window` | the window | four panels in a splitter and all the wiring between them |
| `panel` | panel column | toolbar, role bar, info bar, content; the four panel kinds |
| `role_bar` | strip under the toolbar | panel name and the switch of its viewers / tabs |
| `viewer_bar` | viewer buttons | one button per viewer the shown file has |
| `toolbar` | button wiring | connects the buttons to commands |
| `app_bar` | paste strip | shows the clipboard, a click saves it into a file |
| `panel_bus` | signals | directory / file / line changed - where the panels meet |
| `chroma_page` | web page of a view panel | local files only, its role for the viewer |
| `chroma_www_page` | web page of a www panel | external web only |
| `fs_bridge` | filesystem for the viewers | sandboxed read / write / list, `[[link]]` resolution, selection |
| `viewer_resolver` | viewer choice | which viewer renders a file (walk up `.t2l/`, `config.t2l`) |
| `qt_viewer` | Qt viewers | a Python class as a viewer; host switching web / Qt |
| `help_resolver` | help choice | which help answers for a file or a directory |
| `cmds_chroma` | commands | `chroma_*`, `panel_*`, select, show, ... - drive the window |
| `cmds_www` | commands | `www_*` - the web panels |
| `cmds_paste` | commands | clipboard into a file, exchange dir |
| `window_persist` | session | window, panels and splitter saved on exit, restored on start |
| `theme` | look | tooltip style, tint of a panel of another category |
| `qwebchannel.js` | bridge script | Qt's web channel for the pages (PyQt6 does not ship it) |

Help: [KOUMES.help.md](KOUMES.help.md)

AI Recipe: [KOUMES.recipe.md](KOUMES.recipe.md)
