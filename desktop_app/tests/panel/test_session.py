from dataclasses import replace

import pytest

from dj_poltorashka.panel.events import MutePressed, PresetPressed, SoundPressed
from dj_poltorashka.panel.protocol import Hello, LedUpdate, PanelState, Ping, Pong, encode_message
from dj_poltorashka.panel.session import PanelSession
from dj_poltorashka.panel.simulation import PanelSimulation


def update():
    return LedUpdate(50, tuple((index, index + 1, index + 2) for index in range(24)))


def test_handshake_syncs_state_and_lighting_with_every_byte_fragmented():
    initial = PanelState((0, 1023, 512, 1), 0xFFFF)
    simulation = PanelSimulation(chunk_size=1, initial_state=initial)
    simulation.set_lighting(update(), 0)
    assert simulation.transmitted == []
    simulation.start(0)
    assert simulation.session.status == "connected"
    assert simulation.board.connected
    assert simulation.states == [initial]
    assert simulation.board.lighting(0) == update()
    assert simulation.events == []
    assert simulation.errors == []


@pytest.mark.parametrize("index", range(16))
def test_button_edges_map_all_physical_buttons_without_repeats(index):
    simulation = PanelSimulation()
    simulation.start(0)
    pressed = PanelState((0, 0, 0, 0), 1 << index)
    simulation.set_state(pressed, 10)
    simulation.set_state(pressed, 20)
    simulation.set_state(replace(pressed, sliders=(1, 2, 3, 4)), 30)
    if index < 8:
        expected = SoundPressed(index)
    elif index < 12:
        expected = MutePressed(index - 8)
    else:
        expected = PresetPressed(index - 12)
    assert simulation.events == [expected]
    simulation.set_state(replace(pressed, buttons=0), 40)
    simulation.set_state(pressed, 50)
    assert simulation.events == [expected, expected]
    assert simulation.states[-1] == pressed


def test_simultaneous_buttons_are_all_reported():
    simulation = PanelSimulation()
    simulation.start(0)
    simulation.set_state(PanelState((0, 0, 0, 0), 0x8101), 1)
    assert simulation.events == [SoundPressed(0), MutePressed(0), PresetPressed(3)]


def test_heartbeats_do_not_resend_lighting_and_keep_connection_alive():
    simulation = PanelSimulation()
    simulation.set_lighting(update(), 0)
    simulation.start(0)
    for now in range(500, 10_001, 500):
        simulation.advance(now)
        simulation.set_lighting(update(), now)
        assert simulation.session.status == "connected"
    leds = [data for data in simulation.transmitted if data.startswith(b"LEDS ")]
    pings = [data for data in simulation.transmitted if data.startswith(b"PING ")]
    assert leds == [encode_message(update())]
    assert len(pings) == 21
    assert simulation.errors == []
    changed = replace(update(), colors=((100, 0, 0), *update().colors[1:]))
    simulation.set_lighting(changed, 10_001)
    assert simulation.board.lighting(10_001) == changed
    assert sum(data.startswith(b"LEDS ") for data in simulation.transmitted) == 2


def test_loss_of_both_directions_times_out_and_only_perimeter_blinks():
    simulation = PanelSimulation()
    simulation.set_lighting(update(), 0)
    simulation.start(0)
    simulation.drop_to_board = simulation.drop_to_host = True
    for now in (500, 1000, 1500, 1999):
        simulation.advance(now)
        assert simulation.session.status == "connected"
    simulation.advance(2000)
    assert simulation.session.status == "closed"
    assert not simulation.board.connected
    assert simulation.board.lighting(2000).colors[:8] == ((128, 128, 128),) * 8
    assert simulation.board.lighting(2500).colors[:8] == ((0, 0, 0),) * 8
    assert simulation.board.lighting(3000).colors[:8] == ((128, 128, 128),) * 8
    assert simulation.board.lighting(3000).colors[8:] == update().colors[8:]
    assert len(simulation.errors) == 1


def test_reconnect_resends_one_frame_and_does_not_repeat_held_button():
    simulation = PanelSimulation(chunk_size=1)
    simulation.set_lighting(update(), 0)
    simulation.start(0)
    simulation.set_state(PanelState((100, 200, 300, 400), 0x8000), 10)
    assert simulation.events == [PresetPressed(3)]
    simulation.session.close()
    simulation.start(20)
    assert simulation.events == [PresetPressed(3)]
    assert simulation.states[-1] == simulation.board.state
    assert sum(data.startswith(b"LEDS ") for data in simulation.transmitted) == 2
    simulation.advance(520)
    assert sum(data.startswith(b"LEDS ") for data in simulation.transmitted) == 2


def test_board_restart_forces_fresh_handshake_and_lighting_sync():
    simulation = PanelSimulation(chunk_size=192)
    simulation.set_lighting(update(), 0)
    simulation.start(0)
    simulation.set_state(PanelState((0, 0, 0, 0), 1), 10)
    simulation.restart_board(20)
    assert simulation.session.status == "connected"
    assert simulation.board.lighting(20) == update()
    assert simulation.events == [SoundPressed(0)]
    assert sum(data.startswith(b"HELLO ") for data in simulation.transmitted) == 2
    assert sum(data.startswith(b"LEDS ") for data in simulation.transmitted) == 2
    assert simulation.errors == []


def connected_session():
    sent = []
    def write(data):
        sent.append(data)
        return len(data)
    session = PanelSession(write)
    session.start(0)
    result = session.receive(encode_message(Hello()), 0)
    assert result.errors == ()
    assert sent[-1] == encode_message(Ping(0))
    return session, sent


def test_handshake_must_finish_before_two_second_deadline():
    session = PanelSession(lambda data: len(data))
    session.start(0)
    assert session.receive(b"HELLO OTHER 1\n", 500).errors
    assert session.status == "handshaking"
    result = session.receive(encode_message(Hello()), 2000)
    assert session.status == "closed"
    assert result.errors


def test_state_and_corrupt_data_do_not_extend_heartbeat_deadline():
    session, _ = connected_session()
    session.receive(encode_message(Pong(0)), 0)
    assert session.receive(b"BAD\n", 1000).errors
    assert session.receive(encode_message(PanelState((1, 2, 3, 4), 1)), 1999).states
    assert session.receive(encode_message(Pong(0)), 2000).errors
    assert session.status == "closed"


def test_unexpected_duplicate_and_old_pongs_do_not_extend_connection():
    session, _ = connected_session()
    session.receive(encode_message(Pong(0)), 0)
    assert session.receive(encode_message(Pong(999)), 400).errors
    session.tick(500)
    session.tick(1000)
    assert session.receive(encode_message(Pong(2)), 1100).errors == ()
    assert session.receive(encode_message(Pong(1)), 2000).errors
    assert session.receive(encode_message(Pong(2)), 3000).errors
    session.tick(3100)
    assert session.status == "closed"


def test_state_received_before_hello_cannot_trigger_events():
    session = PanelSession(lambda data: len(data))
    session.start(0)
    result = session.receive(encode_message(PanelState((0, 0, 0, 0), 1)), 1)
    assert result.states == result.events == ()
    assert result.errors


def test_incorrect_message_direction_is_rejected():
    session, _ = connected_session()
    result = session.receive(encode_message(Ping(2)) + encode_message(update()), 1)
    assert len(result.errors) == 2
    assert result.events == ()


@pytest.mark.parametrize("failure", ("partial", "exception", "empty_exception"))
def test_transport_failure_closes_session_and_resyncs_lighting_after_reconnect(failure):
    sent = []
    failing = False
    def write(data):
        if failing and data.startswith(b"LEDS "):
            if failure == "empty_exception":
                raise OSError()
            if failure == "exception":
                raise OSError("port disconnected")
            return len(data) - 1
        sent.append(data)
        return len(data)
    session = PanelSession(write)
    session.set_lighting(update(), 0)
    session.start(0)
    failing = True
    result = session.receive(encode_message(Hello()), 0)
    assert result.errors
    assert session.status == "closed"
    failing = False
    session.start(10)
    assert session.receive(encode_message(Hello()), 10).errors == ()
    assert sent[-1] == encode_message(update())
    assert session.set_lighting(update(), 11).errors == ()
    assert sent.count(encode_message(update())) == 1


def test_time_must_be_monotonic():
    session = PanelSession(lambda data: len(data))
    session.start(100)
    for value in (99, -1, True, 1.5):
        with pytest.raises(ValueError):
            session.tick(value)



def test_one_way_loss_stops_host_then_board_detects_missing_pings():
    simulation = PanelSimulation()
    simulation.start(0)
    simulation.drop_to_host = True
    for now in (500, 1000, 1500, 2000):
        simulation.advance(now)
    assert simulation.session.status == "closed"
    assert simulation.board.connected
    simulation.advance(3500)
    assert not simulation.board.connected
    simulation.drop_to_host = False
    simulation.start(4000)
    assert simulation.session.status == "connected"


def test_simulated_buttons_route_through_existing_application_router():
    from dj_poltorashka.panel.event_router import PanelEventRouter
    calls = []
    router = PanelEventRouter(
        set_volume=lambda index, value: calls.append(("volume", index, value)),
        toggle_mute=lambda index: calls.append(("mute", index)),
        press_sound=lambda index: calls.append(("sound", index)),
        load_preset=lambda index: calls.append(("preset", index)),
    )
    simulation = PanelSimulation(chunk_size=1)
    simulation.start(0)
    simulation.set_state(PanelState((10, 20, 30, 40), 0x8101), 1)
    for event in simulation.events:
        router.route(event)
    assert calls == [("sound", 0), ("mute", 0), ("preset", 3)]
    assert simulation.states[-1].sliders == (10, 20, 30, 40)
