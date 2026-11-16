from dataclasses import replace

from dj_poltorashka.panel.connection import PanelConnection
from dj_poltorashka.panel.events import PresetPressed
from dj_poltorashka.panel.protocol import LedUpdate
from dj_poltorashka.panel.transport import EmulatedPanelTransport


class RecordingTransport(EmulatedPanelTransport):
    def __init__(self, clock):
        super().__init__(clock)
        self.sent = []
        self.close_count = 0
        self.fail_read = False

    def write(self, data):
        self.sent.append(data)
        return super().write(data)

    def read(self):
        if self.fail_read:
            raise OSError("unplugged")
        return super().read()

    def close(self):
        self.close_count += 1
        super().close()


def test_connection_handshake_buttons_lighting_and_explicit_disconnect():
    now = [0]
    transports = []
    def factory(port):
        transport = RecordingTransport(lambda: now[0])
        transports.append(transport)
        return transport
    connection = PanelConnection(factory)
    lights = LedUpdate(50, ((10, 20, 30),) * 24)
    connection.set_lighting(lights, 0)
    assert connection.select_port("test", 0).status.code == "connecting"
    now[0] = 1
    assert connection.poll(1).status.code == "connected"
    now[0] = 2
    connection.poll(2)
    transport = transports[0]
    assert transport.board.lighting(2) == lights
    transport.press_button(15)
    assert connection.poll(2).result.events == (PresetPressed(3),)
    for value in (500, 1000, 1500):
        now[0] = value
        connection.poll(value)
        connection.set_lighting(lights, value)
    assert sum(data.startswith(b"LEDS ") for data in transport.sent) == 1
    changed = replace(lights, colors=((100, 0, 0), *lights.colors[1:]))
    connection.set_lighting(changed, 1500)
    assert transport.board.lighting(1500) == changed
    assert connection.select_port(None, 1500).status.code == "disconnected"
    assert transport.close_count == 1
    now[0] = 10_000
    assert connection.poll(10_000).status.code == "disconnected"
    assert len(transports) == 1


def test_read_failure_closes_port_and_reconnects_only_to_selected_port():
    now = [0]
    calls = []
    transports = []
    def factory(port):
        calls.append(port)
        transport = RecordingTransport(lambda: now[0])
        transports.append(transport)
        return transport
    connection = PanelConnection(factory)
    connection.select_port("COM3", 0)
    connection.poll(0)
    transports[0].fail_read = True
    now[0] = 10
    assert connection.poll(10).status.code == "reconnecting"
    assert transports[0].close_count == 1
    now[0] = 1009
    connection.poll(1009)
    assert calls == ["COM3"]
    now[0] = 1010
    connection.poll(1010)
    assert connection.poll(1010).status.code == "connected"
    assert calls == ["COM3", "COM3"]
    connection.close()


def test_open_failure_retries_and_manual_disconnect_cancels_retry():
    calls = []
    def fail(port):
        calls.append(port)
        raise OSError("busy")
    connection = PanelConnection(fail)
    assert connection.select_port("COM3", 0).status.code == "reconnecting"
    connection.poll(999)
    assert len(calls) == 1
    connection.poll(1000)
    assert len(calls) == 2
    connection.select_port(None, 1001)
    connection.poll(10_000)
    assert len(calls) == 2


def test_nano_settle_delay_does_not_consume_handshake_timeout():
    now = [0]
    transport = RecordingTransport(lambda: now[0])
    transport.settle_ms = 2000
    connection = PanelConnection(lambda port: transport)
    connection.select_port("COM3", 0)
    now[0] = 1999
    assert connection.poll(1999).status.code == "connecting"
    assert transport.sent == []
    now[0] = 2000
    connection.poll(2000)
    assert transport.sent[0].startswith(b"HELLO ")
    now[0] = 2001
    assert connection.poll(2001).status.code == "connected"
    connection.close()
