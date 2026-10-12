"""Окно системных настроек настольного приложения."""

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QCheckBox, QDialog, QVBoxLayout, QWidget

from dj_poltorashka.application.settings_controller import SettingsController


class SettingsDialog:
    def __init__(
        self,
        controller: SettingsController,
        show_error: Callable[[str, str], None],
        parent: QWidget | None = None,
    ):
        self._controller = controller
        self._show_error = show_error
        self._widget = QDialog(parent)
        self._widget.setWindowTitle("Настройки")
        layout = QVBoxLayout(self._widget)
        self._autostart_checkbox = QCheckBox("Запускать вместе с Windows")
        self._autostart_checkbox.setObjectName("autostart_checkbox")
        layout.addWidget(self._autostart_checkbox)
        self._autostart_checkbox.toggled.connect(self._set_autostart)

    @property
    def widget(self) -> QDialog:
        return self._widget

    def open(self) -> None:
        try:
            actual_state = self._controller.autostart_enabled()
        except OSError as error:
            self._show_error("Автозапуск", str(error))
            actual_state = False
        self._show_state(actual_state)
        self._widget.open()

    def _set_autostart(self, enabled: bool) -> None:
        try:
            actual_state = self._controller.set_autostart_enabled(enabled)
        except OSError as error:
            self._show_error("Автозапуск", str(error))
            try:
                actual_state = self._controller.autostart_enabled()
            except OSError:
                actual_state = not enabled
        self._show_state(actual_state)

    def _show_state(self, enabled: bool) -> None:
        blocker = QSignalBlocker(self._autostart_checkbox)
        self._autostart_checkbox.setChecked(enabled)
        del blocker
