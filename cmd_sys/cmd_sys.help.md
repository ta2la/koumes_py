# cmd_sys - command layer

How to use the module: for a person or an agent who registers or calls commands.

cmd_sys is the reason koumes serves a human and an agent the same way: one set of
commands, called from the UI or sent over a WebSocket. Command registry, argument
parser, log and WebSocket bridge. **No Qt dependency** - it runs without a window too.

## Files

| file | what it does |
|---|---|
| `cmd_sys.py` | `CmdSys`: registry and dispatch; `CMD_SYS()` is the shared singleton |
| `cmds.py` | `Cmds`: a group of commands of one application on its own `CmdSys` |
| `cmd_arg_col_parser.py` | splits a line into arguments (quotes too) |
| `ws_server.py` | `WsServer`: WebSocket connector for any `CmdSys` (own port per application) |
| `ws_server_lite.py` | WebSocket server of the `CMD_SYS()` singleton |
| `log_guard.py` | appends every executed command to `other_config/cmdlog.txt` |
| `cmds_cmd_sys.py` | built-in commands (`cmd_help`, `cmds_list`, `execute_script`, ...) |

## Command shape

```
<name> <arguments...> --OUTPUT values
```

The input is what was sent; from the first `--` on, the command has written how it
went. The log keeps both, so it shows afterwards not only what was asked for, but
also what came out of it.

Arguments: positional ones separated by spaces, named ones as `--name value` (a name
may repeat), `"multi word"` in double quotes stays one argument, `{...}` (JSON) is one
token. Every command gets `--USER <who>` appended (the source: UI, WS, script, ...).

## Calling commands from outside

An application with a WebSocket connector takes one command per line:

```bash
echo 'chroma_dir' | websocat -n1 ws://127.0.0.1:<port>
```

Only for local clients: the port listens on 127.0.0.1 and a client with an `Origin` header is
refused, so a web page in a browser cannot get in.

`-n1` waits for the reply. The reply is the command line with the output appended,
e.g. `chroma_dir --DIR /some/dir --USER EXTERNAL_WS`. An error comes as `--ERROR <text>`.
Every executed command is broadcast to all connected clients.

## Commands of an application - `Cmds`

The usual way for a new application: subclass `Cmds`, register commands, open the
WebSocket connector, run the waiting lines on the main thread.

```python
from cmd_sys import Cmds

class MyCmds(Cmds):
    def __init__(self, app):
        super().__init__("my")                      # prefix: my_help lists the commands
        self.app = app
        self.register("my_open", self._open, "<path> - open a file")

    def _open(self, args):
        if not args:
            return "my_open: usage: my_open <path>"  # str = error
        self.app.open(args[0])
        return [(args[0], "FILE")]                   # [(value, name)] = appended output

cmds = MyCmds(app)
cmds.start_ws(port)          # port exactly; start_ws(0, default) = first free from default
while True:
    ...
    cmds.drain()             # lines from the WebSocket, executed on the main thread
```

- A handler gets the unnamed arguments and returns `None`, an error (`str`) or
  `[(value, name)]`.
- Every command runs under `lock` (e.g. a pool lock); an exception never escapes, it
  becomes the error of the command.
- Hooks: `changed()` after every command (e.g. redraw), `mode()` state reported with
  every reply (`--MODE`).
- `cmds.run(line)` runs a command from the own UI the same way, logged and broadcast.

## The shared registry - `CMD_SYS()`

The koumes window uses the singleton directly:

- `add(name, handler, category=...)` - registration; nothing more is needed.
- `execute(line, ...)` - run now.
- `execute_thread_safe(line, ...)` - queue it for the thread with the window; buttons
  and the WS bridge call this.

**Why the queue.** Qt may talk to its widgets only from the main thread, but a command
can come from anywhere - a socket, stdin, a click. Everything is put aside and the
main thread picks it up.

A raw handler (without `Cmds`) has the signature `handler(args, data, ctx) -> int`:
`args` is the parsed `CmdArgCol` (`args.get(i)`, `args.get_by_name(name)`), the reply
is appended to it (`args.append(value, name)`, `args.append_error(text)`), 0 = ok.
`add(..., exclude_update=True)` keeps a command out of the guards (no log, no broadcast).

Dispatch of one command: the filters may veto it, then the handler by name runs (an
unknown name goes to `__not_implemented__`), then the guards are told.

## Filters and guards

- **Filter** (`CmdExeFilter`, `reg_filter`): before a command; `pass_(args)` returning
  `True` filters the command out (it does not run).
- **Guard** (`CmdExeGuard`, `reg_guard`): after every command. Phase `RECORD` (log,
  history) fires before phase `UPDATE` (observers, broadcast).

Guards and connectors that come with the module:

| class | what it does |
|---|---|
| `LogGuard(path, max_lines=0)` | appends `HH:MM:SS <command line>` to a file; `max_lines` keeps only the tail |
| `WsServerLite` + `WsServerLiteGuard` | WebSocket of the `CMD_SYS()` singleton (default port 12345): lines in as commands, every executed command broadcast to all clients; needs the `websockets` package, without it does nothing |
| `CmdBridge.init()` | starts that WebSocket in one call |
| `StdinMonitor` | stdin lines as commands (skips `qt.` debug lines); off until `set_enabled(True)` |
| `StdoutCmdOutput` | echoes every command to stdout; off by default - where stdout comes back to stdin it would loop |

Script files: `execute_script` runs one command per line; `cmds_execute_script`
(`CmdUtils.mine_commands_from_script`) lets one command span several lines, a blank
line ends it.

## Commands

The built-in commands of cmd_sys, one `### <command>` section per command.
`cmd_help <name>` replies with the text of its section (without the heading); lines
`--FLAG` at the start of a section go into the reply as flags. A command without a
section gets "No documentation available for this command." A new command = a new
section here, nothing to register.

### cmd_help

Show help for a command.

Usage: `cmd_help <command_name>`

Output: `cmd_help <command_name> --HELP <text>`

### cmds_list

List registered commands grouped by category. Optionally filter by one or more categories.

Usage: `cmds_list` - all commands
Usage: `cmds_list --type <category>` - filter by category (repeatable)

### cmds_categories

List all registered command categories (sorted).

Usage: `cmds_categories`

### execute_script

Execute commands from a file, line by line. Skips empty lines and lines starting with #.

Usage: `execute_script <path>`

### cmds_execute_script

Execute commands from a script file. A blank line separates commands; consecutive
lines join into one command (CmdUtils.mine_commands_from_script).

Usage: `cmds_execute_script <path>`

### logcmd

No-op command used for logging. Its execution IS the log entry - appears in command
history with all arguments.

Usage: `logcmd <message>`

### voidcmd

No-op command. Does nothing, returns 0. Used to trigger the command pipeline (guards,
broadcast) without side effects.

### __not_implemented__

Fallback handler for unregistered commands. Returns error "command not implemented: <name>".
