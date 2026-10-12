"""Отдельное окно симулятора физических органов управления."""

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from dj_poltorashka.configuration.models import PanelConfiguration
from dj_poltorashka.panel.events import (
    MutePressed,
    PanelEvent,
    PanelPauseChanged,
    PresetPressed,
    SliderChanged,
    SoundPressed,
)


class PanelSimulator:
    def __init__(self, on_event: Callable[[PanelEvent], None]):
        self._on_event = on_event
        self._panel: PanelConfiguration | None = None
        self._is_paused = False
        self._widget = QDialog()
        self._widget.setObjectName("panel_simulator")
        self._widget.setWindowTitle("Симулятор панели")
        root_layout = QVBoxLayout(self._widget)

        self._status_label = QLabel("Симулятор готов")
        self._status_label.setObjectName("simulator_status")
        root_layout.addWidget(self._status_label)

        channels_container = QWidget()
        channels_layout = QHBoxLayout(channels_container)
        self._sliders: list[QSlider] = []
        self._mute_buttons: list[QPushButton] = []
        for index in range(4):
            group = QGroupBox(f"Канал {index + 1}")
            group_layout = QVBoxLayout(group)
            slider = QSlider(Qt.Vertical)
            slider.setRange(0, 100)
            slider.setObjectName(f"simulator_slider_{index}")
            mute_button = QPushButton("Mute")
            mute_button.setCheckable(True)
            mute_button.setObjectName(f"simulator_mute_{index}")
            group_layout.addWidget(slider, alignment=Qt.AlignHCenter)
            group_layout.addWidget(mute_button)
            channels_layout.addWidget(group)
            self._sliders.append(slider)
            self._mute_buttons.append(mute_button)
            slider.valueChanged.connect(
                lambda value, channel_index=index: self._on_event(
                    SliderChanged(channel_index, value / 100.0)
                )
            )
            mute_button.clicked.connect(
                lambda checked=False, channel_index=index: self._on_event(
                    MutePressed(channel_index)
                )
            )
        root_layout.addWidget(channels_container)

        sounds_container = QWidget()
        sounds_layout = QGridLayout(sounds_container)
        self._sound_buttons: list[QPushButton] = []
        for index in range(8):
            button = QPushButton(f"Кнопка {index + 1}")
            button.setObjectName(f"simulator_sound_{index}")
            button.clicked.connect(
                lambda checked=False, button_index=index: self._sound_pressed(
                    button_index
                )
            )
            sounds_layout.addWidget(button, index // 4, index % 4)
            self._sound_buttons.append(button)
        root_layout.addWidget(sounds_container)

        presets_container = QWidget()
        presets_layout = QHBoxLayout(presets_container)
        self._preset_buttons: list[QPushButton] = []
        for index in range(3):
            button = QPushButton(f"Пресет {index + 1}")
            button.setObjectName(f"simulator_preset_{index}")
            button.clicked.connect(
                lambda checked=False, preset_index=index: self._on_event(
                    PresetPressed(preset_index)
                )
            )
            presets_layout.addWidget(button)
            self._preset_buttons.append(button)
        root_layout.addWidget(presets_container)

        self._pause_checkbox = QCheckBox("Пауза")
        self._pause_checkbox.setObjectName("simulator_pause")
        self._pause_checkbox.toggled.connect(self._pause_changed)
        root_layout.addWidget(self._pause_checkbox)
        self._update_enabled_state()

    @property
    def widget(self) -> QDialog:
        return self._widget

    def render(self, panel: PanelConfiguration) -> None:
        self._panel = panel
        blockers = [
            QSignalBlocker(control)
            for control in (*self._sliders, *self._mute_buttons)
        ]
        for index, channel in enumerate(panel.channels):
            self._sliders[index].setValue(round(channel.volume * 100))
            self._mute_buttons[index].setChecked(channel.muted)
        for index, sound in enumerate(panel.sound_buttons):
            self._sound_buttons[index].setText(
                sound.display_name or f"Кнопка {index + 1}"
            )
        del blockers
        self._update_enabled_state()

    def show(self) -> None:
        self._widget.show()

    def hide(self) -> None:
        self._widget.hide()

    def is_visible(self) -> bool:
        return self._widget.isVisible()

    def set_status(self, message: str) -> None:
        self._status_label.setText(message)

    def _sound_pressed(self, button_index: int) -> None:
        self.set_status(f"Кнопка {button_index + 1} нажата")
        self._on_event(SoundPressed(button_index))

    def _pause_changed(self, is_paused: bool) -> None:
        self._is_paused = is_paused
        self._update_enabled_state()
        self._on_event(PanelPauseChanged(is_paused))

    def _update_enabled_state(self) -> None:
        for index, slider in enumerate(self._sliders):
            channel_is_assigned = (
                self._panel is not None
                and self._panel.channels[index].channel_kind != "unassigned"
            )
            enabled = channel_is_assigned and not self._is_paused
            slider.setEnabled(enabled)
            self._mute_buttons[index].setEnabled(enabled)
        for index, button in enumerate(self._sound_buttons):
            sound_is_assigned = (
                self._panel is not None
                and self._panel.sound_buttons[index].sound_id is not None
            )
            button.setEnabled(sound_is_assigned and not self._is_paused)
        for button in self._preset_buttons:
            button.setEnabled(not self._is_paused)
