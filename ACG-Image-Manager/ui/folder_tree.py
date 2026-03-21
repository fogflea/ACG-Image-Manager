from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Signal, QDir, QModelIndex, Qt
from PySide6.QtWidgets import (
    QFileSystemModel, QTreeView, QWidget, QVBoxLayout, QLabel, QPushButton, QMenu
)

from app.i18n import i18n

IMAGES_ROOT = str(Path(__file__).parent.parent / "images")


class FolderTree(QWidget):
    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        i18n.language_changed.connect(self._retranslate_ui)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel()
        self._header.setStyleSheet("font-weight: bold; padding: 4px 6px;")
        layout.addWidget(self._header)

        self._btn_all = QPushButton()
        self._btn_all.setFlat(False)
        self._btn_all.setStyleSheet("text-align: left; padding: 5px 10px; border-radius: 0;")
        self._btn_all.clicked.connect(lambda: self.folder_selected.emit(""))
        layout.addWidget(self._btn_all)

        self._model = QFileSystemModel()
        self._model.setRootPath(IMAGES_ROOT)
        self._model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(IMAGES_ROOT))
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setUniformRowHeights(True)
        self._tree.clicked.connect(self._on_clicked)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        for col in range(1, self._model.columnCount()):
            self._tree.hideColumn(col)

        layout.addWidget(self._tree)
        self._retranslate_ui()

    def _retranslate_ui(self, _lang: str | None = None) -> None:
        self._header.setText(i18n.tr("folder.header"))
        self._btn_all.setText(i18n.tr("folder.all"))

    def _on_clicked(self, index: QModelIndex) -> None:
        self.folder_selected.emit(self._model.filePath(index))

    def _on_context_menu(self, pos) -> None:
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return
        folder_path = self._model.filePath(index)
        menu = QMenu(self)
        action_open = menu.addAction(i18n.tr("folder.open_explorer"))
        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen == action_open:
            self._open_in_file_manager(folder_path)

    def _open_in_file_manager(self, path: str) -> None:
        if sys.platform.startswith("win"):
            subprocess.run(["explorer", "/select,", str(Path(path))], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(Path(path))], check=False)
        else:
            subprocess.run(["xdg-open", str(Path(path))], check=False)

    def select_root(self) -> None:
        self.folder_selected.emit("")

    def refresh(self) -> None:
        self._model.setRootPath("")
        self._model.setRootPath(IMAGES_ROOT)
        self._tree.setRootIndex(self._model.index(IMAGES_ROOT))
