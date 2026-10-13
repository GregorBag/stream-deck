"""Детерминированное распределение headroom между голосом и звуками."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BusLevels:
    microphone: float
    sound_total: float
    per_sound: float


def _require_gain(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError("Коэффициент усиления должен быть от 0 до 1")


def calculate_bus_levels(
    microphone_gain: float,
    sound_gain: float,
    active_sound_count: int,
) -> BusLevels:
    _require_gain(microphone_gain)
    _require_gain(sound_gain)
    if (
        isinstance(active_sound_count, bool)
        or not isinstance(active_sound_count, int)
        or active_sound_count < 0
    ):
        raise ValueError("Количество звуков должно быть неотрицательным")
    microphone = float(microphone_gain) * 0.5
    if active_sound_count == 0:
        return BusLevels(microphone, 0.0, 0.0)
    sound_total = float(sound_gain) * 0.5
    return BusLevels(microphone, sound_total, sound_total / active_sound_count)
