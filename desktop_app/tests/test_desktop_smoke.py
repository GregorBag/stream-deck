import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QPushButton, QSlider, QTabWidget
from pytestqt.qtbot import QtBot

import dj_poltorashka.application.bootstrap as bootstrap
from dj_poltorashka.audio.models import AudioTargetSnapshot
from dj_poltorashka.audio.routing_models import AudioDeviceDescriptor


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
        tabs = running.main_window.widget.findChild(QTabWidget)
        assert tabs is not None
        assert [tabs.tabText(index) for index in range(tabs.count())] == [
            "Конфигурация", "Симулятор панели", "Настройки",
        ]
        assert tabs.tabPosition() == QTabWidget.North
        assert tabs.currentIndex() == 0
        assert not running.simulator.widget.isWindow()
        assert not running.settings_dialog.widget.isWindow()

        qtbot.mouseClick(
            tabs.tabBar(), Qt.LeftButton, pos=tabs.tabBar().tabRect(1).center(),
        )
        assert running.simulator.widget.isVisible()
        slider = running.simulator.widget.findChild(QSlider, "simulator_slider_0")
        slider.setValue(42)

        qtbot.mouseClick(
            tabs.tabBar(), Qt.LeftButton, pos=tabs.tabBar().tabRect(2).center(),
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
        save_button = running.main_window.widget.findChild(
            QPushButton,
            "save_preset_button",
        )
        qtbot.mouseClick(save_button, Qt.LeftButton)

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
