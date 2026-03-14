"""
Search bar widget — top bar with query input, refresh button,
and a Tag/Artist/Series picker popup.

Fix #2 / #3 / #4:
- PickerDialog now uses checkboxes to show which filters are already active.
- Single click on an item toggles it (adds OR removes the token from the
  search box) instead of requiring double-click.
- Popup syncs its checked state from the current search box text every time
  it opens.
- Removing a token is done by rebuilding the query string without that token.
- In-list filter/search still works.
"""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QDialog, QVBoxLayout, QTabWidget, QListWidget,
    QListWidgetItem, QLabel, QDialogButtonBox
)

from app import metadata_manager as mm


# ---------------------------------------------------------------------------
# Helpers — parse / build query strings
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r'(tag|artist|series):(\S+)', re.IGNORECASE)


def _parse_active_tokens(query: str) -> set[str]:
    """
    Return the set of normalised token strings that are present in `query`.
    E.g. 'tag:catgirl artist:abc' → {'tag:catgirl', 'artist:abc'}
    """
    return {f"{m.group(1).lower()}:{m.group(2)}" for m in _TOKEN_RE.finditer(query)}


def _add_token(query: str, token: str) -> str:
    """Append `token` to `query` if it isn't already present."""
    if token.lower() in query.lower():
        return query
    return (query.strip() + " " + token).strip()


def _remove_token(query: str, token: str) -> str:
    """
    Remove the exact `token` (case-insensitive) from `query` and return the
    cleaned-up string.
    """
    # Escape the token for regex, then strip surrounding/extra whitespace
    escaped = re.escape(token)
    result = re.sub(r'\s*' + escaped + r'\s*', ' ', query, flags=re.IGNORECASE)
    return result.strip()


# ---------------------------------------------------------------------------
# Picker Dialog
# ---------------------------------------------------------------------------

class PickerDialog(QDialog):
    """
    Popup with three tabs: Tags, Artists, Series.

    Fix #2d / #4:
    - Items that are already in the search box are shown with a checkmark.
    - Single-clicking an item TOGGLES it — checked → removes from search box,
      unchecked → adds to search box.

    Fix #2e:
    - A filter input at the top lets the user narrow down long lists.

    Fix #3:
    - Emits `token_toggled(token, is_now_checked)` so SearchBar can add or
      remove the token from the query string.
    """

    # token: e.g. "tag:catgirl", is_checked: True = add, False = remove
    token_toggled = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tag / Artist / Series Picker")
        self.setMinimumSize(360, 440)
        self.resize(400, 480)
        # Track which tokens are currently active (updated from search box)
        self._active_tokens: set[str] = set()
        # All data loaded from DB
        self._all_data: dict[str, list[str]] = {"tag": [], "artist": [], "series": []}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # In-popup filter
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter list...")
        self._filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_input)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._lists: dict[str, QListWidget] = {}
        for tab_name, prefix in [("Tags", "tag"), ("Artists", "artist"), ("Series", "series")]:
            lst = QListWidget()
            # itemChanged fires after the check state actually changes, whether
            # the user clicked the checkbox or the text row.  This is more
            # reliable than itemClicked, which fires at different points in the
            # toggle cycle depending on whether the checkbox or text was hit.
            lst.itemChanged.connect(lambda item, p=prefix: self._on_item_changed(item, p))
            self._lists[prefix] = lst
            self._tabs.addTab(lst, tab_name)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Public API called by SearchBar before showing the dialog
    # ------------------------------------------------------------------

    def sync_from_query(self, query: str) -> None:
        """
        Call this every time the popup is opened so it reflects the current
        search box state.  Refreshes DB data and sets checkbox states.
        """
        self._active_tokens = _parse_active_tokens(query)

        # Reload from database so newly added tags / artists / series appear
        self._all_data = {
            "tag": mm.all_tags(),
            "artist": mm.all_artists(),
            "series": mm.all_series(),
        }

        self._apply_filter(self._filter_input.text())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_filter(self, text: str) -> None:
        """
        Re-populate every list, applying the text filter and checkbox state.
        Signals are blocked while building items so that setting check states
        programmatically does not trigger the itemChanged → token_toggled chain.
        """
        text = text.lower()
        for prefix, lst in self._lists.items():
            lst.blockSignals(True)   # prevent false token_toggled emissions
            lst.clear()
            for value in self._all_data.get(prefix, []):
                if text and text not in value.lower():
                    continue
                token = f"{prefix}:{value}"
                item = QListWidgetItem(value)
                item.setData(Qt.UserRole, token)  # store the full token

                # Checkable item — Qt will show a checkbox next to the text
                is_active = token in self._active_tokens
                item.setCheckState(Qt.Checked if is_active else Qt.Unchecked)

                # Extra colour hint for active items
                if is_active:
                    item.setForeground(Qt.green)

                lst.addItem(item)
            lst.blockSignals(False)  # re-enable user interaction events

    def _on_item_changed(self, item: QListWidgetItem, prefix: str) -> None:
        """
        Called by itemChanged AFTER Qt has already updated the check state.
        We read the new state and notify SearchBar to add or remove the token.
        itemChanged is used instead of itemClicked because itemClicked fires at
        different points in the toggle cycle (before/after state change) depending
        on whether the user hit the checkbox area or the text area.
        """
        token = item.data(Qt.UserRole)
        if token is None:
            token = f"{prefix}:{item.text()}"

        new_checked = item.checkState() == Qt.Checked

        # Update colour to match new state
        item.setForeground(Qt.green if new_checked else Qt.white)

        # Keep internal set in sync
        if new_checked:
            self._active_tokens.add(token)
        else:
            self._active_tokens.discard(token)

        # Notify SearchBar
        self.token_toggled.emit(token, new_checked)


# ---------------------------------------------------------------------------
# Search Bar widget
# ---------------------------------------------------------------------------

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
        # Fix #3: emit a live search whenever the text changes
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

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_text_changed(self, text: str) -> None:
        # Emit a live search on every keystroke (clearing the box shows all)
        self.search_triggered.emit(text.strip())

    def _on_search(self) -> None:
        self.search_triggered.emit(self._search_input.text().strip())

    def _on_clear(self) -> None:
        self._search_input.clear()
        self.search_triggered.emit("")

    def _open_picker(self) -> None:
        if self._picker is None:
            self._picker = PickerDialog(self)
            # Fix #2c / #3: connect toggle signal to add/remove logic
            self._picker.token_toggled.connect(self._on_token_toggled)

        # Fix #4: always sync the popup state from the current search box text
        self._picker.sync_from_query(self._search_input.text())
        self._picker.show()
        self._picker.raise_()
        self._picker.activateWindow()

    def _on_token_toggled(self, token: str, is_checked: bool) -> None:
        """
        Fix #2c / #3: add or remove the token from the search box depending
        on whether the picker just checked or unchecked it.
        """
        current = self._search_input.text()
        if is_checked:
            new_query = _add_token(current, token)
        else:
            new_query = _remove_token(current, token)

        # Block the textChanged signal momentarily so we don't fire a search
        # mid-update; we'll emit it once after we're done.
        self._search_input.blockSignals(True)
        self._search_input.setText(new_query)
        self._search_input.blockSignals(False)

        # Trigger the search with the final query
        self.search_triggered.emit(new_query)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_query(self) -> str:
        return self._search_input.text().strip()
