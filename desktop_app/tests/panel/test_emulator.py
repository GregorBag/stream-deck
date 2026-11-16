import pytest

from dj_poltorashka.panel.emulator import PanelEmulator
from dj_poltorashka.panel.protocol import Hello, LedUpdate, PanelState, Ping, Pong, StreamDecoder, encode_message


def test_emulator_requires_hello_and_replies_with_initial_state():
    board = PanelEmulator(PanelState((1, 2, 3, 4), 1))
    assert board.receive(encode_message(Ping(0)), 0).errors
    result = board.receive(encode_message(Hello()), 1)
    assert result.errors == ()
    assert StreamDecoder().feed(result.data).messages == (Hello(), board.state)
    result = board.receive(encode_message(Ping(42)), 2)
    assert StreamDecoder().feed(result.data).messages == (Pong(42),)


def test_only_pings_keep_board_alive_and_leds_do_not_extend_deadline():
    board = PanelEmulator()
    board.receive(encode_message(Hello()), 0)
    leds = LedUpdate(25, ((10, 20, 30),) * 24)
    board.receive(encode_message(leds), 1999)
    assert board.connected
    visible = board.lighting(2000)
    assert not board.connected
    assert visible.colors[:8] == ((64, 64, 64),) * 8
    assert visible.colors[8:] == leds.colors[8:]
    assert visible.brightness_percent == 25


def test_invalid_frame_does_not_partially_overwrite_lighting():
    board = PanelEmulator()
    board.receive(encode_message(Hello()), 0)
    leds = LedUpdate(50, ((10, 20, 30),) * 24)
    board.receive(encode_message(leds), 0)
    assert board.receive(b"LEDS 50 " + b"000000" * 23 + b"GGGGGG\n", 1).errors
    assert board.lighting(1) == leds


def test_disconnected_changes_are_included_in_next_initial_state():
    board = PanelEmulator()
    state = PanelState((100, 200, 300, 400), 0xFFFF)
    assert board.set_state(state, 0) == b""
    result = board.receive(encode_message(Hello()), 1)
    assert StreamDecoder().feed(result.data).messages == (Hello(), state)
    assert board.set_state(state, 2) == b""


def test_incorrect_message_direction_is_rejected_by_board():
    board = PanelEmulator()
    board.receive(encode_message(Hello()), 0)
    assert board.receive(encode_message(Pong(0)), 1).errors
    assert board.receive(encode_message(board.state), 2).errors


@pytest.mark.parametrize("now_ms", (-1, True, 1.5))
def test_emulator_rejects_invalid_time(now_ms):
    with pytest.raises(ValueError):
        PanelEmulator().tick(now_ms)
