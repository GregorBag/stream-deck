from dj_poltorashka.configuration.defaults import (
    create_default_stored_configuration,
)
from dj_poltorashka.configuration.models import SoundButtonConfig


def test_default_configuration_has_expected_channels_buttons_and_presets() -> None:
    stored = create_default_stored_configuration()

    assert stored.active == stored.baseline
    assert stored.presets == (None, None, None)
    assert stored.active.channels[0].channel_kind == "master"
    assert stored.active.channels[0].volume == 1.0
    assert stored.active.channels[0].muted is False
    assert tuple(
        (channel.channel_kind, channel.volume, channel.muted)
        for channel in stored.active.channels[1:]
    ) == (
        ("unassigned", 0.0, False),
        ("unassigned", 0.0, False),
        ("unassigned", 0.0, False),
    )
    assert stored.active.sound_buttons == tuple(SoundButtonConfig() for _ in range(8))
