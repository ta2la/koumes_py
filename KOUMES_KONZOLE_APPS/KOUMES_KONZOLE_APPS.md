# KOUMES_KONZOLE_APPS

The apps of the console: each one is a separate program that runs in a panel of
`KOUMES_KONZOLE` and shows one thing.

**Why it exists.** The core of the console stays small; a view of something is an app next
to it. An app can be run, restarted and replaced without touching the console, and a new
view does not change its code. They share one library, `konzole_view`, so a list, a dialog
or a click work the same in every app.

An app is one file. It talks to the console through options of its tmux pane and through
`clmon` commands. Where things are it reads from `KOUMES_KONZOLE/config.t2l`, which external
program opens what from `KOUMES_KONZOLE/apps.t2l`.

## Files

| file | what it is | what it does |
|---|---|---|
| `konzole_view` | library | the shared panel: scrolling rows, clicks, links, md, images, dialogs, watching a file |
| `viewer` | app | a file: text with line numbers, md, html, images |
| `git_list` | app | a whole git repo as a tree, with state, ticks and folds |
| `dirview` | app | directory browser, repos, C++ modules, timeaxis mode; commands over WebSocket |
| `aicom` | tool | a channel of a person and an agent in the timeaxis: writes, moves files in, clipboard both ways; also remarks |
| `stamp` | tool | one click writes a record with the exact time into a dated t2l file |
| `repos` | app | all repos under `tree` |
| `timeaxis_item_esence` | app | a timeaxis item in one window |
| `pindani` | app | messages between agents, read from their transcripts |

Help: [KOUMES_KONZOLE_APPS.help.md](KOUMES_KONZOLE_APPS.help.md)

AI Recipe: [KOUMES_KONZOLE_APPS.recipe.md](KOUMES_KONZOLE_APPS.recipe.md)
