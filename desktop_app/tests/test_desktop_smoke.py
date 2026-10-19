import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QComboBox, QDialog, QFrame, QSlider, QStackedWidget, QTabBar
from pytestqt.qtbot import QtBot

import dj_poltorashka.application.bootstrap as bootstrap
from dj_poltorashka.audio.models import AudioTargetSnapshot
from dj_poltorashka.audio.routing_models import AudioDeviceDescriptor


def find_qml_item(root, name):
    pending = [root]
    while pending:
        item = pending.pop()
        if item.objectName() == name:
            return item
        pending.extend(item.childItems())
    raise LookupError(name)


class FakeAudioBackend:
    def read_target(self, target) -> AudioTargetSnapshot:
        return AudioTargetSnapshot(())

    def write_target(self, target, volume: float, muted: bool) -> None:
        return None


class FakeSoundPlayerFactory:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def update_mix_gains(self) -> None:
        pass

    def update_output_devices(self) -> None:
        pass


class FakeDeviceRegistry:
    def inputs(self) -> tuple[object, ...]:
        return ()

    def outputs(self) -> tuple[object, ...]:
        return ()

    def close(self) -> None:
        pass


class FakeRoutingService:
    instances: list["FakeRoutingService"] = []

    def __init__(self, registry, settings, on_status) -> None:
        self.start_count = 0
        self.close_count = 0
        self.instances.append(self)

    def start(self) -> None:
        self.start_count += 1

    def apply(self, settings) -> None:
        pass

    def monitor_device(self):
        return None

    def cable_device(self):
        return None

    def report_pipeline_error(self, message: str) -> None:
        pass

    def report_pipeline_active(self) -> None:
        pass

    def close(self) -> None:
        self.close_count += 1


def test_tabs_and_tray_navigate_within_main_window(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap, "WindowsAudioBackend", FakeAudioBackend)
    monkeypatch.setattr(bootstrap, "QtSoundPlayerFactory", FakeSoundPlayerFactory)
    monkeypatch.setattr(bootstrap, "QtAudioDeviceRegistry", FakeDeviceRegistry)
    monkeypatch.setattr(bootstrap, "AudioRoutingService", FakeRoutingService)
    monkeypatch.setattr(bootstrap.WindowsAutostart, "is_enabled", lambda self: False)
    running = bootstrap.build_application(tmp_path)
    qtbot.addWidget(running.main_window.widget)
    try:
        running.controller.start(background=False, draft_available=False)
        tabs = running.main_window.widget.findChild(QTabBar, "main_navigation")
        pages = running.main_window.widget.findChild(QStackedWidget, "main_pages")
        assert tabs is not None
        assert pages is not None
        header = running.main_window.widget.findChild(QFrame, "brand_header")
        assert header.findChild(QTabBar) is tabs
        assert [tabs.tabText(index) for index in range(tabs.count())] == [
            "Конфигурация", "Симулятор панели", "Настройки",
        ]
        assert tabs.currentIndex() == 0
        assert not running.simulator.widget.isWindow()
        assert not running.settings_dialog.widget.isWindow()

        qtbot.mouseClick(
            tabs, Qt.LeftButton, pos=tabs.tabRect(1).center(),
        )
        assert running.simulator.widget.isVisible()
        slider = running.simulator.widget.findChild(QSlider, "simulator_slider_0")
        slider.setValue(42)

        qtbot.mouseClick(
            tabs, Qt.LeftButton, pos=tabs.tabRect(2).center(),
        )
        assert running.settings_dialog.widget.isVisible()
        combo = running.settings_dialog.widget.findChild(
            QComboBox, "input_device_combo",
        )
        assert combo.itemText(0) == "Системное устройство"

        for action, expected_index in zip(
            running.tray.menu.actions()[:3], (0, 1, 2), strict=True,
        ):
            running.main_window.widget.showMinimized()
            running.main_window.hide()
            action.trigger()
            assert running.main_window.is_visible()
            assert not running.main_window.widget.isMinimized()
            assert tabs.currentIndex() == expected_index
            assert pages.currentIndex() == expected_index

        running.main_window.hide()
        monkeypatch.setattr(
            FakeDeviceRegistry, "inputs",
            lambda self: (AudioDeviceDescriptor("new-mic", "Новый микрофон"),),
        )
        running.tray.menu.actions()[2].trigger()
        assert running.settings_dialog.widget.isVisible()
        assert combo.findData("new-mic") >= 0

        running.controller.show_main_window()
        active = running.configuration_service.stored_configuration.active
        assert active.channels[0].volume == 0.42
        assert not running.simulator.widget.isVisible()
        assert not running.settings_dialog.widget.isVisible()
        assert tabs.currentIndex() == 0
    finally:
        running.close()


def test_desktop_configuration_round_trip(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap, "WindowsAudioBackend", FakeAudioBackend)
    monkeypatch.setattr(
        bootstrap,
        "QtSoundPlayerFactory",
        FakeSoundPlayerFactory,
    )
    FakeRoutingService.instances.clear()
    monkeypatch.setattr(bootstrap, "QtAudioDeviceRegistry", FakeDeviceRegistry)
    monkeypatch.setattr(bootstrap, "AudioRoutingService", FakeRoutingService)
    running = bootstrap.build_application(tmp_path)
    qtbot.addWidget(running.main_window.widget)
    qtbot.addWidget(running.simulator.widget)
    try:
        monkeypatch.setattr(
            running.dialogs,
            "choose_preset",
            lambda stored: (0, "Стрим"),
        )
        running.controller.start(background=False, draft_available=False)

        slider = running.simulator.widget.findChild(
            QSlider,
            "simulator_slider_0",
        )
        slider.setValue(42)
        configuration = running.main_window.widget.findChild(QQuickWidget)
        save_button = find_qml_item(configuration.rootObject(), "save_preset_button")
        position = save_button.mapToScene(QPointF(save_button.width() / 2, save_button.height() / 2)).toPoint()
        qtbot.mouseClick(configuration, Qt.LeftButton, pos=position)

        running.main_window.hide()
        assert not running.main_window.is_visible()
        running.controller.handle_instance_command("show")
        assert running.main_window.is_visible()

        saved = json.loads(
            running.paths.configuration_file.read_text(encoding="utf-8")
        )
        assert saved["active"]["channels"][0]["volume"] == 0.42
        assert saved["presets"][0]["name"] == "Стрим"
        assert saved["presets"][0]["panel"] == saved["active"]
    finally:
        running.close()

    routing = FakeRoutingService.instances[-1]
    assert routing.start_count == 1
    assert routing.close_count == 1


def test_qml_actions_work_again_after_modal_cancellation(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "WindowsAudioBackend", FakeAudioBackend)
    monkeypatch.setattr(bootstrap, "QtSoundPlayerFactory", FakeSoundPlayerFactory)
    monkeypatch.setattr(bootstrap, "QtAudioDeviceRegistry", FakeDeviceRegistry)
    monkeypatch.setattr(bootstrap, "AudioRoutingService", FakeRoutingService)
    monkeypatch.setattr(bootstrap.WindowsAutostart, "is_enabled", lambda self: False)
    running = bootstrap.build_application(tmp_path)
    qtbot.addWidget(running.main_window.widget)
    calls = []

    def cancel_modal(*args):
        dialog = QDialog(running.main_window.widget)
        QTimer.singleShot(0, dialog.reject)
        dialog.exec()
        calls.append("cancel")

    try:
        running.controller.start(background=False, draft_available=False)
        monkeypatch.setattr(running.dialogs, "choose_application_file", lambda: Path("C:/Apps/Player.exe"))
        running.controller.set_channel(0, "application")
        monkeypatch.setattr(running.dialogs, "choose_preset", lambda stored: (0, "Тест"))
        assert running.controller.save_active_to_preset()
        monkeypatch.setattr(running.dialogs, "choose_application_file", cancel_modal)
        monkeypatch.setattr(running.dialogs, "choose_sound_file", cancel_modal)
        monkeypatch.setattr(running.dialogs, "edit_preset", cancel_modal)
        original = running.configuration_service.stored_configuration
        page = running.main_window.widget.findChild(QQuickWidget)

        for name in ("application_button_0", "sound_import_0", "preset_edit_0"):
            button = find_qml_item(page.rootObject(), name)
            for _ in range(2):
                position = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
                qtbot.mouseClick(page, Qt.LeftButton, pos=position)
                qtbot.wait(10)
            assert running.configuration_service.stored_configuration == original
        assert calls == ["cancel"] * 6
    finally:
        running.close()
