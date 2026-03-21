from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QStringListModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton,
    QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QCompleter, QMessageBox
)

from app import metadata_manager as mm
from app.i18n import i18n


class MetadataPanel(QWidget):
    metadata_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_paths: list[str] = []
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        self._status_clear_timer.setInterval(3000)
        self._status_clear_timer.timeout.connect(self._clear_status)

        self._artist_model = QStringListModel([])
        self._series_model = QStringListModel([])
        self._tag_model = QStringListModel([])

        i18n.language_changed.connect(self._retranslate_ui)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._header = QLabel()
        self._header.setStyleSheet("font-weight: bold; font-size: 13px; padding-bottom: 4px;")
        self._header.setWordWrap(True)
        layout.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self._lbl_artist = QLabel()
        layout.addWidget(self._lbl_artist)
        artist_row = QHBoxLayout()
        self._artist_edit = QLineEdit()
        self._artist_edit.returnPressed.connect(self._on_save_artist)
        artist_row.addWidget(self._artist_edit)
        self._artist_completer = QCompleter(self._artist_model, self)
        self._artist_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._artist_completer.setFilterMode(Qt.MatchContains)
        self._artist_edit.setCompleter(self._artist_completer)

        self._btn_save_artist = QPushButton()
        self._btn_save_artist.setFixedWidth(60)
        self._btn_save_artist.clicked.connect(self._on_save_artist)
        artist_row.addWidget(self._btn_save_artist)
        layout.addLayout(artist_row)

        self._lbl_series = QLabel()
        layout.addWidget(self._lbl_series)
        series_row = QHBoxLayout()
        self._series_edit = QLineEdit()
        self._series_edit.returnPressed.connect(self._on_save_series)
        series_row.addWidget(self._series_edit)
        self._series_completer = QCompleter(self._series_model, self)
        self._series_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._series_completer.setFilterMode(Qt.MatchContains)
        self._series_edit.setCompleter(self._series_completer)

        self._btn_save_series = QPushButton()
        self._btn_save_series.setFixedWidth(60)
        self._btn_save_series.clicked.connect(self._on_save_series)
        series_row.addWidget(self._btn_save_series)
        layout.addLayout(series_row)

        self._lbl_tags = QLabel()
        layout.addWidget(self._lbl_tags)

        self._tags_list = QListWidget()
        self._tags_list.setFixedHeight(90)
        self._tags_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self._tags_list)

        tag_row = QHBoxLayout()
        self._tag_input = QLineEdit()
        self._tag_input.returnPressed.connect(self._on_add_tag)
        tag_row.addWidget(self._tag_input)
        self._tag_completer = QCompleter(self._tag_model, self)
        self._tag_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._tag_completer.setFilterMode(Qt.MatchContains)
        self._tag_input.setCompleter(self._tag_completer)

        self._btn_add = QPushButton()
        self._btn_add.setFixedWidth(50)
        self._btn_add.clicked.connect(self._on_add_tag)
        tag_row.addWidget(self._btn_add)

        self._btn_remove = QPushButton()
        self._btn_remove.setFixedWidth(70)
        self._btn_remove.clicked.connect(self._on_remove_selected_tags)
        tag_row.addWidget(self._btn_remove)
        layout.addLayout(tag_row)

        self._lbl_description = QLabel()
        layout.addWidget(self._lbl_description)
        self._desc_edit = QTextEdit()
        self._desc_edit.setFixedHeight(75)
        self._desc_edit.focusOutEvent = self._desc_focus_lost
        layout.addWidget(self._desc_edit)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 11px; color: #a6e3a1;")
        layout.addWidget(self._status_label)

        layout.addStretch()
        self._retranslate_ui()
        self._set_enabled(False)
        self.refresh_suggestions()

    def _retranslate_ui(self, _lang: str | None = None) -> None:
        self._lbl_artist.setText(i18n.tr("metadata.artist"))
        self._lbl_series.setText(i18n.tr("metadata.series"))
        self._lbl_tags.setText(i18n.tr("metadata.tags"))
        self._lbl_description.setText(i18n.tr("metadata.description"))
        self._btn_save_artist.setText(i18n.tr("metadata.apply"))
        self._btn_save_series.setText(i18n.tr("metadata.apply"))
        self._btn_add.setText(i18n.tr("metadata.add"))
        self._btn_remove.setText(i18n.tr("metadata.remove"))
        self._artist_edit.setPlaceholderText(i18n.tr("metadata.artist_ph"))
        self._series_edit.setPlaceholderText(i18n.tr("metadata.series_ph"))
        self._tag_input.setPlaceholderText(i18n.tr("metadata.tags_ph"))
        self._desc_edit.setPlaceholderText(i18n.tr("metadata.desc_ph"))
        if not self._selected_paths:
            self._header.setText(i18n.tr("metadata.none"))

    def refresh_suggestions(self) -> None:
        self._artist_model.setStringList(mm.all_artists())
        self._series_model.setStringList(mm.all_series())
        self._tag_model.setStringList(mm.all_tags())

    def load_selection(self, paths: list[str]) -> None:
        self._selected_paths = paths
        self._clear_status()

        if not paths:
            self._header.setText(i18n.tr("metadata.none"))
            self._artist_edit.clear()
            self._series_edit.clear()
            self._tags_list.clear()
            self._desc_edit.clear()
            self._set_enabled(False)
            return

        self._set_enabled(True)

        if len(paths) == 1:
            fname = paths[0].replace("\\", "/").split("/")[-1]
            self._header.setText(fname)
            meta = mm.get_metadata(paths[0])
            self._artist_edit.setText(meta.get("artist", ""))
            self._series_edit.setText(meta.get("series", ""))
            self._desc_edit.setPlainText(meta.get("description", ""))
            self._desc_edit.setPlaceholderText(i18n.tr("metadata.desc_ph"))
            self._populate_tags(meta.get("tags", []))
        else:
            self._header.setText(i18n.tr("metadata.multi", count=len(paths)))
            all_tags: set[str] = set()
            artists: set[str] = set()
            series_s: set[str] = set()
            for p in paths:
                meta = mm.get_metadata(p)
                all_tags.update(meta.get("tags", []))
                if meta.get("artist", ""):
                    artists.add(meta.get("artist"))
                if meta.get("series", ""):
                    series_s.add(meta.get("series"))

            self._artist_edit.setText(next(iter(artists)) if len(artists) == 1 else "")
            self._artist_edit.setPlaceholderText(i18n.tr("metadata.multi_values") if len(artists) > 1 else i18n.tr("metadata.artist_ph"))
            self._series_edit.setText(next(iter(series_s)) if len(series_s) == 1 else "")
            self._series_edit.setPlaceholderText(i18n.tr("metadata.multi_values") if len(series_s) > 1 else i18n.tr("metadata.series_ph"))
            self._desc_edit.clear()
            self._desc_edit.setPlaceholderText(i18n.tr("metadata.batch_desc_ph"))
            self._populate_tags(sorted(all_tags))

    def _populate_tags(self, tags: list[str]) -> None:
        self._tags_list.clear()
        for tag in tags:
            self._tags_list.addItem(QListWidgetItem(tag))

    def _set_enabled(self, enabled: bool) -> None:
        for w in [
            self._artist_edit, self._btn_save_artist,
            self._series_edit, self._btn_save_series,
            self._tag_input, self._desc_edit, self._tags_list,
            self._btn_add, self._btn_remove,
        ]:
            w.setEnabled(enabled)

    def _show_status(self, message: str, is_error: bool = False) -> None:
        colour = "#f38ba8" if is_error else "#a6e3a1"
        self._status_label.setStyleSheet(f"font-size: 11px; color: {colour};")
        self._status_label.setText(message)
        self._status_clear_timer.start()

    def _clear_status(self) -> None:
        self._status_label.setText("")

    def _confirm(self, message: str) -> bool:
        return QMessageBox.question(
            self,
            i18n.tr("confirm.title"),
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes

    def _on_save_artist(self) -> None:
        if not self._selected_paths:
            return
        artist = self._artist_edit.text().strip()
        try:
            mm.save_artist(self._selected_paths, artist)
            self.refresh_suggestions()
            self._show_status(i18n.tr("status.artist_saved", count=len(self._selected_paths)))
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error saving artist: {exc}", is_error=True)

    def _on_save_series(self) -> None:
        if not self._selected_paths:
            return
        series = self._series_edit.text().strip()
        try:
            mm.save_series(self._selected_paths, series)
            self.refresh_suggestions()
            self._show_status(i18n.tr("status.series_saved", count=len(self._selected_paths)))
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error saving series: {exc}", is_error=True)

    def _on_add_tag(self) -> None:
        if not self._selected_paths:
            return
        raw = self._tag_input.text()
        tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        if not tags:
            return
        try:
            mm.add_tags_to_images(self._selected_paths, tags)
            self._tag_input.clear()
            self.refresh_suggestions()
            self.load_selection(self._selected_paths)
            self._show_status(i18n.tr("status.tags_added", count=len(tags)))
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error adding tags: {exc}", is_error=True)

    def _on_remove_selected_tags(self) -> None:
        if not self._selected_paths:
            return
        selected_items = self._tags_list.selectedItems()
        if not selected_items:
            return
        tags = [item.text() for item in selected_items]
        if not self._confirm(i18n.tr("confirm.remove_tags", count=len(self._selected_paths), tags=", ".join(tags))):
            return
        try:
            mm.remove_tags_from_images(self._selected_paths, tags)
            self.refresh_suggestions()
            self.load_selection(self._selected_paths)
            self._show_status(i18n.tr("status.tags_removed", count=len(tags)))
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error removing tags: {exc}", is_error=True)

    def _desc_focus_lost(self, event) -> None:
        if len(self._selected_paths) == 1:
            text = self._desc_edit.toPlainText()
            try:
                mm.save_description(self._selected_paths[0], text)
                self.metadata_changed.emit()
            except Exception as exc:
                self._show_status(f"Error saving description: {exc}", is_error=True)
        QTextEdit.focusOutEvent(self._desc_edit, event)
