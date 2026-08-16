# koumes

Editor / dir browser / t2l viewer / command console. Dual-access: humans and AI agents share the same command interface.

## Install

```bash
pip install koumes
```

## Run

```bash
koumes                       # opens cwd
koumes /path/to/root         # sandbox to <root>
koumes /path/to/root /path/to/root/subdir   # + initial dir
koumes --headless            # no GUI, WS + stdin only
```

WebSocket bridge lives on `ws://127.0.0.1:12345`. Every executed command is broadcast; external tools can inject commands by sending lines.

## Packages

- `cmd_sys/` - command parsing, registration, dispatch, WS bridge, log guard
- `KOUMES/` - the desktop app (PyQt6 UI, panels, chroma bridge)

See `cmd_sys/oneshot.md` and `KOUMES/oneshot.md` for API references.

## Status

Early alpha - port of C++/Qt `APPS/AI_T2LS/` in progress.
