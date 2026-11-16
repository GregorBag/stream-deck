from types import SimpleNamespace

import pytest
from PySide6.QtCore import QIODevice
from PySide6.QtSerialPort import QSerialPort

import dj_poltorashka.panel.transport as module
from dj_poltorashka.panel.protocol import Hello, Ping, Pong, StreamDecoder, encode_message
from dj_poltorashka.panel.transport import EMULATOR_PORT, EmulatedPanelTransport, SerialPanelTransport


class FakeSerial:
    def __init__(self):
        self.settings = {}
        self.closed = 0
        self.open_success = True
        self.clear_success = True
        self.queued = 0
        self.error_code = QSerialPort.SerialPortError.NoError
        self.written = []

    def setPortName(self, name): self.settings["name"] = name
    def setBaudRate(self, value): self.settings["baud"] = value; return True
    def setDataBits(self, value): self.settings["data"] = value; return True
    def setParity(self, value): self.settings["parity"] = value; return True
    def setStopBits(self, value): self.settings["stop"] = value; return True
    def setFlowControl(self, value): self.settings["flow"] = value; return True
    def setReadBufferSize(self, value): self.settings["read_limit"] = value
    def open(self, mode): self.settings["mode"] = mode; return self.open_success
    def clear(self): return self.clear_success
    def errorString(self): return "serial error"
    def error(self): return self.error_code
    def close(self): self.closed += 1
    def bytesToWrite(self): return self.queued
    def read(self, limit): return b"PONG 1\n"
    def write(self, data): self.written.append(data); return len(data)


def test_serial_transport_sets_115200_8n1_and_bounds_buffers():
    serial = FakeSerial()
    transport = SerialPanelTransport("COM3", serial_factory=lambda: serial)
    assert serial.settings == {
        "name": "COM3", "baud": 115200, "data": QSerialPort.DataBits.Data8,
        "parity": QSerialPort.Parity.NoParity, "stop": QSerialPort.StopBits.OneStop,
        "flow": QSerialPort.FlowControl.NoFlowControl, "read_limit": 4096,
        "mode": QIODevice.OpenModeFlag.ReadWrite,
    }
    assert transport.read() == b"PONG 1\n"
    assert transport.write(b"PING 1\n") == 7
    transport.close()
    assert serial.closed == 1


@pytest.mark.parametrize("phase", ("open", "clear"))
def test_failed_serial_open_or_clear_releases_port(phase):
    serial = FakeSerial()
    setattr(serial, f"{phase}_success", False)
    with pytest.raises(OSError, match="serial error"):
        SerialPanelTransport("COM3", serial_factory=lambda: serial)
    assert serial.closed == 1


def test_serial_read_write_errors_and_queue_overflow_are_reported():
    serial = FakeSerial()
    transport = SerialPanelTransport("COM3", serial_factory=lambda: serial)
    serial.queued = 4096
    with pytest.raises(OSError, match="переполнена"):
        transport.write(b"PING 1\n")
    assert serial.written == []
    serial.error_code = QSerialPort.SerialPortError.ResourceError
    with pytest.raises(OSError, match="serial error"):
        transport.read()
    with pytest.raises(OSError, match="serial error"):
        transport.write(b"PING 1\n")
    transport.close()


def test_port_list_includes_emulator_and_stable_names(monkeypatch):
    def port(name, description):
        return SimpleNamespace(portName=lambda: name, description=lambda: description)
    monkeypatch.setattr(module.QSerialPortInfo, "availablePorts", lambda: [port("COM9", "USB"), port("COM3", "")])
    ports = module.available_ports()
    assert [item.name for item in ports] == [EMULATOR_PORT, "COM3", "COM9"]
    assert ports[1].description == "COM3"


def test_emulated_transport_exchanges_bytes_and_emits_press_release():
    transport = EmulatedPanelTransport(clock=lambda: 0)
    transport.write(encode_message(Hello()))
    assert StreamDecoder().feed(transport.read()).messages[0] == Hello()
    transport.write(encode_message(Ping(7)))
    assert StreamDecoder().feed(transport.read()).messages == (Pong(7),)
    transport.press_button(15)
    states = StreamDecoder().feed(transport.read()).messages
    assert [state.buttons for state in states] == [0x8000, 0]
    transport.close()
    with pytest.raises(OSError):
        transport.read()
