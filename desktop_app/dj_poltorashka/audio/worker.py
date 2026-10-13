"""Фоновое выполнение аудиоопераций без блокировки интерфейса."""

from collections.abc import Callable
from dataclasses import replace
from typing import Protocol

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from dj_poltorashka.audio.models import ChannelAudioUpdate
from dj_poltorashka.configuration.models import PanelConfiguration


_POLL_INTERVAL_MS = 250


def _initialize_com() -> None:
    from comtypes import CoInitialize

    CoInitialize()


def _uninitialize_com() -> None:
    from comtypes import CoUninitialize

    CoUninitialize()


class CoordinatorAudioService(Protocol):
    """Операции аудиосервиса, выполняемые в рабочем потоке."""

    def apply_configuration(self, panel: PanelConfiguration) -> None:
        ...

    def adopt_channel(
        self,
        panel: PanelConfiguration,
        channel_index: int,
    ) -> None:
        ...

    def poll(self) -> tuple[ChannelAudioUpdate, ...]:
        ...


class _AudioWorker(QObject):
    updates_ready = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        service: CoordinatorAudioService,
        poll_interval_ms: int,
        initialize_thread: Callable[[], None],
        uninitialize_thread: Callable[[], None],
    ) -> None:
        super().__init__()
        self._service = service
        self._poll_interval_ms = poll_interval_ms
        self._initialize_thread = initialize_thread
        self._uninitialize_thread = uninitialize_thread
        self._thread_initialized = False
        self._revision = 0
        self._timer: QTimer | None = None
        self._last_error: str | None = None

    @Slot(object, int)
    def start(self, panel: PanelConfiguration, revision: int) -> None:
        if self._timer is not None:
            return
        try:
            self._initialize_thread()
        except Exception as error:
            self._report_error(error)
            return
        self._thread_initialized = True
        self._revision = revision
        self._timer = QTimer(self)
        self._timer.setInterval(self._poll_interval_ms)
        self._timer.timeout.connect(self._poll)
        self._run_command(lambda: self._service.apply_configuration(panel))
        self._timer.start()
        self._poll()

    @Slot(object, int)
    def apply_configuration(
        self,
        panel: PanelConfiguration,
        revision: int,
    ) -> None:
        self._revision = revision
        self._run_command(lambda: self._service.apply_configuration(panel))

    @Slot(object, int, int)
    def adopt_channel(
        self,
        panel: PanelConfiguration,
        channel_index: int,
        revision: int,
    ) -> None:
        self._revision = revision
        self._run_command(
            lambda: self._service.adopt_channel(panel, channel_index)
        )

    @Slot()
    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._thread_initialized:
            self._uninitialize_thread()
            self._thread_initialized = False
        QThread.currentThread().quit()

    @Slot()
    def _poll(self) -> None:
        try:
            updates = self._service.poll()
        except Exception as error:
            self._report_error(error)
            return
        self._last_error = None
        self.updates_ready.emit(
            tuple(replace(update, revision=self._revision) for update in updates)
        )

    def _run_command(self, command: Callable[[], None]) -> None:
        try:
            command()
        except Exception as error:
            self._report_error(error)

    def _report_error(self, error: Exception) -> None:
        message = str(error).strip() or type(error).__name__
        if message == self._last_error:
            return
        self._last_error = message
        self.error.emit(message)


class AudioCoordinator(QObject):
    """Управляет одним рабочим потоком аудиосистемы."""

    _start_requested = Signal(object, int)
    _apply_requested = Signal(object, int)
    _adopt_requested = Signal(object, int, int)
    _stop_requested = Signal()

    def __init__(
        self,
        service: CoordinatorAudioService,
        on_updates: Callable[[tuple[ChannelAudioUpdate, ...]], None],
        on_error: Callable[[str], None],
        initialize_thread: Callable[[], None] = _initialize_com,
        uninitialize_thread: Callable[[], None] = _uninitialize_com,
    ) -> None:
        super().__init__()
        self._on_updates = on_updates
        self._on_error = on_error
        self._thread = QThread(self)
        self._worker = _AudioWorker(
            service,
            _POLL_INTERVAL_MS,
            initialize_thread,
            uninitialize_thread,
        )
        self._worker.moveToThread(self._thread)
        self._start_requested.connect(self._worker.start)
        self._apply_requested.connect(self._worker.apply_configuration)
        self._adopt_requested.connect(self._worker.adopt_channel)
        self._stop_requested.connect(self._worker.stop)
        self._worker.updates_ready.connect(self._deliver_updates)
        self._worker.error.connect(self._deliver_error)
        self._thread.finished.connect(self._worker.deleteLater)
        self._started = False
        self._revision = 0

    @property
    def poll_interval_ms(self) -> int:
        return _POLL_INTERVAL_MS

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    def start(self, panel: PanelConfiguration) -> int:
        if self._started:
            return self._revision
        self._started = True
        self._revision += 1
        self._thread.start()
        self._start_requested.emit(panel, self._revision)
        return self._revision

    def apply_configuration(self, panel: PanelConfiguration) -> int:
        if not self._started:
            raise RuntimeError("Аудиокоординатор ещё не запущен")
        self._revision += 1
        self._apply_requested.emit(panel, self._revision)
        return self._revision

    def adopt_channel(
        self,
        panel: PanelConfiguration,
        channel_index: int,
    ) -> int:
        if not self._started:
            raise RuntimeError("Аудиокоординатор ещё не запущен")
        self._revision += 1
        self._adopt_requested.emit(panel, channel_index, self._revision)
        return self._revision

    def close(self) -> None:
        if not self._thread.isRunning():
            return
        self._stop_requested.emit()
        self._thread.wait()

    @Slot(object)
    def _deliver_updates(self, updates: tuple[ChannelAudioUpdate, ...]) -> None:
        self._on_updates(updates)

    @Slot(str)
    def _deliver_error(self, message: str) -> None:
        self._on_error(message)
