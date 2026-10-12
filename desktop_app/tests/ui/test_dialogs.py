from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLineEdit,
    QMessageBox,
)
from pytestqt.qtbot import QtBot

from dj_poltorashka.configuration.defaults import (
    create_default_stored_configuration,
)
from dj_poltorashka.configuration.models import PresetConfig, StoredConfiguration
from dj_poltorashka.ui.dialog_service import DialogService
from dj_poltorashka.ui.preset_dialog import PresetDialog
from dj_poltorashka.ui.settings_dialog import SettingsDialog


def stored_with_first_preset() -> StoredConfiguration:
    stored = create_default_stored_configuration()
    return StoredConfiguration(
        active=stored.active,
        baseline=stored.baseline,
        presets=(PresetConfig("Работа", stored.active), None, None),
    )


def test_file_dialogs_use_expected_filters_and_return_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def get_open_file_name(parent, title: str, directory: str, file_filter: str):
        calls.append((title, file_filter))
        if "Программы" in file_filter:
            return (r"C:\Apps\Player.exe", file_filter)
        return (r"C:\Sounds\intro.mp3", file_filter)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", get_open_file_name)
    dialogs = DialogService()

    application_path = dialogs.choose_application_file()
    sound_path = dialogs.choose_sound_file()

    assert application_path == Path(r"C:\Apps\Player.exe")
    assert sound_path == Path(r"C:\Sounds\intro.mp3")
    assert calls == [
        ("Выберите программу", "Программы (*.exe)"),
        ("Выберите звук", "Аудиофайлы (*.mp3 *.wav)"),
    ]


def test_cancelled_file_dialog_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: ("", ""),
    )

    assert DialogService().choose_sound_file() is None


def test_preset_dialog_returns_zero_based_slot_and_trimmed_name(
    qtbot: QtBot,
) -> None:
    dialog = PresetDialog()
    qtbot.addWidget(dialog.widget)
    dialog.prepare(stored_with_first_preset())
    slot = dialog.widget.findChild(QComboBox, "preset_slot")
    name = dialog.widget.findChild(QLineEdit, "preset_name")
    buttons = dialog.widget.findChild(QDialogButtonBox, "preset_buttons")
    slot.setCurrentIndex(1)
    name.setText("  Игры  ")

    qtbot.mouseClick(buttons.button(QDialogButtonBox.Save), Qt.LeftButton)

    assert dialog.selection() == (1, "Игры")


def test_rejected_preset_dialog_has_no_selection(qtbot: QtBot) -> None:
    dialog = PresetDialog()
    qtbot.addWidget(dialog.widget)
    dialog.prepare(stored_with_first_preset())

    dialog.widget.reject()

    assert dialog.selection() is None


@pytest.mark.parametrize(
    ("answer", "expected"),
    (
        (QMessageBox.Yes, True),
        (QMessageBox.No, False),
    ),
)
def test_confirm_overwrite_maps_question_answer(
    answer: QMessageBox.StandardButton,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(QMessageBox, "question", lambda *args: answer)

    assert DialogService().confirm_overwrite("Работа") is expected


def test_closing_exit_dialog_is_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.NoButton)

    assert DialogService().ask_exit() == "cancel"


class FakeSettingsController:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.requested: list[bool] = []
        self.error: OSError | None = None

    def autostart_enabled(self) -> bool:
        return self.enabled

    def set_autostart_enabled(self, enabled: bool) -> bool:
        self.requested.append(enabled)
        if self.error is not None:
            raise self.error
        self.enabled = enabled
        return self.enabled


def test_settings_dialog_reads_and_changes_autostart(qtbot: QtBot) -> None:
    controller = FakeSettingsController(enabled=False)
    errors: list[tuple[str, str]] = []
    dialog = SettingsDialog(controller, lambda title, message: errors.append((title, message)))
    qtbot.addWidget(dialog.widget)

    dialog.open()
    checkbox = dialog.widget.findChild(QCheckBox, "autostart_checkbox")
    checkbox.setChecked(True)

    assert controller.requested == [True]
    assert checkbox.isChecked()
    assert errors == []


def test_settings_error_restores_actual_checkbox_state(qtbot: QtBot) -> None:
    controller = FakeSettingsController(enabled=False)
    controller.error = PermissionError("registry denied")
    errors: list[tuple[str, str]] = []
    dialog = SettingsDialog(controller, lambda title, message: errors.append((title, message)))
    qtbot.addWidget(dialog.widget)
    dialog.open()
    checkbox = dialog.widget.findChild(QCheckBox, "autostart_checkbox")

    checkbox.setChecked(True)

    assert not checkbox.isChecked()
    assert errors == [("Автозапуск", "registry denied")]
