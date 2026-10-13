"""Глобальные настройки маршрутизации виртуального микрофона."""

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import shutil
import tempfile


def _validate_device_id(value: str | None, field_name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{field_name} должен быть непустой строкой или None")


def _validate_gain(value: float, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(f"{field_name} должен быть конечным числом от 0 до 1")


@dataclass(frozen=True)
class AudioRoutingSettings:
    """Полностью валидный снимок настроек аудиомаршрутизации."""

    input_device_id: str | None = None
    monitor_device_id: str | None = None
    microphone_gain: float = 1.0
    sound_gain: float = 1.0

    def __post_init__(self) -> None:
        _validate_device_id(self.input_device_id, "input_device_id")
        _validate_device_id(self.monitor_device_id, "monitor_device_id")
        _validate_gain(self.microphone_gain, "microphone_gain")
        _validate_gain(self.sound_gain, "sound_gain")


class AudioRoutingSettingsRepository:
    """Атомарно сохраняет глобальные настройки в отдельном JSON-файле."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._loaded_file_is_corrupt = False

    def load(self) -> AudioRoutingSettings:
        if not self._path.exists():
            return AudioRoutingSettings()
        try:
            with self._path.open("r", encoding="utf-8") as source_file:
                data = json.load(source_file)
            if not isinstance(data, dict):
                raise ValueError("корневое значение должно быть объектом")
            return AudioRoutingSettings(
                input_device_id=data.get("input_device_id"),
                monitor_device_id=data.get("monitor_device_id"),
                microphone_gain=data.get("microphone_gain", 1.0),
                sound_gain=data.get("sound_gain", 1.0),
            )
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            self._loaded_file_is_corrupt = True
            raise ValueError(f"{self._path.name}: {error}") from error

    def save(self, settings: AudioRoutingSettings) -> None:
        if not isinstance(settings, AudioRoutingSettings):
            raise ValueError("Ожидался AudioRoutingSettings")
        if self._loaded_file_is_corrupt:
            self._preserve_corrupt_file()
            self._loaded_file_is_corrupt = False
        self._write_atomically(asdict(settings))

    def _preserve_corrupt_file(self) -> None:
        if not self._path.exists():
            return
        backup = self._path.with_name(f"{self._path.name}.corrupt")
        suffix = 1
        while backup.exists():
            backup = self._path.with_name(
                f"{self._path.name}.corrupt.{suffix}"
            )
            suffix += 1
        shutil.copy2(self._path, backup)

    def _write_atomically(self, data: object) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                dir=self._path.parent,
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
            os.replace(temporary_path, self._path)
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
