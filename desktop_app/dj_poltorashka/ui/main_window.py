"""Главное окно редактора активной конфигурации."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.configuration.models import ChannelKind, StoredConfiguration
from dj_poltorashka.ui.channel_card import ChannelCard
from dj_poltorashka.ui.brand_header import create_brand_header
from dj_poltorashka.ui.preset_card import PresetCard
from dj_poltorashka.ui.sound_button import SoundButton
from dj_poltorashka.ui.theme import apply_theme, make_icon


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
    edit_preset_requested: Callable[[int], None]


class MainWindow:
    def __init__(self, callbacks: MainWindowCallbacks):
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("Перед созданием окна требуется QApplication")
        application.setQuitOnLastWindowClosed(False)
        apply_theme(application)

        self._widget = QMainWindow()
        self._widget.setObjectName("main_window")
        self._widget.setWindowTitle("DJ Poltorashka")
        self._widget.resize(1280, 900)
        self._widget.setMinimumSize(880, 620)
        shell = QWidget()
        shell.setObjectName("main_shell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(14, 14, 14, 0)
        shell_layout.setSpacing(12)
        shell_layout.addWidget(create_brand_header())
        central_widget = QWidget()
        central_widget.setObjectName("configuration_page")
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 12)
        root_layout.setSpacing(14)
        self._tabs = QTabWidget()
        self._refresh_settings: Callable[[], None] | None = None
        self._tabs.setObjectName("main_tabs")
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._tabs.setIconSize(QSize(22, 22))
        self._tabs.addTab(self._scroll_page(central_widget), make_icon("sliders"), "Конфигурация")
        shell_layout.addWidget(self._tabs, 1)
        self._widget.setCentralWidget(shell)
        self._widget.statusBar().showMessage("DJ POLTORASHKA  /  CAT CLUB")

        active_group = QGroupBox("Активная настройка")
        active_group.setObjectName("active_configuration")
        active_layout = QVBoxLayout(active_group)
        active_layout.setSpacing(10)
        self._virtual_microphone_status = QLabel(
            "Виртуальный микрофон: состояние ещё не определено"
        )
        self._virtual_microphone_status.setObjectName("virtual_microphone_status")
        self._virtual_microphone_status.setProperty("role", "status")
        self._virtual_microphone_status.setWordWrap(True)
        active_toolbar = QHBoxLayout()
        active_toolbar.addWidget(self._virtual_microphone_status, 1)
        save_button = QPushButton("Сохранить в пресет")
        save_button.setObjectName("save_preset_button")
        save_button.setProperty("role", "primary")
        save_button.setIcon(make_icon("save", "#fff0fc", 18))
        save_button.clicked.connect(callbacks.save_preset_requested)
        active_toolbar.addWidget(save_button, alignment=Qt.AlignTop)
        active_layout.addLayout(active_toolbar)

        channels_container = QWidget()
        channels_container.setObjectName("channels_container")
        channels_layout = QHBoxLayout(channels_container)
        channels_layout.setContentsMargins(0, 0, 0, 0)
        channels_layout.setSpacing(10)
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
        active_layout.addWidget(channels_container, 1)

        sounds_container = QWidget()
        sounds_container.setObjectName("sounds_container")
        sounds_layout = QGridLayout(sounds_container)
        sounds_layout.setContentsMargins(0, 0, 0, 0)
        sounds_layout.setSpacing(10)
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
        presets_container.setMinimumWidth(265)
        presets_container.setMaximumWidth(310)
        presets_layout = QVBoxLayout(presets_container)
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_layout.setSpacing(12)
        self._preset_cards = tuple(
            PresetCard(
                index,
                callbacks.load_preset_requested,
                callbacks.edit_preset_requested,
            )
            for index in range(3)
        )
        for card in self._preset_cards:
            presets_layout.addWidget(card.widget, 1)
        presets_panel = QWidget()
        presets_panel.setObjectName("presets_panel")
        sidebar = QVBoxLayout(presets_panel)
        sidebar.setContentsMargins(12, 14, 12, 12)
        heading = QLabel("Пресеты")
        heading.setProperty("role", "section_title")
        sidebar.addWidget(heading)
        sidebar.addWidget(presets_container, 1)
        root_layout.addWidget(presets_panel)

    @property
    def widget(self) -> QMainWindow:
        return self._widget

    def add_panel_pages(
        self,
        simulator: QWidget,
        settings: QWidget,
        refresh_settings: Callable[[], None],
    ) -> None:
        self._tabs.addTab(self._scroll_page(simulator), make_icon("panel"), "Симулятор панели")
        self._tabs.addTab(self._scroll_page(settings), make_icon("settings"), "Настройки")
        self._refresh_settings = refresh_settings
        self._tabs.currentChanged.connect(self._refresh_page)

    @staticmethod
    def _scroll_page(page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def show_page(
        self,
        page: Literal["configuration", "simulator", "settings"],
    ) -> None:
        index = ("configuration", "simulator", "settings").index(page)
        self.activate()
        if self._tabs.currentIndex() == index:
            self._refresh_page(index)
        else:
            self._tabs.setCurrentIndex(index)

    def _refresh_page(self, index: int) -> None:
        if index == 2 and self._refresh_settings is not None:
            self._refresh_settings()

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
        self._widget.statusBar().showMessage(f"Виртуальный микрофон: {state.message}")

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
