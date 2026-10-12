"""Карточка одного слота пресета."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dj_poltorashka.configuration.models import PresetConfig


class PresetCard:
    def __init__(
        self,
        preset_index: int,
        on_load_requested: Callable[[int], None],
    ):
        self._preset_index = preset_index
        self._widget = QGroupBox()
        self._widget.setObjectName(f"preset_card_{preset_index}")
        layout = QVBoxLayout(self._widget)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"Пресет {preset_index + 1}")
        title.setObjectName(f"preset_title_{preset_index}")
        header_layout.addWidget(title)
        self._load_button = QPushButton("Загрузить")
        self._load_button.setObjectName(f"preset_load_{preset_index}")
        header_layout.addWidget(self._load_button)
        layout.addWidget(header)

        self._name_label = QLabel("Пусто")
        self._name_label.setObjectName(f"preset_name_{preset_index}")
        layout.addWidget(self._name_label)

        self._summary_label = QLabel("Нет сохранённой настройки")
        self._summary_label.setObjectName(f"preset_summary_{preset_index}")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        self._load_button.clicked.connect(
            lambda: on_load_requested(self._preset_index)
        )

    @property
    def widget(self) -> QGroupBox:
        return self._widget

    def render(self, preset: PresetConfig | None) -> None:
        if preset is None:
            self._name_label.setText("Пусто")
            self._summary_label.setText("Нет сохранённой настройки")
            self._load_button.setEnabled(False)
            return

        assigned_channels = sum(
            channel.channel_kind != "unassigned"
            for channel in preset.panel.channels
        )
        assigned_sounds = sum(
            button.sound_id is not None
            for button in preset.panel.sound_buttons
        )
        self._name_label.setText(preset.name)
        self._summary_label.setText(
            f"Каналов: {assigned_channels}; звуков: {assigned_sounds}"
        )
        self._load_button.setEnabled(True)
