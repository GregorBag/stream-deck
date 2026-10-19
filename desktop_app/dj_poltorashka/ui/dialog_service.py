"""Модальные пользовательские запросы настольного приложения."""

from pathlib import Path
from collections.abc import Callable
from typing import Literal

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from dj_poltorashka.configuration.models import PresetConfig, StoredConfiguration
from dj_poltorashka.application.application_catalog import ApplicationCatalog
from dj_poltorashka.ui.application_picker import ApplicationPicker
from dj_poltorashka.ui.preset_dialog import PresetDialog
from dj_poltorashka.ui.preset_edit_dialog import PresetEditDialog, PresetEditResult


ExitChoice = Literal["save", "discard", "cancel"]


class DialogService:
    def __init__(self, parent: QWidget | None = None):
        self._parent = parent

    def choose_sound_file(self) -> Path | None:
        filename, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Выберите звук",
            "",
            "Аудиофайлы (*.mp3 *.wav)",
        )
        return Path(filename) if filename else None

    def choose_application_file(self) -> Path | None:
        return ApplicationPicker(ApplicationCatalog(), self._parent).choose()

    def choose_preset(
        self,
        stored: StoredConfiguration,
    ) -> tuple[int, str] | None:
        return PresetDialog(self._parent).choose(stored)

    def edit_preset(
        self,
        preset: PresetConfig,
        on_save: Callable[[PresetEditResult], bool],
    ) -> None:
        editor = PresetEditDialog(
            self.choose_application_file,
            self.choose_sound_file,
            self.show_error,
            self._parent,
        )
        editor.edit(preset, on_save)

    def confirm_overwrite(self, name: str) -> bool:
        answer = QMessageBox.question(
            self._parent,
            "Замена пресета",
            f"Заменить пресет «{name}»?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def ask_restore(self) -> bool:
        answer = QMessageBox.question(
            self._parent,
            "Восстановление настройки",
            "Восстановить несохранённую активную настройку?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        return answer == QMessageBox.Yes

    def ask_exit(self) -> ExitChoice:
        message = QMessageBox(self._parent)
        message.setWindowTitle("Несохранённая настройка")
        message.setText("Активная настройка не сохранена в пресет.")
        message.setIcon(QMessageBox.Warning)
        save_button = message.addButton(
            "Сохранить в пресет",
            QMessageBox.AcceptRole,
        )
        discard_button = message.addButton(
            "Выйти без сохранения",
            QMessageBox.DestructiveRole,
        )
        message.addButton("Отмена", QMessageBox.RejectRole)
        message.exec()
        clicked_button = message.clickedButton()
        if clicked_button is save_button:
            return "save"
        if clicked_button is discard_button:
            return "discard"
        return "cancel"

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self._parent, title, message)
