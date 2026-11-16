from dataclasses import replace

import pytest

from dj_poltorashka.panel.lighting import (
    LightingSettings, LightingSettingsRepository, RgbColor,
)


@pytest.mark.parametrize("text", ("#1020aF", "#000000", "#FFFFFF"))
def test_rgb_round_trip(text):
    assert RgbColor.parse(text).to_hex() == text.upper()


@pytest.mark.parametrize("text", ("#11223344", "112233", "#gg0011", "#12 456", "#123", None))
def test_rgb_rejects_invalid_input(text):
    with pytest.raises(ValueError):
        RgbColor.parse(text)


@pytest.mark.parametrize("value", (-0.1, 0.51, float("nan"), float("inf"), True))
def test_brightness_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        LightingSettings(brightness=value)


def test_brightness_caps_all_rgb_components():
    assert RgbColor(255, 128, 20).to_rgb(0.5) == (128, 64, 10)
    assert RgbColor(255, 128, 20).to_rgb(0) == (0, 0, 0)


def test_settings_persist_separately_and_preserve_corrupt_original(tmp_path):
    path = tmp_path / "lighting.json"
    repository = LightingSettingsRepository(path)
    assert repository.load() == LightingSettings()
    settings = replace(LightingSettings(), mute_unassigned=RgbColor(10, 20, 30), brightness=0.3)
    repository.save(settings)
    assert LightingSettingsRepository(path).load() == settings
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        repository.load()
    repository.save(settings)
    assert path.with_name("lighting.json.corrupt").read_text(encoding="utf-8") == "{broken"
    assert LightingSettingsRepository(path).load() == settings


def test_failed_atomic_write_preserves_previous_file(tmp_path, monkeypatch):
    import dj_poltorashka.panel.lighting as module
    path = tmp_path / "lighting.json"
    repository = LightingSettingsRepository(path)
    repository.save(LightingSettings())
    before = path.read_bytes()
    def fail(*args):
        raise OSError("replace failed")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        repository.save(replace(LightingSettings(), brightness=0.2))
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
