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
from dj_poltorashka.ui.theme import accent_color, make_icon, set_accent


class PresetCard:
    def __init__(
        self,
        preset_index: int,
        on_load_requested: Callable[[int], None],
        on_edit_requested: Callable[[int], None],
    ):
        self._preset_index = preset_index
        self._widget = QGroupBox()
        self._widget.setObjectName(f"preset_card_{preset_index}")
        self._widget.setProperty("role", "preset")
        set_accent(self._widget, preset_index + 1)
        layout = QVBoxLayout(self._widget)
        layout.setSpacing(10)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"Пресет {preset_index + 1}")
        title.setObjectName(f"preset_title_{preset_index}")
        title.setProperty("role", "muted")
        header_layout.addWidget(title)
        header_layout.addStretch()
        badge = QLabel()
        badge.setPixmap(make_icon("panel", accent_color(preset_index + 1), 26).pixmap(26, 26))
        header_layout.addWidget(badge)
        self._load_button = QPushButton("Загрузить")
        self._load_button.setObjectName(f"preset_load_{preset_index}")
        self._load_button.setProperty("role", "primary")
        self._load_button.setIcon(make_icon("download", "#fff0fc", 17))
        self._edit_button = QPushButton("Редактировать")
        self._edit_button.setObjectName(f"preset_edit_{preset_index}")
        self._edit_button.setIcon(make_icon("edit", size=16))
        self._edit_button.setToolTip("Редактировать пресет")
        layout.addWidget(header)

        self._name_label = QLabel("Пусто")
        self._name_label.setObjectName(f"preset_name_{preset_index}")
        self._name_label.setProperty("role", "card_name")
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        self._summary_label = QLabel("Нет сохранённой настройки")
        self._summary_label.setObjectName(f"preset_summary_{preset_index}")
        self._summary_label.setWordWrap(True)
        self._summary_label.setProperty("role", "muted")
        layout.addWidget(self._summary_label)
        layout.addStretch()
        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(self._load_button)
        actions.addWidget(self._edit_button)
        layout.addLayout(actions)

        self._load_button.clicked.connect(
            lambda: on_load_requested(self._preset_index)
        )
        self._edit_button.clicked.connect(
            lambda: on_edit_requested(self._preset_index)
        )

    @property
    def widget(self) -> QGroupBox:
        return self._widget

    def render(self, preset: PresetConfig | None) -> None:
        if preset is None:
            self._name_label.setText("Пусто")
            self._summary_label.setText("Нет сохранённой настройки")
            self._load_button.setEnabled(False)
            self._edit_button.setEnabled(False)
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
        self._edit_button.setEnabled(True)
