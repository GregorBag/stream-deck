import pytest

from dj_poltorashka.configuration.defaults import (
    create_default_stored_configuration,
)
from dj_poltorashka.configuration.editor import PanelConfigurationEditor
from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    SoundButtonConfig,
)


def make_panel() -> PanelConfiguration:
    return create_default_stored_configuration().active


def test_set_channel_replaces_only_selected_channel() -> None:
    panel = make_panel()
    replacement = MixerChannelConfig(
        "application",
        0.6,
        False,
        application_path=r"C:\Apps\Player.exe",
        display_name="Player",
    )

    changed = PanelConfigurationEditor.set_channel(panel, 2, replacement)

    assert changed is not panel
    assert changed.channels[2] == replacement
    assert changed.channels[:2] == panel.channels[:2]
    assert changed.channels[3] == panel.channels[3]
    assert changed.sound_buttons == panel.sound_buttons


def test_set_volume_preserves_other_channel_fields_and_original_panel() -> None:
    panel = make_panel()

    changed = PanelConfigurationEditor.set_volume(panel, 0, 0.35)

    assert changed.channels[0] == MixerChannelConfig("master", 0.35, False)
    assert panel.channels[0] == MixerChannelConfig("master", 1.0, False)
    assert changed.channels[1:] == panel.channels[1:]


def test_toggle_mute_preserves_volume_and_toggles_twice() -> None:
    panel = make_panel()

    muted = PanelConfigurationEditor.toggle_mute(panel, 0)
    unmuted = PanelConfigurationEditor.toggle_mute(muted, 0)

    assert muted.channels[0] == MixerChannelConfig("master", 1.0, True)
    assert unmuted == panel


def test_set_sound_replaces_only_selected_button() -> None:
    panel = make_panel()
    sound = SoundButtonConfig("intro.mp3", "Заставка")

    changed = PanelConfigurationEditor.set_sound(panel, 5, sound)

    assert changed.sound_buttons[5] == sound
    assert changed.sound_buttons[:5] == panel.sound_buttons[:5]
    assert changed.sound_buttons[6:] == panel.sound_buttons[6:]
    assert changed.channels == panel.channels


def test_clear_sound_restores_empty_button() -> None:
    panel = PanelConfigurationEditor.set_sound(
        make_panel(),
        1,
        SoundButtonConfig("alert.wav", "Сигнал"),
    )

    changed = PanelConfigurationEditor.clear_sound(panel, 1)

    assert changed.sound_buttons[1] == SoundButtonConfig()
    assert panel.sound_buttons[1] == SoundButtonConfig("alert.wav", "Сигнал")


@pytest.mark.parametrize("channel_index", (-1, 4, True, 1.5))
def test_channel_operations_reject_invalid_index_without_changing_panel(
    channel_index: object,
) -> None:
    panel = make_panel()

    with pytest.raises(IndexError):
        PanelConfigurationEditor.set_volume(panel, channel_index, 0.4)

    assert panel == make_panel()


@pytest.mark.parametrize("button_index", (-1, 8, True, 2.5))
def test_sound_operations_reject_invalid_index_without_changing_panel(
    button_index: object,
) -> None:
    panel = make_panel()

    with pytest.raises(IndexError):
        PanelConfigurationEditor.clear_sound(panel, button_index)

    assert panel == make_panel()


@pytest.mark.parametrize("volume", (-0.01, 1.01, True, float("nan")))
def test_set_volume_rejects_invalid_value_without_changing_panel(
    volume: object,
) -> None:
    panel = make_panel()

    with pytest.raises(ValueError):
        PanelConfigurationEditor.set_volume(panel, 0, volume)

    assert panel == make_panel()
