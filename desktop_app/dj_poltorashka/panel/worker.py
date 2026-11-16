"""Фоновая работа порта панели с доставкой событий в поток интерфейса."""

from collections.abc import Callable
import logging

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from dj_poltorashka.panel.connection import ConnectionUpdate, PanelConnection, PanelConnectionStatus
from dj_poltorashka.panel.events import PanelEvent
from dj_poltorashka.panel.protocol import LedUpdate, PanelState
from dj_poltorashka.panel.session import SessionResult
from dj_poltorashka.panel.transport import PanelPort, PanelTransport, available_ports, create_transport, monotonic_ms


_LOGGER = logging.getLogger(__name__)


class _PanelWorker(QObject):
    updated = Signal(object, int)
    status_changed = Signal(object, int)
    ports_changed = Signal(object)

    def __init__(self, factory, port_provider, clock, poll_interval_ms):
        super().__init__()
        self._connection = PanelConnection(factory)
        self._port_provider = port_provider
        self._clock = clock
        self._poll_interval_ms = poll_interval_ms
        self._timer: QTimer | None = None
        self._revision = 0
        self._last_status = None
        self._last_ports = None
        self._next_scan_ms = 0
        self._last_error = None

    def _deliver(self, update: ConnectionUpdate) -> None:
        if update.status != self._last_status:
            self._last_status = update.status
            self.status_changed.emit(update.status, self._revision)
        if update.result.states or update.result.events:
            self.updated.emit(update.result, self._revision)
        for message in update.result.errors:
            if message != self._last_error:
                _LOGGER.warning("Панель: %s", message)
                self._last_error = message

    @Slot()
    def start(self) -> None:
        if self._timer is not None:
            return
        self._timer = QTimer(self)
        self._timer.setInterval(self._poll_interval_ms)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self.refresh_ports()

    @Slot()
    def refresh_ports(self) -> None:
        try:
            ports = self._port_provider()
        except OSError as error:
            _LOGGER.warning("Не удалось обновить список портов: %s", error)
            return
        self._next_scan_ms = self._clock() + 1000
        if ports != self._last_ports:
            self._last_ports = ports
            self.ports_changed.emit(ports)

    @Slot(object, int)
    def select_port(self, name: str | None, revision: int) -> None:
        self._revision = revision
        self._last_status = None
        self._last_error = None
        self._deliver(self._connection.select_port(name, self._clock()))

    @Slot(object)
    def set_lighting(self, update: LedUpdate) -> None:
        self._deliver(self._connection.set_lighting(update, self._clock()))

    @Slot(int, int)
    def press_button(self, index: int, revision: int) -> None:
        if revision == self._revision:
            self._deliver(self._connection.press_emulated_button(index, self._clock()))

    @Slot()
    def _poll(self) -> None:
        now = self._clock()
        if now >= self._next_scan_ms:
            self.refresh_ports()
        self._deliver(self._connection.poll(now))

    @Slot()
    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._connection.close()
        QThread.currentThread().quit()


class PanelCoordinator(QObject):
    _start_requested = Signal()
    _select_requested = Signal(object, int)
    _lighting_requested = Signal(object)
    _refresh_requested = Signal()
    _press_requested = Signal(int, int)
    _stop_requested = Signal()

    def __init__(
        self,
        on_events: Callable[[tuple[PanelEvent, ...]], None],
        on_status: Callable[[PanelConnectionStatus], None],
        *,
        factory: Callable[[str], PanelTransport] = create_transport,
        port_provider: Callable[[], tuple[PanelPort, ...]] = available_ports,
        clock: Callable[[], int] = monotonic_ms,
        poll_interval_ms: int = 20,
    ):
        super().__init__()
        self._on_events = on_events
        self._on_status = on_status
        self._thread = QThread(self)
        self._worker = _PanelWorker(factory, port_provider, clock, poll_interval_ms)
        self._worker.moveToThread(self._thread)
        self._start_requested.connect(self._worker.start)
        self._select_requested.connect(self._worker.select_port)
        self._lighting_requested.connect(self._worker.set_lighting)
        self._refresh_requested.connect(self._worker.refresh_ports)
        self._press_requested.connect(self._worker.press_button)
        self._stop_requested.connect(self._worker.stop)
        self._worker.updated.connect(self._deliver_update)
        self._worker.status_changed.connect(self._deliver_status)
        self._worker.ports_changed.connect(self._deliver_ports)
        self._thread.finished.connect(self._worker.deleteLater)
        self._ports: tuple[PanelPort, ...] = ()
        self._port_name: str | None = None
        self._status = PanelConnectionStatus()
        self._latest_state: PanelState | None = None
        self._revision = 0
        self._started = False
        self._closed = False
        self.on_ports_changed: Callable[[], None] = lambda: None

    @property
    def ports(self) -> tuple[PanelPort, ...]:
        return self._ports

    @property
    def selected_port(self) -> str | None:
        return self._port_name

    @property
    def status(self) -> PanelConnectionStatus:
        return self._status

    @property
    def latest_state(self) -> PanelState | None:
        return self._latest_state

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    def start(self) -> None:
        if self._started or self._closed:
            return
        self._started = True
        self._thread.start()
        self._start_requested.emit()

    def select_port(self, name: str | None) -> None:
        if self._closed:
            return
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ValueError("Требуется имя порта или None")
        self.start()
        self._revision += 1
        self._port_name = name
        self._latest_state = None
        self._status = PanelConnectionStatus("connecting", name, "Подключение к панели…") if name else PanelConnectionStatus()
        self._on_status(self._status)
        self._select_requested.emit(name, self._revision)

    def set_lighting(self, update: LedUpdate) -> None:
        if self._closed:
            return
        self.start()
        self._lighting_requested.emit(update)

    def refresh_ports(self) -> None:
        self.start()
        if not self._closed:
            self._refresh_requested.emit()

    def press_emulated_button(self, index: int) -> None:
        if not self._closed:
            self._press_requested.emit(index, self._revision)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread.isRunning():
            self._stop_requested.emit()
            self._thread.wait()

    @Slot(object, int)
    def _deliver_update(self, result: SessionResult, revision: int) -> None:
        if not self._closed and revision == self._revision:
            if result.states:
                self._latest_state = result.states[-1]
            if result.events:
                self._on_events(result.events)

    @Slot(object, int)
    def _deliver_status(self, status: PanelConnectionStatus, revision: int) -> None:
        if not self._closed and revision == self._revision:
            self._status = status
            if status.code != "connected":
                self._latest_state = None
            self._on_status(status)

    @Slot(object)
    def _deliver_ports(self, ports: tuple[PanelPort, ...]) -> None:
        if not self._closed:
            self._ports = ports
            self.on_ports_changed()
