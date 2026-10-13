from pathlib import Path

import pytest

import dj_poltorashka.audio.routing_settings as routing_settings_module
from dj_poltorashka.audio.routing_settings import (
    AudioRoutingSettings,
    AudioRoutingSettingsRepository,
)


def test_default_routing_settings_use_system_devices() -> None:
    settings = AudioRoutingSettings()

    assert settings.input_device_id is None
    assert settings.monitor_device_id is None
    assert settings.microphone_gain == 1.0
    assert settings.sound_gain == 1.0


@pytest.mark.parametrize("gain", [-0.01, 1.01, float("inf"), float("nan"), True])
def test_routing_settings_reject_invalid_gain(gain: float) -> None:
    with pytest.raises(ValueError):
        AudioRoutingSettings(microphone_gain=gain)


@pytest.mark.parametrize("device_id", ["", "   ", 42])
def test_routing_settings_reject_invalid_device_id(device_id: object) -> None:
    with pytest.raises(ValueError):
        AudioRoutingSettings(input_device_id=device_id)  # type: ignore[arg-type]


def test_repository_round_trips_routing_settings(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    repository = AudioRoutingSettingsRepository(path)
    expected = AudioRoutingSettings("a1", "b2", 0.25, 0.75)

    repository.save(expected)

    assert repository.load() == expected
    assert not tuple(tmp_path.glob("*.tmp"))


def test_repository_preserves_corrupt_settings(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(b"{invalid")
    (tmp_path / "settings.json.corrupt").write_bytes(b"older")
    repository = AudioRoutingSettingsRepository(path)

    with pytest.raises(ValueError, match="settings.json"):
        repository.load()
    repository.save(AudioRoutingSettings(sound_gain=0.4))

    assert (tmp_path / "settings.json.corrupt.1").read_bytes() == b"{invalid"
    assert repository.load() == AudioRoutingSettings(sound_gain=0.4)


def test_failed_atomic_replace_keeps_previous_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "settings.json"
    repository = AudioRoutingSettingsRepository(path)
    original = AudioRoutingSettings(sound_gain=0.2)
    repository.save(original)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(routing_settings_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        repository.save(AudioRoutingSettings(sound_gain=0.9))

    assert repository.load() == original
    assert not tuple(tmp_path.glob("*.tmp"))
