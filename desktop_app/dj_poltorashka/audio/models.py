"""Неизменяемые типы аудиосистемы."""

from dataclasses import dataclass
import math
from typing import Literal

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    normalize_executable_path,
)


AudioTargetKind = Literal["master", "application", "microphone"]
AudioAvailability = Literal["active", "waiting", "unavailable"]

_TARGET_KINDS = ("master", "application", "microphone")
_AVAILABILITIES = ("active", "waiting", "unavailable")


def _require_volume(volume: float) -> None:
    if isinstance(volume, bool) or not isinstance(volume, (int, float)):
        raise ValueError("Громкость должна быть числом")
    if not math.isfinite(volume) or not 0.0 <= volume <= 1.0:
        raise ValueError("Громкость должна находиться в диапазоне от 0.0 до 1.0")


@dataclass(frozen=True)
class AudioTarget:
    """Устойчивая цель управления аудиоканалом."""

    target_kind: AudioTargetKind
    application_path: str | None = None

    def __post_init__(self) -> None:
        if self.target_kind not in _TARGET_KINDS:
            raise ValueError("Неизвестный вид аудиоцели")
        if self.target_kind == "application":
            if self.application_path is None:
                raise ValueError("Программной цели требуется путь к программе")
            object.__setattr__(
                self,
                "application_path",
                normalize_executable_path(self.application_path),
            )
        elif self.application_path is not None:
            raise ValueError("Путь к программе допустим только для программной цели")

    @classmethod
    def for_channel(cls, channel: MixerChannelConfig) -> "AudioTarget | None":
        if channel.channel_kind == "unassigned":
            return None
        return cls(channel.channel_kind, channel.application_path)


@dataclass(frozen=True)
class AudioMemberState:
    """Фактическое состояние endpoint или одной аудиосессии."""

    member_id: str
    volume: float
    muted: bool
    display_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.member_id, str) or not self.member_id:
            raise ValueError("Идентификатор участника не должен быть пустым")
        _require_volume(self.volume)
        if not isinstance(self.muted, bool):
            raise ValueError("Состояние mute должно быть логическим значением")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("Имя аудиоцели не должно быть пустым")
        object.__setattr__(self, "display_name", self.display_name.strip())


@dataclass(frozen=True)
class AudioTargetSnapshot:
    """Снимок всех участников одной аудиоцели."""

    members: tuple[AudioMemberState, ...]
    error: str | None = None

    def __post_init__(self) -> None:
        members = tuple(self.members)
        if not all(isinstance(member, AudioMemberState) for member in members):
            raise ValueError("Снимок должен содержать состояния аудиоучастников")
        member_ids = tuple(member.member_id for member in members)
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("Идентификаторы аудиоучастников не должны повторяться")
        if self.error is not None:
            if not isinstance(self.error, str) or not self.error.strip():
                raise ValueError("Описание ошибки не должно быть пустым")
            object.__setattr__(self, "error", self.error.strip())
        object.__setattr__(self, "members", members)


@dataclass(frozen=True)
class ChannelAudioUpdate:
    """Runtime-состояние одного назначенного канала."""

    channel_index: int
    volume: float
    muted: bool
    availability: AudioAvailability
    display_name: str | None
    externally_changed: bool

    def __post_init__(self) -> None:
        if isinstance(self.channel_index, bool) or not isinstance(
            self.channel_index,
            int,
        ):
            raise ValueError("Индекс канала должен быть целым числом")
        if self.channel_index < 0:
            raise ValueError("Индекс канала не должен быть отрицательным")
        _require_volume(self.volume)
        if not isinstance(self.muted, bool):
            raise ValueError("Состояние mute должно быть логическим значением")
        if self.availability not in _AVAILABILITIES:
            raise ValueError("Неизвестное состояние доступности аудиоцели")
        if self.display_name is not None:
            if not isinstance(self.display_name, str) or not self.display_name.strip():
                raise ValueError("Имя аудиоцели не должно быть пустым")
            object.__setattr__(self, "display_name", self.display_name.strip())
        if not isinstance(self.externally_changed, bool):
            raise ValueError("Признак внешнего изменения должен быть логическим")
