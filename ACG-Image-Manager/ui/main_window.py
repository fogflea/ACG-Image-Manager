from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QStatusBar, QProgressBar, QLabel,
    QFileDialog, QMessageBox
)

from app.database import get_all_image_paths
from app.i18n import i18n
from app.image_scanner import ScannerThread, FolderFilterThread
from app.library_exporter import export_library_zip
from app.library_importer import import_library_zip
from ui.folder_tree import FolderTree
from ui.image_grid import ImageGrid
from ui.metadata_panel import MetadataPanel
from ui.search_bar import SearchBar

_SETTINGS_ORG = "AnimeImageManager"
_SETTINGS_APP = "MainWindow"
_KEY_GEOMETRY = "geometry"
_KEY_SPLITTER = "splitter_sizes"
_KEY_THEME = "theme"
_KEY_LANGUAGE = "language"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_folder: str = ""
        self._current_query: str = ""
        self._scanner: ScannerThread | None = None
        self._filter_thread: FolderFilterThread | None = None
        self._theme_actions: dict[str, object] = {}

        i18n.language_changed.connect(self._retranslate_ui)

        self._build_ui()
        self._build_menu()
        self._load_saved_language()
        self._load_saved_theme()
        self._restore_geometry()
        self._start_initial_scan()

    def _themes_dir(self) -> Path:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "themes"
        return Path(__file__).resolve().parent.parent / "themes"

    def _settings(self) -> QSettings:
        return QSettings(_SETTINGS_ORG, _SETTINGS_APP)

    def _build_ui(self) -> None:
        self.setMinimumSize(900, 600)

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
        self._image_grid.open_viewer_requested.connect(self._open_external)
        self._splitter.addWidget(self._image_grid)
        self._splitter.setCollapsible(1, False)

        self._metadata_panel = MetadataPanel()
        self._metadata_panel.setMinimumWidth(220)
        self._metadata_panel.metadata_changed.connect(self._on_metadata_changed)
        self._splitter.addWidget(self._metadata_panel)
        self._splitter.setCollapsible(2, False)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([210, 900, 290])

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self._status_label = QLabel()
        status_bar.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(150)
        self._progress.setVisible(False)
        status_bar.addPermanentWidget(self._progress)

        self._retranslate_ui()

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

        self._theme_actions = {}
        for label in (
            "Light", "Dark", "Gray", "Blue",
            "Purple", "Green", "Orange", "High Contrast"
        ):
            action = self._theme_menu.addAction(label)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, theme_name=label.lower().replace(" ", "-"): self._apply_theme(theme_name)
            )
            theme_group.addAction(action)
            self._theme_actions[label.lower().replace(" ", "-")] = action

        self._settings_menu = self.menuBar().addMenu("")
        self._language_menu = self._settings_menu.addMenu("")
        self._act_lang_en = self._language_menu.addAction("English")
        self._act_lang_zh = self._language_menu.addAction("中文")
        self._act_lang_en.setCheckable(True)
        self._act_lang_zh.setCheckable(True)
        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        self._lang_group.addAction(self._act_lang_en)
        self._lang_group.addAction(self._act_lang_zh)
        self._act_lang_en.triggered.connect(lambda: self._set_language("en"))
        self._act_lang_zh.triggered.connect(lambda: self._set_language("zh_CN"))

    def _retranslate_ui(self, _lang: str | None = None) -> None:
        self.setWindowTitle(i18n.tr("app.title"))
        self._file_menu.setTitle(i18n.tr("menu.file"))
        self._action_export.setText(i18n.tr("menu.export"))
        self._action_import.setText(i18n.tr("menu.import"))
        self._view_menu.setTitle(i18n.tr("menu.view"))
        self._theme_menu.setTitle(i18n.tr("menu.themes"))
        self._settings_menu.setTitle(i18n.tr("menu.settings"))
        self._language_menu.setTitle(i18n.tr("menu.language"))
        self._status_label.setText(i18n.tr("status.ready"))

    def _load_saved_language(self) -> None:
        saved = str(self._settings().value(_KEY_LANGUAGE, "en"))
        self._set_language(saved, persist=False)

    def _set_language(self, language: str, persist: bool = True) -> None:
        i18n.set_language(language)
        is_zh = i18n.language() == "zh_CN"
        self._act_lang_zh.setChecked(is_zh)
        self._act_lang_en.setChecked(not is_zh)
        if persist:
            self._settings().setValue(_KEY_LANGUAGE, i18n.language())

    def _load_saved_theme(self) -> None:
        theme_name = str(self._settings().value(_KEY_THEME, "light")).lower()
        self._apply_theme(theme_name)

    def _apply_theme(self, theme_name: str) -> None:
        theme_file = self._themes_dir() / f"{theme_name}.qss"
        if not theme_file.exists():
            theme_name = "light"
            theme_file = self._themes_dir() / "light.qss"

        qss = theme_file.read_text(encoding="utf-8")
        self.setStyleSheet(qss)
        self._settings().setValue(_KEY_THEME, theme_name)

        action = self._theme_actions.get(theme_name)
        if action:
            action.setChecked(True)

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

    def _start_initial_scan(self) -> None:
        QTimer.singleShot(200, self._start_scan)

    def _start_scan(self) -> None:
        if self._scanner and self._scanner.isRunning():
            return
        self._show_loading(i18n.tr("status.scanning"))
        self._scanner = ScannerThread(self)
        self._scanner.progress.connect(self._status_label.setText)
        self._scanner.images_added.connect(lambda _: None)
        self._scanner.images_removed.connect(lambda _: None)
        self._scanner.finished_scan.connect(self._on_scan_finished)
        self._scanner.start()

    def _on_scan_finished(self, added: int, removed: int) -> None:
        self._hide_loading()
        self._status_label.setText(i18n.tr("status.scan_done", added=added, removed=removed))
        self._trigger_filter()
        self._folder_tree.refresh()
        self._search_bar.refresh_picker_data()
        self._metadata_panel.refresh_suggestions()

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
            self._status_label.setText(i18n.tr("grid.images_count", count=len(paths)))
            return

        self._show_loading(i18n.tr("status.filtering_folder" if folder else "status.filtering_results"))

        thread = FolderFilterThread(folder_path=folder, search_query=query, parent=self)
        thread.results_ready.connect(self._on_filter_results)
        thread.finished.connect(self._hide_loading)
        self._filter_thread = thread
        thread.start()

    def _on_filter_results(self, paths: list[str]) -> None:
        self._image_grid.load_images(paths)
        if self._current_folder:
            self._status_label.setText(
                i18n.tr("status.folder_count", count=len(paths), label=self._current_folder)
            )
        else:
            self._status_label.setText(i18n.tr("status.query_count", count=len(paths)))

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
        self._metadata_panel.refresh_suggestions()

    def _open_external(self, paths: list[str], index: int) -> None:
        if not paths:
            return
        path = paths[index] if 0 <= index < len(paths) else paths[0]
        self._open_path_external(path)

    def _open_path_external(self, path: str) -> None:
        p = os.path.normpath(path)
        if sys.platform.startswith("win"):
            subprocess.run(["explorer", p], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", p], check=False)
        else:
            subprocess.run(["xdg-open", p], check=False)

    def _show_loading(self, message: str) -> None:
        self._status_label.setText(message)
        self._progress.setVisible(True)

    def _hide_loading(self) -> None:
        self._progress.setVisible(False)

    def _export_library(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self,
            i18n.tr("dialog.export_title"),
            "library-export.zip",
            "ZIP files (*.zip)",
        )
        if not target:
            return
        try:
            export_library_zip(Path(target))
            self.statusBar().showMessage(f"{i18n.tr('menu.export')}: {target}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, i18n.tr("dialog.export_failed"), str(exc))

    def _import_library(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            i18n.tr("dialog.import_title"),
            "",
            "ZIP files (*.zip)",
        )
        if not source:
            return

        answer = QMessageBox.warning(
            self,
            i18n.tr("dialog.import_confirm_title"),
            i18n.tr("dialog.import_confirm"),
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
            QMessageBox.information(self, i18n.tr("dialog.import_done"), i18n.tr("dialog.import_done_text"))
        except Exception as exc:
            QMessageBox.critical(self, i18n.tr("dialog.import_failed"), str(exc))

    def _wait_for_background_tasks(self) -> None:
        if self._scanner and self._scanner.isRunning():
            self._scanner.wait(5000)
        if self._filter_thread and self._filter_thread.isRunning():
            self._filter_thread.wait(5000)
