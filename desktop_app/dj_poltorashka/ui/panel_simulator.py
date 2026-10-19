"""Симулятор физических органов управления."""

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
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
from dj_poltorashka.ui.theme import accent_color, create_volume_indicator, make_icon, set_accent
from dj_poltorashka.ui.fader_scale import FaderScale


class PanelSimulator:
    def __init__(self, on_event: Callable[[PanelEvent], None]):
        self._on_event = on_event
        self._panel: PanelConfiguration | None = None
        self._is_paused = False
        self._widget = QWidget()
        self._widget.setObjectName("panel_simulator")
        self._widget.setWindowTitle("Симулятор панели")
        root_layout = QVBoxLayout(self._widget)
        root_layout.setContentsMargins(14, 8, 14, 14)
        root_layout.setSpacing(12)
        heading = QLabel("Симулятор панели")
        heading.setProperty("role", "section_title")
        root_layout.addWidget(heading)

        self._status_label = QLabel("Симулятор готов")
        self._status_label.setObjectName("simulator_status")
        self._status_label.setProperty("role", "status")
        root_layout.addWidget(self._status_label)

        channels_container = QWidget()
        channels_layout = QHBoxLayout(channels_container)
        channels_layout.setContentsMargins(0, 0, 0, 0)
        channels_layout.setSpacing(12)
        self._sliders: list[QSlider] = []
        self._mute_buttons: list[QPushButton] = []
        self._volume_values: list[QLabel] = []
        self._volume_indicators: list[QProgressBar] = []
        self._volume_scales: list[FaderScale] = []
        for index in range(4):
            group = QGroupBox(f"Канал {index + 1}")
            group.setProperty("role", "channel")
            set_accent(group, index)
            group_layout = QVBoxLayout(group)
            slider = QSlider(Qt.Vertical)
            slider.setRange(0, 100)
            slider.setObjectName(f"simulator_slider_{index}")
            slider.setMinimumHeight(140)
            slider.setFixedWidth(32)
            slider.setAccessibleName(f"Громкость канала {index + 1}")
            mute_button = QPushButton("Заглушить")
            mute_button.setCheckable(True)
            mute_button.setObjectName(f"simulator_mute_{index}")
            mute_button.setIcon(make_icon("speaker", size=18))
            fader_layout = QHBoxLayout()
            fader_layout.addStretch()
            scale = FaderScale(slider)
            self._volume_scales.append(scale)
            fader_layout.addWidget(scale.widget)
            fader_layout.addWidget(slider)
            indicator = create_volume_indicator(index)
            indicator.setObjectName(f"simulator_volume_indicator_{index}")
            fader_layout.addWidget(indicator)
            fader_layout.addStretch()
            group_layout.addLayout(fader_layout, 1)
            self._volume_indicators.append(indicator)
            slider.valueChanged.connect(indicator.setValue)
            readout = QLabel("0%")
            readout.setProperty("role", "readout")
            readout.setAlignment(Qt.AlignCenter)
            group_layout.addWidget(readout)
            self._volume_values.append(readout)
            slider.valueChanged.connect(
                lambda value, label=readout: label.setText(f"{value}%")
            )
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
        root_layout.addWidget(channels_container, 1)

        sounds_container = QWidget()
        sounds_layout = QGridLayout(sounds_container)
        sounds_layout.setContentsMargins(0, 0, 0, 0)
        sounds_layout.setSpacing(10)
        self._sound_buttons: list[QPushButton] = []
        for index in range(8):
            button = QPushButton(f"Кнопка {index + 1}")
            button.setObjectName(f"simulator_sound_{index}")
            button.setProperty("role", "pad")
            set_accent(button, index)
            button.setIcon(make_icon("music", accent_color(index), 22))
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
        presets_layout.setContentsMargins(0, 0, 0, 0)
        self._preset_buttons: list[QPushButton] = []
        for index in range(3):
            button = QPushButton(f"Пресет {index + 1}")
            button.setObjectName(f"simulator_preset_{index}")
            button.setIcon(make_icon("download", size=18))
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
    def widget(self) -> QWidget:
        return self._widget

    def render(self, panel: PanelConfiguration) -> None:
        self._panel = panel
        blockers = [
            QSignalBlocker(control)
            for control in (*self._sliders, *self._mute_buttons)
        ]
        for index, channel in enumerate(panel.channels):
            self._sliders[index].setValue(round(channel.volume * 100))
            self._volume_values[index].setText(f"{self._sliders[index].value()}%")
            self._volume_indicators[index].setValue(self._sliders[index].value())
            self._mute_buttons[index].setChecked(channel.muted)
            self._mute_buttons[index].setText("Включить звук" if channel.muted else "Заглушить")
            icon_name = "microphone" if channel.channel_kind == "microphone" else "speaker"
            self._mute_buttons[index].setIcon(make_icon(f"{icon_name}_muted" if channel.muted else icon_name, size=18))
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
            self._volume_indicators[index].setEnabled(enabled)
            self._mute_buttons[index].setEnabled(enabled)
        for index, button in enumerate(self._sound_buttons):
            sound_is_assigned = (
                self._panel is not None
                and self._panel.sound_buttons[index].sound_id is not None
            )
            button.setEnabled(sound_is_assigned and not self._is_paused)
        for button in self._preset_buttons:
            button.setEnabled(not self._is_paused)
