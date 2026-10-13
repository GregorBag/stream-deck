import pytest
from PySide6.QtWidgets import QSystemTrayIcon
from pytestqt.qtbot import QtBot

from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.ui.tray_controller import TrayController, TrayCallbacks


class CallbackRecorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def callbacks(self) -> TrayCallbacks:
        return TrayCallbacks(
            open_main=lambda: self.calls.append("open_main"),
            open_simulator=lambda: self.calls.append("open_simulator"),
            open_settings=lambda: self.calls.append("open_settings"),
            exit_application=lambda: self.calls.append("exit_application"),
        )


def test_is_available_delegates_to_qt(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        QSystemTrayIcon,
        "isSystemTrayAvailable",
        lambda: True,
    )
    tray = TrayController(CallbackRecorder().callbacks())

    assert tray.is_available()


def test_tray_menu_contains_actions_and_forwards_callbacks(qtbot: QtBot) -> None:
    recorder = CallbackRecorder()
    tray = TrayController(recorder.callbacks())
    action_by_text = {
        action.text(): action
        for action in tray.menu.actions()
        if not action.isSeparator()
    }

    assert list(action_by_text) == [
        "Открыть",
        "Симулятор панели",
        "Настройки",
        "Выход",
    ]

    for action in action_by_text.values():
        action.trigger()

    assert recorder.calls == [
        "open_main",
        "open_simulator",
        "open_settings",
        "exit_application",
    ]


def test_tray_icon_primary_activation_opens_main_window(qtbot: QtBot) -> None:
    recorder = CallbackRecorder()
    tray = TrayController(recorder.callbacks())

    tray.icon.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)

    assert recorder.calls == ["open_main"]


def test_show_message_forwards_title_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QSystemTrayIcon,
        "showMessage",
        lambda self, title, message: calls.append((title, message)),
    )
    tray = TrayController(CallbackRecorder().callbacks())

    tray.show_message("Ошибка", "Не удалось сохранить")

    assert calls == [("Ошибка", "Не удалось сохранить")]


def test_show_and_hide_change_icon_visibility(qtbot: QtBot) -> None:
    tray = TrayController(CallbackRecorder().callbacks())

    tray.show()
    assert tray.icon.isVisible()

    tray.hide()
    assert not tray.icon.isVisible()


def test_tray_tooltip_displays_virtual_microphone_status(qtbot: QtBot) -> None:
    tray = TrayController(CallbackRecorder().callbacks())

    tray.set_virtual_microphone_status(
        AudioRoutingStatus("active", "Виртуальный микрофон активен")
    )

    assert tray.icon.toolTip() == (
        "DJ Poltorashka — Виртуальный микрофон активен"
    )
