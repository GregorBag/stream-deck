"""Значок приложения и команды системного трея."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QStyle,
    QSystemTrayIcon,
)


@dataclass(frozen=True)
class TrayCallbacks:
    open_main: Callable[[], None]
    open_simulator: Callable[[], None]
    open_settings: Callable[[], None]
    exit_application: Callable[[], None]


class TrayController:
    def __init__(self, callbacks: TrayCallbacks):
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("Перед созданием трея требуется QApplication")

        icon = application.style().standardIcon(QStyle.SP_MediaVolume)
        self._icon = QSystemTrayIcon(icon)
        self._icon.setToolTip("DJ Poltorashka")
        self._menu = QMenu()
        self._menu.addAction("Открыть", callbacks.open_main)
        self._menu.addAction("Симулятор панели", callbacks.open_simulator)
        self._menu.addAction("Настройки", callbacks.open_settings)
        self._menu.addSeparator()
        self._menu.addAction("Выход", callbacks.exit_application)
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(
            lambda reason: self._handle_activation(reason, callbacks.open_main)
        )

    @property
    def icon(self) -> QSystemTrayIcon:
        return self._icon

    @property
    def menu(self) -> QMenu:
        return self._menu

    def is_available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def show_message(self, title: str, message: str) -> None:
        self._icon.showMessage(title, message)

    @staticmethod
    def _handle_activation(
        reason: QSystemTrayIcon.ActivationReason,
        open_main: Callable[[], None],
    ) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            open_main()
