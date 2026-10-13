from pathlib import Path

import pytest

from dj_poltorashka.application.autostart import (
    RegistryOperations,
    WindowsAutostart,
    build_background_command,
)


class FakeRegistry:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.read_error: OSError | None = None
        self.write_error: OSError | None = None

    @property
    def operations(self) -> RegistryOperations:
        return RegistryOperations(
            read_value=self.read_value,
            write_value=self.write_value,
            delete_value=self.delete_value,
        )

    def read_value(self, key_path: str, value_name: str) -> str | None:
        if self.read_error is not None:
            raise self.read_error
        return self.values.get((key_path, value_name))

    def write_value(self, key_path: str, value_name: str, value: str) -> None:
        if self.write_error is not None:
            raise self.write_error
        self.values[(key_path, value_name)] = value

    def delete_value(self, key_path: str, value_name: str) -> None:
        if self.write_error is not None:
            raise self.write_error
        self.values.pop((key_path, value_name), None)


def make_autostart(registry: FakeRegistry) -> WindowsAutostart:
    return WindowsAutostart(
        command='"C:\\Program Files\\DJ Poltorashka\\app.exe" --background',
        registry_operations=registry.operations,
    )


def test_packaged_background_command_quotes_executable_path() -> None:
    command = build_background_command(
        Path(r"C:\Program Files\DJ Poltorashka\app.exe"),
        packaged=True,
    )

    assert command == '"C:\\Program Files\\DJ Poltorashka\\app.exe" --background'


def test_packaged_background_command_supports_cyrillic_path() -> None:
    command = build_background_command(
        Path(r"C:\Каталог с пробелами\DJ Poltorashka.exe"),
        packaged=True,
    )

    assert command == (
        '"C:\\Каталог с пробелами\\DJ Poltorashka.exe" --background'
    )
    assert "-m dj_poltorashka" not in command


def test_source_background_command_runs_module_without_console() -> None:
    command = build_background_command(
        Path(r"C:\Program Files\Python\pythonw.exe"),
        packaged=False,
    )

    assert command == (
        '"C:\\Program Files\\Python\\pythonw.exe" '
        "-m dj_poltorashka --background"
    )


def test_missing_registry_value_means_autostart_is_disabled() -> None:
    registry = FakeRegistry()

    assert not make_autostart(registry).is_enabled()


def test_only_exact_registry_command_means_autostart_is_enabled() -> None:
    registry = FakeRegistry()
    autostart = make_autostart(registry)
    registry.values[(autostart.key_path, autostart.value_name)] = autostart.command

    assert autostart.is_enabled()

    registry.values[(autostart.key_path, autostart.value_name)] = "old.exe"
    assert not autostart.is_enabled()


def test_set_enabled_writes_expected_registry_value() -> None:
    registry = FakeRegistry()
    autostart = make_autostart(registry)

    autostart.set_enabled(True)

    assert registry.values == {
        (autostart.key_path, "DjPoltorashka"): autostart.command,
    }


def test_set_disabled_removes_registry_value() -> None:
    registry = FakeRegistry()
    autostart = make_autostart(registry)
    registry.values[(autostart.key_path, autostart.value_name)] = autostart.command

    autostart.set_enabled(False)

    assert registry.values == {}


def test_registry_read_error_is_not_hidden() -> None:
    registry = FakeRegistry()
    registry.read_error = PermissionError("read denied")

    with pytest.raises(PermissionError, match="read denied"):
        make_autostart(registry).is_enabled()


@pytest.mark.parametrize("enabled", (True, False))
def test_registry_write_error_is_not_hidden(enabled: bool) -> None:
    registry = FakeRegistry()
    registry.write_error = PermissionError("write denied")

    with pytest.raises(PermissionError, match="write denied"):
        make_autostart(registry).set_enabled(enabled)
