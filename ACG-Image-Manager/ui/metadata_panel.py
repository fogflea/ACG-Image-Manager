import re

from PySide6.QtCore import Signal, QTimer, Qt, QStringListModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton,
    QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QCompleter
)

from app import metadata_manager as mm
from ui.i18n import i18n


class MetadataPanel(QWidget):
    metadata_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_paths: list[str] = []
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        self._status_clear_timer.setInterval(3000)
        self._status_clear_timer.timeout.connect(self._clear_status)
        self._build_ui()
        self._setup_autocomplete()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._header = QLabel("")
        self._header.setStyleSheet("font-weight: bold; font-size: 13px; padding-bottom: 4px;")
        self._header.setWordWrap(True)
        layout.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self._artist_label = QLabel()
        layout.addWidget(self._artist_label)
        artist_row = QHBoxLayout()
        self._artist_edit = QLineEdit()
        self._artist_edit.returnPressed.connect(self._on_save_artist)
        artist_row.addWidget(self._artist_edit)

        self._btn_save_artist = QPushButton()
        self._btn_save_artist.setFixedWidth(50)
        self._btn_save_artist.clicked.connect(self._on_save_artist)
        artist_row.addWidget(self._btn_save_artist)
        layout.addLayout(artist_row)

        self._series_label = QLabel()
        layout.addWidget(self._series_label)
        series_row = QHBoxLayout()
        self._series_edit = QLineEdit()
        self._series_edit.returnPressed.connect(self._on_save_series)
        series_row.addWidget(self._series_edit)

        self._btn_save_series = QPushButton()
        self._btn_save_series.setFixedWidth(50)
        self._btn_save_series.clicked.connect(self._on_save_series)
        series_row.addWidget(self._btn_save_series)
        layout.addLayout(series_row)

        self._tags_label = QLabel()
        layout.addWidget(self._tags_label)

        self._tags_list = QListWidget()
        self._tags_list.setFixedHeight(90)
        self._tags_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self._tags_list)

        tag_row = QHBoxLayout()
        self._tag_input = QLineEdit()
        self._tag_input.returnPressed.connect(self._on_add_tag)
        self._tag_input.textEdited.connect(self._on_tag_text_edited)
        tag_row.addWidget(self._tag_input)

        self._btn_add = QPushButton()
        self._btn_add.setFixedWidth(44)
        self._btn_add.clicked.connect(self._on_add_tag)
        tag_row.addWidget(self._btn_add)

        self._btn_remove = QPushButton()
        self._btn_remove.setFixedWidth(58)
        self._btn_remove.clicked.connect(self._on_remove_selected_tags)
        tag_row.addWidget(self._btn_remove)

        layout.addLayout(tag_row)

        self._desc_label = QLabel()
        layout.addWidget(self._desc_label)
        self._desc_edit = QTextEdit()
        self._desc_edit.setFixedHeight(75)
        self._desc_edit.focusOutEvent = self._desc_focus_lost
        layout.addWidget(self._desc_edit)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 11px; color: #a6e3a1;")
        layout.addWidget(self._status_label)

        layout.addStretch()
        self._set_enabled(False)

    def _setup_autocomplete(self) -> None:
        self._tag_model = QStringListModel(self)
        self._artist_model = QStringListModel(self)
        self._series_model = QStringListModel(self)

        self._tag_completer = QCompleter(self._tag_model, self)
        self._tag_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._tag_completer.setFilterMode(Qt.MatchContains)
        self._tag_completer.activated.connect(self._apply_tag_completion)
        self._tag_input.setCompleter(self._tag_completer)

        self._artist_completer = QCompleter(self._artist_model, self)
        self._artist_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._artist_completer.setFilterMode(Qt.MatchContains)
        self._artist_edit.setCompleter(self._artist_completer)

        self._series_completer = QCompleter(self._series_model, self)
        self._series_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._series_completer.setFilterMode(Qt.MatchContains)
        self._series_edit.setCompleter(self._series_completer)

        self.refresh_autocomplete()

    def refresh_autocomplete(self) -> None:
        self._tag_model.setStringList(mm.all_tags())
        self._artist_model.setStringList(mm.all_artists())
        self._series_model.setStringList(mm.all_series())

    def _current_tag_token_bounds(self) -> tuple[int, int]:
        text = self._tag_input.text()
        cursor = self._tag_input.cursorPosition()
        left = max(text.rfind(",", 0, cursor), text.rfind(" ", 0, cursor)) + 1
        right_comma = text.find(",", cursor)
        right_space = text.find(" ", cursor)
        rights = [i for i in [right_comma, right_space] if i != -1]
        right = min(rights) if rights else len(text)
        return left, right

    def _on_tag_text_edited(self, _text: str) -> None:
        left, _right = self._current_tag_token_bounds()
        cursor = self._tag_input.cursorPosition()
        token = self._tag_input.text()[left:cursor].strip()
        self._tag_completer.setCompletionPrefix(token)

    def _apply_tag_completion(self, completion: str) -> None:
        text = self._tag_input.text()
        left, right = self._current_tag_token_bounds()
        prefix = text[:left]
        suffix = text[right:]
        if prefix and not prefix.endswith((",", " ")):
            prefix += " "
        new_text = f"{prefix}{completion}"
        if suffix.strip():
            new_text += suffix
        else:
            new_text += ", "
        self._tag_input.setText(new_text)
        self._tag_input.setCursorPosition(len(new_text))

    def retranslate_ui(self) -> None:
        self._artist_label.setText(i18n.tr("artist"))
        self._series_label.setText(i18n.tr("series"))
        self._tags_label.setText(i18n.tr("tags"))
        self._desc_label.setText(i18n.tr("description"))
        self._btn_save_artist.setText(i18n.tr("apply"))
        self._btn_save_series.setText(i18n.tr("apply"))
        self._btn_add.setText(i18n.tr("add"))
        self._btn_remove.setText(i18n.tr("remove"))
        self._artist_edit.setPlaceholderText(i18n.tr("artist_placeholder"))
        self._series_edit.setPlaceholderText(i18n.tr("series_placeholder"))
        self._tag_input.setPlaceholderText(i18n.tr("tags_placeholder"))
        self._desc_edit.setPlaceholderText(i18n.tr("desc_placeholder"))
        self._btn_save_artist.setToolTip(i18n.tr("apply_artist_tip"))
        self._btn_save_series.setToolTip(i18n.tr("apply_series_tip"))
        self._btn_remove.setToolTip(i18n.tr("remove_tags_tip"))
        if not self._selected_paths:
            self._header.setText(i18n.tr("no_image_selected"))

    def load_selection(self, paths: list[str]) -> None:
        self._selected_paths = paths
        self._clear_status()
        self.refresh_autocomplete()

        if not paths:
            self._header.setText(i18n.tr("no_image_selected"))
            self._artist_edit.clear()
            self._series_edit.clear()
            self._tags_list.clear()
            self._desc_edit.clear()
            self._set_enabled(False)
            return

        self._set_enabled(True)

        if len(paths) == 1:
            self._header.setText(paths[0].replace("\\", "/").split("/")[-1])
            meta = mm.get_metadata(paths[0])
            self._artist_edit.setText(meta.get("artist", ""))
            self._series_edit.setText(meta.get("series", ""))
            self._desc_edit.setPlainText(meta.get("description", ""))
            self._populate_tags(meta.get("tags", []))
        else:
            self._header.setText(f"{len(paths)} images selected")
            all_tags, artists, series_s = set(), set(), set()
            for p in paths:
                meta = mm.get_metadata(p)
                all_tags.update(meta.get("tags", []))
                if meta.get("artist", ""):
                    artists.add(meta.get("artist", ""))
                if meta.get("series", ""):
                    series_s.add(meta.get("series", ""))

            self._artist_edit.setText(artists.pop() if len(artists) == 1 else "")
            self._artist_edit.setPlaceholderText(i18n.tr("multiple_values") if len(artists) > 1 else i18n.tr("artist_placeholder"))
            self._series_edit.setText(series_s.pop() if len(series_s) == 1 else "")
            self._series_edit.setPlaceholderText(i18n.tr("multiple_values") if len(series_s) > 1 else i18n.tr("series_placeholder"))
            self._desc_edit.clear()
            self._desc_edit.setPlaceholderText(i18n.tr("desc_batch_unavailable"))
            self._populate_tags(sorted(all_tags))

    def _populate_tags(self, tags: list[str]) -> None:
        self._tags_list.clear()
        for tag in tags:
            self._tags_list.addItem(QListWidgetItem(tag))

    def _set_enabled(self, enabled: bool) -> None:
        for w in [self._artist_edit, self._btn_save_artist, self._series_edit, self._btn_save_series, self._tag_input, self._desc_edit, self._tags_list]:
            w.setEnabled(enabled)

    def _show_status(self, message: str, is_error: bool = False) -> None:
        self._status_label.setStyleSheet(f"font-size: 11px; color: {'#f38ba8' if is_error else '#a6e3a1'};")
        self._status_label.setText(message)
        self._status_clear_timer.start()

    def _clear_status(self) -> None:
        self._status_label.setText("")

    def _on_save_artist(self) -> None:
        if not self._selected_paths:
            return
        try:
            mm.save_artist(self._selected_paths, self._artist_edit.text().strip())
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error saving artist: {exc}", is_error=True)

    def _on_save_series(self) -> None:
        if not self._selected_paths:
            return
        try:
            mm.save_series(self._selected_paths, self._series_edit.text().strip())
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error saving series: {exc}", is_error=True)

    def _on_add_tag(self) -> None:
        if not self._selected_paths:
            return
        raw = self._tag_input.text()
        tags = [t.strip().lower() for t in re.split(r"[\s,]+", raw) if t.strip()]
        if not tags:
            return
        try:
            mm.add_tags_to_images(self._selected_paths, tags)
            self._tag_input.clear()
            self.load_selection(self._selected_paths)
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error adding tags: {exc}", is_error=True)

    def _on_remove_selected_tags(self) -> None:
        if not self._selected_paths:
            return
        selected_items = self._tags_list.selectedItems()
        if not selected_items:
            return
        try:
            mm.remove_tags_from_images(self._selected_paths, [item.text() for item in selected_items])
            self.load_selection(self._selected_paths)
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error removing tags: {exc}", is_error=True)

    def _desc_focus_lost(self, event) -> None:
        if len(self._selected_paths) == 1:
            try:
                mm.save_description(self._selected_paths[0], self._desc_edit.toPlainText())
                self.metadata_changed.emit()
            except Exception as exc:
                self._show_status(f"Error saving description: {exc}", is_error=True)
        QTextEdit.focusOutEvent(self._desc_edit, event)
