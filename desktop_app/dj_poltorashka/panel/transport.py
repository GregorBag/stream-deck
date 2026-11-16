"""Неблокирующий COM-транспорт Qt и транспорт программной платы."""

from collections.abc import Callable
from dataclasses import dataclass, replace
import time
from typing import Protocol

from PySide6.QtCore import QIODevice
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo

from dj_poltorashka.panel.emulator import PanelEmulator
from dj_poltorashka.panel.protocol import BAUD_RATE


EMULATOR_PORT = "emulator://panel"


def monotonic_ms() -> int:
    return time.monotonic_ns() // 1_000_000


@dataclass(frozen=True)
class PanelPort:
    name: str
    description: str


def available_ports() -> tuple[PanelPort, ...]:
    ports = tuple(sorted(
        (PanelPort(info.portName(), info.description() or info.portName()) for info in QSerialPortInfo.availablePorts()),
        key=lambda port: port.name,
    ))
    return (PanelPort(EMULATOR_PORT, "Имитатор платы"), *ports)


class PanelTransport(Protocol):
    settle_ms: int

    def read(self) -> bytes: ...
    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


class SerialPanelTransport:
    settle_ms = 2000

    def __init__(self, port_name: str, *, serial_factory=QSerialPort):
        self._serial = serial_factory()
        self._serial.setPortName(port_name)
        settings = (
            self._serial.setBaudRate(BAUD_RATE),
            self._serial.setDataBits(QSerialPort.DataBits.Data8),
            self._serial.setParity(QSerialPort.Parity.NoParity),
            self._serial.setStopBits(QSerialPort.StopBits.OneStop),
            self._serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl),
        )
        self._serial.setReadBufferSize(4096)
        if not all(settings) or not self._serial.open(QIODevice.OpenModeFlag.ReadWrite):
            message = self._serial.errorString()
            self._serial.close()
            raise OSError(message)
        # Открытие Nano может вызвать перезапуск. HELLO отправляется после settle_ms.
        if not self._serial.clear():
            message = self._serial.errorString()
            self._serial.close()
            raise OSError(message)

    def _check_error(self) -> None:
        if self._serial.error() != QSerialPort.SerialPortError.NoError:
            raise OSError(self._serial.errorString())

    def read(self) -> bytes:
        self._check_error()
        data = bytes(self._serial.read(4096))
        self._check_error()
        return data

    def write(self, data: bytes) -> int:
        self._check_error()
        if self._serial.bytesToWrite() + len(data) > 4096:
            raise OSError("Очередь отправки панели переполнена")
        written = self._serial.write(data)
        self._check_error()
        return written

    def close(self) -> None:
        self._serial.close()


class EmulatedPanelTransport:
    settle_ms = 0

    def __init__(self, clock: Callable[[], int] = monotonic_ms):
        self._clock = clock
        self.board = PanelEmulator()
        self._incoming = bytearray()
        self._closed = False

    def _check_open(self) -> None:
        if self._closed:
            raise OSError("Транспорт закрыт")

    def read(self) -> bytes:
        self._check_open()
        self.board.tick(self._clock())
        data = bytes(self._incoming[:4096])
        del self._incoming[:4096]
        return data

    def write(self, data: bytes) -> int:
        self._check_open()
        result = self.board.receive(data, self._clock())
        self._incoming.extend(result.data)
        if result.errors:
            raise OSError("; ".join(result.errors))
        return len(data)

    def press_button(self, index: int) -> None:
        self._check_open()
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 16:
            raise ValueError("Номер кнопки должен быть от 0 до 15")
        now = self._clock()
        state = self.board.state
        self._incoming.extend(self.board.set_state(replace(state, buttons=state.buttons | (1 << index)), now))
        self._incoming.extend(self.board.set_state(replace(state, buttons=state.buttons & ~(1 << index)), now))

    def close(self) -> None:
        self._closed = True
        self._incoming.clear()


def create_transport(port_name: str) -> PanelTransport:
    return EmulatedPanelTransport() if port_name == EMULATOR_PORT else SerialPanelTransport(port_name)
