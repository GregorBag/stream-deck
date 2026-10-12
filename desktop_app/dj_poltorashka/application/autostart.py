"""Управление автозапуском приложения для текущего пользователя Windows."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess
import winreg


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "DjPoltorashka"


@dataclass(frozen=True)
class RegistryOperations:
    read_value: Callable[[str, str], str | None]
    write_value: Callable[[str, str, str], None]
    delete_value: Callable[[str, str], None]


def build_background_command(executable: Path, packaged: bool) -> str:
    """Сформировать корректно экранированную команду фонового запуска."""
    arguments = [str(Path(executable))]
    if not packaged:
        arguments.extend(("-m", "dj_poltorashka"))
    arguments.append("--background")
    return subprocess.list2cmdline(arguments)


class WindowsAutostart:
    """Читает и изменяет значение приложения в пользовательском Run key."""

    def __init__(
        self,
        command: str,
        registry_operations: RegistryOperations | None = None,
    ):
        if not isinstance(command, str) or not command:
            raise ValueError("Команда автозапуска не должна быть пустой")
        self._command = command
        self._registry_operations = (
            registry_operations or _default_registry_operations()
        )

    @property
    def command(self) -> str:
        return self._command

    @property
    def key_path(self) -> str:
        return _RUN_KEY

    @property
    def value_name(self) -> str:
        return _VALUE_NAME

    def is_enabled(self) -> bool:
        value = self._registry_operations.read_value(_RUN_KEY, _VALUE_NAME)
        return value == self._command

    def set_enabled(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Состояние автозапуска должно быть логическим значением")
        if enabled:
            self._registry_operations.write_value(
                _RUN_KEY,
                _VALUE_NAME,
                self._command,
            )
        else:
            self._registry_operations.delete_value(_RUN_KEY, _VALUE_NAME)


def _default_registry_operations() -> RegistryOperations:
    def read_value(key_path: str, value_name: str) -> str | None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_READ,
            ) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
        except FileNotFoundError:
            return None
        return value if isinstance(value, str) else None

    def write_value(key_path: str, value_name: str, value: str) -> None:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            key_path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value)

    def delete_value(key_path: str, value_name: str) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, value_name)
        except FileNotFoundError:
            return

    return RegistryOperations(
        read_value=read_value,
        write_value=write_value,
        delete_value=delete_value,
    )
