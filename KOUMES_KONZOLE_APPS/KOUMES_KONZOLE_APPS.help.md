# KOUMES_KONZOLE_APPS - how to use it

For a person in the console and for an agent who drives it. Normally the console starts
the apps: a file goes to `viewer`, a directory to `git_list`, buttons start the others.
Each one also runs by hand: `clmon --tp1 --run 'path/to/app.py ARGS'`.

Optional programs: chafa (images), rich (md), pandoc (html). A missing one only means that
kind of content shows as text or a note.

## Keys of every app but dirview and pindani

Arrows or j k, PgUp PgDn or b space, g G start and end, Home End, wheel; r reload; w images
full width; q close the panel. Links: URL blue, file with ▶▶▶; a click opens it.

## viewer

```bash
viewer.py FILE [--line N]
```

Text with line numbers, md and html rendered, images through chafa. A block fenced with
` ```monospace ` is console output or a text diagram: shown as it is, a long row is cut, escape sequences give colors and styles. Extra keys: s rendered /
source, e editor on the top line. Under an image [more] / [less]; a click on it opens it
outside.

## git_list

```bash
git_list.py DIR
```

Shows the **whole repo** of DIR as a tree, whichever directory DIR is. Not a repo: it says so.

| mark | meaning |
|---|---|
| ● | in git |
| 📝 | changed against HEAD |
| ⊗ | in git, missing on disk |
| ✗ | ignored by git; an ignored directory is closed until you open it with ⊞ |
| no mark | not in git |
| ✔ | ticked |
| ⊟ ⊞ | a click folds or unfolds a directory |

Click right of the name = tick, again = off; a directory ticks all under it, it shows ✔ only
when all its files are ticked; the top row ticks the repo, after a confirmation. A click on a
file opens it in the panel to the right. Colors: `.md` yellow, module descriptions (`.md`,
`.recipe.md`, `.help.md`) magenta. The title shows the state against GitHub: ↑ not pushed,
↓ missing here.

Ticks and folds are in `git_list.t2l` in the root of the repo, not in git.

## dirview

```bash
dirview.py [DIR] [--port N] [--code CODE_ROOT]
```

One directory at a time. Keys and mouse call the same commands an agent sends.

| mark | meaning |
|---|---|
| 🈴 🅰️ 🟥 | a repo: C++, apps, other (remark in `<repo>/<repo>.t2l`) |
| 🧩 | a C++ module, a directory with a `.pro` file |
| ● ✗ 📝 | in git, ignored, changed |

A `.t2l` file with `type: filelist` shows as a directory; its rows are `file: [[file:path]]`,
`...]]:25` a line, `...]]:25:40` lines. Timeaxis mode: items from the newest, 25 at a time,
[more]; the selected one opens to the right; [back] returns.

### Commands

Over the WebSocket of the panel; the port is in `clmon --port pN`.

```bash
echo 'chroma_dir' | websocat -n1 ws://127.0.0.1:PORT
```

| command | what it does |
|---|---|
| `chroma_dir` | `--DIR` current directory |
| `chroma_setdir <path>` | go to a directory; a file: select it |
| `chroma_line` | `--LINE` selected line, from 1 |
| `chroma_setline <n>` | select line n |
| `cppb_open` | open the selected line |
| `cppb_view [path]` | the repo tree on the right |
| `cppb_repos` | all repos on the right |
| `cppb_timeaxis` | timeaxis mode |
| `cppb_aicom` | aicom mode |
| `cppb_remarks` | the last remarks on the right |
| `cppb_paste` | `--FILE` the clipboard as a new item of the last aicom |
| `cppb_copy` | the selected aicom item into the clipboard |
| `cppb_up` | one level up; [back] in timeaxis and aicom mode |
| `cppb_move <-1\|+1\|pgup\|pgdn\|home\|end>` | moves the selection |
| `panel_reload` | reads the directory again |
| `cppb_filter [on\|off]` | filter of the code root |

## aicom

```bash
aicom.py last | list | new [NAME] | add FILE [NAME] | write NAME | paste [NAME] | copy [FILE]
```

A shared channel in the timeaxis. An aicom is an item `<year>_qN/MM_DD_name.AICOM`; its items are
files `YYYY_MM_DD_HH_MM_SS_name.ext`: md, pictures, anything. Everything goes to the last aicom,
which is created when there is none.

| command | what it does |
|---|---|
| `last` | prints the last aicom |
| `list` | prints all items, oldest first |
| `new [NAME]` | a new aicom dated today |
| `add FILE [NAME]` | moves a file in |
| `write NAME` | text on stdin as a new md item |
| `paste [NAME]` | the clipboard as a new item: text = md, picture = its format |
| `copy [FILE]` | an item into the clipboard, default the newest |

**remarks** is the same with items `MM_DD_name.REMARKS`: `--remarks` before any command selects
it, `link URL [NAME] [--clip]` writes one item from its parts: the link, text on stdin, and the
clipboard; a picture lies next to the md under the same name and belongs to that item. A URL in a shown md
is active: a click opens the original.

[remarks] opens the last remarks in `timeaxis_item_esence`. In dirview [aicom] shows the items of the last aicom, opposite to timeaxis mode: the
newest at the bottom, [more] on top adds older ones. Otherwise the same: the selected item
opens on the right, [back] returns. [paste] and [copy] do the same as the commands; the list
follows a new item while the last row is selected.

## stamp

```bash
stamp.py ID
```

A button from a `type: stamp` record in `config.t2l`: one click writes a record with date and time
to a t2l file. The time or an error shows in the top bar. Attributes are described in `stamp.py`.

## repos

```bash
repos.py
```

All repos under `tree`. Click = its description (record `description` in `<repo>/<repo>.t2l`,
rows `co:`), again = dirview in p1. Commands: none.

## timeaxis_item_esence

```bash
timeaxis_item_esence.py ITEM
```

ITEM is a file, or a directory whose files go one after another. 25 rows of each, [more] 50
more, [less] back. A file name is a link to the panel on the right, binaries and URLs open
outside. Commands: none.

An item of an aicom shows all items from it to the oldest, each under a rule with its date and
time; the newest one selected = everything from the newest on. A click on ⊟ at the start of
the rule shrinks an item to that rule, ⊞ expands it; kept in `aicom.t2l` in the aicom.

## pindani

```bash
pindani.py [-H HOURS] [--once] [--chat]
```

Who runs and what they write to each other. Only reads, touches no session. `--once` prints
text and ends, `--chat` shows only the messages, `-H` hours back, default 24. Commands: none.

## Library: konzole_view

For whoever writes an app:

```python
from konzole_view import Pane

class App(Pane):
    WATCH = ""                       # a file; on a change the panel redraws

    def render(self, w, h):          # add rows
        self.add("text", ("sel", 3)) # ("sel", 3) goes to action() on a click
        self.title("name", "info")

    def action(self, what, arg):
        self.resized = True          # redraw

App("path").run()
```

`add`, `add_link`, `add_text`, `add_image`, `add_md`, `add_rendered`, `cut_rows`; `ask(text,
choices, on_yes, image, value)` a dialog, with `value` a text field read by `dlg_value()`;
`console(*args)` a `clmon` command; `hover_at`, `key`, `more_less` to override.

Files of the module: [KOUMES_KONZOLE_APPS.md](KOUMES_KONZOLE_APPS.md). How it is built:
`KOUMES_KONZOLE_APPS.recipe.md`.
