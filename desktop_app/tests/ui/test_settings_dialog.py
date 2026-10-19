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
