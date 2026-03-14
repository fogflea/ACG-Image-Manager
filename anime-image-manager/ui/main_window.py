"""
Main window — root QMainWindow that assembles all panels using QSplitter.

Fix #5: Window size is saved on close and restored on next launch via QSettings.
Fix #6: QSplitter panels are set non-collapsible and have a minimum size so the
        center thumbnail grid can never be hidden behind the metadata panel.
        The splitter stretch factor on the center panel ensures it always
        expands to fill available space.
"""

from PySide6.QtCore import Qt, QTimer, QSettings
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

# QSettings keys
_SETTINGS_ORG = "AnimeImageManager"
_SETTINGS_APP = "MainWindow"
_KEY_GEOMETRY = "geometry"
_KEY_SPLITTER  = "splitter_sizes"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anime Image Manager")
        self.setMinimumSize(900, 600)

        self._current_folder: str = ""
        self._current_query: str = ""
        self._scanner: ScannerThread = None

        self._build_ui()
        self._apply_dark_style()

        # Fix #5: restore previous window size (falls back to 1400×850)
        self._restore_geometry()

        self._start_initial_scan()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

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

        # Fix #6: use a QSplitter so all three panels resize correctly.
        # setCollapsible(False) prevents any panel from shrinking to zero,
        # which was the root cause of thumbnails disappearing.
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(5)
        root_layout.addWidget(self._splitter, stretch=1)

        self._folder_tree = FolderTree()
        self._folder_tree.setMinimumWidth(120)
        self._folder_tree.folder_selected.connect(self._on_folder_selected)
        self._splitter.addWidget(self._folder_tree)
        self._splitter.setCollapsible(0, False)   # left panel never collapses

        self._image_grid = ImageGrid()
        self._image_grid.setMinimumWidth(300)      # always visible
        self._image_grid.selection_changed.connect(self._on_selection_changed)
        self._image_grid.open_viewer_requested.connect(self._open_viewer)
        self._splitter.addWidget(self._image_grid)
        self._splitter.setCollapsible(1, False)   # center panel never collapses

        self._metadata_panel = MetadataPanel()
        self._metadata_panel.setMinimumWidth(200)
        self._metadata_panel.metadata_changed.connect(self._on_metadata_changed)
        self._splitter.addWidget(self._metadata_panel)
        self._splitter.setCollapsible(2, False)   # right panel never collapses

        # Fix #6: only the center panel (index 1) stretches when the window grows
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)

        # Default proportions — overridden by saved settings if present
        self._splitter.setSizes([210, 900, 290])

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._status_label = QLabel("Ready")
        status_bar.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(150)
        self._progress.setVisible(False)
        status_bar.addPermanentWidget(self._progress)

    # ------------------------------------------------------------------
    # Window geometry persistence  (Fix #5)
    # ------------------------------------------------------------------

    def _settings(self) -> QSettings:
        return QSettings(_SETTINGS_ORG, _SETTINGS_APP)

    def _restore_geometry(self) -> None:
        settings = self._settings()
        geometry = settings.value(_KEY_GEOMETRY)
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # Default size when no settings exist yet
            self.resize(1400, 850)

        splitter_sizes = settings.value(_KEY_SPLITTER)
        if splitter_sizes:
            # QSettings stores lists as strings on some platforms; convert
            try:
                sizes = [int(s) for s in splitter_sizes]
                if len(sizes) == 3 and all(s > 0 for s in sizes):
                    self._splitter.setSizes(sizes)
            except (TypeError, ValueError):
                pass

    def _save_geometry(self) -> None:
        settings = self._settings()
        settings.setValue(_KEY_GEOMETRY, self.saveGeometry())
        settings.setValue(_KEY_SPLITTER, self._splitter.sizes())

    def closeEvent(self, event) -> None:
        """Fix #5: persist window size + splitter layout before closing."""
        self._save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Dark stylesheet
    # ------------------------------------------------------------------

    def _apply_dark_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QSplitter::handle {
                background: #313244;
            }
            QSplitter::handle:hover {
                background: #585b70;
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

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

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

    def _on_images_added(self, _paths: list[str]) -> None:
        self._refresh_grid()

    def _on_images_removed(self, _paths: list[str]) -> None:
        self._refresh_grid()

    def _on_scan_finished(self, added: int, removed: int) -> None:
        self._progress.setVisible(False)
        self._status_label.setText(f"Scan complete — {added} added, {removed} removed")
        self._refresh_grid()
        self._folder_tree.refresh()

    # ------------------------------------------------------------------
    # Grid refresh (Fix #1 support — folder filter uses LIKE prefix in DB)
    # ------------------------------------------------------------------

    def _refresh_grid(self) -> None:
        query = self._current_query
        folder = self._current_folder   # empty string = no folder filter

        if query:
            # search_engine passes folder_prefix to the DB for combined filter
            paths = execute_search(query, folder_prefix=folder)
        elif folder:
            # Fix #1: folder_prefix is a LIKE 'path%' match → includes subfolders
            paths = search_images(folder_prefix=folder)
        else:
            paths = get_all_image_paths()

        self._image_grid.set_images(sorted(paths))

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_folder_selected(self, folder_path: str) -> None:
        """
        Fix #1: receives the absolute folder path from FolderTree.
        An empty string means "All Images" (no folder filter).
        """
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
