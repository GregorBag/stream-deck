"""Главное окно редактора активной конфигурации."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.configuration.models import ChannelKind, StoredConfiguration
from dj_poltorashka.ui.channel_card import ChannelCard
from dj_poltorashka.ui.preset_card import PresetCard
from dj_poltorashka.ui.sound_button import SoundButton


@dataclass(frozen=True)
class MainWindowCallbacks:
    channel_kind_changed: Callable[[int, ChannelKind], None]
    application_requested: Callable[[int], None]
    volume_changed: Callable[[int, float], None]
    mute_toggled: Callable[[int], None]
    sound_import_requested: Callable[[int], None]
    sound_clear_requested: Callable[[int], None]
    save_preset_requested: Callable[[], None]
    load_preset_requested: Callable[[int], None]


class MainWindow:
    def __init__(self, callbacks: MainWindowCallbacks):
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("Перед созданием окна требуется QApplication")
        application.setQuitOnLastWindowClosed(False)

        self._widget = QMainWindow()
        self._widget.setObjectName("main_window")
        self._widget.setWindowTitle("DJ Poltorashka")
        central_widget = QWidget()
        root_layout = QHBoxLayout(central_widget)
        self._widget.setCentralWidget(central_widget)

        active_group = QGroupBox("Активная настройка")
        active_group.setObjectName("active_configuration")
        active_layout = QVBoxLayout(active_group)
        self._virtual_microphone_status = QLabel(
            "Виртуальный микрофон: состояние ещё не определено"
        )
        self._virtual_microphone_status.setObjectName("virtual_microphone_status")
        active_layout.addWidget(self._virtual_microphone_status)
        save_button = QPushButton("Сохранить в пресет")
        save_button.setObjectName("save_preset_button")
        save_button.clicked.connect(callbacks.save_preset_requested)
        active_layout.addWidget(save_button)

        channels_container = QWidget()
        channels_container.setObjectName("channels_container")
        channels_layout = QHBoxLayout(channels_container)
        self._channel_cards = tuple(
            ChannelCard(
                channel_index=index,
                on_kind_changed=callbacks.channel_kind_changed,
                on_application_requested=callbacks.application_requested,
                on_volume_changed=callbacks.volume_changed,
                on_mute_toggled=callbacks.mute_toggled,
            )
            for index in range(4)
        )
        for card in self._channel_cards:
            channels_layout.addWidget(card.widget)
        active_layout.addWidget(channels_container)

        sounds_container = QWidget()
        sounds_container.setObjectName("sounds_container")
        sounds_layout = QGridLayout(sounds_container)
        self._sound_buttons = tuple(
            SoundButton(
                button_index=index,
                on_import_requested=callbacks.sound_import_requested,
                on_clear_requested=callbacks.sound_clear_requested,
            )
            for index in range(8)
        )
        for index, button in enumerate(self._sound_buttons):
            sounds_layout.addWidget(button.widget, index // 4, index % 4)
        active_layout.addWidget(sounds_container)
        root_layout.addWidget(active_group, 1)

        presets_container = QWidget()
        presets_container.setObjectName("presets_container")
        presets_layout = QVBoxLayout(presets_container)
        self._preset_cards = tuple(
            PresetCard(index, callbacks.load_preset_requested)
            for index in range(3)
        )
        for card in self._preset_cards:
            presets_layout.addWidget(card.widget)
        root_layout.addWidget(presets_container)

    @property
    def widget(self) -> QMainWindow:
        return self._widget

    def render(
        self,
        stored: StoredConfiguration,
        audio_states: tuple[ChannelAudioUpdate, ...] = (),
    ) -> None:
        states_by_index = {
            state.channel_index: state
            for state in audio_states
        }
        for index, (card, channel) in enumerate(
            zip(
                self._channel_cards,
                stored.active.channels,
                strict=True,
            )
        ):
            card.render(channel, states_by_index.get(index))
        for button, sound in zip(
            self._sound_buttons,
            stored.active.sound_buttons,
            strict=True,
        ):
            button.render(sound)
        for card, preset in zip(
            self._preset_cards,
            stored.presets,
            strict=True,
        ):
            card.render(preset)

    def show(self) -> None:
        self._widget.show()

    def set_virtual_microphone_status(self, state: AudioRoutingStatus) -> None:
        self._virtual_microphone_status.setText(
            f"Виртуальный микрофон: {state.message}"
        )

    def activate(self) -> None:
        if self._widget.isMinimized():
            state = self._widget.windowState() & ~Qt.WindowMinimized
            self._widget.setWindowState(state)
        self._widget.show()
        self._widget.raise_()
        self._widget.activateWindow()

    def hide(self) -> None:
        self._widget.hide()

    def is_visible(self) -> bool:
        return self._widget.isVisible()
