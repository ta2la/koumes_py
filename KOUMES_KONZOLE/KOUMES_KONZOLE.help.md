# KOUMES_KONZOLE - how to use it

For a person who uses the window and for an agent who drives it by commands.

```bash
clmon                # opens, or connects to the running one
```

Needs tmux. Optional: helix, micro, chafa (images), rich (md), pandoc (html), xclip.
Agents keep running when the window closes; `clmon` returns to them.

## First start

`config.t2l` and `apps.t2l` are written when missing. The console runs at once with
nothing assigned. Click **[config]** to assign what you want: a feature with an empty
row has no button. [apps] shows what is installed.

## The window

Left: the menu, the list of running agents and the terminal of the selected agent.
Right: panels p1 to p9, each with a bar, a label and its content.

| menu | what it does |
|---|---|
| `[exit actual]` | sends `/exit` to the shown agent; there while any agent runs |
| `[close]` | ends the console; there only when no agent runs |
| `[config]` | where things are on this machine, in p1 |
| koumes buttons | one per `koumes` record in `config.t2l`: starts it, or places its window beside the terminal |
| `[dir]` | dirview in p1, in `tree` |
| `[diag]` | the diagram viewer; there with a `diag` record |
| `[pindání]` | messages between agents |
| `[p1]` `[p2]` ... | orange = open, click jumps there; the grey one opens the next free panel |

Second part of the menu: agents that do not run, click starts them.

| panel bar | what it does |
|---|---|
| `[repos]` | all git repos under `tree` |
| `[>_]` | a shell in the panel, again = back |
| `[timeax]` | dirview in timeaxis mode; there with `timeaxis` assigned |
| `[aicom]` | the last aicom as a timeaxis item; there with `timeaxis` assigned |
| `[remarks]` | the last remarks as a timeaxis item; there with `timeaxis` assigned |
| `[apps]` | the list of apps and programs |
| `[← dir]` | the directory of the shown file in dirview |
| `[🔃]` | reloads the panel; a change of an app's code needs a restart of the app |
| `[🔓]` | a locked panel is not overwritten, its content goes to the next one |
| `[<]` `[>]` | moves the panel |
| `[x]` | closes the panel |

The label of a panel shows what it holds, and on the right how else it can be opened:
`[viewer] [helix] ↗eog ↗xdg-open`, for a directory `[dirview] [git_list] ↗nautilus`.

## Keys

| where | keys |
|---|---|
| list | arrows move, Enter = to the agent, 1-9 switch or start, 0 messages, p next panel, + - list height, z full window, q detach |
| viewer | arrows, PgUp, PgDn, Home, End, wheel, r reload, s source, w images full width, e editor, q close |
| anywhere | F12 + number = agent, F12 0 messages, F12 p next panel, F12 arrows between panels, F12 z agent full window |

## Commands

Any shell, the console does not have to be the parent. `tpN`, `txN` and `pN` take the
panel number.

### Showing things

| command | what it does |
|---|---|
| `clmon --tp1 FILE [--line N]` | shows a file in p1, the panel opens when it is not there |
| `clmon --tp1 FILE --edit` | in micro |
| `clmon --tp1 FILE --hx` | in helix |
| `clmon --tp1 --run 'COMMAND'` | runs a program in p1 |
| `clmon --open-right PANE FILE[:N[:M]]` | in the panel right of tmux pane PANE; N = line, N:M = lines |
| `clmon --tx1` | closes p1 |
| `clmon --switch pN view\|hx\|dirview\|esence\|ext BIN` | switches how the panel shows its content |
| `clmon --show-dir PATH` | that path or its directory in dirview, in p1 |

### Asking

| command | what it answers |
|---|---|
| `clmon --where` | what is in the panels and which agent is shown |
| `clmon --port pN` | the port of the program in the panel, only the number |
| `clmon --free-worker` | which worker is free |

### Agents

| command | what it does |
|---|---|
| `clmon --start worker` | starts the free worker with the lowest number, in the background |
| `clmon --start NAME\|NUMBER` | starts an agent in the background, without switching |

### Snapshot of a window

| command | what it does |
|---|---|
| `clmon --snapshot pN\|agent` | prints what the panel or the agent window shows, with colors, as a ` ```monospace ` block |
| `clmon --snapshot pN --to FILE` | appends it to a file |
| `clmon --snapshot pN --aicom [NAME]` | a new item of the last aicom |

### Testing an app

| command | what it does |
|---|---|
| `clmon --in_test pN AGENT [--msg TEXT]` | a dialog over the app: that agent is testing it; `\n` in TEXT = new line, for a checklist |
| `clmon --in_test pN off` | the dialog away |

### Configuration

| command | what it does |
|---|---|
| `clmon --config KEY VALUE` | assigns: `timeaxis`, `koumes-x.port`, `diag.script`, ...; no value = clear |

### The console itself

| command | what it does |
|---|---|
| `clmon --close` | ends it, only when no agent runs |
| `clmon --kill` | ends everything in it; agents can continue later with `--continue` |
| `clmon --reload` | restarts only the list, agents keep running |
| `clmon --say TEXT` | shows a message in the menu |
| `clmon -h` | help |

Internal, called by the console itself: `--toggle`, `--tbar`, `--menu`, `--stitek`,
`--avatar`, `--view`, `--list`, `--idle`, `--number`, `--clamp`, `--fit`, `--paste`, `--copy`,
`--dblstatus`, `--focus-list`, `--focus-agent`, `--zoom`.

## config.t2l

| record | attributes |
|---|---|
| `places` | `tree`, `code_root`, `agents`, `timeaxis`, `avatars`, `workers`, `panel_port`, `koumes_port` |
| `koumes`, one per instance | `id` (button), `code`, `root`, `port`, `python` |
| `diag` | `script`, `file`, `python` |
| `stamp`, one per button | `id` (button after [apps]), `file`, `section`, `days`, `record`, the rest goes to the record; see `stamp` in `KOUMES_KONZOLE_APPS` |

What each one is for: [config], click its row. A change appears without a restart.

## apps.t2l

Records `app`, `tool` (ext `*` = editor of non-binary files), `viewer_ext` (external
viewers by extension; the first installed one of a record is used, then the `*` record).
`origin: py` was written by `apps`, `origin: user` was added by hand.

Files of the module: [KOUMES_KONZOLE.md](KOUMES_KONZOLE.md). How it is built:
`KOUMES_KONZOLE.recipe.md`.
