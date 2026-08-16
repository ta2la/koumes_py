# cmd_sys - port plan

Python port of `base2/cmd_sys` plus the classes we need from `base2/base2` and `base2/mccp_com`.

## Group 1 - Arguments (base2/base2)

- [x] **1. CmdArg** - `cmd_arg.py`
- [x] **2. CmdArgCol** - `cmd_arg_col.py`
- [x] **3. CmdArgCol_parser** - `cmd_arg_col_parser.py`

## Group 2 - Interfaces

- [x] **4. CmdContextDataIface** - `cmd_context_data_iface.py`
- [x] **5. CmdContextIface** - `cmd_context_iface.py`
- [x] **6. CmdContext** - `cmd_context.py`

## Group 3 - Command wrapper

- [x] **7. Cmd** - `cmd.py`
- [x] **8. CmdUtils** - `cmd_utils.py`

## Group 4 - Filter / Guard

- [x] **9. CmdExeFilter** - `cmd_exe_filter.py`
- [x] **10. CmdExeGuard** - `cmd_exe_guard.py`

## Group 5 - Singleton core

- [x] **11. CmdSys** - `cmd_sys.py`

## Group 6 - I/O

- [x] **12. StdoutCmdOutput** - `stdout_cmd_output.py`
- [x] **13. StdinMonitor** - `stdin_monitor.py`

## Group 7 - Built-in commands

- [x] **14. Cmds_cmd_sys** - `cmds_cmd_sys.py` (as `CmdsCmdSys`)

## Group 8 (later) - mccp_com (WebSocket)

- [x] **15. WsServerLite** - `ws_server_lite.py` (requires `pip install websockets`)
- [x] **16. WsServerLiteGuard** - `ws_server_lite_guard.py`
- [x] **17. CmdBridge** - `cmd_bridge.py`

## Group 9 (later) - LogGuard

- [x] **18. LogGuard** - `log_guard.py`
