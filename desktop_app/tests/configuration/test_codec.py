import copy

import pytest

from dj_poltorashka.configuration.codec import (
    decode_panel_configuration,
    decode_stored_configuration,
    encode_panel_configuration,
    encode_stored_configuration,
)
from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    PresetConfig,
    SoundButtonConfig,
    StoredConfiguration,
)


def make_panel(volume: float = 0.5) -> PanelConfiguration:
    return PanelConfiguration(
        channels=(
            MixerChannelConfig("master", volume, False, display_name="Система"),
            MixerChannelConfig(
                "application",
                0.7,
                True,
                application_path=r"C:\Apps\Player.exe",
                display_name="Player",
            ),
            MixerChannelConfig("microphone", 0.4, False, display_name="Микрофон"),
            MixerChannelConfig("master", 0.3, True),
        ),
        sound_buttons=(
            SoundButtonConfig("intro.mp3", "Заставка"),
            *(SoundButtonConfig() for _ in range(7)),
        ),
    )


def make_stored_configuration() -> StoredConfiguration:
    active = make_panel(0.8)
    baseline = make_panel(0.5)
    return StoredConfiguration(
        active=active,
        baseline=baseline,
        presets=(PresetConfig("Основной", baseline), None, PresetConfig("Игры", active)),
    )


def test_stored_configuration_round_trip_preserves_all_fields() -> None:
    stored = make_stored_configuration()

    encoded = encode_stored_configuration(stored)
    decoded = decode_stored_configuration(encoded)

    assert encoded["schema_version"] == 1
    assert decoded == stored


def test_panel_configuration_round_trip_preserves_all_fields() -> None:
    panel = make_panel()

    encoded = encode_panel_configuration(panel)
    decoded = decode_panel_configuration(encoded)

    assert decoded == panel


def test_decoder_rejects_unknown_schema_version() -> None:
    encoded = encode_stored_configuration(make_stored_configuration())
    encoded["schema_version"] = 2

    with pytest.raises(ValueError, match="schema_version"):
        decode_stored_configuration(encoded)


def test_decoder_rejects_missing_required_field() -> None:
    encoded = encode_stored_configuration(make_stored_configuration())
    del encoded["active"]

    with pytest.raises(ValueError, match="active"):
        decode_stored_configuration(encoded)


def test_decoder_rejects_invalid_channel_kind() -> None:
    encoded = encode_stored_configuration(make_stored_configuration())
    active = encoded["active"]
    assert isinstance(active, dict)
    channels = active["channels"]
    assert isinstance(channels, list)
    channel = channels[0]
    assert isinstance(channel, dict)
    channel["channel_kind"] = "speakers"

    with pytest.raises(ValueError, match=r"active\.channels\[0\]\.channel_kind"):
        decode_stored_configuration(encoded)


def test_decoder_wraps_model_validation_error() -> None:
    encoded = encode_stored_configuration(make_stored_configuration())
    invalid = copy.deepcopy(encoded)
    active = invalid["active"]
    assert isinstance(active, dict)
    channels = active["channels"]
    assert isinstance(channels, list)
    channel = channels[0]
    assert isinstance(channel, dict)
    channel["volume"] = 2.0

    with pytest.raises(ValueError, match=r"active\.channels\[0\]"):
        decode_stored_configuration(invalid)
