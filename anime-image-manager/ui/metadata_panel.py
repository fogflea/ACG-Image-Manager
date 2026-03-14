"""
Metadata editor panel — displayed on the right side.
Shows and edits tags, artist, series, description for selected image(s).
Supports batch editing when multiple images are selected.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QScrollArea,
    QFrame, QSizePolicy, QListWidget, QListWidgetItem,
    QAbstractItemView
)

from app import metadata_manager as mm


class TagWidget(QWidget):
    """A single removable tag chip."""
    remove_requested = Signal(str)

    def __init__(self, tag: str, parent=None):
        super().__init__(parent)
        self.tag = tag
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        lbl = QLabel(tag)
        lbl.setStyleSheet("background: #3a3a5c; color: #ccc; border-radius: 3px; padding: 1px 4px;")
        layout.addWidget(lbl)

        btn = QPushButton("✕")
        btn.setFixedSize(16, 16)
        btn.setFlat(True)
        btn.setStyleSheet("color: #aaa; font-size: 10px;")
        btn.clicked.connect(lambda: self.remove_requested.emit(self.tag))
        layout.addWidget(btn)


class MetadataPanel(QWidget):
    metadata_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_paths: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        self._header = QLabel("No image selected")
        self._header.setStyleSheet("font-weight: bold; font-size: 13px; padding-bottom: 4px;")
        self._header.setWordWrap(True)
        layout.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        layout.addWidget(QLabel("Artist:"))
        self._artist_edit = QLineEdit()
        self._artist_edit.setPlaceholderText("e.g. SomeArtist")
        self._artist_edit.editingFinished.connect(self._on_artist_changed)
        layout.addWidget(self._artist_edit)

        layout.addWidget(QLabel("Series:"))
        self._series_edit = QLineEdit()
        self._series_edit.setPlaceholderText("e.g. Re:Zero")
        self._series_edit.editingFinished.connect(self._on_series_changed)
        layout.addWidget(self._series_edit)

        layout.addWidget(QLabel("Tags:"))

        self._tags_list = QListWidget()
        self._tags_list.setFixedHeight(100)
        self._tags_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self._tags_list)

        add_row = QHBoxLayout()
        self._tag_input = QLineEdit()
        self._tag_input.setPlaceholderText("Add tag(s), comma-separated...")
        self._tag_input.returnPressed.connect(self._on_add_tag)
        add_row.addWidget(self._tag_input)

        btn_add = QPushButton("Add")
        btn_add.setFixedWidth(50)
        btn_add.clicked.connect(self._on_add_tag)
        add_row.addWidget(btn_add)

        btn_remove = QPushButton("Remove")
        btn_remove.setFixedWidth(60)
        btn_remove.clicked.connect(self._on_remove_selected_tags)
        add_row.addWidget(btn_remove)

        layout.addLayout(add_row)

        layout.addWidget(QLabel("Description:"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Optional description...")
        self._desc_edit.setFixedHeight(80)
        self._desc_edit.focusOutEvent = self._desc_focus_lost
        layout.addWidget(self._desc_edit)

        layout.addStretch()

    def load_selection(self, paths: list[str]) -> None:
        self._selected_paths = paths

        if not paths:
            self._header.setText("No image selected")
            self._artist_edit.clear()
            self._series_edit.clear()
            self._tags_list.clear()
            self._desc_edit.clear()
            self._set_enabled(False)
            return

        self._set_enabled(True)

        if len(paths) == 1:
            self._header.setText(paths[0].split("/")[-1].split("\\")[-1])
            meta = mm.get_metadata(paths[0])
            self._artist_edit.setText(meta.get("artist", ""))
            self._series_edit.setText(meta.get("series", ""))
            self._desc_edit.setPlainText(meta.get("description", ""))
            self._populate_tags(meta.get("tags", []))
        else:
            self._header.setText(f"{len(paths)} images selected")
            all_tags: set[str] = set()
            artists: set[str] = set()
            series_set: set[str] = set()
            for p in paths:
                meta = mm.get_metadata(p)
                all_tags.update(meta.get("tags", []))
                a = meta.get("artist", "")
                if a:
                    artists.add(a)
                s = meta.get("series", "")
                if s:
                    series_set.add(s)

            self._artist_edit.setText(artists.pop() if len(artists) == 1 else "")
            self._artist_edit.setPlaceholderText(
                "Multiple values" if len(artists) > 1 else "e.g. SomeArtist"
            )
            self._series_edit.setText(series_set.pop() if len(series_set) == 1 else "")
            self._series_edit.setPlaceholderText(
                "Multiple values" if len(series_set) > 1 else "e.g. Re:Zero"
            )
            self._desc_edit.clear()
            self._desc_edit.setPlaceholderText("(batch edit not available for description)")
            self._populate_tags(sorted(all_tags))

    def _populate_tags(self, tags: list[str]) -> None:
        self._tags_list.clear()
        for tag in tags:
            item = QListWidgetItem(tag)
            self._tags_list.addItem(item)

    def _set_enabled(self, enabled: bool) -> None:
        for w in [self._artist_edit, self._series_edit,
                  self._tag_input, self._desc_edit, self._tags_list]:
            w.setEnabled(enabled)

    def _on_artist_changed(self) -> None:
        if not self._selected_paths:
            return
        artist = self._artist_edit.text().strip()
        mm.save_artist(self._selected_paths, artist)
        self.metadata_changed.emit()

    def _on_series_changed(self) -> None:
        if not self._selected_paths:
            return
        series = self._series_edit.text().strip()
        mm.save_series(self._selected_paths, series)
        self.metadata_changed.emit()

    def _on_add_tag(self) -> None:
        if not self._selected_paths:
            return
        raw = self._tag_input.text()
        tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        if not tags:
            return
        mm.add_tags_to_images(self._selected_paths, tags)
        self._tag_input.clear()
        self.load_selection(self._selected_paths)
        self.metadata_changed.emit()

    def _on_remove_selected_tags(self) -> None:
        if not self._selected_paths:
            return
        selected_items = self._tags_list.selectedItems()
        if not selected_items:
            return
        tags = [item.text() for item in selected_items]
        mm.remove_tags_from_images(self._selected_paths, tags)
        self.load_selection(self._selected_paths)
        self.metadata_changed.emit()

    def _desc_focus_lost(self, event) -> None:
        if len(self._selected_paths) == 1:
            text = self._desc_edit.toPlainText()
            mm.save_description(self._selected_paths[0], text)
            self.metadata_changed.emit()
        QTextEdit.focusOutEvent(self._desc_edit, event)
