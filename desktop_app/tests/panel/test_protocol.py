from dataclasses import replace
import random

import pytest

from dj_poltorashka.panel.protocol import (
    MAX_LINE_BYTES, Hello, LedUpdate, LightingUpdateTracker, PanelState,
    Ping, Pong, StreamDecoder, decode_line, encode_message,
)


def make_led_update():
    return LedUpdate(50, tuple((index, index + 1, index + 2) for index in range(24)))


MESSAGES = (
    Hello(), Ping(0), Ping(65535), Pong(42),
    PanelState((0, 1023, 512, 1), 0x8001), make_led_update(),
)


@pytest.mark.parametrize("message", MESSAGES)
def test_message_round_trip(message):
    encoded = encode_message(message)
    assert encoded.endswith(b"\n")
    assert len(encoded) - 1 <= MAX_LINE_BYTES
    assert decode_line(encoded[:-1]) == message


def test_wire_format_preserves_button_bits_and_logical_led_order():
    assert encode_message(PanelState((1, 2, 3, 4), 0x8001)) == b"STATE 1 2 3 4 8001\n"
    encoded = encode_message(make_led_update())
    assert encoded.startswith(b"LEDS 50 000102010203")
    assert encoded.endswith(b"171819\n")


@pytest.mark.parametrize("line", (
    b"HELLO OTHER 1", b"HELLO DJ_POLTORASHKA 2", b"HELLO DJ_POLTORASHKA -1",
    b"PING 65536", b"PING -1", b"PING +1", b"PING 1.0", b"PING  1", b" PING 1",
    b"PONG", b"PONG 1 extra", b"STATE 0 0 0 1024 0000", b"STATE 0 0 0 0000",
    b"STATE 0 0 0 0 FFFFF", b"STATE 0 0 0 0 XXXX", b"LEDS 50 000000",
    b"LEDS 51 " + b"000000" * 24, b"LEDS 50 " + b"FFFFFF" * 24,
    b"LEDS 0 " + b"010000" * 24, b"LEDS 50 " + b"GG0000" * 24,
    b"PING 1\x00", b"PING \xff", b"", b"UNKNOWN", b"x" * (MAX_LINE_BYTES + 1),
))
def test_rejects_invalid_messages(line):
    with pytest.raises(ValueError):
        decode_line(line)


@pytest.mark.parametrize("message", MESSAGES)
def test_every_possible_two_chunk_split(message):
    encoded = encode_message(message)
    for offset in range(len(encoded)):
        decoder = StreamDecoder()
        first = decoder.feed(encoded[:offset])
        second = decoder.feed(encoded[offset:])
        assert first.messages == ()
        assert first.errors == second.errors == ()
        assert second.messages == (message,)


def test_random_chunking_preserves_many_messages():
    expected = MESSAGES * 50
    wire = b"".join(encode_message(message) for message in expected)
    decoder = StreamDecoder()
    randomizer = random.Random(7)
    received = []
    offset = 0
    while offset < len(wire):
        count = randomizer.randint(1, 100)
        result = decoder.feed(wire[offset:offset + count])
        assert result.errors == ()
        received.extend(result.messages)
        offset += count
    assert tuple(received) == expected


def test_bad_line_does_not_discard_next_valid_message():
    decoder = StreamDecoder()
    result = decoder.feed(b"PING \xff\nBAD\nPING 12\r\n")
    assert len(result.errors) == 2
    assert result.messages == (Ping(12),)


def test_overlong_message_is_discarded_until_newline_once():
    decoder = StreamDecoder()
    first = decoder.feed(b"x" * 100_000)
    second = decoder.feed(b"PING 1\nPING 2\n")
    assert len(first.errors) == 1
    assert first.messages == ()
    assert second.errors == ()
    assert second.messages == (Ping(2),)


def test_reconnect_discards_partial_previous_message():
    decoder = StreamDecoder()
    decoder.feed(b"STATE 1 2")
    decoder.reset()
    assert decoder.feed(b"HELLO DJ_POLTORASHKA 1\n").messages == (Hello(),)
    decoder.feed(b"x" * (MAX_LINE_BYTES + 1))
    decoder.reset()
    assert decoder.feed(b"PING 3\n").messages == (Ping(3),)


def test_unchanged_lighting_is_not_resent_even_when_heartbeat_is_sent():
    update = make_led_update()
    tracker = LightingUpdateTracker()
    assert tracker.prepare(update) == encode_message(update)
    tracker.confirm_sent(update)
    for sequence in range(10):
        assert encode_message(Ping(sequence))
        assert tracker.prepare(update) is None
    changed = replace(update, colors=((128, 0, 0), *update.colors[1:]))
    assert tracker.prepare(changed) == encode_message(changed)
    tracker.confirm_sent(changed)
    assert tracker.prepare(changed) is None


def test_failed_transport_write_does_not_suppress_retry():
    tracker = LightingUpdateTracker()
    update = make_led_update()
    first = tracker.prepare(update)
    # Транспорт не подтвердил запись; повторная подготовка сохраняет сообщение.
    assert tracker.prepare(update) == first


def test_reconnect_forces_one_full_lighting_sync():
    tracker = LightingUpdateTracker()
    update = make_led_update()
    tracker.confirm_sent(update)
    assert tracker.prepare(update) is None
    tracker.reset()
    assert tracker.prepare(update) == encode_message(update)
    tracker.confirm_sent(update)
    assert tracker.prepare(update) is None


def test_brightness_change_updates_disconnect_white_limit_even_if_colors_are_black():
    update = LedUpdate(50, ((0, 0, 0),) * 24)
    tracker = LightingUpdateTracker()
    tracker.confirm_sent(update)
    changed = replace(update, brightness_percent=25)
    assert tracker.prepare(changed) == encode_message(changed)


@pytest.mark.parametrize("value", (True, -1, 65536, 1.5))
def test_message_model_rejects_invalid_sequence(value):
    with pytest.raises(ValueError):
        Ping(value)


@pytest.mark.parametrize("colors", (((0, 0, 0),) * 23, ((False, 0, 0),) * 24, ((0, 0),) * 24))
def test_led_model_rejects_invalid_frames(colors):
    with pytest.raises(ValueError):
        LedUpdate(50, colors)
