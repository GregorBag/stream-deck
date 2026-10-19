"""Выбор запущенной или установленной программы."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QFileDialog, QLabel, QLineEdit, QListWidget, QPushButton,
    QStackedWidget, QVBoxLayout,
)

from dj_poltorashka.application.application_catalog import ApplicationCandidate


class ApplicationPicker:
    def __init__(self, catalog, parent=None) -> None:
        self._catalog = catalog
        self._selection: tuple[Path, str] | None = None
        self._running: tuple[ApplicationCandidate, ...] = ()
        self._installed: tuple[ApplicationCandidate, ...] = ()
        self._widget = QDialog(parent)
        self._widget.setWindowTitle("Выберите программу")
        self._widget.resize(560, 420)
        layout = QVBoxLayout(self._widget)
        self._pages = QStackedWidget()
        layout.addWidget(self._pages)

        running_page = QDialog()
        running_layout = QVBoxLayout(running_page)
        running_layout.addWidget(QLabel("Открытые программы"))
        self._running_list = QListWidget()
        self._running_list.setObjectName("running_applications")
        running_layout.addWidget(self._running_list)
        select_running = QPushButton("Выбрать")
        select_running.setObjectName("select_running")
        select_running.clicked.connect(self._select_running)
        running_layout.addWidget(select_running)
        other = QPushButton("Другая программа")
        other.setObjectName("other_application")
        other.clicked.connect(self._show_installed)
        running_layout.addWidget(other)
        self._pages.addWidget(running_page)

        installed_page = QDialog()
        installed_layout = QVBoxLayout(installed_page)
        self._search = QLineEdit()
        self._search.setObjectName("application_search")
        self._search.setPlaceholderText("Название программы")
        self._search.textChanged.connect(self._filter_installed)
        installed_layout.addWidget(self._search)
        self._installed_list = QListWidget()
        self._installed_list.setObjectName("installed_applications")
        installed_layout.addWidget(self._installed_list)
        select_installed = QPushButton("Выбрать")
        select_installed.setObjectName("select_installed")
        select_installed.clicked.connect(self._select_installed)
        installed_layout.addWidget(select_installed)
        browse = QPushButton("Указать .exe вручную")
        browse.setObjectName("browse_application")
        browse.clicked.connect(self._browse)
        installed_layout.addWidget(browse)
        self._pages.addWidget(installed_page)

        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self._widget.reject)
        layout.addWidget(cancel)

    @property
    def widget(self) -> QDialog:
        return self._widget

    def prepare(self) -> None:
        self._selection = None
        self._pages.setCurrentIndex(0)
        self._running = self._catalog.running()
        self._running_list.clear()
        for item in self._running:
            self._running_list.addItem(f"{item.name}  —  {item.path}")

    def choose(self) -> Path | None:
        self.prepare()
        return self._selection[0] if self._widget.exec() == QDialog.Accepted and self._selection else None

    def selection(self) -> tuple[Path, str] | None:
        return self._selection if self._widget.result() == QDialog.Accepted else None

    def _show_installed(self) -> None:
        self._installed = self._catalog.installed()
        self._search.clear()
        self._filter_installed("")
        self._pages.setCurrentIndex(1)
        self._search.setFocus()

    def _filter_installed(self, query: str) -> None:
        self._installed_list.clear()
        for item in self._installed:
            if query.casefold() in item.name.casefold() or query.casefold() in item.path.stem.casefold():
                self._installed_list.addItem(f"{item.name}  —  {item.path}")
                self._installed_list.item(self._installed_list.count() - 1).setData(256, item)

    def _select_running(self) -> None:
        index = self._running_list.currentRow()
        if 0 <= index < len(self._running):
            item = self._running[index]
            self._selection = (item.path, item.name)
            self._widget.accept()

    def _select_installed(self) -> None:
        row = self._installed_list.currentItem()
        if row is not None:
            item = row.data(256)
            self._selection = (item.path, item.name)
            self._widget.accept()

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self._widget, "Выберите программу", "", "Программы (*.exe)"
        )
        if filename:
            path = Path(filename)
            self._selection = (path, path.stem)
            self._widget.accept()
