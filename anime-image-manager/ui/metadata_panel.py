"""
Metadata editor panel — displayed on the right side.
Shows and edits tags, artist, series, description for selected image(s).
Supports batch editing when multiple images are selected.

Changes in this version
------------------------
* Artist and Series fields now each have an explicit "Apply" button.
  The old editingFinished approach was unreliable for batch edits because
  focus changes while tabbing through a multi-selection would silently
  fire partial saves.  An explicit button makes the intent unambiguous.

* Pressing Enter inside an Artist or Series field also triggers the save
  (returnPressed connected to the same handler).

* All saves are wrapped in try/except so metadata save errors are shown
  in a small status label instead of
  crashing silently.

* The status label auto-clears after 3 seconds so it doesn't clutter the UI.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton,
    QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView
)

from app import metadata_manager as mm


class MetadataPanel(QWidget):
    metadata_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_paths: list[str] = []
        # Timer to auto-clear the status label
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        self._status_clear_timer.setInterval(3000)
        self._status_clear_timer.timeout.connect(self._clear_status)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header — shows filename or "N images selected"
        self._header = QLabel("No image selected")
        self._header.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding-bottom: 4px;"
        )
        self._header.setWordWrap(True)
        layout.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # ---- Artist ----
        layout.addWidget(QLabel("Artist:"))
        artist_row = QHBoxLayout()
        self._artist_edit = QLineEdit()
        self._artist_edit.setPlaceholderText("e.g. SomeArtist")
        # Enter key in the field also saves
        self._artist_edit.returnPressed.connect(self._on_save_artist)
        artist_row.addWidget(self._artist_edit)

        self._btn_save_artist = QPushButton("Apply")
        self._btn_save_artist.setFixedWidth(50)
        self._btn_save_artist.setToolTip(
            "Save artist to all selected images (also: press Enter)"
        )
        self._btn_save_artist.clicked.connect(self._on_save_artist)
        artist_row.addWidget(self._btn_save_artist)
        layout.addLayout(artist_row)

        # ---- Series ----
        layout.addWidget(QLabel("Series:"))
        series_row = QHBoxLayout()
        self._series_edit = QLineEdit()
        self._series_edit.setPlaceholderText("e.g. Re:Zero")
        self._series_edit.returnPressed.connect(self._on_save_series)
        series_row.addWidget(self._series_edit)

        self._btn_save_series = QPushButton("Apply")
        self._btn_save_series.setFixedWidth(50)
        self._btn_save_series.setToolTip(
            "Save series to all selected images (also: press Enter)"
        )
        self._btn_save_series.clicked.connect(self._on_save_series)
        series_row.addWidget(self._btn_save_series)
        layout.addLayout(series_row)

        # ---- Tags ----
        layout.addWidget(QLabel("Tags:"))

        self._tags_list = QListWidget()
        self._tags_list.setFixedHeight(90)
        self._tags_list.setSelectionMode(QAbstractItemView.MultiSelection)
        layout.addWidget(self._tags_list)

        tag_row = QHBoxLayout()
        self._tag_input = QLineEdit()
        self._tag_input.setPlaceholderText("tag1, tag2, ...")
        self._tag_input.returnPressed.connect(self._on_add_tag)
        tag_row.addWidget(self._tag_input)

        btn_add = QPushButton("Add")
        btn_add.setFixedWidth(44)
        btn_add.clicked.connect(self._on_add_tag)
        tag_row.addWidget(btn_add)

        btn_remove = QPushButton("Remove")
        btn_remove.setFixedWidth(58)
        btn_remove.setToolTip("Remove selected tag(s) from all selected images")
        btn_remove.clicked.connect(self._on_remove_selected_tags)
        tag_row.addWidget(btn_remove)

        layout.addLayout(tag_row)

        # ---- Description ----
        layout.addWidget(QLabel("Description:"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Optional description...")
        self._desc_edit.setFixedHeight(75)
        # Auto-save description on focus-out (single image only)
        self._desc_edit.focusOutEvent = self._desc_focus_lost
        layout.addWidget(self._desc_edit)

        # ---- Status label (error / success feedback) ----
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 11px; color: #a6e3a1;")  # green
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Start disabled
        self._set_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_selection(self, paths: list[str]) -> None:
        """Populate all fields from the selected image(s)."""
        self._selected_paths = paths
        self._clear_status()

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
            fname = paths[0].replace("\\", "/").split("/")[-1]
            self._header.setText(fname)
            meta = mm.get_metadata(paths[0])
            self._artist_edit.setText(meta.get("artist", ""))
            self._series_edit.setText(meta.get("series", ""))
            self._desc_edit.setPlainText(meta.get("description", ""))
            self._populate_tags(meta.get("tags", []))
        else:
            self._header.setText(f"{len(paths)} images selected")

            all_tags: set[str] = set()
            artists:  set[str] = set()
            series_s: set[str] = set()

            for p in paths:
                meta = mm.get_metadata(p)
                all_tags.update(meta.get("tags", []))
                a = meta.get("artist", "")
                if a:
                    artists.add(a)
                s = meta.get("series", "")
                if s:
                    series_s.add(s)

            # Show the shared value if all images agree; otherwise blank
            self._artist_edit.setText(artists.pop() if len(artists) == 1 else "")
            self._artist_edit.setPlaceholderText(
                "— multiple values —" if len(artists) > 1 else "e.g. SomeArtist"
            )
            self._series_edit.setText(series_s.pop() if len(series_s) == 1 else "")
            self._series_edit.setPlaceholderText(
                "— multiple values —" if len(series_s) > 1 else "e.g. Re:Zero"
            )
            self._desc_edit.clear()
            self._desc_edit.setPlaceholderText(
                "(description editing not available in batch mode)"
            )
            self._populate_tags(sorted(all_tags))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_tags(self, tags: list[str]) -> None:
        self._tags_list.clear()
        for tag in tags:
            self._tags_list.addItem(QListWidgetItem(tag))

    def _set_enabled(self, enabled: bool) -> None:
        for w in [
            self._artist_edit, self._btn_save_artist,
            self._series_edit, self._btn_save_series,
            self._tag_input,   self._desc_edit, self._tags_list,
        ]:
            w.setEnabled(enabled)

    def _show_status(self, message: str, is_error: bool = False) -> None:
        """Display a brief status message that auto-clears after 3 s."""
        colour = "#f38ba8" if is_error else "#a6e3a1"   # red or green
        self._status_label.setStyleSheet(f"font-size: 11px; color: {colour};")
        self._status_label.setText(message)
        self._status_clear_timer.start()

    def _clear_status(self) -> None:
        self._status_label.setText("")

    # ------------------------------------------------------------------
    # Save handlers — each wrapped in try/except for safe error display
    # ------------------------------------------------------------------

    def _on_save_artist(self) -> None:
        """
        Apply button (or Enter) for the Artist field.
        """
        if not self._selected_paths:
            return
        artist = self._artist_edit.text().strip()
        try:
            mm.save_artist(self._selected_paths, artist)
            n = len(self._selected_paths)
            self._show_status(
                f"Artist saved to {n} image{'s' if n != 1 else ''}."
            )
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error saving artist: {exc}", is_error=True)

    def _on_save_series(self) -> None:
        """
        Apply button (or Enter) for the Series field.
        """
        if not self._selected_paths:
            return
        series = self._series_edit.text().strip()
        try:
            mm.save_series(self._selected_paths, series)
            n = len(self._selected_paths)
            self._show_status(
                f"Series saved to {n} image{'s' if n != 1 else ''}."
            )
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error saving series: {exc}", is_error=True)

    def _on_add_tag(self) -> None:
        """
        Add the comma-separated tags from the input field to all selected images.
        """
        if not self._selected_paths:
            return
        raw = self._tag_input.text()
        tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        if not tags:
            return
        try:
            mm.add_tags_to_images(self._selected_paths, tags)
            self._tag_input.clear()
            self.load_selection(self._selected_paths)
            self._show_status(
                f"Added {len(tags)} tag{'s' if len(tags) != 1 else ''}."
            )
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error adding tags: {exc}", is_error=True)

    def _on_remove_selected_tags(self) -> None:
        """Remove all selected tags (in the list widget) from selected images."""
        if not self._selected_paths:
            return
        selected_items = self._tags_list.selectedItems()
        if not selected_items:
            return
        tags = [item.text() for item in selected_items]
        try:
            mm.remove_tags_from_images(self._selected_paths, tags)
            self.load_selection(self._selected_paths)
            self._show_status(
                f"Removed {len(tags)} tag{'s' if len(tags) != 1 else ''}."
            )
            self.metadata_changed.emit()
        except Exception as exc:
            self._show_status(f"Error removing tags: {exc}", is_error=True)

    def _desc_focus_lost(self, event) -> None:
        """Auto-save description when the text area loses focus (single image only)."""
        if len(self._selected_paths) == 1:
            text = self._desc_edit.toPlainText()
            try:
                mm.save_description(self._selected_paths[0], text)
                self.metadata_changed.emit()
            except Exception as exc:
                self._show_status(f"Error saving description: {exc}", is_error=True)
        QTextEdit.focusOutEvent(self._desc_edit, event)
