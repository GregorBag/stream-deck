"""Конфигурация панели для первого запуска приложения."""

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    SoundButtonConfig,
    StoredConfiguration,
)


def create_default_stored_configuration() -> StoredConfiguration:
    """Вернуть готовую к редактированию конфигурацию по умолчанию."""
    panel = PanelConfiguration(
        channels=(
            MixerChannelConfig("master", 1.0, False),
            MixerChannelConfig("unassigned", 0.0, False),
            MixerChannelConfig("unassigned", 0.0, False),
            MixerChannelConfig("unassigned", 0.0, False),
        ),
        sound_buttons=tuple(SoundButtonConfig() for _ in range(8)),
    )
    return StoredConfiguration(
        active=panel,
        baseline=panel,
        presets=(None, None, None),
    )
