from threading import Event

from PySide6.QtCore import QThread, QTimer

from dj_poltorashka.panel.events import PresetPressed
from dj_poltorashka.panel.protocol import LedUpdate, StreamDecoder
from dj_poltorashka.panel.transport import EMULATOR_PORT, EmulatedPanelTransport, PanelPort
from dj_poltorashka.panel.worker import PanelCoordinator


def test_port_open_read_write_close_run_in_worker_and_events_arrive_on_gui_thread(qtbot):
    operations = []
    transports = []
    callbacks = []
    statuses = []
    class Transport(EmulatedPanelTransport):
        def __init__(self):
            super().__init__()
            self.sent = []
        def read(self):
            operations.append(QThread.currentThread())
            return super().read()
        def write(self, data):
            self.sent.append(data)
            operations.append(QThread.currentThread())
            return super().write(data)
        def close(self):
            operations.append(QThread.currentThread())
            super().close()
    def factory(name):
        operations.append(QThread.currentThread())
        transport = Transport()
        transports.append(transport)
        return transport
    def receive(events):
        callbacks.append((events, QThread.currentThread()))
    coordinator = PanelCoordinator(receive, statuses.append, factory=factory, port_provider=lambda: (PanelPort(EMULATOR_PORT, "Имитатор платы"),), poll_interval_ms=5)
    try:
        coordinator.set_lighting(LedUpdate(50, ((10, 20, 30),) * 24))
        coordinator.select_port(EMULATOR_PORT)
        qtbot.waitUntil(lambda: coordinator.status.code == "connected")
        coordinator.press_emulated_button(15)
        qtbot.waitUntil(lambda: bool(callbacks))
        assert callbacks[0][0] == (PresetPressed(3),)
        assert callbacks[0][1] is QThread.currentThread()
        assert coordinator.latest_state.buttons == 0
        assert coordinator.ports[0].name == EMULATOR_PORT
        assert any(isinstance(message, LedUpdate) and message.colors[0] == (10, 20, 30) for data in transports[0].sent for message in StreamDecoder().feed(data).messages)
    finally:
        coordinator.close()
    assert not coordinator.is_running
    assert operations and all(thread is not QThread.currentThread() for thread in operations)



def test_slow_port_open_does_not_block_gui_timer(qtbot):
    entered = Event()
    release = Event()
    ticks = []
    def factory(name):
        entered.set()
        release.wait(3)
        return EmulatedPanelTransport()
    coordinator = PanelCoordinator(lambda events: None, lambda status: None, factory=factory, port_provider=lambda: (), poll_interval_ms=5)
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    try:
        coordinator.select_port("COM3")
        qtbot.waitUntil(entered.is_set)
        timer.start()
        qtbot.waitUntil(lambda: len(ticks) >= 3)
        assert not release.is_set()
        release.set()
        qtbot.waitUntil(lambda: coordinator.status.code == "connected")
    finally:
        timer.stop()
        release.set()
        coordinator.close()


def test_worker_retries_after_open_failure_and_disconnect_cancels_selection(qtbot):
    calls = []
    def factory(name):
        calls.append(name)
        if len(calls) == 1:
            raise OSError("port busy")
        return EmulatedPanelTransport()
    coordinator = PanelCoordinator(lambda events: None, lambda status: None, factory=factory, port_provider=lambda: (), poll_interval_ms=5)
    try:
        coordinator.select_port("COM3")
        qtbot.waitUntil(lambda: coordinator.status.code == "reconnecting")
        qtbot.waitUntil(lambda: coordinator.status.code == "connected", timeout=3000)
        assert calls == ["COM3", "COM3"]
        coordinator.select_port(None)
        qtbot.waitUntil(lambda: coordinator.status.code == "disconnected")
        assert coordinator.selected_port is None
    finally:
        coordinator.close()
    coordinator.close()
