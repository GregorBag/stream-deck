from PySide6.QtWidgets import QComboBox, QGroupBox, QLabel, QSlider
from pytestqt.qtbot import QtBot

from dj_poltorashka.audio.routing_models import AudioDeviceDescriptor, AudioRoutingStatus
from dj_poltorashka.audio.routing_settings import AudioRoutingSettings
from dj_poltorashka.ui.settings_dialog import SettingsDialog


class FakeController:
    def __init__(self) -> None:
        self.settings = AudioRoutingSettings("02", None, 0.4, 0.7)
        self.input_values: list[str | None] = []
        self.monitor_values: list[str | None] = []
        self.microphone_values: list[float] = []
        self.sound_values: list[float] = []

    def autostart_enabled(self) -> bool:
        return False

    def set_autostart_enabled(self, enabled: bool) -> bool:
        return enabled

    def routing_settings(self) -> AudioRoutingSettings:
        return self.settings

    def input_devices(self) -> tuple[AudioDeviceDescriptor, ...]:
        return (
            AudioDeviceDescriptor("01", "Микрофон"),
            AudioDeviceDescriptor("02", "Микрофон"),
        )

    def monitor_devices(self) -> tuple[AudioDeviceDescriptor, ...]:
        return (AudioDeviceDescriptor("10", "Наушники"),)

    def set_input_device(self, value: str | None) -> None:
        self.input_values.append(value)

    def set_monitor_device(self, value: str | None) -> None:
        self.monitor_values.append(value)

    def set_microphone_gain(self, value: float) -> None:
        self.microphone_values.append(value)

    def set_sound_gain(self, value: float) -> None:
        self.sound_values.append(value)


def make_dialog(qtbot: QtBot) -> tuple[SettingsDialog, FakeController]:
    controller = FakeController()
    dialog = SettingsDialog(controller, lambda title, message: None)
    qtbot.addWidget(dialog.widget)
    return dialog, controller


def test_dialog_builds_cyrillic_virtual_microphone_controls(qtbot: QtBot) -> None:
    dialog, controller = make_dialog(qtbot)

    dialog.open()

    group = dialog.widget.findChild(QGroupBox, "virtual_microphone_group")
    input_combo = dialog.widget.findChild(QComboBox, "input_device_combo")
    monitor_combo = dialog.widget.findChild(QComboBox, "monitor_device_combo")
    microphone_slider = dialog.widget.findChild(QSlider, "microphone_gain_slider")
    sound_slider = dialog.widget.findChild(QSlider, "sound_gain_slider")

    assert group.title() == "Виртуальный микрофон"
    assert input_combo.itemData(0) is None
    assert input_combo.currentData() == "02"
    assert input_combo.itemText(1) != input_combo.itemText(2)
    assert monitor_combo.currentData() is None
    assert (microphone_slider.minimum(), microphone_slider.maximum()) == (0, 100)
    assert (microphone_slider.value(), sound_slider.value()) == (40, 70)
    assert controller.input_values == []
    assert controller.monitor_values == []
    assert controller.microphone_values == []
    assert controller.sound_values == []


def test_user_changes_use_none_for_system_default_and_scaled_gains(qtbot: QtBot) -> None:
    dialog, controller = make_dialog(qtbot)
    dialog.open()
    input_combo = dialog.widget.findChild(QComboBox, "input_device_combo")
    sound_slider = dialog.widget.findChild(QSlider, "sound_gain_slider")

    input_combo.setCurrentIndex(0)
    sound_slider.setValue(25)

    assert controller.input_values == [None]
    assert controller.sound_values == [0.25]


def test_dialog_displays_every_virtual_microphone_status(qtbot: QtBot) -> None:
    dialog, _ = make_dialog(qtbot)
    label = dialog.widget.findChild(QLabel, "virtual_microphone_status")
    states = (
        AudioRoutingStatus("active", "Активен"),
        AudioRoutingStatus("cable_missing", "VB-CABLE не найден"),
        AudioRoutingStatus("microphone_missing", "Микрофон недоступен"),
        AudioRoutingStatus("monitor_missing", "Мониторинг недоступен"),
        AudioRoutingStatus("pipeline_error", "Ошибка аудиопотока"),
    )

    for state in states:
        dialog.set_virtual_microphone_status(state)
        assert label.text() == state.message
        assert label.property("status_code") == state.code


def test_missing_selected_device_remains_visible_and_selected(qtbot: QtBot) -> None:
    dialog, controller = make_dialog(qtbot)
    controller.settings = AudioRoutingSettings("disconnected", None, 0.4, 0.7)

    dialog.open()

    input_combo = dialog.widget.findChild(QComboBox, "input_device_combo")
    assert input_combo.currentData() == "disconnected"
    assert input_combo.currentText() == "Недоступно — disconnected"
    assert controller.input_values == []


def test_gain_readouts_follow_edits_and_refresh_without_saving(qtbot: QtBot) -> None:
    dialog, controller = make_dialog(qtbot)
    dialog.open()
    microphone_value = dialog.widget.findChild(QLabel, "microphone_gain_value")
    sound_value = dialog.widget.findChild(QLabel, "sound_gain_value")
    assert microphone_value is not None
    assert sound_value is not None
    assert (microphone_value.text(), sound_value.text()) == ("40%", "70%")
    slider = dialog.widget.findChild(QSlider, "sound_gain_slider")

    slider.setValue(25)

    assert sound_value.text() == "25%"
    assert controller.sound_values == [0.25]
    controller.settings = AudioRoutingSettings("02", None, 1.0, 0.0)
    dialog.refresh()
    assert (microphone_value.text(), sound_value.text()) == ("100%", "0%")
    assert controller.microphone_values == []
    assert controller.sound_values == [0.25]


def test_failed_gain_change_restores_slider_and_readout(qtbot: QtBot, monkeypatch) -> None:
    dialog, controller = make_dialog(qtbot)
    dialog.open()

    def fail(value: float) -> None:
        raise OSError("Недоступно")

    monkeypatch.setattr(controller, "set_sound_gain", fail)
    slider = dialog.widget.findChild(QSlider, "sound_gain_slider")
    slider.setValue(25)

    readout = dialog.widget.findChild(QLabel, "sound_gain_value")
    assert slider.value() == 70
    assert readout is not None
    assert readout.text() == "70%"



def make_lighting_dialog(qtbot, tmp_path):
    from types import SimpleNamespace
    from dj_poltorashka.application.settings_controller import SettingsController
    from dj_poltorashka.panel.lighting import LightingSettingsRepository
    repository = LightingSettingsRepository(tmp_path / "lighting.json")
    controller = SettingsController(SimpleNamespace(is_enabled=lambda: False), lighting_repository=repository)
    errors = []
    dialog = SettingsDialog(controller, lambda *args: errors.append(args))
    qtbot.addWidget(dialog.widget)
    dialog.open()
    return dialog, controller, repository, errors


def test_rgb_controls_save_three_mute_colors_and_brightness(qtbot, tmp_path):
    from PySide6.QtWidgets import QLineEdit, QPushButton
    from dj_poltorashka.panel.lighting import RgbColor
    dialog, controller, repository, errors = make_lighting_dialog(qtbot, tmp_path)
    slider = dialog.widget.findChild(QSlider, "lighting_brightness_slider")
    assert slider.maximum() == 50
    assert slider.value() == 50
    for name, color in (("mute_active", "#123456"), ("mute_muted", "#ABCDEF"), ("mute_unassigned", "#102030")):
        dialog.widget.findChild(QLineEdit, f"lighting_{name}").setText(color)
    slider.setValue(30)
    dialog.widget.findChild(QPushButton, "save_lighting_button").click()
    saved = repository.load()
    assert saved == controller.lighting_settings()
    assert saved.mute_active == RgbColor(18, 52, 86)
    assert saved.mute_muted == RgbColor(171, 205, 239)
    assert saved.mute_unassigned == RgbColor(16, 32, 48)
    assert saved.brightness == 0.3
    assert errors == []


def test_invalid_rgb_does_not_save_partial_settings(qtbot, tmp_path):
    from PySide6.QtWidgets import QLineEdit, QPushButton
    from dj_poltorashka.panel.lighting import LightingSettings
    dialog, controller, repository, errors = make_lighting_dialog(qtbot, tmp_path)
    dialog.widget.findChild(QLineEdit, "lighting_mute_active").setText("#112233")
    dialog.widget.findChild(QLineEdit, "lighting_mute_muted").setText("#GG0000")
    dialog.widget.findChild(QPushButton, "save_lighting_button").click()
    assert controller.lighting_settings() == LightingSettings()
    assert repository.load() == LightingSettings()
    assert len(errors) == 1


def test_palette_selection_updates_rgb_field_without_saving(qtbot, tmp_path, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog, QLineEdit, QPushButton
    from dj_poltorashka.panel.lighting import LightingSettings
    dialog, controller, repository, errors = make_lighting_dialog(qtbot, tmp_path)
    calls = []
    def choose(initial, parent, title):
        calls.append((initial.name(), title))
        return QColor("#123ABC")
    monkeypatch.setattr(QColorDialog, "getColor", choose)
    dialog.widget.findChild(QPushButton, "lighting_preview_mute_active").click()
    assert dialog.widget.findChild(QLineEdit, "lighting_mute_active").text() == "#123ABC"
    assert len(calls) == 1
    assert controller.lighting_settings() == LightingSettings()
    assert repository.load() == LightingSettings()
    assert errors == []


def test_cancelling_palette_preserves_input(qtbot, tmp_path, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog, QLineEdit, QPushButton
    dialog, _, _, _ = make_lighting_dialog(qtbot, tmp_path)
    edit = dialog.widget.findChild(QLineEdit, "lighting_perimeter")
    previous = edit.text()
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor())
    dialog.widget.findChild(QPushButton, "lighting_preview_perimeter").click()
    assert edit.text() == previous


def test_failed_lighting_save_preserves_controller_state_and_input(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QLineEdit, QPushButton
    from dj_poltorashka.panel.lighting import LightingSettings
    dialog, controller, repository, errors = make_lighting_dialog(qtbot, tmp_path)
    def fail(settings):
        raise OSError("write failed")
    monkeypatch.setattr(repository, "save", fail)
    edit = dialog.widget.findChild(QLineEdit, "lighting_perimeter")
    edit.setText("#123456")
    dialog.widget.findChild(QPushButton, "save_lighting_button").click()
    assert controller.lighting_settings() == LightingSettings()
    assert edit.text() == "#123456"
    assert len(errors) == 1
