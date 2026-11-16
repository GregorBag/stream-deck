"""Окно системных настроек настольного приложения."""

from collections import Counter
from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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
from dj_poltorashka.panel.lighting import COLOR_LABELS, RgbColor
from dj_poltorashka.panel.connection import PanelConnectionStatus


class SettingsDialog:
    def __init__(
        self,
        controller: SettingsController,
        show_error: Callable[[str, str], None],
        parent: QWidget | None = None,
    ) -> None:
        self._controller = controller
        self._show_error = show_error
        self._widget = QWidget(parent)
        self._widget.setObjectName("settings_page")
        self._widget.setWindowTitle("Настройки")
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(14, 8, 14, 14)
        layout.setSpacing(16)
        heading = QLabel("Настройки приложения")
        heading.setProperty("role", "section_title")
        layout.addWidget(heading)
        self._autostart_checkbox = QCheckBox("Запускать вместе с Windows")
        self._autostart_checkbox.setObjectName("autostart_checkbox")
        layout.addWidget(self._autostart_checkbox)
        self._autostart_checkbox.toggled.connect(self._set_autostart)

        panel_group = QGroupBox("Подключение панели")
        panel_group.setObjectName("panel_connection_group")
        panel_layout = QFormLayout(panel_group)
        port_control = QWidget()
        port_row = QHBoxLayout(port_control)
        port_row.setContentsMargins(0, 0, 0, 0)
        self._panel_port_combo = QComboBox()
        self._panel_port_combo.setObjectName("panel_port_combo")
        self._panel_port_combo.addItem("Не выбран", None)
        refresh_ports = QPushButton("Обновить")
        refresh_ports.setObjectName("refresh_panel_ports_button")
        refresh_ports.clicked.connect(self._refresh_panel_ports)
        self._panel_connect = QPushButton("Подключить")
        self._panel_connect.setObjectName("connect_panel_button")
        self._panel_connect.clicked.connect(self._connect_panel)
        self._panel_disconnect = QPushButton("Отключить")
        self._panel_disconnect.setObjectName("disconnect_panel_button")
        self._panel_disconnect.clicked.connect(lambda: self._controller.select_panel_port(None))
        self._panel_disconnect.setEnabled(False)
        self._panel_connection_status = QLabel("Панель не подключена")
        self._panel_connection_status.setObjectName("panel_connection_status")
        self._panel_connection_status.setWordWrap(True)
        port_row.addWidget(self._panel_port_combo, 1)
        port_row.addWidget(refresh_ports)
        port_row.addWidget(self._panel_connect)
        port_row.addWidget(self._panel_disconnect)
        panel_layout.addRow("Порт", port_control)
        panel_layout.addRow("Состояние", self._panel_connection_status)
        layout.addWidget(panel_group)
        panel_group.setVisible(hasattr(controller, "panel_ports"))

        group = QGroupBox("Виртуальный микрофон")
        group.setObjectName("virtual_microphone_group")
        routing_layout = QFormLayout(group)
        self._input_combo = QComboBox()
        self._input_combo.setObjectName("input_device_combo")
        self._monitor_combo = QComboBox()
        self._monitor_combo.setObjectName("monitor_device_combo")
        microphone_control, self._microphone_slider, self._microphone_value = self._make_gain_control("microphone_gain", "pink")
        sound_control, self._sound_slider, self._sound_value = self._make_gain_control("sound_gain", "pink")
        self._status_label = QLabel("Состояние ещё не определено")
        self._status_label.setObjectName("virtual_microphone_status")
        self._status_label.setWordWrap(True)
        self._status_label.setProperty("role", "status")
        routing_layout.setVerticalSpacing(18)
        routing_layout.setContentsMargins(20, 24, 20, 20)
        routing_layout.addRow("Физический микрофон", self._input_combo)
        routing_layout.addRow("Мониторинг звуков", self._monitor_combo)
        routing_layout.addRow("Громкость микрофона", microphone_control)
        routing_layout.addRow("Громкость звуков", sound_control)
        routing_layout.addRow("Состояние", self._status_label)
        layout.addWidget(group)
        note = QLabel(
            "Для передачи голоса и звуков в голосовой чат выберите CABLE Output "
            "в качестве микрофона в настройках этого чата."
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._color_edits: dict[str, QLineEdit] = {}
        self._color_previews: dict[str, QPushButton] = {}
        lighting_group = QGroupBox("Подсветка панели")
        lighting_group.setObjectName("lighting_group")
        lighting_layout = QVBoxLayout(lighting_group)
        lighting_layout.setSpacing(18)
        brightness_control, self._brightness_slider, _ = self._make_gain_control("lighting_brightness", "pink")
        self._brightness_slider.setRange(0, 50)
        self._brightness_slider.setValue(50)
        brightness_row = QHBoxLayout()
        brightness_row.addWidget(QLabel("Общая яркость"))
        brightness_row.addWidget(brightness_control, 1)
        lighting_layout.addLayout(brightness_row)

        colors_row = QHBoxLayout()
        colors_row.setSpacing(20)
        color_grid = QGridLayout()
        color_grid.setHorizontalSpacing(16)
        color_grid.setVerticalSpacing(6)
        color_groups = (
            ("Программируемая кнопка", (("sound_ready", "Настроена"), ("sound_playing", "Воспроизводится"), ("sound_unassigned", "Не назначена"))),
            ("Mute", (("mute_active", "Активен"), ("mute_muted", "Заглушён"), ("mute_unassigned", "Не активен"))),
            ("Пресет", (("preset_active", "Активен"), ("preset_saved", "Сохранён"), ("preset_empty", "Пустой"))),
        )
        for group_index, (group_label, colors) in enumerate(color_groups):
            heading_row = group_index * 3
            color_grid.addWidget(QLabel(group_label), heading_row + 1, 0, Qt.AlignmentFlag.AlignVCenter)
            for column_index, (name, state_label) in enumerate(colors, 1):
                color_grid.addWidget(QLabel(state_label), heading_row, column_index)
                color_grid.addWidget(self._make_color_control(name), heading_row + 1, column_index)
            color_grid.setRowMinimumHeight(heading_row + 2, 6)
        colors_row.addLayout(color_grid)

        perimeter_group = QGroupBox("Периметр")
        perimeter_group.setObjectName("perimeter_color_group")
        perimeter_layout = QVBoxLayout(perimeter_group)
        perimeter_layout.setSpacing(12)
        perimeter_layout.addWidget(QLabel("Постоянный цвет"))
        perimeter_layout.addWidget(self._make_color_control("perimeter"))
        perimeter_note = QLabel("При потере связи — белое мигание")
        perimeter_note.setWordWrap(True)
        perimeter_note.setProperty("role", "muted")
        perimeter_layout.addWidget(perimeter_note)
        perimeter_layout.addStretch()
        perimeter_group.setFixedWidth(164)
        colors_row.addWidget(perimeter_group)
        colors_row.addStretch()
        lighting_layout.addLayout(colors_row)
        self._brightness_slider.valueChanged.connect(self._update_color_previews)
        apply_lighting = QPushButton("Сохранить подсветку")
        apply_lighting.setObjectName("save_lighting_button")
        apply_lighting.clicked.connect(self._save_lighting)
        lighting_layout.addWidget(apply_lighting)
        layout.addWidget(lighting_group)
        lighting_group.setVisible(hasattr(controller, "lighting_settings"))
        layout.addStretch()

        self._input_combo.currentIndexChanged.connect(self._set_input_device)
        self._monitor_combo.currentIndexChanged.connect(self._set_monitor_device)
        self._microphone_slider.valueChanged.connect(self._set_microphone_gain)
        self._sound_slider.valueChanged.connect(self._set_sound_gain)

    @property
    def widget(self) -> QWidget:
        return self._widget

    def open(self) -> None:
        self.refresh()
        self._widget.show()

    def refresh(self) -> None:
        try:
            actual_state = self._controller.autostart_enabled()
        except OSError as error:
            self._show_error("Автозапуск", str(error))
            actual_state = False
        self._show_autostart_state(actual_state)
        if hasattr(self._controller, "routing_settings"):
            self._refresh_routing_controls()
        if hasattr(self._controller, "panel_ports"):
            self.refresh_panel_ports(preserve_selection=False)
            self._controller.refresh_panel_ports()
        if hasattr(self._controller, "lighting_settings"):
            settings = self._controller.lighting_settings()
            self._brightness_slider.setValue(round(settings.brightness * 100))
            for name, edit in self._color_edits.items():
                edit.setText(getattr(settings, name).to_hex())
            self._update_color_previews()

    def refresh_panel_ports(self, *, preserve_selection: bool = True) -> None:
        selected = self._panel_port_combo.currentData() if preserve_selection else self._controller.selected_panel_port()
        blocker = QSignalBlocker(self._panel_port_combo)
        self._panel_port_combo.clear()
        self._panel_port_combo.addItem("Не выбран", None)
        for port in self._controller.panel_ports():
            text = port.description if port.name.startswith("emulator://") else f"{port.name} — {port.description}"
            self._panel_port_combo.addItem(text, port.name)
        index = self._panel_port_combo.findData(selected)
        if selected is not None and index < 0:
            self._panel_port_combo.addItem(f"Недоступен — {selected}", selected)
            index = self._panel_port_combo.count() - 1
        self._panel_port_combo.setCurrentIndex(max(0, index))
        del blocker
        self.set_panel_connection_status(self._controller.panel_status())

    def set_panel_connection_status(self, status: PanelConnectionStatus) -> None:
        self._panel_connection_status.setText(status.message)
        self._panel_connection_status.setProperty("status_code", status.code)
        self._panel_disconnect.setEnabled(status.port_name is not None)

    def _refresh_panel_ports(self) -> None:
        self._controller.refresh_panel_ports()

    def _connect_panel(self) -> None:
        self._controller.select_panel_port(self._panel_port_combo.currentData())

    def _make_color_control(self, name: str) -> QWidget:
        control = QWidget()
        row = QHBoxLayout(control)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        edit = QLineEdit()
        edit.setObjectName(f"lighting_{name}")
        edit.setPlaceholderText("#RRGGBB")
        edit.setMaxLength(7)
        edit.setFixedWidth(92)
        preview = QPushButton()
        preview.setObjectName(f"lighting_preview_{name}")
        preview.setFixedSize(32, 32)
        preview.setToolTip("Выбрать цвет")
        preview.setAccessibleName(f"Выбрать цвет: {COLOR_LABELS[name]}")
        preview.clicked.connect(lambda checked=False: self._choose_color(name))
        row.addWidget(edit)
        row.addWidget(preview)
        self._color_edits[name] = edit
        self._color_previews[name] = preview
        edit.textChanged.connect(self._update_color_previews)
        return control

    def _update_color_previews(self) -> None:
        for name, edit in self._color_edits.items():
            try:
                red, green, blue = RgbColor.parse(edit.text()).to_rgb(self._brightness_slider.value() / 100)
            except ValueError:
                self._color_previews[name].setStyleSheet("padding: 0; min-height: 0; min-width: 0; background: transparent; border: 1px solid red;")
            else:
                self._color_previews[name].setStyleSheet(f"padding: 0; min-height: 0; min-width: 0; background: rgb({red}, {green}, {blue}); border: 1px solid #7585a5;")

    def _choose_color(self, name: str) -> None:
        edit = self._color_edits[name]
        try:
            initial = RgbColor.parse(edit.text())
        except ValueError:
            initial = getattr(self._controller.lighting_settings(), name)
        selected = QColorDialog.getColor(
            QColor(initial.red, initial.green, initial.blue),
            self._widget,
            COLOR_LABELS[name],
        )
        if selected.isValid():
            edit.setText(selected.name(QColor.NameFormat.HexRgb).upper())

    def _save_lighting(self) -> None:
        try:
            colors = {}
            for name, edit in self._color_edits.items():
                try:
                    colors[name] = RgbColor.parse(edit.text().strip())
                except ValueError as error:
                    edit.setFocus()
                    raise ValueError(f"{COLOR_LABELS[name]}: {error}") from error
            settings = replace(
                self._controller.lighting_settings(),
                brightness=self._brightness_slider.value() / 100,
                **colors,
            )
            self._controller.set_lighting_settings(settings)
        except (OSError, ValueError) as error:
            self._show_error("Подсветка панели", str(error))

    def set_virtual_microphone_status(self, state: AudioRoutingStatus) -> None:
        message = state.message
        prefix = "Виртуальный микрофон"
        if message.casefold().startswith(prefix.casefold()):
            message = message[len(prefix):].lstrip(" :—–-")
        self._status_label.setText(message)
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
        self._microphone_value.setText(f"{self._microphone_slider.value()}%")
        self._sound_value.setText(f"{self._sound_slider.value()}%")
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
        if selected_id is not None and selected_index < 0:
            combo.addItem(f"Недоступно — {selected_id}", selected_id)
            selected_index = combo.count() - 1
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
    def _make_gain_control(name: str, accent: str) -> tuple[QWidget, QSlider, QLabel]:
        control = QWidget()
        layout = QHBoxLayout(control)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setObjectName(f"{name}_slider")
        slider.setProperty("role", "gain")
        slider.setProperty("accent", accent)
        slider.setFixedHeight(34)
        slider.setRange(0, 100)
        readout = QLabel("0%")
        readout.setObjectName(f"{name}_value")
        readout.setProperty("role", "gain_value")
        readout.setProperty("accent", accent)
        readout.setFixedWidth(64)
        readout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slider.valueChanged.connect(lambda value: readout.setText(f"{value}%"))
        layout.addWidget(slider, 1)
        layout.addWidget(readout)
        return control, slider, readout
