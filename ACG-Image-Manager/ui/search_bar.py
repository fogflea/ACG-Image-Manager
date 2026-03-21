import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QDialog, QVBoxLayout, QTabWidget, QListWidget,
    QListWidgetItem, QDialogButtonBox,
    QMenu, QInputDialog, QMessageBox
)

from app import metadata_manager as mm
from app.i18n import i18n

_TOKEN_RE = re.compile(r'(-?)(tag|artist|series):("([^"]+)"|(\S+))', re.IGNORECASE)


def _parse_active_tokens(query: str) -> set[str]:
    tokens = set()
    for m in _TOKEN_RE.finditer(query):
        neg = m.group(1) or ""
        prefix = m.group(2).lower()
        value = (m.group(4) or m.group(5) or "").strip()
        if value and not neg:
            tokens.add(f"{prefix}:{value}")
    return tokens


def _add_token(query: str, token: str) -> str:
    if token.lower() in query.lower():
        return query
    return (query.strip() + " " + token).strip()


def _remove_token(query: str, token: str) -> str:
    escaped = re.escape(token)
    result = re.sub(r'\s*' + escaped + r'\s*', ' ', query, flags=re.IGNORECASE)
    return result.strip()


class PickerDialog(QDialog):
    token_toggled = Signal(str, bool)
    metadata_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_tokens: set[str] = set()
        self._all_data = {"tag": [], "artist": [], "series": []}
        i18n.language_changed.connect(self._retranslate_ui)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setMinimumSize(360, 440)
        self.resize(400, 480)

        layout = QVBoxLayout(self)
        self._filter_input = QLineEdit()
        self._filter_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_input)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._lists = {}
        for tab_name, prefix in [("tags", "tag"), ("artists", "artist"), ("series", "series")]:
            lst = QListWidget()
            lst.setContextMenuPolicy(Qt.CustomContextMenu)
            lst.customContextMenuRequested.connect(lambda pos, p=prefix: self._show_item_menu(p, pos))
            lst.itemChanged.connect(lambda item, p=prefix: self._on_item_changed(item, p))
            self._lists[prefix] = lst
            self._tabs.addTab(lst, tab_name)

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

    def sync_from_query(self, query: str) -> None:
        self._active_tokens = _parse_active_tokens(query)
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
            lst.blockSignals(True)
            lst.clear()
            for value, count in self._all_data.get(prefix, []):
                if text and text not in value.lower():
                    continue
                token = f"{prefix}:{value}"
                item = QListWidgetItem(f"{value} ({count})")
                item.setData(Qt.UserRole, token)
                item.setData(Qt.UserRole + 1, value)
                is_active = token in self._active_tokens
                item.setCheckState(Qt.Checked if is_active else Qt.Unchecked)
                if is_active:
                    item.setForeground(Qt.green)
                lst.addItem(item)
            lst.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem, prefix: str) -> None:
        token = item.data(Qt.UserRole)
        if token is None:
            raw = item.data(Qt.UserRole + 1) or item.text()
            token = f"{prefix}:{raw}"

        new_checked = item.checkState() == Qt.Checked
        item.setForeground(Qt.green if new_checked else Qt.white)
        if new_checked:
            self._active_tokens.add(token)
        else:
            self._active_tokens.discard(token)
        self.token_toggled.emit(token, new_checked)

    def _show_item_menu(self, prefix: str, pos) -> None:
        lst = self._lists[prefix]
        item = lst.itemAt(pos)
        if item is None:
            return

        menu = QMenu(self)
        action_rename = menu.addAction(i18n.tr("picker.rename"))
        action_delete = menu.addAction(i18n.tr("picker.delete"))
        chosen = menu.exec(lst.mapToGlobal(pos))

        value = (item.data(Qt.UserRole + 1) or item.text()).strip()
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
            self._picker.token_toggled.connect(self._on_token_toggled)
            self._picker.metadata_updated.connect(
                lambda: self.search_triggered.emit(self._search_input.text().strip())
            )

        self._picker.sync_from_query(self._search_input.text())
        self._picker.show()
        self._picker.raise_()
        self._picker.activateWindow()

    def _on_token_toggled(self, token: str, is_checked: bool) -> None:
        current = self._search_input.text()
        new_query = _add_token(current, token) if is_checked else _remove_token(current, token)
        self._search_input.blockSignals(True)
        self._search_input.setText(new_query)
        self._search_input.blockSignals(False)
        self.search_triggered.emit(new_query)

    def get_query(self) -> str:
        return self._search_input.text().strip()

    def refresh_picker_data(self) -> None:
        if self._picker is not None and self._picker.isVisible():
            self._picker.sync_from_query(self._search_input.text())
