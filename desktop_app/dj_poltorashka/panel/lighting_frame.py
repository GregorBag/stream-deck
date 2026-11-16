"""Расчёт логического кадра подсветки панели."""

from dataclasses import dataclass

from dj_poltorashka.configuration.models import StoredConfiguration
from dj_poltorashka.panel.lighting import LightingSettings, RgbColor


@dataclass(frozen=True)
class LightingFrame:
    """Логический порядок: LED1–LED8 и SW1–SW16; не порядок передачи по проводу."""

    perimeter: tuple[tuple[int, int, int], ...]
    buttons: tuple[tuple[int, int, int], ...]


def build_lighting_frame(
    stored: StoredConfiguration,
    settings: LightingSettings,
    *,
    connected: bool,
    elapsed_ms: int = 0,
    playing_buttons: frozenset[int] = frozenset(),
) -> LightingFrame:
    if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, int) or elapsed_ms < 0:
        raise ValueError("Время должно быть целым неотрицательным числом миллисекунд")
    perimeter = settings.perimeter
    if not connected:
        perimeter = RgbColor(255, 255, 255) if elapsed_ms % 1000 < 500 else RgbColor(0, 0, 0)
    colors = []
    for index, sound in enumerate(stored.active.sound_buttons):
        if sound.sound_id is None:
            colors.append(settings.sound_unassigned)
        else:
            colors.append(settings.sound_playing if index in playing_buttons else settings.sound_ready)
    for channel in stored.active.channels:
        if channel.channel_kind == "unassigned":
            colors.append(settings.mute_unassigned)
        else:
            colors.append(settings.mute_muted if channel.muted else settings.mute_active)
    for slot, preset in enumerate(stored.presets, 1):
        if preset is None:
            colors.append(settings.preset_empty)
        else:
            colors.append(settings.preset_active if stored.active_preset_slot == slot else settings.preset_saved)
    return LightingFrame(
        perimeter=(perimeter.to_rgb(settings.brightness),) * 8,
        buttons=tuple(color.to_rgb(settings.brightness) for color in colors),
    )
