"""
Full-screen image viewer dialog.
Supports zoom, fit-to-window, previous/next navigation, and keyboard shortcuts.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QTransform, QKeyEvent, QWheelEvent, QAction
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QToolBar, QSizePolicy
)


class ImageViewer(QDialog):
    def __init__(self, image_paths: list[str], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.current_index = start_index
        self._zoom_factor = 1.0
        self._fit_mode = True

        self.setWindowTitle("Image Viewer")
        self.setMinimumSize(800, 600)
        self.resize(1100, 750)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

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

        act_fit = QAction("Fit Window", self)
        act_fit.setCheckable(True)
        act_fit.setChecked(True)
        act_fit.triggered.connect(self._toggle_fit)
        self._act_fit = act_fit
        toolbar.addAction(act_fit)

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

        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setWidgetResizable(False)
        self._scroll.setStyleSheet("background: #1a1a1a;")

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setStyleSheet("background: #1a1a1a;")
        self._scroll.setWidget(self._img_label)

        layout.addWidget(self._scroll)

    def _load_current(self) -> None:
        if not self.image_paths:
            return
        path = self.image_paths[self.current_index]
        self._pixmap = QPixmap(path)
        self._zoom_factor = 1.0
        self._fit_mode = self._act_fit.isChecked()

        name = Path(path).name
        idx_str = f"{self.current_index + 1} / {len(self.image_paths)}"
        self._title_label.setText(f"{name}  —  {idx_str}")

        self._apply_display()

    def _apply_display(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            self._img_label.setText("Cannot load image")
            return

        if self._fit_mode:
            available = self._scroll.size()
            scaled = self._pixmap.scaled(
                available, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            w = int(self._pixmap.width() * self._zoom_factor)
            h = int(self._pixmap.height() * self._zoom_factor)
            scaled = self._pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self._img_label.setPixmap(scaled)
        self._img_label.resize(scaled.size())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_display()

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

    def _toggle_fit(self, checked: bool) -> None:
        self._fit_mode = checked
        self._apply_display()

    def _zoom_in(self) -> None:
        self._act_fit.setChecked(False)
        self._fit_mode = False
        self._zoom_factor = min(self._zoom_factor * 1.25, 8.0)
        self._apply_display()

    def _zoom_out(self) -> None:
        self._act_fit.setChecked(False)
        self._fit_mode = False
        self._zoom_factor = max(self._zoom_factor / 1.25, 0.05)
        self._apply_display()

    def _zoom_reset(self) -> None:
        self._act_fit.setChecked(False)
        self._fit_mode = False
        self._zoom_factor = 1.0
        self._apply_display()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom_in()
        elif delta < 0:
            self._zoom_out()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Left:
            self.show_prev()
        elif event.key() == Qt.Key_Right:
            self.show_next()
        else:
            super().keyPressEvent(event)
