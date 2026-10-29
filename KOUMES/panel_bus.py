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
"""PanelBus - pub/sub channel between HTML panels in chroma.

Python port of the C++ predecessor's PanelBus.h.

Register as "bus" in every WebChannel (left/dir/detail/rightmost panel).
When one panel calls a notify_* method, every panel receives the corresponding
signal. Each panel decides what to do based on its role.
"""

from typing import Optional

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot


class PanelBus(QObject):
    dirChanged = pyqtSignal(str)
    fileSelected = pyqtSignal(str)
    fileSelectedRightmost = pyqtSignal(str)
    fileSelectedForBrowse = pyqtSignal(str, int)
    sandboxChanged = pyqtSignal(str)
    lineChanged = pyqtSignal(int)
    lineChangedRightmost = pyqtSignal(int)
    wwwUrlRequested = pyqtSignal(QUrl, str)
    selectionChanged = pyqtSignal(str, str, int)
    panelShow = pyqtSignal(str, str, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    @pyqtSlot(str)
    def notifyDirChange(self, path: str) -> None:
        self.dirChanged.emit(path)

    @pyqtSlot(str)
    def notifyFileSelected(self, path: str) -> None:
        self.fileSelected.emit(path)

    @pyqtSlot(str)
    def notifyFileSelectedRightmost(self, path: str) -> None:
        self.fileSelectedRightmost.emit(path)

    @pyqtSlot(str, int)
    def notifyFileSelectedForBrowse(self, path: str, line: int) -> None:
        self.fileSelectedForBrowse.emit(path, line)

    @pyqtSlot(str)
    def notifySandboxChanged(self, new_root: str) -> None:
        self.sandboxChanged.emit(new_root)

    @pyqtSlot(int)
    def notifyLineChanged(self, line: int) -> None:
        self.lineChanged.emit(line)

    @pyqtSlot(int)
    def notifyLineChangedRightmost(self, line: int) -> None:
        self.lineChangedRightmost.emit(line)

    @pyqtSlot(QUrl, str)
    def notifyWwwUrlRequested(self, url: QUrl, source: str) -> None:
        self.wwwUrlRequested.emit(url, source)

    @pyqtSlot(str, str, int)
    def notifySelectionChanged(self, panel: str, file: str, line: int) -> None:
        self.selectionChanged.emit(panel, file, line)

    @pyqtSlot(str, str, str)
    def notifyPanelShow(self, panel: str, file: str, viewer: str = "") -> None:
        self.panelShow.emit(panel, file, viewer)

    def notify_dir_change(self, path: str) -> None:
        self.notifyDirChange(path)

    def notify_file_selected(self, path: str) -> None:
        self.notifyFileSelected(path)

    def notify_file_selected_rightmost(self, path: str) -> None:
        self.notifyFileSelectedRightmost(path)

    def notify_file_selected_for_browse(self, path: str, line: int) -> None:
        self.notifyFileSelectedForBrowse(path, line)

    def notify_sandbox_changed(self, new_root: str) -> None:
        self.notifySandboxChanged(new_root)

    def notify_line_changed(self, line: int) -> None:
        self.notifyLineChanged(line)

    def notify_line_changed_rightmost(self, line: int) -> None:
        self.notifyLineChangedRightmost(line)

    def notify_www_url_requested(self, url: QUrl, source: str) -> None:
        self.notifyWwwUrlRequested(url, source)

    def notify_selection_changed(self, panel: str, file: str, line: int) -> None:
        self.notifySelectionChanged(panel, file, line)

    def notify_panel_show(self, panel: str, file: str, viewer: str = "") -> None:
        self.notifyPanelShow(panel, file, viewer)
