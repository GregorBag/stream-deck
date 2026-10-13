"""Окно системных настроек настольного приложения."""

from collections import Counter
from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from dj_poltorashka.application.settings_controller import SettingsController
from dj_poltorashka.audio.routing_models import (
    AudioDeviceDescriptor,
    AudioRoutingStatus,
)
from dj_poltorashka.audio.routing_settings import AudioRoutingSettings


class SettingsDialog:
    def __init__(
        self,
        controller: SettingsController,
        show_error: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        self._controller = controller
        self._show_error = show_error
        self._widget = QDialog(parent)
        self._widget.setWindowTitle("Настройки")
        layout = QVBoxLayout(self._widget)
        self._autostart_checkbox = QCheckBox("Запускать вместе с Windows")
        self._autostart_checkbox.setObjectName("autostart_checkbox")
        layout.addWidget(self._autostart_checkbox)
        self._autostart_checkbox.toggled.connect(self._set_autostart)

        group = QGroupBox("Виртуальный микрофон")
        group.setObjectName("virtual_microphone_group")
        routing_layout = QFormLayout(group)
        self._input_combo = QComboBox()
        self._input_combo.setObjectName("input_device_combo")
        self._monitor_combo = QComboBox()
        self._monitor_combo.setObjectName("monitor_device_combo")
        self._microphone_slider = self._make_slider("microphone_gain_slider")
        self._sound_slider = self._make_slider("sound_gain_slider")
        self._status_label = QLabel("Состояние ещё не определено")
        self._status_label.setObjectName("virtual_microphone_status")
        routing_layout.addRow("Физический микрофон", self._input_combo)
        routing_layout.addRow("Мониторинг звуков", self._monitor_combo)
        routing_layout.addRow("Громкость микрофона", self._microphone_slider)
        routing_layout.addRow("Громкость звуков", self._sound_slider)
        routing_layout.addRow("Состояние", self._status_label)
        layout.addWidget(group)

        self._input_combo.currentIndexChanged.connect(self._set_input_device)
        self._monitor_combo.currentIndexChanged.connect(self._set_monitor_device)
        self._microphone_slider.valueChanged.connect(self._set_microphone_gain)
        self._sound_slider.valueChanged.connect(self._set_sound_gain)

    @property
    def widget(self) -> QDialog:
        return self._widget

    def open(self) -> None:
        try:
            actual_state = self._controller.autostart_enabled()
        except OSError as error:
            self._show_error("Автозапуск", str(error))
            actual_state = False
        self._show_autostart_state(actual_state)
        if hasattr(self._controller, "routing_settings"):
            self._refresh_routing_controls()
        self._widget.open()

    def set_virtual_microphone_status(self, state: AudioRoutingStatus) -> None:
        self._status_label.setText(state.message)
        self._status_label.setProperty("status_code", state.code)

    def _set_autostart(self, enabled: bool) -> None:
        try:
            actual_state = self._controller.set_autostart_enabled(enabled)
        except OSError as error:
            self._show_error("Автозапуск", str(error))
            try:
                actual_state = self._controller.autostart_enabled()
            except OSError:
                actual_state = not enabled
        self._show_autostart_state(actual_state)

    def _show_autostart_state(self, enabled: bool) -> None:
        blocker = QSignalBlocker(self._autostart_checkbox)
        self._autostart_checkbox.setChecked(enabled)
        del blocker

    def _refresh_routing_controls(self) -> None:
        settings = self._controller.routing_settings()
        blockers = [
            QSignalBlocker(self._input_combo),
            QSignalBlocker(self._monitor_combo),
            QSignalBlocker(self._microphone_slider),
            QSignalBlocker(self._sound_slider),
        ]
        self._populate_devices(
            self._input_combo,
            self._controller.input_devices(),
            settings.input_device_id,
        )
        self._populate_devices(
            self._monitor_combo,
            self._controller.monitor_devices(),
            settings.monitor_device_id,
        )
        self._microphone_slider.setValue(round(settings.microphone_gain * 100))
        self._sound_slider.setValue(round(settings.sound_gain * 100))
        del blockers

    @staticmethod
    def _populate_devices(
        combo: QComboBox,
        devices: tuple[AudioDeviceDescriptor, ...],
        selected_id: str | None,
    ) -> None:
        combo.clear()
        combo.addItem("Системное устройство", None)
        counts = Counter(item.description.casefold() for item in devices)
        for device in devices:
            text = device.description
            if counts[device.description.casefold()] > 1:
                text = f"{text} — {device.device_id}"
            combo.addItem(text, device.device_id)
        selected_index = combo.findData(selected_id)
        combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)

    def _set_input_device(self, index: int) -> None:
        self._apply_routing_change(
            lambda: self._controller.set_input_device(self._input_combo.itemData(index))
        )

    def _set_monitor_device(self, index: int) -> None:
        self._apply_routing_change(
            lambda: self._controller.set_monitor_device(
                self._monitor_combo.itemData(index)
            )
        )

    def _set_microphone_gain(self, value: int) -> None:
        self._apply_routing_change(
            lambda: self._controller.set_microphone_gain(value / 100.0)
        )

    def _set_sound_gain(self, value: int) -> None:
        self._apply_routing_change(
            lambda: self._controller.set_sound_gain(value / 100.0)
        )

    def _apply_routing_change(self, operation: Callable[[], None]) -> None:
        try:
            operation()
        except (OSError, ValueError) as error:
            self._show_error("Виртуальный микрофон", str(error))
            self._refresh_routing_controls()

    @staticmethod
    def _make_slider(object_name: str) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName(object_name)
        slider.setRange(0, 100)
        return slider
