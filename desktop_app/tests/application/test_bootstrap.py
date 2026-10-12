from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

import dj_poltorashka.application.bootstrap as bootstrap
from dj_poltorashka.configuration.defaults import (
    create_default_stored_configuration,
)
from dj_poltorashka.configuration.repository import ConfigurationPaths


def test_parse_arguments_defaults_to_visible_start() -> None:
    options = bootstrap.parse_arguments([])

    assert not options.background


def test_parse_arguments_accepts_background_start() -> None:
    options = bootstrap.parse_arguments(["--background"])

    assert options.background


def test_parse_arguments_rejects_unknown_option() -> None:
    with pytest.raises(SystemExit):
        bootstrap.parse_arguments(["--unknown"])


def test_build_sets_qt_names_before_resolving_paths(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_root = tmp_path / "data"

    def resolve_paths(root: Path | None) -> ConfigurationPaths:
        assert QCoreApplication.organizationName() == "DJ Poltorashka"
        assert QCoreApplication.applicationName() == "DJ Poltorashka"
        assert root == requested_root
        return ConfigurationPaths.under(requested_root)

    monkeypatch.setattr(bootstrap, "resolve_configuration_paths", resolve_paths)

    running = bootstrap.build_application(requested_root)

    assert running.paths.root == requested_root
    running.close()


def test_corrupt_configuration_is_preserved_and_default_is_loaded(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    configuration_file = tmp_path / "configuration.json"
    invalid_contents = "{not-json"
    configuration_file.write_text(invalid_contents, encoding="utf-8")

    running = bootstrap.build_application(tmp_path)

    assert configuration_file.read_text(encoding="utf-8") == invalid_contents
    assert (
        running.configuration_service.stored_configuration
        == create_default_stored_configuration()
    )
    assert running.startup_errors == (
        ("Конфигурация", "configuration.json: некорректный JSON в строке 1"),
    )
    running.close()


def test_corrupt_draft_is_preserved_and_not_offered_for_restore(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    draft_file = tmp_path / "draft.json"
    invalid_contents = "[broken"
    draft_file.write_text(invalid_contents, encoding="utf-8")

    running = bootstrap.build_application(tmp_path)

    assert draft_file.read_text(encoding="utf-8") == invalid_contents
    assert not running.draft_available
    assert running.startup_errors == (
        ("Черновик", "draft.json: некорректный JSON в строке 1"),
    )
    running.close()


def test_restoring_valid_draft_does_not_overwrite_corrupt_configuration(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_file = tmp_path / "configuration.json"
    invalid_contents = "{not-json"
    configuration_file.write_text(invalid_contents, encoding="utf-8")
    source = bootstrap.build_application(tmp_path)
    draft = source.configuration_service.stored_configuration.active
    source.repository.save_draft(draft)
    source.close()

    running = bootstrap.build_application(tmp_path)
    monkeypatch.setattr(running.dialogs, "ask_restore", lambda: True)
    try:
        running.controller.start(background=True, draft_available=True)

        assert configuration_file.read_text(encoding="utf-8") == invalid_contents
    finally:
        running.close()


class FakeApplication:
    def __init__(self) -> None:
        self.exec_count = 0

    def exec(self) -> int:
        self.exec_count += 1
        return 23


class FakeSingleInstance:
    def __init__(self, existing: bool) -> None:
        self.existing = existing
        self.commands: list[str] = []
        self.listeners = []
        self.close_count = 0
        self.listen_error: RuntimeError | None = None
        self.notify_results: list[bool] = []

    def notify_existing(self, command: str) -> bool:
        self.commands.append(command)
        if self.notify_results:
            return self.notify_results.pop(0)
        return self.existing

    def listen(self, on_command) -> None:
        if self.listen_error is not None:
            raise self.listen_error
        self.listeners.append(on_command)

    def close(self) -> None:
        self.close_count += 1


class FakeTray:
    def __init__(self, available: bool) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


class FakeController:
    def __init__(self) -> None:
        self.starts: list[tuple[bool, bool]] = []
        self.instance_commands: list[str] = []

    def start(self, background: bool, draft_available: bool) -> None:
        self.starts.append((background, draft_available))

    def handle_instance_command(self, command: str) -> None:
        self.instance_commands.append(command)


class FakeDialogs:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []

    def show_error(self, title: str, message: str) -> None:
        self.errors.append((title, message))


class FakeRunningApplication:
    def __init__(self, existing: bool, tray_available: bool = True) -> None:
        self.application = FakeApplication()
        self.single_instance = FakeSingleInstance(existing)
        self.tray = FakeTray(tray_available)
        self.controller = FakeController()
        self.dialogs = FakeDialogs()
        self.draft_available = True
        self.startup_errors = (("Чтение", "warning"),)
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1
        self.single_instance.close()


@pytest.mark.parametrize(
    ("arguments", "expected_command"),
    (([], "show"), (["--background"], "ping")),
)
def test_second_instance_sends_expected_command_and_exits(
    qtbot: QtBot,
    arguments: list[str],
    expected_command: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = FakeRunningApplication(existing=True)
    monkeypatch.setattr(bootstrap, "build_application", lambda: running)

    exit_code = bootstrap.main(arguments)

    assert exit_code == 0
    assert running.single_instance.commands == [expected_command]
    assert running.controller.starts == []
    assert running.application.exec_count == 0
    assert running.close_count == 1


def test_first_instance_refuses_to_start_without_system_tray(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = FakeRunningApplication(existing=False, tray_available=False)
    monkeypatch.setattr(bootstrap, "build_application", lambda: running)

    exit_code = bootstrap.main([])

    assert exit_code == 1
    assert running.dialogs.errors == [
        ("Системный трей", "Системный трей недоступен")
    ]
    assert running.controller.starts == []
    assert running.close_count == 1


def test_first_instance_listens_starts_and_runs_event_loop(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = FakeRunningApplication(existing=False)
    monkeypatch.setattr(bootstrap, "build_application", lambda: running)

    exit_code = bootstrap.main(["--background"])

    assert exit_code == 23
    assert running.single_instance.commands == ["ping"]
    assert running.single_instance.listeners == [
        running.controller.handle_instance_command
    ]
    assert running.dialogs.errors == [("Чтение", "warning")]
    assert running.controller.starts == [(True, True)]
    assert running.application.exec_count == 1
    assert running.close_count == 1


def test_bootstrap_error_is_shown_and_returns_failure(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[tuple[str, str]] = []

    def fail_build():
        raise RuntimeError("startup failed")

    monkeypatch.setattr(bootstrap, "build_application", fail_build)
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, message: errors.append((title, message)),
    )

    assert bootstrap.main([]) == 1
    assert errors == [("Ошибка запуска", "startup failed")]


def test_single_instance_listen_error_is_shown_and_returns_failure(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = FakeRunningApplication(existing=False)
    running.single_instance.listen_error = RuntimeError("listen failed")
    monkeypatch.setattr(bootstrap, "build_application", lambda: running)

    assert bootstrap.main([]) == 1
    assert running.dialogs.errors == [("Ошибка запуска", "listen failed")]
    assert running.close_count == 1


def test_concurrent_first_instance_retries_notification(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = FakeRunningApplication(existing=False)
    running.single_instance.notify_results = [False, True]
    running.single_instance.listen_error = RuntimeError("already running")
    monkeypatch.setattr(bootstrap, "build_application", lambda: running)

    assert bootstrap.main([]) == 0
    assert running.single_instance.commands == ["show", "show"]
    assert running.dialogs.errors == []
    assert running.controller.starts == []
