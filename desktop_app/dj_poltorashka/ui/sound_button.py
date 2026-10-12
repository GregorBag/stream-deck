"""Карточка одной программируемой звуковой кнопки."""

from collections.abc import Callable

from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout

from dj_poltorashka.configuration.models import SoundButtonConfig


class SoundButton:
    def __init__(
        self,
        button_index: int,
        on_import_requested: Callable[[int], None],
        on_clear_requested: Callable[[int], None],
    ):
        self._button_index = button_index
        self._widget = QGroupBox(f"Кнопка {button_index + 1}")
        self._widget.setObjectName(f"sound_button_{button_index}")
        layout = QVBoxLayout(self._widget)

        self._name_label = QLabel("Пусто")
        self._name_label.setObjectName(f"sound_name_{button_index}")
        layout.addWidget(self._name_label)

        self._import_button = QPushButton("Импортировать")
        self._import_button.setObjectName(f"sound_import_{button_index}")
        layout.addWidget(self._import_button)

        self._clear_button = QPushButton("Очистить")
        self._clear_button.setObjectName(f"sound_clear_{button_index}")
        layout.addWidget(self._clear_button)

        self._import_button.clicked.connect(
            lambda: on_import_requested(self._button_index)
        )
        self._clear_button.clicked.connect(
            lambda: on_clear_requested(self._button_index)
        )

    @property
    def widget(self) -> QGroupBox:
        return self._widget

    def render(self, sound: SoundButtonConfig) -> None:
        is_assigned = sound.sound_id is not None
        self._name_label.setText(sound.display_name or "Пусто")
        self._import_button.setText("Заменить" if is_assigned else "Импортировать")
        self._clear_button.setEnabled(is_assigned)
