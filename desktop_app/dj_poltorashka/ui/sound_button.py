"""Карточка одной программируемой звуковой кнопки."""

from collections.abc import Callable

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from dj_poltorashka.configuration.models import SoundButtonConfig
from dj_poltorashka.ui.theme import make_icon, set_accent


class SoundButton:
    def __init__(
        self,
        button_index: int,
        on_import_requested: Callable[[int], None],
        on_clear_requested: Callable[[int], None],
    ):
        self._button_index = button_index
        self._widget = QGroupBox()
        self._widget.setObjectName(f"sound_button_{button_index}")
        self._widget.setProperty("role", "sound")
        set_accent(self._widget, button_index)
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        heading = QHBoxLayout()
        paw = QLabel()
        paw.setPixmap(make_icon("paw", "#efb4ea", 20).pixmap(20, 20))
        heading.addWidget(paw)
        layout.addLayout(heading)

        self._name_label = QLabel("Пусто")
        self._name_label.setObjectName(f"sound_name_{button_index}")
        self._name_label.setProperty("role", "card_name")
        self._name_label.setWordWrap(True)
        heading.insertWidget(0, self._name_label, 1)

        self._import_button = QPushButton("Импортировать")
        self._import_button.setObjectName(f"sound_import_{button_index}")
        self._import_button.setProperty("role", "compact")
        self._import_button.setIcon(make_icon("plus", size=14))

        self._clear_button = QPushButton()
        self._clear_button.setToolTip("Очистить звук")
        self._clear_button.setAccessibleName("Очистить звук")
        self._clear_button.setObjectName(f"sound_clear_{button_index}")
        self._clear_button.setProperty("role", "compact")
        self._clear_button.setIcon(make_icon("close", size=14))
        self._clear_button.setFixedWidth(30)
        layout.addStretch()
        actions = QHBoxLayout()
        actions.setSpacing(5)
        actions.addWidget(self._import_button)
        actions.addWidget(self._clear_button)
        layout.addLayout(actions)

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
        self._name_label.setToolTip(sound.display_name or "Звук не назначен")
        self._import_button.setText("Заменить" if is_assigned else "Импортировать")
        self._clear_button.setEnabled(is_assigned)
