import math

import pytest

from dj_poltorashka.panel.events import (
    MutePressed,
    PanelPauseChanged,
    PresetPressed,
    SliderChanged,
    SoundPressed,
)


@pytest.mark.parametrize("channel_index", (0, 3))
@pytest.mark.parametrize("value", (0.0, 1.0))
def test_slider_accepts_boundary_indexes_and_values(
    channel_index: int,
    value: float,
) -> None:
    assert SliderChanged(channel_index, value) == SliderChanged(channel_index, value)


@pytest.mark.parametrize("channel_index", (-1, 4, True, 1.5))
def test_slider_rejects_invalid_channel_index(channel_index: object) -> None:
    with pytest.raises(IndexError):
        SliderChanged(channel_index, 0.5)


@pytest.mark.parametrize("value", (-0.01, 1.01, True, math.nan, "0.5"))
def test_slider_rejects_invalid_value(value: object) -> None:
    with pytest.raises(ValueError):
        SliderChanged(0, value)


@pytest.mark.parametrize("event_type", (MutePressed,))
@pytest.mark.parametrize("channel_index", (-1, 4, True, 1.5))
def test_channel_button_event_rejects_invalid_index(
    event_type,
    channel_index: object,
) -> None:
    with pytest.raises(IndexError):
        event_type(channel_index)


@pytest.mark.parametrize("button_index", (-1, 8, True, 1.5))
def test_sound_event_rejects_invalid_index(button_index: object) -> None:
    with pytest.raises(IndexError):
        SoundPressed(button_index)


@pytest.mark.parametrize("preset_index", (-1, 3, True, 1.5))
def test_preset_event_rejects_invalid_index(preset_index: object) -> None:
    with pytest.raises(IndexError):
        PresetPressed(preset_index)


def test_button_events_accept_boundary_indexes() -> None:
    assert MutePressed(0).channel_index == 0
    assert MutePressed(3).channel_index == 3
    assert SoundPressed(0).button_index == 0
    assert SoundPressed(7).button_index == 7
    assert PresetPressed(0).preset_index == 0
    assert PresetPressed(2).preset_index == 2


@pytest.mark.parametrize("is_paused", (0, 1, None, "yes"))
def test_pause_event_requires_boolean(is_paused: object) -> None:
    with pytest.raises(ValueError):
        PanelPauseChanged(is_paused)


def test_events_are_immutable() -> None:
    event = SliderChanged(1, 0.25)

    with pytest.raises(AttributeError):
        event.value = 0.75
