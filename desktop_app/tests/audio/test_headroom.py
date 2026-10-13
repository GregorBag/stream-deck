import pytest

from dj_poltorashka.audio.headroom import calculate_bus_levels


def test_bus_levels_for_zero_one_and_three_sounds() -> None:
    zero = calculate_bus_levels(1.0, 0.8, 0)
    one = calculate_bus_levels(1.0, 0.8, 1)
    three = calculate_bus_levels(1.0, 0.8, 3)

    assert (zero.microphone, zero.sound_total, zero.per_sound) == (0.5, 0.0, 0.0)
    assert (one.microphone, one.sound_total, one.per_sound) == (0.5, 0.4, 0.4)
    assert three.microphone == 0.5
    assert three.sound_total == 0.4
    assert three.per_sound == pytest.approx(0.13333333333333333)


@pytest.mark.parametrize(
    ("microphone_gain", "sound_gain", "count"),
    [(-0.1, 1.0, 1), (1.0, 1.1, 1), (float("nan"), 1.0, 1), (1.0, 1.0, -1)],
)
def test_bus_levels_reject_invalid_inputs(
    microphone_gain: float,
    sound_gain: float,
    count: int,
) -> None:
    with pytest.raises(ValueError):
        calculate_bus_levels(microphone_gain, sound_gain, count)
