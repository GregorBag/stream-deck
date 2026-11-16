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
            MixerChannelConfig("unassigned", 0.3, True),
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
        presets=(PresetConfig("Основной", baseline), None, PresetConfig("Игры", active), PresetConfig("Четвёртый", active)),
    )


def test_stored_configuration_round_trip_preserves_all_fields() -> None:
    stored = make_stored_configuration()

    encoded = encode_stored_configuration(stored)
    decoded = decode_stored_configuration(encoded)

    assert encoded["schema_version"] == 3
    assert decoded == stored


def test_panel_configuration_round_trip_preserves_all_fields() -> None:
    panel = make_panel()

    encoded = encode_panel_configuration(panel)
    decoded = decode_panel_configuration(encoded)

    assert decoded == panel


def test_unassigned_channel_round_trip_keeps_schema_version_three() -> None:
    panel = PanelConfiguration(
        channels=(
            MixerChannelConfig("master", 1.0, False),
            MixerChannelConfig("unassigned", 0.0, False),
            MixerChannelConfig("unassigned", 0.0, False),
            MixerChannelConfig("unassigned", 0.0, False),
        ),
        sound_buttons=tuple(SoundButtonConfig() for _ in range(8)),
    )
    stored = StoredConfiguration(
        active=panel,
        baseline=panel,
        presets=(None, None, None, None),
    )

    encoded = encode_stored_configuration(stored)

    assert encoded["schema_version"] == 3
    assert decode_stored_configuration(encoded) == stored


def test_decoder_rejects_unknown_schema_version() -> None:
    encoded = encode_stored_configuration(make_stored_configuration())
    encoded["schema_version"] = 4

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


def test_decode_rejects_configuration_with_duplicate_targets() -> None:
    encoded = encode_panel_configuration(make_panel())
    channels = encoded["channels"]
    assert isinstance(channels, list)
    duplicate = channels[3]
    assert isinstance(duplicate, dict)
    duplicate["channel_kind"] = "master"

    with pytest.raises(ValueError, match=r"panel: Общая громкость"):
        decode_panel_configuration(encoded)


@pytest.mark.parametrize("occupied", (False, True))
def test_legacy_configuration_adds_empty_fourth_slot_without_changing_data(occupied):
    encoded = encode_stored_configuration(make_stored_configuration())
    encoded["schema_version"] = 1
    encoded["presets"] = encoded["presets"][:3] if occupied else [None] * 3
    original = copy.deepcopy(encoded)

    migrated = decode_stored_configuration(encoded)
    saved = encode_stored_configuration(migrated)

    assert encoded == original
    assert saved["schema_version"] == 3
    assert saved["active"] == original["active"]
    assert saved["baseline"] == original["baseline"]
    assert saved["presets"] == [*original["presets"], None]
    assert decode_stored_configuration(saved) == migrated


@pytest.mark.parametrize("version, count", [(1, 2), (1, 4), (2, 3), (2, 5)])
def test_decoder_rejects_wrong_slot_count_for_schema_version(version, count):
    encoded = encode_stored_configuration(make_stored_configuration())
    encoded["schema_version"] = version
    encoded["presets"] = [None] * count
    with pytest.raises(ValueError):
        decode_stored_configuration(encoded)


@pytest.mark.parametrize("slot", (1, 3, 4))
def test_active_preset_slot_survives_round_trip(slot):
    from dataclasses import replace
    stored = replace(make_stored_configuration(), active_preset_slot=slot)
    assert decode_stored_configuration(encode_stored_configuration(stored)) == stored


@pytest.mark.parametrize("slot", (0, 5, True, 1.5, 2))
def test_invalid_or_empty_active_slot_is_rejected(slot):
    encoded = encode_stored_configuration(make_stored_configuration())
    encoded["active_preset_slot"] = slot
    with pytest.raises(ValueError):
        decode_stored_configuration(encoded)


def test_version_two_migrates_without_guessing_active_slot():
    encoded = encode_stored_configuration(make_stored_configuration())
    encoded["schema_version"] = 2
    del encoded["active_preset_slot"]
    assert decode_stored_configuration(encoded).active_preset_slot is None
