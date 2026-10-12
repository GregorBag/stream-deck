"""Надёжное файловое хранилище конфигурации и черновика."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile

from dj_poltorashka.configuration.codec import (
    decode_panel_configuration,
    decode_stored_configuration,
    encode_panel_configuration,
    encode_stored_configuration,
)
from dj_poltorashka.configuration.models import PanelConfiguration, StoredConfiguration


@dataclass(frozen=True)
class ConfigurationPaths:
    """Все каталоги и файлы, которыми управляет настольное приложение."""

    root: Path
    configuration_file: Path
    draft_file: Path
    sounds_dir: Path
    logs_dir: Path

    @classmethod
    def under(cls, root: Path) -> "ConfigurationPaths":
        root_path = Path(root)
        return cls(
            root=root_path,
            configuration_file=root_path / "configuration.json",
            draft_file=root_path / "draft.json",
            sounds_dir=root_path / "sounds",
            logs_dir=root_path / "logs",
        )


class ConfigurationRepository:
    """Сохраняет конфигурацию атомарно в JSON-файлах."""

    def __init__(self, paths: ConfigurationPaths):
        if not isinstance(paths, ConfigurationPaths):
            raise ValueError("Хранилищу требуется ConfigurationPaths")
        self._paths = paths
        self._configuration_is_corrupt = False
        self._draft_is_corrupt = False

    def load(self, default: StoredConfiguration) -> StoredConfiguration:
        if not self._paths.configuration_file.exists():
            return default
        try:
            data = self._read_json(self._paths.configuration_file)
        except ValueError:
            self._configuration_is_corrupt = True
            raise
        try:
            return decode_stored_configuration(data)
        except ValueError as error:
            self._configuration_is_corrupt = True
            raise ValueError(
                f"{self._paths.configuration_file.name}: {error}"
            ) from error

    def save(self, stored: StoredConfiguration) -> None:
        if self._configuration_is_corrupt:
            self._preserve_corrupt(self._paths.configuration_file)
            self._configuration_is_corrupt = False
        self._write_json(
            self._paths.configuration_file,
            encode_stored_configuration(stored),
        )

    def load_draft(self) -> PanelConfiguration | None:
        if not self._paths.draft_file.exists():
            return None
        try:
            data = self._read_json(self._paths.draft_file)
        except ValueError:
            self._draft_is_corrupt = True
            raise
        try:
            return decode_panel_configuration(data)
        except ValueError as error:
            self._draft_is_corrupt = True
            raise ValueError(f"{self._paths.draft_file.name}: {error}") from error

    def save_draft(self, panel: PanelConfiguration) -> None:
        if self._draft_is_corrupt:
            self._preserve_corrupt(self._paths.draft_file)
            self._draft_is_corrupt = False
        self._write_json(
            self._paths.draft_file,
            encode_panel_configuration(panel),
        )

    def clear_draft(self) -> None:
        if self._draft_is_corrupt:
            self._preserve_corrupt(self._paths.draft_file)
            self._draft_is_corrupt = False
        self._paths.draft_file.unlink(missing_ok=True)

    @staticmethod
    def _preserve_corrupt(path: Path) -> None:
        if not path.exists():
            return
        backup = path.with_name(f"{path.name}.corrupt")
        suffix = 1
        while backup.exists():
            backup = path.with_name(f"{path.name}.corrupt.{suffix}")
            suffix += 1
        shutil.copy2(path, backup)

    @staticmethod
    def _read_json(path: Path) -> object:
        try:
            with path.open("r", encoding="utf-8") as source_file:
                return json.load(source_file)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{path.name}: некорректный JSON в строке {error.lineno}"
            ) from error

    @staticmethod
    def _write_json(path: Path, data: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(
                    data,
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, path)
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
