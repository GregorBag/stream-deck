"""Неизменяемые модели конфигурации звуковой панели."""

from dataclasses import dataclass
import math
import ntpath
from pathlib import PureWindowsPath
from typing import Literal


ChannelKind = Literal["unassigned", "master", "application", "microphone"]

_CHANNEL_KINDS = ("unassigned", "master", "application", "microphone")
_CHANNEL_COUNT = 4
_SOUND_BUTTON_COUNT = 8
_PRESET_COUNT = 3


def normalize_executable_path(path: str) -> str:
    """Вернуть абсолютный путь Windows в нормализованном виде."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Путь к программе не должен быть пустым")

    normalized = ntpath.normcase(ntpath.normpath(path.strip()))
    if not PureWindowsPath(normalized).is_absolute():
        raise ValueError("Путь к программе должен быть абсолютным")

    return normalized


@dataclass(frozen=True)
class MixerChannelConfig:
    """Назначение и сохранённое состояние одного канала микшера."""

    channel_kind: ChannelKind
    volume: float
    muted: bool
    application_path: str | None = None
    display_name: str | None = None

    def __post_init__(self) -> None:
        if self.channel_kind not in _CHANNEL_KINDS:
            raise ValueError("Неизвестный вид аудиоканала")
        if isinstance(self.volume, bool) or not isinstance(self.volume, (int, float)):
            raise ValueError("Громкость должна быть числом")
        if not math.isfinite(self.volume) or not 0.0 <= self.volume <= 1.0:
            raise ValueError("Громкость должна находиться в диапазоне от 0.0 до 1.0")
        if not isinstance(self.muted, bool):
            raise ValueError("Состояние mute должно быть логическим значением")
        if self.display_name is not None:
            if not isinstance(self.display_name, str) or not self.display_name.strip():
                raise ValueError("Отображаемое имя не должно быть пустым")
            object.__setattr__(self, "display_name", self.display_name.strip())

        if self.channel_kind == "application":
            if self.application_path is None:
                raise ValueError("Программному каналу требуется путь к программе")
            object.__setattr__(
                self,
                "application_path",
                normalize_executable_path(self.application_path),
            )
        elif self.application_path is not None:
            raise ValueError("Путь к программе допустим только для программного канала")


@dataclass(frozen=True)
class SoundButtonConfig:
    """Назначение одной звуковой кнопки."""

    sound_id: str | None = None
    display_name: str | None = None

    def __post_init__(self) -> None:
        if (self.sound_id is None) != (self.display_name is None):
            raise ValueError("Идентификатор и имя звука должны задаваться вместе")
        if self.sound_id is None:
            return
        if not isinstance(self.sound_id, str) or not self.sound_id.strip():
            raise ValueError("Идентификатор звука не должен быть пустым")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("Имя звука не должно быть пустым")
        object.__setattr__(self, "sound_id", self.sound_id.strip())
        object.__setattr__(self, "display_name", self.display_name.strip())


@dataclass(frozen=True)
class PanelConfiguration:
    """Полная рабочая конфигурация физических элементов панели."""

    channels: tuple[MixerChannelConfig, ...]
    sound_buttons: tuple[SoundButtonConfig, ...]

    def __post_init__(self) -> None:
        channels = tuple(self.channels)
        sound_buttons = tuple(self.sound_buttons)
        if len(channels) != _CHANNEL_COUNT:
            raise ValueError("Конфигурация должна содержать четыре канала")
        if len(sound_buttons) != _SOUND_BUTTON_COUNT:
            raise ValueError("Конфигурация должна содержать восемь звуковых кнопок")
        if not all(isinstance(channel, MixerChannelConfig) for channel in channels):
            raise ValueError("Все каналы должны иметь тип MixerChannelConfig")
        if not all(isinstance(button, SoundButtonConfig) for button in sound_buttons):
            raise ValueError("Все кнопки должны иметь тип SoundButtonConfig")
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "sound_buttons", sound_buttons)


@dataclass(frozen=True)
class PresetConfig:
    """Именованный снимок конфигурации панели."""

    name: str
    panel: PanelConfiguration

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Имя пресета не должно быть пустым")
        if not isinstance(self.panel, PanelConfiguration):
            raise ValueError("Пресет должен содержать конфигурацию панели")
        object.__setattr__(self, "name", self.name.strip())


@dataclass(frozen=True)
class StoredConfiguration:
    """Активная конфигурация, база сравнения и три слота пресетов."""

    active: PanelConfiguration
    baseline: PanelConfiguration
    presets: tuple[PresetConfig | None, ...]

    def __post_init__(self) -> None:
        presets = tuple(self.presets)
        if not isinstance(self.active, PanelConfiguration):
            raise ValueError("Активная настройка должна быть конфигурацией панели")
        if not isinstance(self.baseline, PanelConfiguration):
            raise ValueError("Базовая настройка должна быть конфигурацией панели")
        if len(presets) != _PRESET_COUNT:
            raise ValueError("Хранилище должно содержать три слота пресетов")
        if not all(preset is None or isinstance(preset, PresetConfig) for preset in presets):
            raise ValueError("Слот должен быть пустым или содержать PresetConfig")
        object.__setattr__(self, "presets", presets)
