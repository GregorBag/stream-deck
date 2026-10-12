import pytest

from dj_poltorashka.panel.event_router import PanelEventRouter
from dj_poltorashka.panel.events import (
    MutePressed,
    PanelPauseChanged,
    PresetPressed,
    SliderChanged,
    SoundPressed,
)


class EventRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def set_volume(self, channel_index: int, value: float) -> None:
        self.calls.append(("set_volume", channel_index, value))

    def toggle_mute(self, channel_index: int) -> None:
        self.calls.append(("toggle_mute", channel_index))

    def press_sound(self, button_index: int) -> None:
        self.calls.append(("press_sound", button_index))

    def load_preset(self, preset_index: int) -> None:
        self.calls.append(("load_preset", preset_index))


def make_router(recorder: EventRecorder) -> PanelEventRouter:
    return PanelEventRouter(
        set_volume=recorder.set_volume,
        toggle_mute=recorder.toggle_mute,
        press_sound=recorder.press_sound,
        load_preset=recorder.load_preset,
    )


@pytest.mark.parametrize(
    ("event", "expected_call"),
    (
        (SliderChanged(2, 0.75), ("set_volume", 2, 0.75)),
        (MutePressed(1), ("toggle_mute", 1)),
        (SoundPressed(6), ("press_sound", 6)),
        (PresetPressed(2), ("load_preset", 2)),
    ),
)
def test_route_dispatches_event_to_matching_operation(
    event: object,
    expected_call: tuple[object, ...],
) -> None:
    recorder = EventRecorder()
    router = make_router(recorder)

    router.route(event)

    assert recorder.calls == [expected_call]


def test_pause_blocks_control_events_until_resumed() -> None:
    recorder = EventRecorder()
    router = make_router(recorder)

    router.route(PanelPauseChanged(True))
    router.route(SliderChanged(0, 0.2))
    router.route(MutePressed(0))
    router.route(SoundPressed(0))
    router.route(PresetPressed(0))

    assert router.is_paused
    assert recorder.calls == []

    router.route(PanelPauseChanged(False))
    router.route(MutePressed(3))

    assert not router.is_paused
    assert recorder.calls == [("toggle_mute", 3)]


def test_unknown_event_is_rejected_without_callback() -> None:
    recorder = EventRecorder()
    router = make_router(recorder)

    with pytest.raises(TypeError, match="событие"):
        router.route(object())

    assert recorder.calls == []
