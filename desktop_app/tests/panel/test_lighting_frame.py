from dataclasses import replace

from dj_poltorashka.configuration.defaults import create_default_stored_configuration
from dj_poltorashka.configuration.models import PresetConfig
from dj_poltorashka.panel.lighting import LightingSettings, RgbColor
from dj_poltorashka.panel.lighting_frame import build_lighting_frame


def test_disconnection_blinks_only_perimeter_at_one_hertz():
    stored = create_default_stored_configuration()
    settings = LightingSettings()
    connected = build_lighting_frame(stored, settings, connected=True)
    for elapsed, white in ((0, True), (499, True), (500, False), (999, False), (1000, True)):
        frame = build_lighting_frame(stored, settings, connected=False, elapsed_ms=elapsed)
        assert frame.perimeter == (((128, 128, 128) if white else (0, 0, 0)),) * 8
        assert frame.buttons == connected.buttons
    assert len(connected.buttons) == 16


def test_mute_has_three_configurable_states_and_active_preset_is_highlighted():
    stored = create_default_stored_configuration()
    channels = list(stored.active.channels)
    channels[0] = replace(channels[0], channel_kind="master", muted=False)
    channels[1] = replace(channels[1], channel_kind="microphone", muted=True)
    channels[2] = replace(channels[2], channel_kind="unassigned", muted=False)
    panel = replace(stored.active, channels=tuple(channels))
    stored = replace(stored, active=panel, presets=(PresetConfig("Первый", panel), None, None, PresetConfig("Четвёртый", panel)), active_preset_slot=4)
    settings = LightingSettings(mute_active=RgbColor(10, 0, 0), mute_muted=RgbColor(0, 20, 0), mute_unassigned=RgbColor(0, 0, 30))
    frame = build_lighting_frame(stored, settings, connected=True)
    assert frame.buttons[8:11] == ((5, 0, 0), (0, 10, 0), (0, 0, 15))
    assert frame.buttons[12] == settings.preset_saved.to_rgb(0.5)
    assert frame.buttons[15] == settings.preset_active.to_rgb(0.5)
