import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QRunnable, QThreadPool, QObject, QPoint, QTimer
from PySide6.QtGui import QPixmap, QIcon, QColor
from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout,
    QHBoxLayout, QSlider, QLabel, QAbstractItemView, QMenu
)

from app.thumbnail_cache import get_thumbnail
from ui.i18n import i18n


class ThumbnailLoader(QObject):
    loaded = Signal(str, QPixmap)


class ThumbnailTask(QRunnable):
    def __init__(self, file_path: str, size: int, signals: ThumbnailLoader):
        super().__init__()
        self.file_path = file_path
        self.size = size
        self.signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        cached = get_thumbnail(self.file_path, self.size)
        if cached:
            px = QPixmap(str(cached))
        else:
            px = QPixmap(self.size, self.size)
            px.fill(QColor(60, 60, 60))
        self.signals.loaded.emit(self.file_path, px)


class ImageGrid(QWidget):
    selection_changed = Signal(list)
    open_image_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_paths: list[str] = []
        self._thumb_size = 128
        self._item_map: dict[str, QListWidgetItem] = {}
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)
        self._pending: set[str] = set()
        self._build_ui()

        self._lazy_timer = QTimer(self)
        self._lazy_timer.setInterval(100)
        self._lazy_timer.timeout.connect(self._load_visible_thumbnails)
        self._lazy_timer.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        controls = QHBoxLayout()
        controls.setContentsMargins(4, 4, 4, 4)

        self._count_label = QLabel("0 images")
        controls.addWidget(self._count_label)
        controls.addStretch()

        self._size_text = QLabel(i18n.tr("size"))
        controls.addWidget(self._size_text)
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(2)
        self._slider.setValue(1)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.setFixedWidth(100)
        self._slider.valueChanged.connect(self._on_size_changed)
        controls.addWidget(self._slider)

        self._size_label = QLabel("128px")
        self._size_label.setFixedWidth(40)
        controls.addWidget(self._size_label)

        layout.addLayout(controls)

        self._list = QListWidget()
        self._list.setViewMode(QListWidget.IconMode)
        self._list.setResizeMode(QListWidget.Adjust)
        self._list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._list.setSpacing(4)
        self._list.setUniformItemSizes(True)
        self._list.setDragEnabled(False)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        self._update_icon_size()

    def retranslate_ui(self) -> None:
        self._size_text.setText(i18n.tr("size"))

    def _on_size_changed(self, value: int) -> None:
        sizes = [64, 128, 256]
        self._thumb_size = sizes[value]
        self._size_label.setText(f"{self._thumb_size}px")
        self._update_icon_size()
        self._reload_thumbnails()

    def _update_icon_size(self) -> None:
        s = self._thumb_size
        self._list.setIconSize(QSize(s, s))
        self._list.setGridSize(QSize(s + 10, s + 28))

    def set_images(self, paths: list[str]) -> None:
        self._all_paths = paths
        self._item_map.clear()
        self._pending.clear()
        self._list.clear()

        placeholder = QPixmap(self._thumb_size, self._thumb_size)
        placeholder.fill(QColor(40, 40, 40))
        placeholder_icon = QIcon(placeholder)

        for path in paths:
            item = QListWidgetItem(placeholder_icon, Path(path).name)
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            item.setSizeHint(QSize(self._thumb_size + 10, self._thumb_size + 28))
            self._list.addItem(item)
            self._item_map[path] = item

        self._count_label.setText(f"{len(paths)} image(s)")

    def load_images(self, paths: list[str]) -> None:
        self.set_images(paths)

    def _load_visible_thumbnails(self) -> None:
        vp_rect = self._list.viewport().rect()
        for i in range(self._list.count()):
            item = self._list.item(i)
            rect = self._list.visualItemRect(item)
            if not vp_rect.intersects(rect):
                continue
            path = item.data(Qt.UserRole)
            if path in self._pending:
                continue
            if item.icon().cacheKey() != QIcon().cacheKey() and item.data(Qt.UserRole + 1) == self._thumb_size:
                continue
            self._pending.add(path)
            signals = ThumbnailLoader()
            signals.loaded.connect(self._on_thumbnail_loaded)
            self._pool.start(ThumbnailTask(path, self._thumb_size, signals))

    def _on_thumbnail_loaded(self, path: str, pixmap: QPixmap) -> None:
        self._pending.discard(path)
        item = self._item_map.get(path)
        if item is None:
            return
        item.setIcon(QIcon(pixmap))
        item.setData(Qt.UserRole + 1, self._thumb_size)

    def _reload_thumbnails(self) -> None:
        self._pending.clear()
        placeholder = QPixmap(self._thumb_size, self._thumb_size)
        placeholder.fill(QColor(40, 40, 40))
        placeholder_icon = QIcon(placeholder)
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setIcon(placeholder_icon)
            item.setData(Qt.UserRole + 1, None)
            item.setSizeHint(QSize(self._thumb_size + 10, self._thumb_size + 28))
        self._update_icon_size()

    def get_selected_paths(self) -> list[str]:
        return [item.data(Qt.UserRole) for item in self._list.selectedItems()]

    def _on_selection_changed(self) -> None:
        self.selection_changed.emit(self.get_selected_paths())

    def _on_double_click(self, item: QListWidgetItem) -> None:
        self.open_image_requested.emit(item.data(Qt.UserRole))

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        path = item.data(Qt.UserRole)

        menu = QMenu(self)
        act_open = menu.addAction(i18n.tr("open_image"))
        act_open.triggered.connect(lambda: self.open_image_requested.emit(path))

        act_explore = menu.addAction(i18n.tr("show_in_explorer"))
        act_explore.triggered.connect(lambda: self._show_in_explorer(path))

        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _show_in_explorer(self, path: str) -> None:
        try:
            subprocess.run(["explorer", "/select,", os.path.normpath(path)], check=False)
        except FileNotFoundError:
            subprocess.run(["xdg-open", str(Path(path).parent)], check=False)
