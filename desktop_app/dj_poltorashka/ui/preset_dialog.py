"""Диалог выбора слота и имени пресета."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from dj_poltorashka.configuration.models import StoredConfiguration


class PresetDialog:
    def __init__(self, parent: QWidget | None = None):
        self._widget = QDialog(parent)
        self._widget.setWindowTitle("Сохранить в пресет")
        layout = QFormLayout(self._widget)

        self._slot_combo = QComboBox()
        self._slot_combo.setObjectName("preset_slot")
        layout.addRow("Слот", self._slot_combo)

        self._name_edit = QLineEdit()
        self._name_edit.setObjectName("preset_name")
        layout.addRow("Название", self._name_edit)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self._buttons.setObjectName("preset_buttons")
        layout.addRow(self._buttons)

        self._stored: StoredConfiguration | None = None
        self._selection: tuple[int, str] | None = None
        self._slot_combo.currentIndexChanged.connect(self._load_slot_name)
        self._buttons.accepted.connect(self._accept)
        self._buttons.rejected.connect(self._widget.reject)
        self._widget.rejected.connect(self._clear_selection)

    @property
    def widget(self) -> QDialog:
        return self._widget

    def prepare(self, stored: StoredConfiguration) -> None:
        self._stored = stored
        self._selection = None
        self._slot_combo.clear()
        for index, preset in enumerate(stored.presets):
            suffix = "Пусто" if preset is None else preset.name
            self._slot_combo.addItem(f"Пресет {index + 1} — {suffix}", index)
        self._slot_combo.setCurrentIndex(0)
        self._load_slot_name(0)

    def choose(self, stored: StoredConfiguration) -> tuple[int, str] | None:
        self.prepare(stored)
        self._widget.exec()
        return self.selection()

    def selection(self) -> tuple[int, str] | None:
        return self._selection

    def _load_slot_name(self, index: int) -> None:
        if self._stored is None or not 0 <= index < len(self._stored.presets):
            self._name_edit.clear()
            return
        preset = self._stored.presets[index]
        self._name_edit.setText("" if preset is None else preset.name)

    def _accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            return
        self._selection = (self._slot_combo.currentIndex(), name)
        self._widget.accept()

    def _clear_selection(self) -> None:
        self._selection = None
