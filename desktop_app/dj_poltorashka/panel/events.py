"""Типизированные события симулятора и физической панели."""

from dataclasses import dataclass
import math


def _require_index(index: int, item_count: int) -> None:
    if isinstance(index, bool) or not isinstance(index, int):
        raise IndexError("Индекс должен быть целым числом")
    if not 0 <= index < item_count:
        raise IndexError("Индекс находится вне допустимого диапазона")


@dataclass(frozen=True)
class SliderChanged:
    channel_index: int
    value: float

    def __post_init__(self) -> None:
        _require_index(self.channel_index, 4)
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError("Значение ползунка должно быть числом")
        if not math.isfinite(self.value) or not 0.0 <= self.value <= 1.0:
            raise ValueError("Значение ползунка должно быть от 0.0 до 1.0")
        object.__setattr__(self, "value", float(self.value))


@dataclass(frozen=True)
class MutePressed:
    channel_index: int

    def __post_init__(self) -> None:
        _require_index(self.channel_index, 4)


@dataclass(frozen=True)
class SoundPressed:
    button_index: int

    def __post_init__(self) -> None:
        _require_index(self.button_index, 8)


@dataclass(frozen=True)
class PresetPressed:
    preset_index: int

    def __post_init__(self) -> None:
        _require_index(self.preset_index, 3)


@dataclass(frozen=True)
class PanelPauseChanged:
    is_paused: bool

    def __post_init__(self) -> None:
        if not isinstance(self.is_paused, bool):
            raise ValueError("Состояние паузы должно быть логическим значением")


PanelEvent = (
    SliderChanged
    | MutePressed
    | SoundPressed
    | PresetPressed
    | PanelPauseChanged
)
