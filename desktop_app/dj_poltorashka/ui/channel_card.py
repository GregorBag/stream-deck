"""Карточка назначения одного канала микшера."""

from collections.abc import Callable

from pathlib import PureWindowsPath

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.configuration.models import ChannelKind, MixerChannelConfig
from dj_poltorashka.ui.theme import create_volume_indicator, make_icon, set_accent


_CHANNEL_OPTIONS: tuple[tuple[str, ChannelKind], ...] = (
    ("Не назначен", "unassigned"),
    ("Общая громкость", "master"),
    ("Программа", "application"),
    ("Микрофон", "microphone"),
)


class ChannelCard:
    def __init__(
        self,
        channel_index: int,
        on_kind_changed: Callable[[int, ChannelKind], None],
        on_application_requested: Callable[[int], None],
        on_volume_changed: Callable[[int, float], None],
        on_mute_toggled: Callable[[int], None],
    ):
        self._channel_index = channel_index
        self._widget = QGroupBox(f"Канал {channel_index + 1}")
        self._widget.setObjectName(f"channel_card_{channel_index}")
        self._widget.setProperty("role", "channel")
        set_accent(self._widget, channel_index)
        self._widget.setMinimumWidth(175)
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self._name_label = QLabel("Не назначен")
        self._name_label.setObjectName(f"channel_name_{channel_index}")
        self._name_label.setProperty("role", "card_name")
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        self._kind_combo = QComboBox()
        self._kind_combo.setObjectName(f"channel_kind_{channel_index}")
        for title, channel_kind in _CHANNEL_OPTIONS:
            self._kind_combo.addItem(title, channel_kind)
        layout.addWidget(self._kind_combo)

        self._status_label = QLabel("")
        self._status_label.setObjectName(f"channel_status_{channel_index}")
        self._status_label.setProperty("role", "muted")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._application_button = QPushButton("Выбрать программу")
        self._application_button.setObjectName(
            f"application_button_{channel_index}"
        )
        self._application_button.setProperty("role", "compact")
        self._application_button.setIcon(make_icon("app", size=16))
        layout.addWidget(self._application_button)

        fader_layout = QHBoxLayout()
        scale_layout = QVBoxLayout()
        for value in (100, 75, 50, 25, 0):
            mark = QLabel(str(value))
            mark.setProperty("role", "muted")
            scale_layout.addWidget(mark, alignment=Qt.AlignRight)
            if value:
                scale_layout.addStretch()
        fader_layout.addStretch()
        fader_layout.addLayout(scale_layout)
        self._volume_slider = QSlider(Qt.Vertical)
        self._volume_slider.setObjectName(f"volume_slider_{channel_index}")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setMinimumHeight(112)
        self._volume_slider.setFixedWidth(32)
        self._volume_slider.setAccessibleName(f"Громкость канала {channel_index + 1}")
        fader_layout.addWidget(self._volume_slider)
        self._volume_indicator = create_volume_indicator(channel_index)
        self._volume_indicator.setObjectName(f"volume_indicator_{channel_index}")
        fader_layout.addWidget(self._volume_indicator)
        fader_layout.addStretch()
        layout.addLayout(fader_layout, 1)
        self._volume_value = QLabel("0%")
        self._volume_value.setObjectName(f"volume_value_{channel_index}")
        self._volume_value.setProperty("role", "readout")
        self._volume_value.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._volume_value)

        self._mute_button = QPushButton("Заглушить")
        self._mute_button.setObjectName(f"mute_button_{channel_index}")
        self._mute_button.setCheckable(True)
        self._mute_button.setIcon(make_icon("speaker", size=18))
        layout.addWidget(self._mute_button)

        self._kind_combo.currentIndexChanged.connect(
            lambda _: on_kind_changed(
                self._channel_index,
                self._kind_combo.currentData(),
            )
        )
        self._application_button.clicked.connect(
            lambda: on_application_requested(self._channel_index)
        )
        self._volume_slider.valueChanged.connect(
            lambda value: self._volume_value.setText(f"{value}%")
        )
        self._volume_slider.valueChanged.connect(self._volume_indicator.setValue)
        self._volume_slider.valueChanged.connect(
            lambda value: on_volume_changed(self._channel_index, value / 100.0)
        )
        self._mute_button.clicked.connect(
            lambda: on_mute_toggled(self._channel_index)
        )

    @property
    def widget(self) -> QGroupBox:
        return self._widget

    def render(
        self,
        channel: MixerChannelConfig,
        audio_state: ChannelAudioUpdate | None = None,
    ) -> None:
        blockers = (
            QSignalBlocker(self._kind_combo),
            QSignalBlocker(self._volume_slider),
            QSignalBlocker(self._mute_button),
        )
        self._kind_combo.setCurrentIndex(
            self._kind_combo.findData(channel.channel_kind)
        )
        display_name = self._display_name(channel)
        if audio_state is not None and audio_state.display_name is not None:
            display_name = audio_state.display_name
        self._name_label.setText(display_name)
        self._name_label.setToolTip(display_name)
        status_text = self._status_text(audio_state)
        self._status_label.setText(status_text)
        self._status_label.setVisible(bool(status_text))
        self._volume_slider.setValue(round(channel.volume * 100))
        self._volume_value.setText(f"{self._volume_slider.value()}%")
        self._volume_indicator.setValue(self._volume_slider.value())
        self._mute_button.setChecked(channel.muted)
        self._mute_button.setText("Включить звук" if channel.muted else "Заглушить")

        is_assigned = channel.channel_kind != "unassigned"
        self._volume_slider.setEnabled(is_assigned)
        self._volume_indicator.setEnabled(is_assigned)
        self._mute_button.setEnabled(is_assigned)
        self._application_button.setEnabled(channel.channel_kind == "application")
        del blockers

    @staticmethod
    def _status_text(audio_state: ChannelAudioUpdate | None) -> str:
        if audio_state is None:
            return ""
        return {
            "active": "Активно",
            "waiting": "Ожидание программы",
            "unavailable": "Временно недоступно",
        }[audio_state.availability]

    @staticmethod
    def _display_name(channel: MixerChannelConfig) -> str:
        if channel.display_name is not None:
            return channel.display_name
        if channel.channel_kind == "application" and channel.application_path:
            return PureWindowsPath(channel.application_path).stem
        return {
            "unassigned": "Не назначен",
            "master": "Общая громкость",
            "microphone": "Микрофон",
        }.get(channel.channel_kind, "Программа")
