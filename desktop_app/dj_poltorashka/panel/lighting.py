"""Цвета физической панели и расчёт RGB с ограничением яркости."""

from dataclasses import dataclass, fields
import json
import math
import os
from pathlib import Path
import shutil
import tempfile


@dataclass(frozen=True)
class RgbColor:
    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        for value in (self.red, self.green, self.blue):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError("Компоненты RGB должны быть целыми числами от 0 до 255")

    @classmethod
    def parse(cls, text: str) -> "RgbColor":
        if not isinstance(text, str) or len(text) != 7 or not text.startswith("#"):
            raise ValueError("Введите RGB в формате #RRGGBB")
        if any(char not in "0123456789abcdefABCDEF" for char in text[1:]):
            raise ValueError("Введите RGB в формате #RRGGBB")
        return cls(*(int(text[index:index + 2], 16) for index in (1, 3, 5)))

    def to_hex(self) -> str:
        return f"#{self.red:02X}{self.green:02X}{self.blue:02X}"

    def to_rgb(self, brightness: float) -> tuple[int, int, int]:
        _validate_brightness(brightness)
        scale = brightness
        return tuple(round(value * scale) for value in (self.red, self.green, self.blue))


def _validate_brightness(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 0.5:
        raise ValueError("Яркость должна быть от 0 до 50%")


# Имена соответствуют настройкам, подписи используются в окне приложения.
COLOR_LABELS = {
    "sound_ready": "Программируемая кнопка — настроена",
    "sound_playing": "Программируемая кнопка — воспроизводится",
    "sound_unassigned": "Программируемая кнопка — не назначена",
    "mute_active": "Mute — канал активен",
    "mute_muted": "Mute — канал заглушён",
    "mute_unassigned": "Mute — канал не активен",
    "preset_active": "Пресет — активен",
    "preset_saved": "Пресет — сохранён",
    "preset_empty": "Пресет — пустой",
    "perimeter": "Подсветка периметра",
}


@dataclass(frozen=True)
class LightingSettings:
    brightness: float = 0.5
    sound_ready: RgbColor = RgbColor(22, 85, 96)
    sound_playing: RgbColor = RgbColor(57, 217, 244)
    sound_unassigned: RgbColor = RgbColor(0, 0, 0)
    mute_active: RgbColor = RgbColor(0, 255, 0)
    mute_muted: RgbColor = RgbColor(255, 0, 0)
    mute_unassigned: RgbColor = RgbColor(0, 0, 0)
    preset_active: RgbColor = RgbColor(161, 106, 255)
    preset_saved: RgbColor = RgbColor(40, 27, 64)
    preset_empty: RgbColor = RgbColor(0, 0, 0)
    perimeter: RgbColor = RgbColor(161, 106, 255)

    def __post_init__(self) -> None:
        _validate_brightness(self.brightness)
        for name in COLOR_LABELS:
            if not isinstance(getattr(self, name), RgbColor):
                raise ValueError(f"{name}: требуется цвет RGB")


class LightingSettingsRepository:
    """Сохраняет подсветку отдельно от аудионастроек и пресетов."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._corrupt = False

    def load(self) -> LightingSettings:
        if not self._path.exists():
            return LightingSettings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
                raise ValueError("Ожидались настройки подсветки версии 1")
            values = {}
            for field in fields(LightingSettings):
                if field.name in data:
                    value = data[field.name]
                    values[field.name] = RgbColor.parse(value) if field.name in COLOR_LABELS else value
            return LightingSettings(**values)
        except (ValueError, TypeError) as error:
            self._corrupt = True
            raise ValueError(f"{self._path.name}: {error}") from error

    def save(self, settings: LightingSettings) -> None:
        if not isinstance(settings, LightingSettings):
            raise ValueError("Ожидались LightingSettings")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._corrupt and self._path.exists():
            backup = self._path.with_name(f"{self._path.name}.corrupt")
            suffix = 1
            while backup.exists():
                backup = self._path.with_name(f"{self._path.name}.corrupt.{suffix}")
                suffix += 1
            shutil.copy2(self._path, backup)
            self._corrupt = False
        data = {"schema_version": 1, "brightness": settings.brightness}
        data.update({name: getattr(settings, name).to_hex() for name in COLOR_LABELS})
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self._path.parent, delete=False) as output:
                temporary_path = Path(output.name)
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self._path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
