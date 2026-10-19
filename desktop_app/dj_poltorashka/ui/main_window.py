"""Главное окно редактора активной конфигурации."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.configuration.models import ChannelKind, StoredConfiguration
from dj_poltorashka.ui.configuration_view import ConfigurationView
from dj_poltorashka.ui.brand_header import create_brand_header
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
        self._pages = QStackedWidget()
        self._pages.setObjectName("main_pages")
        self._navigation = QTabBar()
        self._navigation.setObjectName("main_navigation")
        self._navigation.setAccessibleName("Разделы приложения")
        self._navigation.setIconSize(QSize(18, 18))
        self._navigation.setExpanding(False)
        self._navigation.setDrawBase(False)
        self._navigation.setUsesScrollButtons(True)
        self._navigation.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._navigation.setMinimumWidth(240)
        self._navigation.currentChanged.connect(self._pages.setCurrentIndex)
        shell_layout.addWidget(create_brand_header(self._navigation))
        self._refresh_settings: Callable[[], None] | None = None
        self.configuration_view_ = ConfigurationView(callbacks, self._widget)
        self._pages.addWidget(self.configuration_view_.widget)
        self._navigation.addTab(make_icon("sliders"), "Конфигурация")
        shell_layout.addWidget(self._pages, 1)
        self._widget.setCentralWidget(shell)

    @property
    def widget(self) -> QMainWindow:
        return self._widget

    def add_panel_pages(
        self,
        simulator: QWidget,
        settings: QWidget,
        refresh_settings: Callable[[], None],
    ) -> None:
        self._pages.addWidget(self._scroll_page(simulator))
        self._navigation.addTab(make_icon("panel"), "Симулятор панели")
        self._pages.addWidget(self._scroll_page(settings))
        self._navigation.addTab(make_icon("settings"), "Настройки")
        self._refresh_settings = refresh_settings
        self._navigation.currentChanged.connect(self._refresh_page)

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
        if self._navigation.currentIndex() == index:
            self._refresh_page(index)
        else:
            self._navigation.setCurrentIndex(index)

    def _refresh_page(self, index: int) -> None:
        if index == 2 and self._refresh_settings is not None:
            self._refresh_settings()

    def render(
        self,
        stored: StoredConfiguration,
        audio_states: tuple[ChannelAudioUpdate, ...] = (),
    ) -> None:
        self.configuration_view_.render(stored, audio_states)

    def show(self) -> None:
        self._widget.show()

    def set_virtual_microphone_status(self, state: AudioRoutingStatus) -> None:
        self.configuration_view_.set_virtual_microphone_status(state)

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
