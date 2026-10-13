import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QSlider
from pytestqt.qtbot import QtBot

import dj_poltorashka.application.bootstrap as bootstrap
from dj_poltorashka.audio.models import AudioTargetSnapshot


class FakeAudioBackend:
    def read_target(self, target) -> AudioTargetSnapshot:
        return AudioTargetSnapshot(())

    def write_target(self, target, volume: float, muted: bool) -> None:
        return None


class FakeSoundPlayerFactory:
    pass


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
