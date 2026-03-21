from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QAction, QActionGroup
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
from ui.i18n import i18n

_SETTINGS_ORG = "ACG-Image-Manager"
_SETTINGS_APP = "MainWindow"
_KEY_GEOMETRY = "geometry"
_KEY_SPLITTER = "splitter_sizes"
_KEY_THEME = "theme"
_KEY_LANGUAGE = "language"


class MainWindow(QMainWindow):
    def __init__(self, resource_path_func):
        super().__init__()
        self._resource_path = resource_path_func
        self.setMinimumSize(900, 600)

        self._current_folder: str = ""
        self._current_query: str = ""
        self._scanner: ScannerThread = None
        self._filter_thread: FolderFilterThread = None

        i18n.load_from_settings(self._settings(), _KEY_LANGUAGE, "en")

        self._build_ui()
        self._build_menu()
        self._retranslate_ui()
        self._load_saved_theme()
        self._restore_geometry()
        self._start_initial_scan()

    def _themes_dir(self) -> Path:
        return Path(self._resource_path("themes"))

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
        self._image_grid.open_image_requested.connect(self._open_image)
        self._splitter.addWidget(self._image_grid)
        self._splitter.setCollapsible(1, False)

        self._metadata_panel = MetadataPanel()
        self._metadata_panel.setMinimumWidth(200)
        self._metadata_panel.metadata_changed.connect(self._on_metadata_changed)
        self._splitter.addWidget(self._metadata_panel)
        self._splitter.setCollapsible(2, False)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([210, 900, 290])

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._status_label = QLabel(i18n.tr("ready"))
        status_bar.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(150)
        self._progress.setVisible(False)
        status_bar.addPermanentWidget(self._progress)

    def _build_menu(self) -> None:
        self._file_menu = self.menuBar().addMenu("")
        self._action_export = self._file_menu.addAction("")
        self._action_export.triggered.connect(self._export_library)
        self._action_import = self._file_menu.addAction("")
        self._action_import.triggered.connect(self._import_library)

        self._view_menu = self.menuBar().addMenu("")
        self._theme_menu = self._view_menu.addMenu("")

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self._theme_actions: dict[str, QAction] = {}
        for theme_name in ("light", "dark", "gray", "blue", "purple", "green", "orange", "high-contrast"):
            action = self._theme_menu.addAction(theme_name.title())
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, t=theme_name: self._apply_theme(t))
            theme_group.addAction(action)
            self._theme_actions[theme_name] = action

        self._settings_menu = self.menuBar().addMenu("")
        self._language_menu = self._settings_menu.addMenu("")
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)

        self._lang_actions = {
            "en": self._language_menu.addAction(""),
            "zh": self._language_menu.addAction(""),
        }
        for code, action in self._lang_actions.items():
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, c=code: self._set_language(c))
            lang_group.addAction(action)

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(i18n.tr("app_title"))
        self._file_menu.setTitle(i18n.tr("file"))
        self._action_export.setText(i18n.tr("export_library"))
        self._action_import.setText(i18n.tr("import_library"))
        self._view_menu.setTitle(i18n.tr("view"))
        self._theme_menu.setTitle(i18n.tr("themes"))
        self._settings_menu.setTitle(i18n.tr("settings"))
        self._language_menu.setTitle(i18n.tr("language"))
        self._lang_actions["en"].setText(i18n.tr("english"))
        self._lang_actions["zh"].setText(i18n.tr("chinese"))
        self._search_bar.retranslate_ui()
        self._folder_tree.retranslate_ui()
        self._image_grid.retranslate_ui()
        self._metadata_panel.retranslate_ui()

    def _set_language(self, code: str) -> None:
        i18n.set_language(code)
        self._settings().setValue(_KEY_LANGUAGE, code)
        action = self._lang_actions.get(code)
        if action:
            action.setChecked(True)
        self._retranslate_ui()

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

        lang = str(s.value(_KEY_LANGUAGE, "en"))
        if lang in self._lang_actions:
            self._lang_actions[lang].setChecked(True)

    def _save_geometry(self) -> None:
        s = self._settings()
        s.setValue(_KEY_GEOMETRY, self.saveGeometry())
        s.setValue(_KEY_SPLITTER, self._splitter.sizes())

    def closeEvent(self, event) -> None:
        self._save_geometry()
        super().closeEvent(event)

    def _load_saved_theme(self) -> None:
        self._apply_theme(str(self._settings().value(_KEY_THEME, "light")).lower())

    def _apply_theme(self, theme_name: str) -> None:
        theme_file = self._themes_dir() / f"{theme_name}.qss"
        if not theme_file.exists():
            theme_name = "light"
            theme_file = self._themes_dir() / "light.qss"

        self.setStyleSheet(theme_file.read_text(encoding="utf-8"))
        self._settings().setValue(_KEY_THEME, theme_name)
        if theme_name in self._theme_actions:
            self._theme_actions[theme_name].setChecked(True)

    def _start_initial_scan(self) -> None:
        QTimer.singleShot(200, self._start_scan)

    def _start_scan(self) -> None:
        if self._scanner and self._scanner.isRunning():
            return
        self._show_loading(i18n.tr("scan_images"))
        self._scanner = ScannerThread(self)
        self._scanner.progress.connect(self._status_label.setText)
        self._scanner.images_added.connect(lambda _: None)
        self._scanner.images_removed.connect(lambda _: None)
        self._scanner.finished_scan.connect(self._on_scan_finished)
        self._scanner.start()

    def _on_scan_finished(self, added: int, removed: int) -> None:
        self._hide_loading()
        self._status_label.setText(i18n.tr("scan_complete", added=added, removed=removed))
        self._trigger_filter()
        self._folder_tree.refresh()
        self._search_bar.refresh_picker_data()

    def _trigger_filter(self) -> None:
        if self._filter_thread is not None and self._filter_thread.isRunning():
            try:
                self._filter_thread.results_ready.disconnect()
            except RuntimeError:
                pass

        folder = self._current_folder
        query = self._current_query

        if not folder and not query:
            paths = sorted(get_all_image_paths())
            self._image_grid.load_images(paths)
            self._status_label.setText(i18n.tr("images_loaded", count=len(paths)))
            return

        self._show_loading(i18n.tr("filtering_folder" if folder else "filtering_results"))

        thread = FolderFilterThread(folder_path=folder, search_query=query, parent=self)
        thread.results_ready.connect(self._on_filter_results)
        thread.finished.connect(self._hide_loading)

        self._filter_thread = thread
        thread.start()

    def _on_filter_results(self, paths: list[str]) -> None:
        self._image_grid.load_images(paths)
        if self._current_folder:
            self._status_label.setText(i18n.tr("in_folder", count=len(paths), label=self._current_folder))
        else:
            self._status_label.setText(i18n.tr("matching_query", count=len(paths)))

    def _on_folder_selected(self, folder_path: str) -> None:
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

    def _open_image(self, path: str) -> None:
        os.startfile(path)

    def _show_loading(self, message: str | None = None) -> None:
        self._status_label.setText(message or i18n.tr("loading"))
        self._progress.setVisible(True)

    def _hide_loading(self) -> None:
        self._progress.setVisible(False)

    def _export_library(self) -> None:
        target, _ = QFileDialog.getSaveFileName(self, i18n.tr("export_library"), "library-export.zip", "ZIP files (*.zip)")
        if not target:
            return

        try:
            export_library_zip(Path(target))
            self.statusBar().showMessage(f"{i18n.tr('export_library')}: {target}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, i18n.tr("export_failed"), str(exc))

    def _import_library(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, i18n.tr("import_library"), "", "ZIP files (*.zip)")
        if not source:
            return

        answer = QMessageBox.warning(
            self,
            i18n.tr("confirm_import"),
            i18n.tr("import_confirm_text"),
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
            QMessageBox.information(self, i18n.tr("import_complete"), i18n.tr("import_complete_msg"))
        except Exception as exc:
            QMessageBox.critical(self, i18n.tr("import_failed"), str(exc))

    def _wait_for_background_tasks(self) -> None:
        if self._scanner and self._scanner.isRunning():
            self._scanner.wait(5000)
        if self._filter_thread and self._filter_thread.isRunning():
            self._filter_thread.wait(5000)
