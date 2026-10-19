from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit, QPushButton, QSlider
from pytestqt.qtbot import QtBot

from dj_poltorashka.configuration.models import (
    MixerChannelConfig, PanelConfiguration, PresetConfig, SoundButtonConfig,
)
from dj_poltorashka.ui.preset_edit_dialog import PresetEditDialog, PresetEditResult
from dj_poltorashka.ui.dialog_service import DialogService


def make_preset() -> PresetConfig:
    panel = PanelConfiguration(
        channels=(
            MixerChannelConfig("master", 0.5, False),
            MixerChannelConfig("application", 0.3, False, r"C:\Apps\Player.exe"),
            *(MixerChannelConfig("unassigned", 0.5, False) for _ in range(2)),
        ),
        sound_buttons=(SoundButtonConfig("old.mp3", "Старый"), *(SoundButtonConfig() for _ in range(7))),
    )
    return PresetConfig("Работа", panel)


def make_dialog(choose_application=lambda: None, choose_sound=lambda: None, errors=None):
    errors = errors if errors is not None else []
    return PresetEditDialog(choose_application, choose_sound, lambda title, message: errors.append((title, message)))


def test_dialog_starts_from_preset_and_submits_edited_name_and_panel(qtbot: QtBot) -> None:
    dialog = make_dialog()
    qtbot.addWidget(dialog.widget)
    results: list[PresetEditResult] = []
    dialog.prepare(make_preset(), lambda result: results.append(result) or True)
    name = dialog.widget.findChild(QLineEdit, "preset_edit_name")
    volume = dialog.widget.findChild(QSlider, "volume_slider_0")
    assert name.text() == "Работа"
    assert volume.value() == 50

    name.setText("  Игры  ")
    volume.setValue(70)
    qtbot.mouseClick(dialog.widget.findChild(QPushButton, "preset_edit_save"), Qt.LeftButton)

    assert dialog.widget.result() == QDialog.Accepted
    assert results[0].name == "Игры"
    assert results[0].panel.channels[0].volume == 0.7
    assert results[0].sound_sources == (None,) * 8


def test_cancel_does_not_call_save(qtbot: QtBot) -> None:
    dialog = make_dialog()
    qtbot.addWidget(dialog.widget)
    results: list[PresetEditResult] = []
    dialog.prepare(make_preset(), lambda result: results.append(result) or True)
    qtbot.mouseClick(dialog.widget.findChild(QPushButton, "preset_edit_cancel"), Qt.LeftButton)
    assert dialog.widget.result() == QDialog.Rejected
    assert results == []


def test_duplicate_channel_keeps_previous_panel(qtbot: QtBot) -> None:
    errors: list[tuple[str, str]] = []
    dialog = make_dialog(errors=errors)
    qtbot.addWidget(dialog.widget)
    results: list[PresetEditResult] = []
    dialog.prepare(make_preset(), lambda result: results.append(result) or True)
    kind = dialog.widget.findChild(QComboBox, "channel_kind_2")
    kind.setCurrentIndex(kind.findData("master"))
    qtbot.mouseClick(dialog.widget.findChild(QPushButton, "preset_edit_save"), Qt.LeftButton)
    assert errors and "уже назначен" in errors[0][1]
    assert results[0].panel.channels[2].channel_kind == "unassigned"
    assert kind.currentData() == "unassigned"


def test_cancelled_application_choice_keeps_channel(qtbot: QtBot) -> None:
    dialog = make_dialog(choose_application=lambda: None)
    qtbot.addWidget(dialog.widget)
    results: list[PresetEditResult] = []
    dialog.prepare(make_preset(), lambda result: results.append(result) or True)
    qtbot.mouseClick(dialog.widget.findChild(QPushButton, "application_button_1"), Qt.LeftButton)
    qtbot.mouseClick(dialog.widget.findChild(QPushButton, "preset_edit_save"), Qt.LeftButton)
    assert results[0].panel.channels[1].application_path == r"c:\apps\player.exe"


def test_replacing_sound_twice_keeps_last_source(qtbot: QtBot) -> None:
    sources = iter((Path("C:/Sounds/one.mp3"), Path("C:/Sounds/two.mp3")))
    dialog = make_dialog(choose_sound=lambda: next(sources))
    qtbot.addWidget(dialog.widget)
    results: list[PresetEditResult] = []
    dialog.prepare(make_preset(), lambda result: results.append(result) or True)
    button = dialog.widget.findChild(QPushButton, "sound_import_0")
    qtbot.mouseClick(button, Qt.LeftButton)
    qtbot.mouseClick(button, Qt.LeftButton)
    qtbot.mouseClick(dialog.widget.findChild(QPushButton, "preset_edit_save"), Qt.LeftButton)
    assert results[0].sound_sources[0] == Path("C:/Sounds/two.mp3")


def test_failed_save_callback_keeps_dialog_open(qtbot: QtBot) -> None:
    dialog = make_dialog()
    qtbot.addWidget(dialog.widget)
    dialog.prepare(make_preset(), lambda result: False)
    qtbot.mouseClick(dialog.widget.findChild(QPushButton, "preset_edit_save"), Qt.LeftButton)
    assert dialog.widget.result() != QDialog.Accepted


def test_dialog_service_opens_real_preset_editor(qtbot: QtBot) -> None:
    results: list[PresetEditResult] = []
    QTimer.singleShot(
        0,
        lambda: QApplication.activeModalWidget()
        .findChild(QPushButton, "preset_edit_save")
        .click(),
    )

    DialogService().edit_preset(make_preset(), lambda result: results.append(result) or True)

    assert results[0].name == "Работа"
