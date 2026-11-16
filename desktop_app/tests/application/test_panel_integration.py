from dataclasses import replace
from types import SimpleNamespace

from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton

import dj_poltorashka.application.bootstrap as bootstrap
from dj_poltorashka.panel.protocol import StreamDecoder, LedUpdate
from dj_poltorashka.panel.transport import EMULATOR_PORT, EmulatedPanelTransport, PanelPort
from dj_poltorashka.panel.worker import PanelCoordinator
from test_bootstrap import (
    RecordingAudioBackend, RecordingAudioCoordinator, RecordingAudioService,
    RecordingDeviceRegistry, RecordingRoutingService,
)


def build_running(qtbot, tmp_path, monkeypatch):
    transports = []
    class RecordingTransport(EmulatedPanelTransport):
        def __init__(self):
            super().__init__()
            self.sent = []
        def write(self, data):
            self.sent.append(data)
            return super().write(data)
    def factory(name):
        transport = RecordingTransport()
        transports.append(transport)
        return transport
    def coordinator(on_events, on_status):
        return PanelCoordinator(on_events, on_status, factory=factory, port_provider=lambda: (PanelPort(EMULATOR_PORT, "Имитатор платы"),), poll_interval_ms=5)
    monkeypatch.setattr(bootstrap, "WindowsAutostart", lambda *args: SimpleNamespace(is_enabled=lambda: False))
    monkeypatch.setattr(bootstrap, "QtAudioDeviceRegistry", RecordingDeviceRegistry)
    monkeypatch.setattr(bootstrap, "AudioRoutingService", RecordingRoutingService)
    monkeypatch.setattr(bootstrap, "PanelCoordinator", coordinator)
    monkeypatch.setattr(bootstrap, "WindowsAudioBackend", RecordingAudioBackend)
    monkeypatch.setattr(bootstrap, "AudioService", RecordingAudioService)
    monkeypatch.setattr(bootstrap, "AudioCoordinator", RecordingAudioCoordinator)
    running = bootstrap.build_application(tmp_path)
    running.controller.start(background=True, draft_available=False)
    return running, transports


def connect_emulator(qtbot, running):
    dialog = running.settings_dialog
    dialog.refresh()
    combo = dialog.widget.findChild(QComboBox, "panel_port_combo")
    qtbot.waitUntil(lambda: combo.findData(EMULATOR_PORT) >= 0)
    combo.setCurrentIndex(combo.findData(EMULATOR_PORT))
    dialog.widget.findChild(QPushButton, "connect_panel_button").click()
    qtbot.waitUntil(lambda: running.panel_coordinator.status.code == "connected")


def test_gui_emulator_buttons_route_once_and_lighting_follows_mute(qtbot, tmp_path, monkeypatch):
    running, transports = build_running(qtbot, tmp_path, monkeypatch)
    try:
        connect_emulator(qtbot, running)
        qtbot.waitUntil(lambda: running.panel_coordinator.latest_state is not None)
        assert running.panel_coordinator.latest_state.sliders == (0, 0, 0, 0)
        assert running.configuration_service.stored_configuration.active.channels[0].volume == 1.0
        button = running.simulator.widget.findChild(QPushButton, "simulator_mute_0")
        assert not running.configuration_service.stored_configuration.active.channels[0].muted
        button.click()
        qtbot.waitUntil(lambda: running.configuration_service.stored_configuration.active.channels[0].muted)
        qtbot.waitUntil(lambda: any(data.startswith(b"LEDS ") for data in transports[0].sent))
        def latest_led():
            values = [message for data in transports[0].sent for message in StreamDecoder().feed(data).messages if isinstance(message, LedUpdate)]
            return values[-1] if values else None
        qtbot.waitUntil(lambda: latest_led() is not None and latest_led().colors[16] == (128, 0, 0))
        assert button.isChecked()
        running.settings_dialog.widget.findChild(QPushButton, "disconnect_panel_button").click()
        qtbot.waitUntil(lambda: running.panel_coordinator.status.code == "disconnected")
    finally:
        running.close()
    assert not running.panel_coordinator.is_running


def test_color_save_updates_transport_and_fourth_preset_button_uses_protocol(qtbot, tmp_path, monkeypatch):
    running, transports = build_running(qtbot, tmp_path, monkeypatch)
    try:
        panel = running.configuration_service.stored_configuration.active
        running.configuration_service.replace_active(replace(panel, channels=(replace(panel.channels[0], volume=0.2), *panel.channels[1:])))
        running.configuration_service.save_active_to_preset(4, "Четвёртый")
        running.configuration_service.replace_active(panel)
        running.configuration_service.save_active_to_preset(1, "Первый")
        connect_emulator(qtbot, running)
        dialog = running.settings_dialog
        dialog.widget.findChild(QLineEdit, "lighting_perimeter").setText("#204060")
        dialog.widget.findChild(QPushButton, "save_lighting_button").click()
        def has_color():
            return any(isinstance(message, LedUpdate) and message.colors[0] == (16, 32, 48) for data in transports[0].sent for message in StreamDecoder().feed(data).messages)
        qtbot.waitUntil(has_color)
        running.simulator.widget.findChild(QPushButton, "simulator_preset_3").click()
        qtbot.waitUntil(lambda: running.configuration_service.stored_configuration.active_preset_slot == 4)
        assert running.configuration_service.stored_configuration.active.channels[0].volume == 0.2
        assert running.configuration_service.stored_configuration.presets[0].panel == panel
    finally:
        running.close()



def test_playback_callbacks_update_programmable_button_lighting(qtbot, tmp_path, monkeypatch):
    from pathlib import Path
    from dj_poltorashka.configuration.models import SoundButtonConfig
    from test_bootstrap import RecordingSoundPlayback, RecordingSoundPlayerFactory
    monkeypatch.setattr(bootstrap, "SoundPlaybackService", RecordingSoundPlayback)
    monkeypatch.setattr(bootstrap, "QtSoundPlayerFactory", RecordingSoundPlayerFactory)
    running, transports = build_running(qtbot, tmp_path, monkeypatch)
    try:
        panel = running.configuration_service.stored_configuration.active
        running.configuration_service.replace_active(replace(panel, sound_buttons=(SoundButtonConfig("intro.wav", "Заставка"), *panel.sound_buttons[1:])))
        connect_emulator(qtbot, running)
        def last_button_color():
            values = [message for data in transports[0].sent for message in StreamDecoder().feed(data).messages if isinstance(message, LedUpdate)]
            return values[-1].colors[8] if values else None
        running.sound_playback.on_started(0, Path("intro.wav"))
        qtbot.waitUntil(lambda: last_button_color() == (28, 108, 122))
        running.sound_playback.on_finished(0)
        qtbot.waitUntil(lambda: last_button_color() == (11, 42, 48))
        running.sound_playback.on_started(0, Path("intro.wav"))
        qtbot.waitUntil(lambda: last_button_color() == (28, 108, 122))
        running.sound_playback.on_error(0, "failed")
        qtbot.waitUntil(lambda: last_button_color() == (11, 42, 48))
    finally:
        running.close()
