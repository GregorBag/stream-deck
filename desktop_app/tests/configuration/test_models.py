import math

import pytest

from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
    StoredConfiguration,
    normalize_executable_path,
)


def make_channels(count: int = 4) -> tuple[MixerChannelConfig, ...]:
    return tuple(
        MixerChannelConfig(channel_kind="unassigned", volume=0.5, muted=False)
        for _ in range(count)
    )


def make_buttons(count: int = 8) -> tuple[SoundButtonConfig, ...]:
    return tuple(SoundButtonConfig() for _ in range(count))


def make_panel() -> PanelConfiguration:
    return PanelConfiguration(channels=make_channels(), sound_buttons=make_buttons())


@pytest.mark.parametrize(
    ("channel_count", "button_count"),
    ((3, 8), (5, 8), (4, 7), (4, 9)),
)
def test_panel_configuration_requires_four_channels_and_eight_buttons(
    channel_count: int,
    button_count: int,
) -> None:
    with pytest.raises(ValueError):
        PanelConfiguration(
            channels=make_channels(channel_count),
            sound_buttons=make_buttons(button_count),
        )


@pytest.mark.parametrize("volume", (-0.01, 1.01, math.nan))
def test_volume_must_be_between_zero_and_one(volume: float) -> None:
    with pytest.raises(ValueError):
        MixerChannelConfig(channel_kind="master", volume=volume, muted=False)


@pytest.mark.parametrize("application_path", (None, "", "Discord.exe", "apps\\Discord.exe"))
def test_application_channel_requires_absolute_executable_path(
    application_path: str | None,
) -> None:
    with pytest.raises(ValueError):
        MixerChannelConfig(
            channel_kind="application",
            volume=0.5,
            muted=False,
            application_path=application_path,
            display_name="Discord",
        )


@pytest.mark.parametrize("channel_kind", ("unassigned", "master", "microphone"))
def test_non_application_channel_rejects_executable_path(channel_kind: str) -> None:
    with pytest.raises(ValueError):
        MixerChannelConfig(
            channel_kind=channel_kind,
            volume=0.5,
            muted=False,
            application_path=r"C:\Apps\Discord.exe",
        )


def test_unassigned_channel_is_valid_without_application_path() -> None:
    channel = MixerChannelConfig(
        channel_kind="unassigned",
        volume=0.0,
        muted=False,
    )

    assert channel.channel_kind == "unassigned"
    assert channel.application_path is None


def test_executable_path_is_normalized_case_insensitively() -> None:
    first = normalize_executable_path(r"C:/Program Files/Discord/DISCORD.exe")
    second = normalize_executable_path(r"c:\program files\discord\discord.exe")

    assert first == r"c:\program files\discord\discord.exe"
    assert second == first


@pytest.mark.parametrize(
    ("duplicate_channels", "error_fragment"),
    (
        (
            (
                MixerChannelConfig("master", 0.5, False),
                MixerChannelConfig("master", 0.7, True),
            ),
            "Общая громкость",
        ),
        (
            (
                MixerChannelConfig("microphone", 0.5, False),
                MixerChannelConfig("microphone", 0.7, True),
            ),
            "Микрофон",
        ),
        (
            (
                MixerChannelConfig(
                    "application",
                    0.5,
                    False,
                    application_path=r"C:\Apps\Player.exe",
                ),
                MixerChannelConfig(
                    "application",
                    0.7,
                    True,
                    application_path=r"c:\apps\.\player.exe",
                ),
            ),
            "player.exe",
        ),
    ),
)
def test_panel_configuration_rejects_duplicate_audio_targets(
    duplicate_channels: tuple[MixerChannelConfig, MixerChannelConfig],
    error_fragment: str,
) -> None:
    channels = (
        *duplicate_channels,
        MixerChannelConfig("unassigned", 0.0, False),
        MixerChannelConfig("unassigned", 0.0, False),
    )

    with pytest.raises(ValueError, match=error_fragment):
        PanelConfiguration(channels=channels, sound_buttons=make_buttons())


def test_panel_configuration_accepts_unassigned_and_distinct_applications() -> None:
    channels = (
        MixerChannelConfig("unassigned", 0.0, False),
        MixerChannelConfig("unassigned", 0.0, False),
        MixerChannelConfig(
            "application",
            0.5,
            False,
            application_path=r"C:\Apps\Player.exe",
        ),
        MixerChannelConfig(
            "application",
            0.7,
            True,
            application_path=r"C:\Apps\Browser.exe",
        ),
    )

    panel = PanelConfiguration(channels=channels, sound_buttons=make_buttons())

    assert panel.channels == channels


@pytest.mark.parametrize(
    ("sound_id", "display_name"),
    (("sample.mp3", None), (None, "Sample")),
)
def test_sound_button_requires_id_and_display_name_together(
    sound_id: str | None,
    display_name: str | None,
) -> None:
    with pytest.raises(ValueError):
        SoundButtonConfig(sound_id=sound_id, display_name=display_name)


@pytest.mark.parametrize("preset_count", (2, 4))
def test_stored_configuration_requires_three_preset_slots(preset_count: int) -> None:
    panel = make_panel()

    with pytest.raises(ValueError):
        StoredConfiguration(
            active=panel,
            baseline=panel,
            presets=tuple(None for _ in range(preset_count)),
        )


def test_channel_kind_must_be_supported() -> None:
    with pytest.raises(ValueError):
        MixerChannelConfig(channel_kind="speakers", volume=0.5, muted=False)


@pytest.mark.parametrize("name", ("", "   "))
def test_preset_name_must_not_be_empty(name: str) -> None:
    with pytest.raises(ValueError):
        PresetConfig(name=name, panel=make_panel())
