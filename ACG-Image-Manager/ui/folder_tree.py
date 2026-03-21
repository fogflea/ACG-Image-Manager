from pathlib import Path
import subprocess

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex, QPoint
from PySide6.QtWidgets import (
    QFileSystemModel, QTreeView, QWidget, QVBoxLayout, QLabel, QPushButton, QMenu
)

from ui.i18n import i18n

IMAGES_ROOT = str(Path(__file__).parent.parent / "images")


class FolderTree(QWidget):
    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("")
        self._header.setStyleSheet("font-weight: bold; padding: 4px 6px;")
        layout.addWidget(self._header)

        self._btn_all = QPushButton("")
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
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        for col in range(1, self._model.columnCount()):
            self._tree.hideColumn(col)

        self._tree.clicked.connect(self._on_clicked)
        layout.addWidget(self._tree)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._header.setText(i18n.tr("folders"))
        self._btn_all.setText(i18n.tr("all_images"))

    def _on_clicked(self, index: QModelIndex) -> None:
        self.folder_selected.emit(self._model.filePath(index))

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return
        path = self._model.filePath(index)
        menu = QMenu(self)
        act = menu.addAction(i18n.tr("open_in_explorer"))
        act.triggered.connect(lambda: subprocess.run(["explorer", path], check=False))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def select_root(self) -> None:
        self.folder_selected.emit("")

    def refresh(self) -> None:
        self._model.setRootPath("")
        self._model.setRootPath(IMAGES_ROOT)
        self._tree.setRootIndex(self._model.index(IMAGES_ROOT))
