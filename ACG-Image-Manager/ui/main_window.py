"""
Main window — root QMainWindow that assembles all panels using QSplitter.

Key changes in this version
----------------------------
* Folder click → FolderFilterThread (background, non-blocking).
  The thread uses get_images_in_folder() which:
    - queries the DB with a properly-normalised LIKE prefix (fixes the
      backslash / forward-slash mismatch on Windows), AND
    - falls back to a direct filesystem scan so images that haven't been
      indexed yet still appear immediately.
* A loading indicator in the status bar is shown while any filter thread
  is running.
* Window size + splitter proportions are persisted via QSettings.
* All three QSplitter panels are non-collapsible with a minimum width so
  the center grid can never be hidden.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QStatusBar, QProgressBar, QLabel,
    QFileDialog, QMessageBox
)

from app.database import get_all_image_paths
from app.image_scanner import ScannerThread, FolderFilterThread
from app.library_exporter import export_library_zip
from app.library_importer import import_library_zip
from ui.folder_tree import FolderTree
from ui.image_grid import ImageGrid
from ui.metadata_panel import MetadataPanel
from ui.search_bar import SearchBar
from ui.image_viewer import ImageViewer

_SETTINGS_ORG  = "AnimeImageManager"
_SETTINGS_APP  = "MainWindow"
_KEY_GEOMETRY  = "geometry"
_KEY_SPLITTER  = "splitter_sizes"
_KEY_THEME     = "theme"
_THEMES_DIR    = Path(__file__).resolve().parent.parent / "themes"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anime Image Manager")
        self.setMinimumSize(900, 600)

        self._current_folder: str = ""
        self._current_query:  str = ""

        # Keep a reference to any running background threads so we can
        # cancel a stale one before starting a new filter request.
        self._scanner: ScannerThread = None
        self._filter_thread: FolderFilterThread = None

        self._build_ui()
        self._build_menu()
        self._load_saved_theme()
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

        # Splitter — all three panels are non-collapsible so the center
        # grid can never be hidden behind the right metadata panel.
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(5)
        root_layout.addWidget(self._splitter, stretch=1)

        self._folder_tree = FolderTree()
        self._folder_tree.setMinimumWidth(120)
        self._folder_tree.folder_selected.connect(self._on_folder_selected)
        self._splitter.addWidget(self._folder_tree)
        self._splitter.setCollapsible(0, False)

        self._image_grid = ImageGrid()
        self._image_grid.setMinimumWidth(300)
        self._image_grid.selection_changed.connect(self._on_selection_changed)
        self._image_grid.open_viewer_requested.connect(self._open_viewer)
        self._splitter.addWidget(self._image_grid)
        self._splitter.setCollapsible(1, False)

        self._metadata_panel = MetadataPanel()
        self._metadata_panel.setMinimumWidth(200)
        self._metadata_panel.metadata_changed.connect(self._on_metadata_changed)
        self._splitter.addWidget(self._metadata_panel)
        self._splitter.setCollapsible(2, False)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)   # center panel stretches
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([210, 900, 290])  # default; overridden by settings

        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._status_label = QLabel("Ready")
        status_bar.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)          # indeterminate spinner
        self._progress.setFixedWidth(150)
        self._progress.setVisible(False)
        status_bar.addPermanentWidget(self._progress)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        action_export = file_menu.addAction("Export Library")
        action_export.triggered.connect(self._export_library)

        action_import = file_menu.addAction("Import Library")
        action_import.triggered.connect(self._import_library)

        view_menu = self.menuBar().addMenu("View")
        theme_menu = view_menu.addMenu("Themes")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        self._theme_actions = {}
        for label in (
            "Light", "Dark", "Gray", "Blue",
            "Purple", "Green", "Orange", "High Contrast"
        ):
            action = theme_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, theme_name=label.lower().replace(" ", "-"): self._apply_theme(theme_name)
            )
            theme_group.addAction(action)
            self._theme_actions[label.lower().replace(" ", "-")] = action

    # ------------------------------------------------------------------
    # Window geometry persistence
    # ------------------------------------------------------------------

    def _settings(self) -> QSettings:
        return QSettings(_SETTINGS_ORG, _SETTINGS_APP)

    def _restore_geometry(self) -> None:
        s = self._settings()
        geo = s.value(_KEY_GEOMETRY)
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1400, 850)

        sizes = s.value(_KEY_SPLITTER)
        if sizes:
            try:
                int_sizes = [int(v) for v in sizes]
                if len(int_sizes) == 3 and all(v > 0 for v in int_sizes):
                    self._splitter.setSizes(int_sizes)
            except (TypeError, ValueError):
                pass

    def _save_geometry(self) -> None:
        s = self._settings()
        s.setValue(_KEY_GEOMETRY, self.saveGeometry())
        s.setValue(_KEY_SPLITTER, self._splitter.sizes())

    def closeEvent(self, event) -> None:
        self._save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Dark stylesheet
    # ------------------------------------------------------------------

    def _load_saved_theme(self) -> None:
        theme_name = str(self._settings().value(_KEY_THEME, "light")).lower()
        self._apply_theme(theme_name)

    def _apply_theme(self, theme_name: str) -> None:
        """
        Apply a QSS theme from ./themes and persist the preference.
        """
        theme_file = _THEMES_DIR / f"{theme_name}.qss"
        if not theme_file.exists():
            theme_name = "light"
            theme_file = _THEMES_DIR / "light.qss"

        qss = theme_file.read_text(encoding="utf-8")
        self.setStyleSheet(qss)
        self._settings().setValue(_KEY_THEME, theme_name)

        action = self._theme_actions.get(theme_name)
        if action:
            action.setChecked(True)

    # ------------------------------------------------------------------
    # DB / filesystem sync (ScannerThread)
    # ------------------------------------------------------------------

    def _start_initial_scan(self) -> None:
        QTimer.singleShot(200, self._start_scan)

    def _start_scan(self) -> None:
        if self._scanner and self._scanner.isRunning():
            return
        self._show_loading("Scanning images folder...")
        self._scanner = ScannerThread(self)
        self._scanner.progress.connect(self._status_label.setText)
        self._scanner.images_added.connect(lambda _: None)   # grid refresh on finished
        self._scanner.images_removed.connect(lambda _: None)
        self._scanner.finished_scan.connect(self._on_scan_finished)
        self._scanner.start()

    def _on_scan_finished(self, added: int, removed: int) -> None:
        self._hide_loading()
        self._status_label.setText(
            f"Scan complete — {added} added, {removed} removed"
        )
        # Re-apply current folder + query so the grid shows correct results
        self._trigger_filter()
        self._folder_tree.refresh()
        self._search_bar.refresh_picker_data()

    # ------------------------------------------------------------------
    # Non-blocking grid filter (FolderFilterThread)
    # ------------------------------------------------------------------

    def _trigger_filter(self) -> None:
        """
        Start a FolderFilterThread for the current folder + query state.

        Any previously running filter thread is abandoned (its result will
        be ignored because we reconnect the signal on each new thread).
        """
        # Disconnect the old thread's signal so stale results are ignored
        if self._filter_thread is not None and self._filter_thread.isRunning():
            try:
                self._filter_thread.results_ready.disconnect()
            except RuntimeError:
                pass   # already disconnected

        folder = self._current_folder
        query  = self._current_query

        # Fast synchronous path: no folder and no query — just dump the DB
        if not folder and not query:
            paths = sorted(get_all_image_paths())
            self._image_grid.load_images(paths)
            self._status_label.setText(f"{len(paths)} images loaded")
            return

        # Slow path: run in a background thread
        self._show_loading(
            f"Filtering {'folder' if folder else 'results'}…"
        )

        thread = FolderFilterThread(
            folder_path=folder,
            search_query=query,
            parent=self,
        )
        # Connect BEFORE starting so we don't miss an instant result
        thread.results_ready.connect(self._on_filter_results)
        thread.finished.connect(self._hide_loading)

        self._filter_thread = thread
        thread.start()

    def _on_filter_results(self, paths: list[str]) -> None:
        """Receives sorted image paths from FolderFilterThread."""
        self._image_grid.load_images(paths)
        label = self._current_folder or "search results"
        self._status_label.setText(
            f"{len(paths)} image(s) in {label!r}"
            if self._current_folder
            else f"{len(paths)} image(s) matching query"
        )

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_folder_selected(self, folder_path: str) -> None:
        """
        Called when the user clicks a folder in the left tree.

        folder_path is an absolute path emitted by QFileSystemModel, using
        forward slashes on Qt 6 (even on Windows).  An empty string means
        "All Images" — no folder filter.

        The actual image resolution runs in FolderFilterThread so the UI
        never freezes, even for folders with thousands of images.
        """
        self._current_folder = folder_path
        self._trigger_filter()

    def _on_search(self, query: str) -> None:
        self._current_query = query
        self._trigger_filter()

    def _on_selection_changed(self, paths: list[str]) -> None:
        self._metadata_panel.load_selection(paths)

    def _on_metadata_changed(self) -> None:
        selected = self._image_grid.get_selected_paths()
        if selected:
            self._metadata_panel.load_selection(selected)
        self._search_bar.refresh_picker_data()

    def _open_viewer(self, paths: list[str], index: int) -> None:
        viewer = ImageViewer(paths, start_index=index, parent=self)
        viewer.exec()

    # ------------------------------------------------------------------
    # Loading indicator helpers
    # ------------------------------------------------------------------

    def _show_loading(self, message: str = "Loading…") -> None:
        self._status_label.setText(message)
        self._progress.setVisible(True)

    def _hide_loading(self) -> None:
        self._progress.setVisible(False)

    # ------------------------------------------------------------------
    # Import / Export actions
    # ------------------------------------------------------------------

    def _export_library(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export Library",
            "library-export.zip",
            "ZIP files (*.zip)",
        )
        if not target:
            return

        try:
            export_library_zip(Path(target))
            self.statusBar().showMessage(f"Library exported to {target}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def _import_library(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Import Library",
            "",
            "ZIP files (*.zip)",
        )
        if not source:
            return

        answer = QMessageBox.warning(
            self,
            "Confirm import",
            (
                "Import will overwrite current data/database.db.\n"
                "Metadata will be replaced from metadata.json in the ZIP.\n"
                "Images and cache files are not changed.\n\n"
                "Continue?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self._wait_for_background_tasks()
            import_library_zip(Path(source))
            self._start_scan()
            self._folder_tree.refresh()
            self._trigger_filter()
            QMessageBox.information(self, "Import complete", "Library import finished.")
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def _wait_for_background_tasks(self) -> None:
        """
        Wait for scanner/filter threads to finish so they can't hold DB locks
        during import replacement.
        """
        if self._scanner and self._scanner.isRunning():
            self._scanner.wait(5000)
        if self._filter_thread and self._filter_thread.isRunning():
            self._filter_thread.wait(5000)
