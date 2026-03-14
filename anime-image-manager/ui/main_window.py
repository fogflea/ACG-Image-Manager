"""
Main window — root QMainWindow that assembles all panels using QSplitter.
Coordinates communication between folder tree, image grid, metadata panel,
search bar, and the background scanner thread.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QStatusBar, QProgressBar, QLabel
)

from app.database import search_images, get_all_image_paths
from app.image_scanner import ScannerThread
from app.search_engine import execute_search
from ui.folder_tree import FolderTree
from ui.image_grid import ImageGrid
from ui.metadata_panel import MetadataPanel
from ui.search_bar import SearchBar
from ui.image_viewer import ImageViewer


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anime Image Manager")
        self.resize(1400, 850)
        self.setMinimumSize(900, 600)

        self._current_folder: str = ""
        self._current_query: str = ""
        self._scanner: ScannerThread = None

        self._build_ui()
        self._apply_dark_style()
        self._start_initial_scan()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._search_bar = SearchBar()
        self._search_bar.search_triggered.connect(self._on_search)
        self._search_bar.refresh_triggered.connect(self._start_scan)
        root_layout.addWidget(self._search_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        root_layout.addWidget(splitter, stretch=1)

        self._folder_tree = FolderTree()
        self._folder_tree.folder_selected.connect(self._on_folder_selected)
        splitter.addWidget(self._folder_tree)

        self._image_grid = ImageGrid()
        self._image_grid.selection_changed.connect(self._on_selection_changed)
        self._image_grid.open_viewer_requested.connect(self._open_viewer)
        splitter.addWidget(self._image_grid)

        self._metadata_panel = MetadataPanel()
        self._metadata_panel.metadata_changed.connect(self._on_metadata_changed)
        splitter.addWidget(self._metadata_panel)

        splitter.setSizes([200, 900, 280])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._status_label = QLabel("Ready")
        status_bar.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(150)
        self._progress.setVisible(False)
        status_bar.addPermanentWidget(self._progress)

    def _apply_dark_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QSplitter::handle {
                background: #313244;
            }
            QLineEdit, QTextEdit {
                background: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px;
                color: #cdd6f4;
            }
            QListWidget {
                background: #181825;
                border: 1px solid #313244;
                color: #cdd6f4;
            }
            QListWidget::item:selected {
                background: #45475a;
            }
            QPushButton {
                background: #45475a;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                color: #cdd6f4;
            }
            QPushButton:hover {
                background: #585b70;
            }
            QPushButton:pressed {
                background: #313244;
            }
            QTreeView {
                background: #181825;
                border: none;
                color: #cdd6f4;
            }
            QTreeView::item:hover {
                background: #313244;
            }
            QTreeView::item:selected {
                background: #45475a;
            }
            QTabWidget::pane {
                border: 1px solid #313244;
            }
            QTabBar::tab {
                background: #313244;
                color: #cdd6f4;
                padding: 6px 14px;
            }
            QTabBar::tab:selected {
                background: #45475a;
            }
            QScrollBar:vertical {
                background: #1e1e2e;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                border-radius: 5px;
            }
            QStatusBar {
                background: #181825;
                color: #6c7086;
            }
            QLabel {
                color: #cdd6f4;
            }
            QToolBar {
                background: #181825;
                border-bottom: 1px solid #313244;
                spacing: 4px;
            }
            QToolButton {
                color: #cdd6f4;
                padding: 4px 8px;
            }
            QToolButton:hover {
                background: #313244;
            }
            QMenu {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
            }
            QMenu::item:selected {
                background: #45475a;
            }
        """)

    def _start_initial_scan(self) -> None:
        QTimer.singleShot(200, self._start_scan)

    def _start_scan(self) -> None:
        if self._scanner and self._scanner.isRunning():
            return

        self._progress.setVisible(True)
        self._status_label.setText("Scanning images folder...")

        self._scanner = ScannerThread(self)
        self._scanner.progress.connect(self._status_label.setText)
        self._scanner.images_added.connect(self._on_images_added)
        self._scanner.images_removed.connect(self._on_images_removed)
        self._scanner.finished_scan.connect(self._on_scan_finished)
        self._scanner.start()

    def _on_images_added(self, paths: list[str]) -> None:
        self._refresh_grid()

    def _on_images_removed(self, paths: list[str]) -> None:
        self._refresh_grid()

    def _on_scan_finished(self, added: int, removed: int) -> None:
        self._progress.setVisible(False)
        msg = f"Scan complete — {added} added, {removed} removed"
        self._status_label.setText(msg)
        self._refresh_grid()
        self._folder_tree.refresh()

    def _refresh_grid(self) -> None:
        query = self._current_query
        folder = self._current_folder

        if query:
            paths = execute_search(query, folder_prefix=folder)
        elif folder:
            paths = search_images(folder_prefix=folder)
        else:
            paths = get_all_image_paths()

        self._image_grid.set_images(sorted(paths))

    def _on_folder_selected(self, folder_path: str) -> None:
        self._current_folder = folder_path
        self._refresh_grid()

    def _on_search(self, query: str) -> None:
        self._current_query = query
        self._refresh_grid()

    def _on_selection_changed(self, paths: list[str]) -> None:
        self._metadata_panel.load_selection(paths)

    def _on_metadata_changed(self) -> None:
        selected = self._image_grid.get_selected_paths()
        if selected:
            self._metadata_panel.load_selection(selected)

    def _open_viewer(self, paths: list[str], index: int) -> None:
        viewer = ImageViewer(paths, start_index=index, parent=self)
        viewer.exec()
