# koumes

A shared workspace for a person and an AI agent: both use the same commands and see the same
screen. Two variants, independent of each other:

- **Python** (`KOUMES/`, `KOUMES_PY_APPS/`): a desktop window, a browser for local files with html
  viewers. Needs PyQt6, PyQt6-WebEngine, websockets. `python3 -m KOUMES /path/to/tree`.
- **Console** (`KOUMES_KONZOLE/`, `KOUMES_KONZOLE_APPS/`): panels in a terminal, on tmux. Needs tmux.
  `KOUMES_KONZOLE/clmon`. A panel can run ordinary terminal software, and through tmux both a person
  and an agent work with the same program.

## Install

Install is a copy: copy the directory and run it from there. No pip, no package.

Start in [KOUMES_PY.help.md](KOUMES_PY.help.md).

## Status

Early alpha.
