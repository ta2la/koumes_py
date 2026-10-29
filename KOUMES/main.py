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
DEFAULT_DIRVIEW = str(Path(__file__).resolve().parents[2])   # ../.. = koren baliku (.t2l/ viewery)


def parse_args(argv: list) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="koumes", description="koumes desktop app")
    p.add_argument("root", nargs="?", default=str(Path.cwd()),
                   help="sandbox root directory (default: cwd)")
    p.add_argument("start_dir", nargs="?", default=None,
                   help="initial directory to open (default: root)")
    p.add_argument("--headless", action="store_true",
                   help="run without GUI (stdin + WS only)")
    p.add_argument("--port", type=int, default=None,
                   help=f"WebSocket port (default: config.t2l ws_port, else {DEFAULT_WS_PORT})")
    p.add_argument("--dirview", default=DEFAULT_DIRVIEW,
                   help=f"Fallback dir for viewer HTMLs (default: {DEFAULT_DIRVIEW})")
    return p.parse_args(argv)


def _load_port_from_config() -> int:
    """Read `ws_port:` from <dir_config>/config.t2l. Returns 0 if missing/invalid.

    The port has to be known before the WS server starts, which is long before
    the config is executed as a script - so it is read here, not run.
    """
    try:
        return int(AppPaths.inst().settings().get("ws_port", ""))
    except (TypeError, ValueError):
        return 0


#: commands kept in `other_config/cmdlog.txt` when the deployment says nothing
DEFAULT_LOG_LINES = 300


def _load_log_lines_from_config() -> int:
    """`log_lines:` from this deployment's config.t2l. 0 there means no cap."""
    raw = AppPaths.inst().settings().get("log_lines", "")
    if raw == "":
        return DEFAULT_LOG_LINES
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_LOG_LINES


def bootstrap(args: argparse.Namespace) -> None:
    """One-time init that works with or without PyQt6."""
    AppPaths.inst()

    CmdsCmdSys.register_cmds_()

    log_path = os.path.join(AppPaths.inst().dir_config(), "cmdlog.txt")
    LogGuard(log_path, max_lines=_load_log_lines_from_config())

    port = args.port or _load_port_from_config() or DEFAULT_WS_PORT
    args.port = port
    WsServerLite.init(port=port)
    CmdBridge.init()

    stdin = StdinMonitor.init()
    stdin.set_enabled(True)


def register_gui_cmds() -> None:
    """Register chroma / www command tables. GUI-only (needs PyQt6 at import)."""
    from .cmds_chroma import CmdsChroma
    from .cmds_paste import CmdsPaste
    from .cmds_www import CmdsWww
    CmdsChroma.register_cmds()
    CmdsWww.register_cmds()
    CmdsPaste.register_cmds()


def _quit_on_signals(app) -> None:
    """Turn SIGTERM / SIGINT into a normal quit.

    The session is written in `aboutToQuit`, and a killed process never gets
    there - so a `pkill` restart (which is how the app is normally cycled during
    development) would silently throw the state away. The idle timer is the
    usual trick to let Python see signals at all while Qt owns the loop.
    """
    import signal
    from PyQt6.QtCore import QTimer

    def bye(_sig, _frame):
        app.quit()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, bye)
        except (ValueError, OSError):
            pass

    waker = QTimer(app)
    waker.start(200)
    waker.timeout.connect(lambda: None)


def _prefer_xcb() -> None:
    """Ask for XWayland on a Wayland session, so window placement works.

    A Wayland client is not allowed to position its own window - the compositor
    decides, which in practice means "wherever the mouse is". `setGeometry`
    silently keeps the size and drops the coordinates, so a saved position can
    never be restored and the app opens on a different monitor every time.
    Under XWayland the same call lands exactly where it was asked to.

    Set KOUMES_QPA to override, e.g. KOUMES_QPA=wayland to take the native
    session back and give up on remembering where the window was.
    """
    override = os.environ.get("KOUMES_QPA")
    if override:
        os.environ["QT_QPA_PLATFORM"] = override
        return
    if os.environ.get("QT_QPA_PLATFORM"):
        return
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def run_gui(args: argparse.Namespace) -> int:
    _prefer_xcb()
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("PyQt6 not installed. Install with: pip install PyQt6", file=sys.stderr)
        print("Falling back to headless mode.", file=sys.stderr)
        return run_headless(args)

    register_gui_cmds()

    from . import viewer_resolver as vr
    from .app_paths import AppPaths as _AP
    koumes_dirview = os.path.join(os.path.dirname(_AP.inst().dir_exe()), "KOUMES_PY_APPS")   # HTML appky koumesu
    vr.set_extra_fallback_dirs([koumes_dirview, args.dirview])
    from .qt_viewer import registry as _qt_registry
    vr.set_qt_viewers(_qt_registry().keys())

    from .main_window import MainWindow
    from .toolbar import wire_toolbar
    from .window_persist import WindowPersist

    app = QApplication(sys.argv[:1])
    from .theme import apply_tooltip_style
    apply_tooltip_style()
    _quit_on_signals(app)
    win = MainWindow(args.root, args.start_dir)
    wire_toolbar(win)
    WindowPersist.install(win, app)
    win.show()
    # After show: `set_window` fights the show itself if it lands earlier, and
    # the panel restore wants a window that already has its startup content.
    WindowPersist.restore()
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
