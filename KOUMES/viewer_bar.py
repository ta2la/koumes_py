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
"""viewer_bar - dynamic per-file viewer switch buttons.

Python port of the `rebuildViewerBar` function from APPS/AI_T2LS/Main.cpp.

Populates a panel's `viewer_bar` QWidget with one button per registered
viewer available for the file. Order:
  1. In-file + walk-up config viewers (via read_all_viewers)
  2. `txt` (universal fallback)
  3. `native` (browser direct)

Click switches active button + calls load_fn(target_html, file_path).
First button = active (or the one matching active_name if provided).
"""

import os
from typing import Callable, List

from PyQt6.QtWidgets import QButtonGroup, QPushButton, QWidget

from cmd_sys import CMD_SYS

from . import viewer_resolver as vr


LoadFn = Callable[[str, str], None]


def rebuild_viewer_bar(
    viewer_bar: QWidget,
    file_path: str,
    root: str,
    load_fn: LoadFn,
    active_name: str = "",
    panel_key: str = "",
) -> List[str]:
    lay = viewer_bar.layout()
    if lay is not None:
        while lay.count() > 0:
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    names = list(vr.read_all_viewers(file_path, root))
    if "txt" not in names:
        names.append("txt")
    names.append("native")

    file_dir = os.path.dirname(file_path)
    items: List[tuple] = []
    for n in names:
        if n == "native":
            target = file_path
        else:
            target = vr.find_viewer_html(file_dir, root, n)
            if not target:
                continue
        items.append((n, target))

    if not items:
        return []

    active_idx = 0
    if active_name:
        for i, (n, _) in enumerate(items):
            if n == active_name:
                active_idx = i
                break

    grp = QButtonGroup(viewer_bar)
    grp.setExclusive(True)
    for i, (name, target) in enumerate(items):
        btn = QPushButton(name, viewer_bar)
        btn.setCheckable(True)
        btn.setChecked(i == active_idx)
        grp.addButton(btn)
        viewer_bar.layout().addWidget(btn)
        if panel_key:
            btn.setToolTip(f"viewer_switch {panel_key} {name}")

        def make_click(bname=name, tgt=target, key=panel_key, fpath=file_path, fn=load_fn):
            def on_click(_checked=False):
                if key:
                    CMD_SYS().execute_thread_safe(
                        f'viewer_switch {key} {bname}', "ui", -1, "VIEWERBAR"
                    )
                else:
                    fn(tgt, fpath)
            return on_click

        btn.clicked.connect(make_click())

    load_fn(items[active_idx][1], file_path)

    return [n for n, _ in items]
