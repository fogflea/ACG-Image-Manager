"""
Search bar widget — top bar with query input, refresh button,
and a Tag/Artist/Series picker popup.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QDialog, QVBoxLayout, QTabWidget, QListWidget,
    QListWidgetItem, QLabel, QDialogButtonBox
)

from app import metadata_manager as mm


class PickerDialog(QDialog):
    """
    Popup with three tabs: Tags, Artists, Series.
    Clicking an item inserts it into the search box.
    """
    item_picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tag / Artist / Series Picker")
        self.resize(380, 460)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter...")
        self._filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_input)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._lists: dict[str, QListWidget] = {}

        for tab_name, prefix in [("Tags", "tag"), ("Artists", "artist"), ("Series", "series")]:
            lst = QListWidget()
            lst.itemDoubleClicked.connect(lambda item, p=prefix: self._on_pick(item, p))
            self._lists[prefix] = lst
            self._tabs.addTab(lst, tab_name)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def refresh_data(self) -> None:
        self._all_data: dict[str, list[str]] = {
            "tag": mm.all_tags(),
            "artist": mm.all_artists(),
            "series": mm.all_series(),
        }
        self._apply_filter(self._filter_input.text())

    def _apply_filter(self, text: str) -> None:
        text = text.lower()
        for prefix, lst in self._lists.items():
            lst.clear()
            for item_text in self._all_data.get(prefix, []):
                if text in item_text.lower():
                    lst.addItem(QListWidgetItem(item_text))

    def _on_pick(self, item: QListWidgetItem, prefix: str) -> None:
        self.item_picked.emit(f"{prefix}:{item.text()}")


class SearchBar(QWidget):
    search_triggered = Signal(str)
    refresh_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._picker: PickerDialog = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            'Search: tag:catgirl  artist:SomeArtist  series:ReZero'
        )
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._search_input)

        btn_search = QPushButton("Search")
        btn_search.setFixedWidth(70)
        btn_search.clicked.connect(self._on_search)
        layout.addWidget(btn_search)

        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(55)
        btn_clear.clicked.connect(self._on_clear)
        layout.addWidget(btn_clear)

        btn_picker = QPushButton("🏷 Picker")
        btn_picker.setFixedWidth(80)
        btn_picker.clicked.connect(self._open_picker)
        layout.addWidget(btn_picker)

        btn_refresh = QPushButton("⟳ Refresh")
        btn_refresh.setFixedWidth(90)
        btn_refresh.clicked.connect(self.refresh_triggered.emit)
        layout.addWidget(btn_refresh)

    def _on_text_changed(self, text: str) -> None:
        if not text.strip():
            self.search_triggered.emit("")

    def _on_search(self) -> None:
        self.search_triggered.emit(self._search_input.text().strip())

    def _on_clear(self) -> None:
        self._search_input.clear()
        self.search_triggered.emit("")

    def _open_picker(self) -> None:
        if self._picker is None:
            self._picker = PickerDialog(self)
            self._picker.item_picked.connect(self._insert_picker_item)
        self._picker.refresh_data()
        self._picker.show()
        self._picker.raise_()

    def _insert_picker_item(self, token: str) -> None:
        current = self._search_input.text().strip()
        if current:
            if token not in current:
                self._search_input.setText(f"{current} {token}")
        else:
            self._search_input.setText(token)

    def get_query(self) -> str:
        return self._search_input.text().strip()
