"""
Folder tree panel — Windows Explorer-style directory tree rooted at ./images.

Fix #1: Clicking a folder now correctly filters the grid to that folder AND
all nested subfolders, because the signal emits the full folder path and the
database query uses a LIKE 'path%' prefix match.

Added: "All Images" button at the top emits an empty path to clear the folder
filter and show every image in the database.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex
from PySide6.QtWidgets import (
    QFileSystemModel, QTreeView, QWidget, QVBoxLayout, QLabel, QPushButton
)

IMAGES_ROOT = str(Path(__file__).parent.parent / "images")


class FolderTree(QWidget):
    # Emits the absolute folder path that was clicked.
    # Emits an empty string when "All Images" is selected (no filter).
    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Folders")
        header.setStyleSheet("font-weight: bold; padding: 4px 6px;")
        layout.addWidget(header)

        # "All Images" button — clicking it clears the folder filter
        self._btn_all = QPushButton("🖼  All Images")
        self._btn_all.setFlat(False)
        self._btn_all.setStyleSheet(
            "text-align: left; padding: 5px 10px; border-radius: 0;"
        )
        # Emit empty string → main_window treats this as "no folder filter"
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

        # Hide size / type / date columns — show folder names only
        for col in range(1, self._model.columnCount()):
            self._tree.hideColumn(col)

        # Fix #1: single click selects folder, signal carries full path.
        # The database search_images() uses LIKE 'path%' so subfolders are
        # automatically included in the result set.
        self._tree.clicked.connect(self._on_clicked)

        layout.addWidget(self._tree)

    def _on_clicked(self, index: QModelIndex) -> None:
        folder_path = self._model.filePath(index)
        self.folder_selected.emit(folder_path)

    def select_root(self) -> None:
        """Programmatically select the root (all images)."""
        self.folder_selected.emit("")

    def refresh(self) -> None:
        """Re-root the model so newly created subdirectories appear."""
        self._model.setRootPath("")
        self._model.setRootPath(IMAGES_ROOT)
        self._tree.setRootIndex(self._model.index(IMAGES_ROOT))
