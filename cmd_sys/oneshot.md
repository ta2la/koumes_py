# cmd_sys - module reference

Command parsing and dispatch subsystem. Complete API reference of classes, methods and commands.

## Package overview

**Exports** (from `cmd_sys`):
`CmdArg`, `CmdArgCol`, `Style`, `CmdArgColParser`,
`CmdContextDataIface`, `CmdContextIface`, `CmdContext`, `CMD_CONTEXT`,
`Cmd`, `CommandHandler`, `CmdUtils`, `CmdExeFilter`,
`CmdExeGuard`, `Phase`, `CmdSys`, `CMD_SYS`,
`StdoutCmdOutput`, `StdinMonitor`, `CmdsCmdSys`,
`WsServerLite`, `WsServerLiteGuard`, `CmdBridge`, `LogGuard`

**Dependency graph:**
```
CmdArg
   ^
   |
CmdArgCol  ---uses--->  CmdArgColParser
   ^
   |
   +----- Cmd (handler receives CmdArgCol + CmdContextIface)
   
CmdContextDataIface
   ^
   |  (attached via client_data_)
   |
CmdContextIface
   ^
   |  (inherits)
CmdContext (singleton)
```

---

## CmdArg

Single command argument (name/value pair). Positional args have empty name. Implemented as a `@dataclass`.

**File:** `cmd_arg.py`

### Construction
- `CmdArg(name: str = "", value: str = "")` - both fields default to empty

### Attributes
- `name: str` - argument name (empty for positional)
- `value: str` - argument value

### Methods
- `is_null() -> bool` - true when both name and value are empty

---

## CmdArgCol

Ordered collection of `CmdArg`. Built either empty or from a raw command-line string (which invokes `CmdArgColParser`).

**File:** `cmd_arg_col.py`

### Enum: Style
Output style for `to_string`:
- `NORMAL` - shell-like: `pos1 pos2 --name value`
- `FORMATTED` - HTML with indices and non-breaking spaces
- `JSON` - array of `["name","value"]` pairs

### Construction
- `CmdArgCol()` - empty collection
- `CmdArgCol(args: str)` - parse `args` via `CmdArgColParser`

### Methods
- `append(value: str, name: str = "") -> int` - append arg, returns 1
- `append_error(text: str) -> int` - append with name `"ERROR"`
- `append_warning(text: str) -> int` - append with name `"WARNING"`
- `count() -> int` / `__len__()` - number of args
- `get(index: int) -> CmdArg` - by index (empty `CmdArg` on out-of-range)
- `get_by_name(name: str, implicit_value: str = "", index: int = 0) -> CmdArg` - by name (implicit fallback)
- `get_arg(name: str, index: int = 0) -> CmdArg | None` - by name, `None` if missing
- `to_string(style: Style = NORMAL, last: int = 0) -> str` - render
  - `last > 0` - take only the last N
  - `last < 0` - drop |last| from end
  - `last == 0` - all
- `size_occupied() -> int` - total characters (names + values)
- `is_null() -> bool` - true when empty

---

## CmdArgColParser

Static parser turning a raw command-line string into a `CmdArgCol`.

**File:** `cmd_arg_col_parser.py`

### Syntax
- Positional args separated by spaces: `cmd arg1 arg2`
- Named args: `--name value` (name may repeat)
- Quoted string: `"multi word"` - stays whole when after `--name`, splits by spaces when positional
- JSON blob: `{...}` - kept as one token
- Escapes: `\\` -> `\`, `\"` -> `"`; other `\x` preserved

### Methods (all static)
- `split_custom(input_: str, result: list[str]) -> None` - tokenizer stage; fills `result`
- `split_custom_append(result: list[str], current: str, is_noname: bool) -> tuple[str, bool]` - append helper; returns new `(current, is_noname)`
- `create_list(divided: list[str], args: CmdArgCol) -> None` - second stage; consumes tokens, appends to `args`

---

## CmdContextDataIface

Opaque client-side data attachable to a `CmdContextIface`. Base class; subclass and override.

**File:** `cmd_context_data_iface.py`

### Construction
- `CmdContextDataIface()` - default

### Methods
- `get_as_client_context() -> object | None` - downcast to `ClientContext` (defaults to `None`)
- `has_client_id() -> bool` - defaults to `True`
- `unique_id() -> int` - stable id per client; defaults to `-1`

---

## CmdContextIface

Reply channel + client data holder. Interface for how a command reaches back to its caller.

**File:** `cmd_context_iface.py`

### Construction
- `CmdContextIface()` - initializes `client_data_` to `None`

### Attributes
- `client_data_: CmdContextDataIface | None`

### Abstract methods (implement in subclass)
- `reply(cmd: str, data: bytes = b"") -> None`
- `reply_thread_safe(cmd: str, data: bytes = b"") -> None`

### Methods (default impls)
- `get_as_client_context() -> object | None` - `None` by default
- `force_disconnect() -> None` - no-op
- `log_cmd() -> bool` - `False` by default
- `unique_id() -> int` - delegates to `client_data_.unique_id()`; `-1` if unset
- `client_data() -> CmdContextDataIface | None` - getter
- `client_data_set(data: CmdContextDataIface) -> None` - one-time setter (asserts previously `None`)

---

## CmdContext

Concrete singleton implementation of `CmdContextIface` with no-op `reply`. Used as the default context when no client is attached.

**File:** `cmd_context.py`
**Inheritance:** `CmdContextIface`

### Construction
- `CmdContext.inst() -> CmdContext` - singleton accessor (creates on first call, returns same instance thereafter)
- `CMD_CONTEXT()` - module-level shortcut function (mirror of C++ macro `#define CMD_CONTEXT CmdContext::inst()`)

### Methods
- `reply(cmd: str, data: bytes = b"") -> None` - no-op

---

## Cmd

Single registered command: name + handler callback + flags. `CmdSys` (registry, coming later) will store instances of `Cmd` and dispatch to them by name.

**File:** `cmd.py`

### Type alias
- `CommandHandler = Callable[[CmdArgCol, Optional[bytearray], CmdContextIface], int]` - handler signature: parsed args, optional mutable data payload, context; returns int (typically 0 on success, error code otherwise)

### Construction
- `Cmd(name: str, handler: CommandHandler, exclude_exe_rec: bool = False, exclude_update: bool = False, category: str = "common")`
  - `exclude_exe_rec` - do not log this command in execute-record history
  - `exclude_update` - do not trigger update events after this command
  - `category` - grouping tag (`"common"`, `"debug"`, etc.)

### Attributes
- `name_: str`
- `handler_: CommandHandler`
- `exclude_exe_rec_: bool`
- `exclude_update_: bool`
- `category_: str`

### Methods
- `execute(args: CmdArgCol, data: Optional[bytearray], context: CmdContextIface) -> int` - invoke the handler
- `name() -> str` - getter
- `category() -> str` - getter
- `exclude_exe_rec() -> bool` - getter
- `exclude_update() -> bool` - getter

---

## CmdUtils

Static helpers for turning a script (multi-line text) into a list of commands and executing them via `CmdSys` (the singleton, ported later).

**File:** `cmd_utils.py`

### Methods (all static)
- `mine_commands_from_script(input_: str) -> list[str]` - parses a script (multi-line text) into command strings:
  - Normalizes line endings (`\r\n`, `\r` -> `\n`)
  - **Blank line separates commands.** Consecutive non-blank lines join with a single space (so one command can span multiple lines in the source).
  - Returns the list in source order.
- `execute_commands(commands: list[str]) -> int` - iterates and dispatches each non-empty command via `CMD_SYS().execute_thread_safe(cmd, "", -1, "SCRIPT")`. Returns number of executed commands.
  - Uses lazy import of `CmdSys` (not yet ported at time of this file's creation - resolves at call time).

---

## CmdExeFilter

Predicate that decides whether a command is allowed to execute. Attached to `CmdSys` (registry, coming later) as a chain of filters; each filter can veto a command by returning `False`.

**File:** `cmd_exe_filter.py`

### Abstract methods (implement in subclass)
- `pass_(args: CmdArgCol) -> bool` - `True` to allow, `False` to filter out

**Naming note:** C++ method is `pass(args)`. In Python `pass` is a keyword, so renamed to `pass_` (PEP8 trailing-underscore convention for keyword-clash).

---

## CmdExeGuard

Abstract base for objects that observe command execution (called after each command). `CmdSys` (registry, coming later) keeps a list of guards and iterates them in `Phase` order after each dispatched command.

**File:** `cmd_exe_guard.py`

### Enum: Phase (IntEnum)
Ordering / priority of the guard - guards fire in ascending phase value:
- `RECORD = 0` - runs early (typical use: append to execution history / log)
- `UPDATE = 100` - runs later (typical use: notify observers that state may have changed)

### Construction
- `CmdExeGuard(phase: Phase = Phase.RECORD)`

### Attributes
- `phase_: Phase`

### Methods
- `phase() -> Phase` - getter
- `command_executed() -> None` - **abstract**; called by CmdSys after each command executes

**Subclass example:** `LogGuard` (in KOUMES app) subclasses this to append each executed command to a log file.

---

## CmdSys

Command registry + dispatcher. Singleton. Holds all registered commands, all filters, all guards. Entry point for executing a command from a raw string.

**File:** `cmd_sys.py`

### Construction
- `CmdSys.inst() -> CmdSys` - singleton accessor
- `CMD_SYS()` - module-level shortcut (mirror of C++ `#define CMD_SYS CmdSys::inst()`)

### Attributes
- `cmds_: dict[str, Cmd]` - name -> Cmd
- `guards_: list[CmdExeGuard]` - fired after each executed command, in insertion/phase order
- `filters_: list[CmdExeFilter]` - checked before dispatch; any `pass_(args) == True` short-circuits execution (returns 0 without running the command)
- `executing_args_: CmdArgCol | None` - currently-executing command (re-entrancy guard)
- `running_index_: int` - monotonic counter incremented per command
- `main_thread_: bool` - enable/disable main-thread expectation
- `_deferred: deque` - queue of args for `execute_thread_safe`
- `_lock: threading.RLock` - protects `_deferred`

### Registration
- `add(name: str, handler: CommandHandler, exclude_exe_rec: bool = False, exclude_update: bool = False, category: str = "common") -> None` - register a command
- `reg_guard(guard: CmdExeGuard) -> None` - guards with `Phase.RECORD` are **prepended**, others appended (preserves fire order: record-guards first)
- `reg_filter(filter_: CmdExeFilter) -> None` - append filter

### Lookup
- `get(name: str) -> Cmd | None` - by name

### Execution
- `execute(args: str, source_name: str = "", source_index: int = -1, user: str = "UNKNOWN") -> int` - parse `args` via `CmdArgCol`, append `("USER", user)`, dispatch; **always returns 0** (result of internal dispatch is discarded, faithful to C++). Re-entrant calls are queued and drained after the outer call completes.
- `execute_thread_safe(args: str, source_name: str = "", source_index: int = -1, user: str = "internal") -> None` - push args onto deferred queue (thread-safe via `RLock`). The next `execute` call on the main thread drains the queue.
- `set_main_thread(value: bool) -> None` - toggle main-thread expectation flag

### Dispatch flow (internal `_execute`)
1. If `args.count() == 0` -> return -1
2. Increment `running_index_`
3. Iterate filters; if any `pass_(args)` returns True -> return 0 (command silently filtered)
4. Look up command by name (`args.get(0).value`)
5. If not found -> look up fallback `__not_implemented__`; if that also missing -> return -1
6. Execute the command's handler
7. Unless command has `exclude_update` -> fire all guards' `command_executed()`
8. Return handler result

**Threading model note:** Qt's `QMetaObject::invokeMethod(..., Qt::QueuedConnection)` for `execute_thread_safe` is replaced with a lock-protected `deque`. This works for single-threaded main-loop usage; when integrated with PyQt at the app layer, the app can bind a Qt event to drain the queue.

---

## StdoutCmdOutput

Guard that echoes each executed command to stdout. Singleton. Subclasses `CmdExeGuard(Phase.UPDATE)` so it fires after guards in `RECORD` phase.

**File:** `stdout_cmd_output.py`
**Inheritance:** `CmdExeGuard`

### Construction
- `StdoutCmdOutput.inst() -> StdoutCmdOutput` - singleton accessor. Constructor auto-registers with `CmdSys` (`CMD_SYS().reg_guard(self)`).

### Attributes
- `enabled_: bool` - defaults to `False`

### Methods
- `set_enabled(value: bool) -> None`
- `is_enabled() -> bool`
- `command_executed() -> None` - override; when enabled, writes `CMD_SYS().executing_args_.to_string() + "\\n"` to stdout and flushes

**Disabled by default.** When enabled and running under an environment that pipes stdout back to stdin (e.g. Qt Creator terminal), you get an echo loop. Enable only for pipe/bridge setups (e.g. STDIO_BRIDGE-like tools).

---

## StdinMonitor

Background thread that reads stdin line-by-line and dispatches each non-empty line as a command via `CmdSys`. Singleton. Auto-starts the reader thread when first created.

**File:** `stdin_monitor.py`
**Inheritance:** `threading.Thread` (daemon)

### Construction
- `StdinMonitor.init() -> StdinMonitor` - singleton accessor; creates the thread and starts it on first call

### Attributes
- `enabled_: bool` - defaults to `False`
- `_stop_event: threading.Event` - set to stop the reader loop

### Methods
- `set_enabled(value: bool) -> None`
- `is_enabled() -> bool`
- `request_interruption() -> None` - signals the reader loop to exit
- `process_line(line: str) -> None` - default: when enabled, skips lines starting with `qt.` (Qt debug spam), then calls `CMD_SYS().execute_thread_safe(line, "stdin", -1, "EXTERNAL_STD")`. Override to customize per-line handling.
- `run() -> None` - reader loop; blocks on `sys.stdin.readline()`, calls `process_line` for each non-empty trimmed line, exits on EOF or stop event.

**Threading model:** Uses `threading.Thread` (daemon so the app can exit without waiting for stdin EOF). Cross-platform via `sys.stdin.readline()` (no OS-conditional code needed unlike the C++ Win/POSIX split).

---

## CmdsCmdSys

Container class holding the built-in commands of CmdSys. All commands are registered with a single call: `CmdsCmdSys.register_cmds_()`.

**File:** `cmds_cmd_sys.py`

### Class method
- `register_cmds_() -> bool` - registers all built-in commands into `CMD_SYS()`. Returns `True`.

### Registered commands

| Command | Category | Description |
| --- | --- | --- |
| `voidcmd` | `cmd_sys` | No-op, returns 0. Used to reserve names / for testing. |
| `logcmd <msg>` | `cmd_sys` | No-op; **its execution IS the log entry** (guards see it). |
| `__not_implemented__` | `__cmd_sys_core__` | Fallback for unknown commands. Appends `ERROR: command not implemented: <name>` to args, returns 1. |
| `cmds_execute_script <path>` | `cmd_sys` | Reads file `<path>`, mines commands via `CmdUtils.mine_commands_from_script`, executes them. Appends `INFO: executed N command(s)`. |
| `cmd_help <name>` | `cmd_sys` | Loads help file `cmds_help/<name>.md` (falls back to `__not_documented__.md`). Parses leading `--flag` lines as named args, appends the rest as `HELP:`. |
| `cmds_categories` | `cmd_sys` | Appends each unique category as `CATEGORY:` (sorted). |
| `cmds_list [--type <cat>]...` | `cmd_sys` | Groups commands by category, appends `CATEGORY: <cat> : <cmd1> <cmd2> ...`. Optional `--type` filter (may repeat). |
| `execute_script <file>` | `cmd_sys` | Reads file line-by-line, skips empty / `#`-prefixed lines, dispatches each via `execute_thread_safe`. Appends `INIT_OK: <file>`. |

### `cmd_help` file format

Help files live in `cmds_help/` (sibling of `cmds_cmd_sys.py`). Any leading lines starting with `--` are stripped and returned as named args (flags). The remaining text is appended as the `HELP` field.

Example `cmds_help/echo.md`:
```
--positional message
Prints a message. Args:
  message  - text to print
```

---

## WsServerLite

Lightweight WebSocket server bound to `127.0.0.1:<port>`. Each incoming text message is split by newlines and each non-empty line is dispatched to `CMD_SYS` via `execute_thread_safe(line, "ws", -1, "EXTERNAL_WS")`. Also supports broadcasting text to all connected clients.

**File:** `ws_server_lite.py`
**Requires:** `websockets` Python package (`pip install websockets`). If missing, class loads but the server does nothing (no exception raised).

### Construction
- `WsServerLite(port: int = 12345)` - raw constructor (does NOT start the server)
- `WsServerLite.init(port: int = 12345) -> WsServerLite` - singleton accessor; starts the reader thread on first call

### Attributes
- `port_: int`
- `_clients: set` - currently connected websockets
- `_loop: asyncio.AbstractEventLoop | None` - the background asyncio loop
- `_server` - websockets server instance
- `_thread: threading.Thread | None`
- `_started: bool`

### Methods
- `broadcast(text: str) -> None` - schedule text broadcast to all clients (thread-safe via `asyncio.run_coroutine_threadsafe`)

### Threading model
Qt's `QThread` + `QWebSocketServer` replaced with Python threading + asyncio:
- A daemon thread runs its own asyncio event loop.
- `websockets.serve()` runs the WS accept loop inside that loop.
- Incoming messages: each line dispatched via `CMD_SYS().execute_thread_safe(...)` (goes onto the main-thread deferred queue).
- `broadcast()` from any thread: cross-thread submission via `asyncio.run_coroutine_threadsafe`.

---

## WsServerLiteGuard

Guard that broadcasts each executed command (as `CmdArgCol.to_string()`) to all connected WebSocket clients. Singleton.

**File:** `ws_server_lite_guard.py`
**Inheritance:** `CmdExeGuard`

### Construction
- `WsServerLiteGuard(server: WsServerLite)` - wraps an existing server; auto-registers with `CMD_SYS`
- `WsServerLiteGuard.inst() -> WsServerLiteGuard` - singleton accessor; creates the guard bound to `WsServerLite.init()` (default port 12345)

### Attributes
- `server_: WsServerLite`

### Methods
- `command_executed() -> None` - override; calls `server_.broadcast(CMD_SYS().executing_args_.to_string())`. Broadcast itself is thread-safe (see `WsServerLite.broadcast`), so no extra queued invocation needed on the Python side (unlike C++ which uses `QMetaObject::invokeMethod`).

**Use case:** external monitoring - any tool connected to the WS sees a live stream of executed commands, one per line. Useful for logging, debugging, remote observation.

---

## CmdBridge

Unified facade for "external command in / output broadcast". Single `init()` call spins up the transport chosen for this build.

**File:** `cmd_bridge.py`

### Class method
- `init() -> None` - starts `WsServerLiteGuard.inst()` which in turn starts `WsServerLite.init()` on 127.0.0.1:12345.

### Transport selection

The C++ version has two backends selected by build:
- **Native** (any non-WASM): WsServerLite on `ws://127.0.0.1:12345` (same as Python port)
- **WASM/Emscripten**: `EM_JS` JS bridge — `craseExec(cmd)` -> `CMD_SYS`, plus a floating DOM REPL panel and `window.craseLog` mirror

**The Python port has no WASM branch** (Python doesn't compile to WASM in the same way). `init()` reduces to the native path. When koumes eventually needs an in-browser variant (e.g. Pyodide), a separate bridge class can be added; this facade would then dispatch by runtime detection.

---

## LogGuard

Guard that appends every executed command line (with a timestamp) to a text file.

**File:** `log_guard.py`
**Inheritance:** `CmdExeGuard`

### Construction
- `LogGuard(path: str = "config/cmdlog.txt")` - creates parent directory if needed, opens the file in append+utf-8 mode, and auto-registers with `CMD_SYS`

### Attributes
- `file_: TextIO | None` - open file handle, or `None` if opening failed

### Methods
- `command_executed() -> None` - override; writes `HH:MM:SS <args_string>\\n` to the file and flushes. Silent no-op if file couldn't be opened.
- `__del__()` - closes the file if still open

### Log line format

```
HH:MM:SS <cmd> [<arg1> ...] [--<name> <value> ...] --USER <who>
```

Example:
```
14:23:07 marker hello --USER EXTERNAL_STD
14:23:12 cmds_list --USER UNKNOWN
```

The user field is auto-appended by `CmdSys.execute()` to the parsed args, so it shows up in every log line - useful for post-hoc filtering by source (which UI / connector produced the command).

---
