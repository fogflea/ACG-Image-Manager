"""
Full-screen image viewer using QGraphicsView/QGraphicsScene.

- Wheel zoom (cursor-centered)
- Drag-to-pan (ScrollHandDrag)
- No image reload on zoom (transform-only)
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeyEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QToolBar,
    QSizePolicy, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setRenderHints(self.renderHints())

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(factor, factor)
        elif event.angleDelta().y() < 0:
            self.scale(1 / factor, 1 / factor)
        event.accept()


class ImageViewer(QDialog):
    def __init__(self, image_paths: list[str], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.current_index = start_index
        self._scale_factor = 1.0

        self.setWindowTitle("Image Viewer")
        self.setMinimumSize(800, 600)
        self.resize(1100, 750)

        self._scene = QGraphicsScene(self)
        self._pix_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pix_item)
        self._pixmap_cache: dict[str, QPixmap] = {}

        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar()
        toolbar.setMovable(False)

        act_prev = QAction("◀  Prev", self)
        act_prev.setShortcut("Left")
        act_prev.triggered.connect(self.show_prev)
        toolbar.addAction(act_prev)

        act_next = QAction("Next  ▶", self)
        act_next.setShortcut("Right")
        act_next.triggered.connect(self.show_next)
        toolbar.addAction(act_next)

        toolbar.addSeparator()

        act_zoom_in = QAction("Zoom In (+)", self)
        act_zoom_in.setShortcut("+")
        act_zoom_in.triggered.connect(self._zoom_in)
        toolbar.addAction(act_zoom_in)

        act_zoom_out = QAction("Zoom Out (−)", self)
        act_zoom_out.setShortcut("-")
        act_zoom_out.triggered.connect(self._zoom_out)
        toolbar.addAction(act_zoom_out)

        act_zoom_reset = QAction("100%", self)
        act_zoom_reset.setShortcut("0")
        act_zoom_reset.triggered.connect(self._zoom_reset)
        toolbar.addAction(act_zoom_reset)

        toolbar.addSeparator()

        act_close = QAction("✕ Close", self)
        act_close.setShortcut("Escape")
        act_close.triggered.connect(self.close)
        toolbar.addAction(act_close)

        self._title_label = QLabel()
        self._title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._title_label.setAlignment(Qt.AlignCenter)
        toolbar.addWidget(self._title_label)

        layout.addWidget(toolbar)

        self._view = ZoomableGraphicsView(self)
        self._view.setScene(self._scene)
        self._view.setStyleSheet("background: #111; border: none;")
        layout.addWidget(self._view)

    def _get_pixmap(self, path: str) -> QPixmap:
        if path not in self._pixmap_cache:
            self._pixmap_cache[path] = QPixmap(path)
        return self._pixmap_cache[path]

    def _load_current(self) -> None:
        if not self.image_paths:
            return

        path = self.image_paths[self.current_index]
        pixmap = self._get_pixmap(path)

        if pixmap.isNull():
            self._title_label.setText("Cannot load image")
            self._pix_item.setPixmap(QPixmap())
            return

        self._pix_item.setPixmap(pixmap)
        self._scene.setSceneRect(self._pix_item.boundingRect())

        self._zoom_reset()

        name = Path(path).name
        idx_str = f"{self.current_index + 1} / {len(self.image_paths)}"
        self._title_label.setText(f"{name}  —  {idx_str}")

    def show_prev(self) -> None:
        if not self.image_paths:
            return
        self.current_index = (self.current_index - 1) % len(self.image_paths)
        self._load_current()

    def show_next(self) -> None:
        if not self.image_paths:
            return
        self.current_index = (self.current_index + 1) % len(self.image_paths)
        self._load_current()

    def _zoom_in(self) -> None:
        self._scale_factor *= 1.15
        self._view.scale(1.15, 1.15)

    def _zoom_out(self) -> None:
        self._scale_factor /= 1.15
        self._view.scale(1 / 1.15, 1 / 1.15)

    def _zoom_reset(self) -> None:
        self._view.resetTransform()
        self._scale_factor = 1.0
        self._view.centerOn(self._pix_item)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Left:
            self.show_prev()
        elif event.key() == Qt.Key_Right:
            self.show_next()
        else:
            super().keyPressEvent(event)
