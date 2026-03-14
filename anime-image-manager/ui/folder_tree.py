"""
Folder tree panel — Windows Explorer-style directory tree rooted at ./images.
Selecting a folder filters the image grid to that folder.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex
from PySide6.QtGui import QFileSystemModel
from PySide6.QtWidgets import QTreeView, QWidget, QVBoxLayout, QLabel

IMAGES_ROOT = str(Path(__file__).parent.parent / "images")


class FolderTree(QWidget):
    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QLabel("Folders")
        header.setStyleSheet("font-weight: bold; padding: 4px 6px;")
        layout.addWidget(header)

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

        for col in range(1, self._model.columnCount()):
            self._tree.hideColumn(col)

        self._tree.clicked.connect(self._on_clicked)

        layout.addWidget(self._tree)

    def _on_clicked(self, index: QModelIndex) -> None:
        folder_path = self._model.filePath(index)
        self.folder_selected.emit(folder_path)

    def select_root(self) -> None:
        self.folder_selected.emit(IMAGES_ROOT)

    def refresh(self) -> None:
        self._model.setRootPath("")
        self._model.setRootPath(IMAGES_ROOT)
        self._tree.setRootIndex(self._model.index(IMAGES_ROOT))
