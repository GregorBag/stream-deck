"""Чистые операции редактирования конфигурации панели."""

from dataclasses import replace

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    SoundButtonConfig,
)


class PanelConfigurationEditor:
    """Создаёт изменённые конфигурации, не меняя исходные объекты."""

    @staticmethod
    def set_channel(
        panel: PanelConfiguration,
        channel_index: int,
        channel: MixerChannelConfig,
    ) -> PanelConfiguration:
        PanelConfigurationEditor._require_index(channel_index, len(panel.channels))
        channels = list(panel.channels)
        channels[channel_index] = channel
        return PanelConfiguration(tuple(channels), panel.sound_buttons)

    @staticmethod
    def set_volume(
        panel: PanelConfiguration,
        channel_index: int,
        volume: float,
    ) -> PanelConfiguration:
        PanelConfigurationEditor._require_index(channel_index, len(panel.channels))
        channel = replace(panel.channels[channel_index], volume=volume)
        return PanelConfigurationEditor.set_channel(panel, channel_index, channel)

    @staticmethod
    def toggle_mute(
        panel: PanelConfiguration,
        channel_index: int,
    ) -> PanelConfiguration:
        PanelConfigurationEditor._require_index(channel_index, len(panel.channels))
        current = panel.channels[channel_index]
        channel = replace(current, muted=not current.muted)
        return PanelConfigurationEditor.set_channel(panel, channel_index, channel)

    @staticmethod
    def set_sound(
        panel: PanelConfiguration,
        button_index: int,
        sound: SoundButtonConfig,
    ) -> PanelConfiguration:
        PanelConfigurationEditor._require_index(
            button_index,
            len(panel.sound_buttons),
        )
        sound_buttons = list(panel.sound_buttons)
        sound_buttons[button_index] = sound
        return PanelConfiguration(panel.channels, tuple(sound_buttons))

    @staticmethod
    def clear_sound(
        panel: PanelConfiguration,
        button_index: int,
    ) -> PanelConfiguration:
        return PanelConfigurationEditor.set_sound(
            panel,
            button_index,
            SoundButtonConfig(),
        )

    @staticmethod
    def _require_index(index: int, item_count: int) -> None:
        if isinstance(index, bool) or not isinstance(index, int):
            raise IndexError("Индекс должен быть целым числом")
        if not 0 <= index < item_count:
            raise IndexError("Индекс находится вне допустимого диапазона")
