"""Маршрутизация событий панели в операции приложения."""

from collections.abc import Callable

from dj_poltorashka.panel.events import (
    MutePressed,
    PanelEvent,
    PanelPauseChanged,
    PresetPressed,
    SliderChanged,
    SoundPressed,
)


class PanelEventRouter:
    """Передаёт проверенные события соответствующим операциям."""

    def __init__(
        self,
        set_volume: Callable[[int, float], None],
        toggle_mute: Callable[[int], None],
        press_sound: Callable[[int], None],
        load_preset: Callable[[int], None],
    ):
        self._set_volume = set_volume
        self._toggle_mute = toggle_mute
        self._press_sound = press_sound
        self._load_preset = load_preset
        self._is_paused = False

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def route(self, event: PanelEvent) -> None:
        if isinstance(event, PanelPauseChanged):
            self._is_paused = event.is_paused
            return

        is_control_event = isinstance(
            event,
            (SliderChanged, MutePressed, SoundPressed, PresetPressed),
        )
        if not is_control_event:
            raise TypeError("Неизвестное событие панели")
        if self._is_paused:
            return

        if isinstance(event, SliderChanged):
            self._set_volume(event.channel_index, event.value)
        elif isinstance(event, MutePressed):
            self._toggle_mute(event.channel_index)
        elif isinstance(event, SoundPressed):
            self._press_sound(event.button_index)
        else:
            self._load_preset(event.preset_index)
