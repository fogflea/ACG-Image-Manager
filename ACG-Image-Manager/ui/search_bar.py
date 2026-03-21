import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QDialog, QVBoxLayout, QTabWidget, QListWidget,
    QListWidgetItem, QDialogButtonBox,
    QMenu, QInputDialog, QMessageBox, QAbstractItemView
)

from app import metadata_manager as mm
from app.i18n import i18n

_TOKEN_RE = re.compile(r'(-?)(tag|artist|series):("([^"]+)"|(\S+))', re.IGNORECASE)


def _parse_token_states(query: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for m in _TOKEN_RE.finditer(query):
        neg = m.group(1) or ""
        prefix = m.group(2).lower()
        value = (m.group(4) or m.group(5) or "").strip()
        if not value:
            continue
        token = f"{prefix}:{value}"
        states[token] = "exclude" if neg else "include"
    return states


def _add_token(query: str, token: str) -> str:
    if token.lower() in query.lower():
        return query
    return (query.strip() + " " + token).strip()


def _remove_token(query: str, token: str) -> str:
    escaped = re.escape(token)
    result = re.sub(r'\s*' + escaped + r'\s*', ' ', query, flags=re.IGNORECASE)
    return result.strip()


class PickerDialog(QDialog):
    token_state_changed = Signal(str, str)  # token, include|exclude|neutral
    metadata_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token_states: dict[str, str] = {}
        self._all_data = {"tag": [], "artist": [], "series": []}
        i18n.language_changed.connect(self._retranslate_ui)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setMinimumSize(380, 460)
        self.resize(420, 500)

        layout = QVBoxLayout(self)
        self._filter_input = QLineEdit()
        self._filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_input)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._lists = {}
        for tab_name, prefix in [("tags", "tag"), ("artists", "artist"), ("series", "series")]:
            lst = QListWidget()
            lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
            lst.setContextMenuPolicy(Qt.CustomContextMenu)
            lst.customContextMenuRequested.connect(lambda pos, p=prefix: self._show_item_menu(p, pos))
            lst.itemClicked.connect(lambda item, p=prefix: self._cycle_item_state(item, p))
            self._lists[prefix] = lst
            self._tabs.addTab(lst, tab_name)

        action_row = QHBoxLayout()
        self._btn_delete_selected = QPushButton()
        self._btn_delete_selected.clicked.connect(self._delete_selected_items)
        action_row.addWidget(self._btn_delete_selected)
        action_row.addStretch()
        layout.addLayout(action_row)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        self._retranslate_ui()

    def _retranslate_ui(self, _lang: str | None = None) -> None:
        self.setWindowTitle(i18n.tr("picker.title"))
        self._filter_input.setPlaceholderText(i18n.tr("picker.filter"))
        self._tabs.setTabText(0, i18n.tr("picker.tags"))
        self._tabs.setTabText(1, i18n.tr("picker.artists"))
        self._tabs.setTabText(2, i18n.tr("picker.series"))
        self._btn_delete_selected.setText(i18n.tr("picker.delete_selected"))

    def sync_from_query(self, query: str) -> None:
        self._token_states = _parse_token_states(query)
        self._reload_stats()
        self._apply_filter(self._filter_input.text())

    def _reload_stats(self) -> None:
        self._all_data = {
            "tag": mm.tag_usage_counts(),
            "artist": mm.artist_usage_counts(),
            "series": mm.series_usage_counts(),
        }

    def _apply_filter(self, text: str) -> None:
        text = text.lower()
        for prefix, lst in self._lists.items():
            lst.clear()
            for value, count in self._all_data.get(prefix, []):
                if text and text not in value.lower():
                    continue
                token = f"{prefix}:{value}"
                state = self._token_states.get(token, "neutral")
                item = QListWidgetItem()
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setData(Qt.UserRole, token)
                item.setData(Qt.UserRole + 1, value)
                item.setData(Qt.UserRole + 2, count)
                self._set_item_visual_state(item, state)
                lst.addItem(item)

    def _set_item_visual_state(self, item: QListWidgetItem, state: str) -> None:
        name = item.data(Qt.UserRole + 1)
        count = int(item.data(Qt.UserRole + 2) or 0)
        item.setData(Qt.UserRole + 3, state)
        font = QFont(item.font())

        if state == "include":
            item.setText(f"{name} ({count})")
            item.setCheckState(Qt.Checked)
            item.setForeground(QBrush(QColor("#7bd88f")))
            font.setStrikeOut(False)
            item.setFont(font)
        elif state == "exclude":
            item.setText(f"✖ {name} ({count})")
            item.setCheckState(Qt.Unchecked)
            item.setForeground(QBrush(QColor("#ff6b6b")))
            font.setStrikeOut(True)
            item.setFont(font)
        else:
            item.setText(f"{name} ({count})")
            item.setCheckState(Qt.Unchecked)
            item.setForeground(QBrush())
            font.setStrikeOut(False)
            item.setFont(font)

    def _cycle_item_state(self, item: QListWidgetItem, prefix: str) -> None:
        token = item.data(Qt.UserRole) or f"{prefix}:{item.data(Qt.UserRole + 1)}"
        current = item.data(Qt.UserRole + 3) or "neutral"
        next_state = {"neutral": "include", "include": "exclude", "exclude": "neutral"}.get(current, "neutral")

        self._token_states[token] = next_state
        if next_state == "neutral":
            self._token_states.pop(token, None)

        self._set_item_visual_state(item, next_state)
        self.token_state_changed.emit(token, next_state)

    def _current_prefix(self) -> str:
        return ["tag", "artist", "series"][self._tabs.currentIndex()]

    def _delete_selected_items(self) -> None:
        prefix = self._current_prefix()
        lst = self._lists[prefix]
        selected = lst.selectedItems()
        if not selected:
            return

        values = [str(item.data(Qt.UserRole + 1)).strip() for item in selected if item.data(Qt.UserRole + 1)]
        if not values:
            return

        answer = QMessageBox.question(
            self,
            i18n.tr("picker.delete_title", prefix=prefix),
            i18n.tr("picker.delete_selected_confirm", count=len(values), prefix=prefix),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            for value in values:
                if prefix == "tag":
                    mm.delete_tag(value)
                elif prefix == "artist":
                    mm.delete_artist(value)
                else:
                    mm.delete_series(value)
                self._token_states.pop(f"{prefix}:{value}", None)

            self._reload_stats()
            self._apply_filter(self._filter_input.text())
            self.metadata_updated.emit()
        except RuntimeError as exc:
            QMessageBox.critical(self, i18n.tr("picker.delete_fail"), str(exc))

    def _show_item_menu(self, prefix: str, pos) -> None:
        lst = self._lists[prefix]
        item = lst.itemAt(pos)
        if item is None:
            return

        menu = QMenu(self)
        action_rename = menu.addAction(i18n.tr("picker.rename"))
        action_delete = menu.addAction(i18n.tr("picker.delete"))
        chosen = menu.exec(lst.mapToGlobal(pos))

        value = (item.data(Qt.UserRole + 1) or "").strip()
        if not value:
            return

        if chosen == action_rename:
            self._rename_value(prefix, value)
        elif chosen == action_delete:
            self._delete_value(prefix, value)

    def _rename_value(self, prefix: str, old_value: str) -> None:
        new_value, ok = QInputDialog.getText(
            self,
            i18n.tr("picker.rename_title", prefix=prefix),
            i18n.tr("picker.rename_label", prefix=prefix),
            text=old_value,
        )
        if not ok:
            return
        new_value = new_value.strip()
        if not new_value or new_value == old_value:
            return

        try:
            if prefix == "tag":
                mm.rename_tag(old_value, new_value)
            elif prefix == "artist":
                mm.rename_artist(old_value, new_value)
            else:
                mm.rename_series(old_value, new_value)

            old_token = f"{prefix}:{old_value}"
            state = self._token_states.pop(old_token, "neutral")
            if state != "neutral":
                self._token_states[f"{prefix}:{new_value}"] = state

            self._reload_stats()
            self._apply_filter(self._filter_input.text())
            self.metadata_updated.emit()
        except RuntimeError as exc:
            QMessageBox.critical(self, i18n.tr("picker.rename_fail"), str(exc))

    def _delete_value(self, prefix: str, value: str) -> None:
        answer = QMessageBox.question(
            self,
            i18n.tr("picker.delete_title", prefix=prefix),
            i18n.tr("picker.delete_msg", value=value),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            if prefix == "tag":
                mm.delete_tag(value)
            elif prefix == "artist":
                mm.delete_artist(value)
            else:
                mm.delete_series(value)

            self._token_states.pop(f"{prefix}:{value}", None)
            self._reload_stats()
            self._apply_filter(self._filter_input.text())
            self.metadata_updated.emit()
        except RuntimeError as exc:
            QMessageBox.critical(self, i18n.tr("picker.delete_fail"), str(exc))


class SearchBar(QWidget):
    search_triggered = Signal(str)
    refresh_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._picker: PickerDialog | None = None
        i18n.language_changed.connect(self._retranslate_ui)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self._search_input = QLineEdit()
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._search_input)

        self._btn_search = QPushButton()
        self._btn_search.setFixedWidth(70)
        self._btn_search.clicked.connect(self._on_search)
        layout.addWidget(self._btn_search)

        self._btn_clear = QPushButton()
        self._btn_clear.setFixedWidth(55)
        self._btn_clear.clicked.connect(self._on_clear)
        layout.addWidget(self._btn_clear)

        self._btn_picker = QPushButton()
        self._btn_picker.setFixedWidth(85)
        self._btn_picker.clicked.connect(self._open_picker)
        layout.addWidget(self._btn_picker)

        self._btn_refresh = QPushButton()
        self._btn_refresh.setFixedWidth(90)
        self._btn_refresh.clicked.connect(self.refresh_triggered.emit)
        layout.addWidget(self._btn_refresh)

        self._retranslate_ui()

    def _retranslate_ui(self, _lang: str | None = None) -> None:
        self._search_input.setPlaceholderText(i18n.tr("search.placeholder"))
        self._btn_search.setText(i18n.tr("search.button"))
        self._btn_clear.setText(i18n.tr("search.clear"))
        self._btn_picker.setText(i18n.tr("search.picker"))
        self._btn_refresh.setText(i18n.tr("search.refresh"))

    def _on_text_changed(self, text: str) -> None:
        self.search_triggered.emit(text.strip())

    def _on_search(self) -> None:
        self.search_triggered.emit(self._search_input.text().strip())

    def _on_clear(self) -> None:
        self._search_input.clear()
        self.search_triggered.emit("")

    def _open_picker(self) -> None:
        if self._picker is None:
            self._picker = PickerDialog(self)
            self._picker.token_state_changed.connect(self._on_token_state_changed)
            self._picker.metadata_updated.connect(
                lambda: self.search_triggered.emit(self._search_input.text().strip())
            )

        self._picker.sync_from_query(self._search_input.text())
        self._picker.show()
        self._picker.raise_()
        self._picker.activateWindow()

    def _on_token_state_changed(self, token: str, state: str) -> None:
        current = self._search_input.text()
        new_query = _remove_token(_remove_token(current, token), f"-{token}")
        if state == "include":
            new_query = _add_token(new_query, token)
        elif state == "exclude":
            new_query = _add_token(new_query, f"-{token}")

        self._search_input.blockSignals(True)
        self._search_input.setText(new_query)
        self._search_input.blockSignals(False)
        self.search_triggered.emit(new_query)

    def get_query(self) -> str:
        return self._search_input.text().strip()

    def refresh_picker_data(self) -> None:
        if self._picker is not None and self._picker.isVisible():
            self._picker.sync_from_query(self._search_input.text())
