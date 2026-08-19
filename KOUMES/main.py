#
# Copyright (C) 2026 Petr Talla. [petr.talla@gmail.com]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#           http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""KOUMES main entry.

Usage:
    koumes                       # opens cwd
    koumes <root>                # bind sandbox to <root>
    koumes <root> <start_dir>    # bind sandbox + open <start_dir>
    koumes --headless            # no GUI (stdin + WS only)
"""

import argparse
import os
import sys
from pathlib import Path

from cmd_sys import CmdBridge, CmdsCmdSys, LogGuard, StdinMonitor, WsServerLite

from .app_paths import AppPaths


DEFAULT_WS_PORT = 54325
DEFAULT_DIRVIEW = "CODE_ROOT/APPS/AI_T2LS/dirview"


def parse_args(argv: list) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="koumes", description="koumes desktop app")
    p.add_argument("root", nargs="?", default=str(Path.cwd()),
                   help="sandbox root directory (default: cwd)")
    p.add_argument("start_dir", nargs="?", default=None,
                   help="initial directory to open (default: root)")
    p.add_argument("--headless", action="store_true",
                   help="run without GUI (stdin + WS only)")
    p.add_argument("--port", type=int, default=None,
                   help=f"WebSocket port (default: settings.t2l ws_port, else {DEFAULT_WS_PORT})")
    p.add_argument("--dirview", default=DEFAULT_DIRVIEW,
                   help=f"Fallback dir for viewer HTMLs (default: {DEFAULT_DIRVIEW})")
    return p.parse_args(argv)


def _load_port_from_settings() -> int:
    """Read ws_port from <dir_config>/settings.t2l. Returns 0 if missing/invalid."""
    try:
        p = os.path.join(AppPaths.inst().dir_config(), "settings.t2l")
        if not os.path.isfile(p):
            return 0
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                k, _, v = line.partition(":")
                if k.strip() == "ws_port":
                    try:
                        return int(v.strip())
                    except ValueError:
                        return 0
    except Exception:
        pass
    return 0


def bootstrap(args: argparse.Namespace) -> None:
    """One-time init that works with or without PyQt6."""
    AppPaths.inst()

    CmdsCmdSys.register_cmds_()

    log_path = os.path.join(AppPaths.inst().dir_config(), "cmdlog.txt")
    LogGuard(log_path)

    port = args.port or _load_port_from_settings() or DEFAULT_WS_PORT
    args.port = port
    WsServerLite.init(port=port)
    CmdBridge.init()

    stdin = StdinMonitor.init()
    stdin.set_enabled(True)


def register_gui_cmds() -> None:
    """Register chroma / www command tables. GUI-only (needs PyQt6 at import)."""
    from .cmds_chroma import CmdsChroma
    from .cmds_www import CmdsWww
    CmdsChroma.register_cmds()
    CmdsWww.register_cmds()


def run_gui(args: argparse.Namespace) -> int:
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("PyQt6 not installed. Install with: pip install PyQt6", file=sys.stderr)
        print("Falling back to headless mode.", file=sys.stderr)
        return run_headless(args)

    register_gui_cmds()

    from . import viewer_resolver as vr
    from .app_paths import AppPaths as _AP
    koumes_dirview = os.path.join(_AP.inst().dir_exe(), "dirview")
    vr.set_extra_fallback_dirs([koumes_dirview, args.dirview])

    from .main_window import MainWindow
    from .toolbar import wire_toolbar
    from .window_persist import WindowPersist

    app = QApplication(sys.argv[:1])
    win = MainWindow(args.root, args.start_dir)
    wire_toolbar(win)
    WindowPersist.install(win, app)
    win.show()
    return app.exec()


def run_headless(args: argparse.Namespace) -> int:
    print(f"koumes headless. root={args.root} start_dir={args.start_dir or args.root}")
    print(f"WS on ws://127.0.0.1:{args.port}. Ctrl+C to exit.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    return 0


def main(argv: list = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    bootstrap(args)
    if args.headless:
        return run_headless(args)
    return run_gui(args)


if __name__ == "__main__":
    sys.exit(main())
