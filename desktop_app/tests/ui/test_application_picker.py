from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLineEdit, QListWidget, QPushButton
from pytestqt.qtbot import QtBot

from dj_poltorashka.ui.application_picker import ApplicationPicker
from dj_poltorashka.application.application_catalog import ApplicationCandidate


class Catalog:
    def running(self):
        return (
            ApplicationCandidate("Player — Music", Path("C:/Apps/Player.exe")),
            ApplicationCandidate("Browser", Path("C:/Apps/Browser.exe")),
        )

    def installed(self):
        return (
            ApplicationCandidate("Audacity", Path("C:/Apps/Audacity.exe")),
            ApplicationCandidate("Player", Path("C:/Apps/Player.exe")),
        )


def test_running_application_can_be_selected(qtbot: QtBot) -> None:
    picker = ApplicationPicker(Catalog())
    qtbot.addWidget(picker.widget)
    picker.prepare()
    running = picker.widget.findChild(QListWidget, "running_applications")
    running.setCurrentRow(0)
    qtbot.mouseClick(picker.widget.findChild(QPushButton, "select_running"), Qt.LeftButton)

    assert picker.selection() == (Path("C:/Apps/Player.exe"), "Player — Music")


def test_other_application_search_filters_installed_names(qtbot: QtBot) -> None:
    picker = ApplicationPicker(Catalog())
    qtbot.addWidget(picker.widget)
    picker.prepare()
    qtbot.mouseClick(picker.widget.findChild(QPushButton, "other_application"), Qt.LeftButton)
    search = picker.widget.findChild(QLineEdit, "application_search")
    search.setText("Auda")
    results = picker.widget.findChild(QListWidget, "installed_applications")

    assert results.count() == 1
    assert "Audacity" in results.item(0).text()
    results.setCurrentRow(0)
    qtbot.mouseClick(picker.widget.findChild(QPushButton, "select_installed"), Qt.LeftButton)
    assert picker.selection() == (Path("C:/Apps/Audacity.exe"), "Audacity")


def test_cancel_keeps_selection_empty(qtbot: QtBot) -> None:
    picker = ApplicationPicker(Catalog())
    qtbot.addWidget(picker.widget)
    picker.prepare()
    picker.widget.reject()
    assert picker.selection() is None


def test_manual_executable_fallback(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    picker = ApplicationPicker(Catalog())
    qtbot.addWidget(picker.widget)
    picker.prepare()
    qtbot.mouseClick(picker.widget.findChild(QPushButton, "other_application"), Qt.LeftButton)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        lambda *args: (r"C:\Tools\Custom.exe", "Программы (*.exe)"),
    )
    qtbot.mouseClick(picker.widget.findChild(QPushButton, "browse_application"), Qt.LeftButton)
    assert picker.selection() == (Path(r"C:\Tools\Custom.exe"), "Custom")
