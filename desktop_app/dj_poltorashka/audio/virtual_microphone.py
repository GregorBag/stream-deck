"""Фоновый relay физического микрофона в VB-CABLE."""

from collections.abc import Callable
import math
from typing import Protocol

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QAudioSource

from dj_poltorashka.audio.routing_models import AudioRoutingStatus


_RELAY_PERIOD_US = 20_000


def _format_key(audio_format: QAudioFormat) -> tuple[int, int, object]:
    return (
        audio_format.sampleRate(),
        audio_format.channelCount(),
        audio_format.sampleFormat(),
    )


def _fallback_format(channels: int) -> QAudioFormat:
    audio_format = QAudioFormat()
    audio_format.setSampleRate(48_000)
    audio_format.setChannelCount(channels)
    audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    return audio_format


def select_relay_format(input_device: object, cable_device: object) -> QAudioFormat | None:
    """Выбирает общий PCM-формат без неявного преобразования Qt."""

    candidates = [
        input_device.preferredFormat(),  # type: ignore[attr-defined]
        cable_device.preferredFormat(),  # type: ignore[attr-defined]
        _fallback_format(1),
        _fallback_format(2),
    ]
    visited: set[tuple[int, int, object]] = set()
    for candidate in candidates:
        key = _format_key(candidate)
        if key in visited or not candidate.isValid():
            continue
        visited.add(key)
        if input_device.isFormatSupported(candidate) and (  # type: ignore[attr-defined]
            cable_device.isFormatSupported(candidate)  # type: ignore[attr-defined]
        ):
            return candidate
    return None


class AudioRelayPump:
    """Переносит только свежий ограниченный блок PCM-данных."""

    def __init__(
        self,
        source: object,
        sink: object,
        period_bytes: int,
        bytes_per_frame: int = 1,
    ):
        if period_bytes <= 0:
            raise ValueError("Размер периода должен быть положительным")
        if bytes_per_frame <= 0:
            raise ValueError("Размер PCM-кадра должен быть положительным")
        self._source = source
        self._sink = sink
        self._period_bytes = period_bytes
        self._bytes_per_frame = bytes_per_frame
        self._pending = b""

    def forward(self) -> None:
        available = max(0, int(self._source.bytesAvailable()))  # type: ignore[attr-defined]
        if available == 0:
            return
        data = self._pending + bytes(  # type: ignore[attr-defined]
            self._source.read(available)
        )
        usable = len(data) - len(data) % self._bytes_per_frame
        self._pending = data[usable:]
        complete_frames = data[:usable]
        writable = min(
            usable,
            max(0, int(self._sink.bytesFree())),  # type: ignore[attr-defined]
            self._period_bytes,
        )
        writable -= writable % self._bytes_per_frame
        if writable > 0:
            self._sink.write(complete_frames[-writable:])  # type: ignore[attr-defined]


class RelayRuntime(Protocol):
    def apply(
        self,
        input_device: object,
        cable_device: object,
        audio_format: QAudioFormat,
        volume: float,
        generation: int,
    ) -> None:
        ...

    def stop(self) -> None:
        ...

    def close(self) -> None:
        ...


class _RelayWorker(QObject):
    configured = Signal(int)
    error = Signal(int, str)

    def __init__(
        self,
        source_factory: Callable[[object, QAudioFormat], object],
        sink_factory: Callable[[object, QAudioFormat], object],
    ) -> None:
        super().__init__()
        self._source_factory = source_factory
        self._sink_factory = sink_factory
        self._source: object | None = None
        self._sink: object | None = None
        self._source_io: object | None = None
        self._sink_io: object | None = None
        self._pump: AudioRelayPump | None = None
        self._generation = 0
        self._configuring = False

    @Slot(object, object, object, float, int)
    def configure(
        self,
        input_device: object,
        cable_device: object,
        audio_format: QAudioFormat,
        volume: float,
        generation: int,
    ) -> None:
        self._generation = generation
        self._configuring = True
        self.stop()
        try:
            source = self._source_factory(input_device, audio_format)
            sink = self._sink_factory(cable_device, audio_format)
            self._source = source
            self._sink = sink
            self._connect_state_signal(source)
            self._connect_state_signal(sink)
            period_bytes = max(1, audio_format.bytesForDuration(_RELAY_PERIOD_US))
            sink.setBufferSize(period_bytes)  # type: ignore[attr-defined]
            sink.setVolume(volume)  # type: ignore[attr-defined]
            sink_io = sink.start()  # type: ignore[attr-defined]
            source_io = source.start()  # type: ignore[attr-defined]
            if source_io is None or sink_io is None:
                raise RuntimeError("Qt не запустил аудиопоток")
            self._require_started(source)
            self._require_started(sink)
            self._source_io = source_io
            self._sink_io = sink_io
            self._pump = AudioRelayPump(
                source_io,
                sink_io,
                period_bytes,
                audio_format.bytesPerFrame(),
            )
            source_io.readyRead.connect(self._forward)  # type: ignore[attr-defined]
            self._configuring = False
            self.configured.emit(generation)
        except Exception as error:
            self.stop()
            self._configuring = False
            self._emit_error(error)

    @Slot()
    def stop(self) -> None:
        if self._source is not None:
            self._source.stop()  # type: ignore[attr-defined]
        if self._sink is not None:
            self._sink.stop()  # type: ignore[attr-defined]
        for audio_object in (self._source, self._sink):
            if audio_object is not None:
                audio_object.deleteLater()  # type: ignore[attr-defined]
        self._source = None
        self._sink = None
        self._source_io = None
        self._sink_io = None
        self._pump = None

    @Slot()
    def shutdown(self) -> None:
        self.stop()
        QThread.currentThread().quit()

    @Slot()
    def _forward(self) -> None:
        if self._pump is None:
            return
        try:
            self._pump.forward()
        except Exception as error:
            self._emit_error(error)

    @Slot(object)
    def _check_state(self, state: object) -> None:
        if self._configuring:
            return
        for audio_object in (self._source, self._sink):
            if audio_object is None or not hasattr(audio_object, "error"):
                continue
            if audio_object.error() != QAudio.Error.NoError:  # type: ignore[attr-defined]
                self._emit_error(RuntimeError("Ошибка Qt Audio"))
                return

    @staticmethod
    def _require_started(audio_object: object) -> None:
        error_reader = getattr(audio_object, "error", None)
        if error_reader is not None and error_reader() != QAudio.Error.NoError:
            raise RuntimeError("Ошибка открытия Qt Audio")
        state_reader = getattr(audio_object, "state", None)
        if state_reader is None:
            return
        if state_reader() not in (
            QAudio.State.ActiveState,
            QAudio.State.IdleState,
        ):
            raise RuntimeError("Qt Audio не перешёл в рабочее состояние")

    def _connect_state_signal(self, audio_object: object) -> None:
        signal = getattr(audio_object, "stateChanged", None)
        if signal is not None:
            signal.connect(self._check_state)

    def _emit_error(self, error: Exception) -> None:
        self.error.emit(
            self._generation,
            str(error).strip() or type(error).__name__,
        )


class _RelayBridge(QObject):
    configure_requested = Signal(object, object, object, float, int)
    stop_requested = Signal()
    shutdown_requested = Signal()


class _RelayEventReceiver(QObject):
    def __init__(
        self,
        on_event: Callable[[int, str | None], None],
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._on_event = on_event

    @Slot(int)
    def handle_configured(self, generation: int) -> None:
        self._on_event(generation, None)

    @Slot(int, str)
    def handle_error(self, generation: int, message: str) -> None:
        self._on_event(generation, message)


class QtRelayRuntime(QObject):
    """Владеет рабочим потоком и создаёт Qt Audio объекты только в нём."""

    def __init__(
        self,
        on_event: Callable[[int, str | None], None],
        source_factory: Callable[[object, QAudioFormat], object] = QAudioSource,
        sink_factory: Callable[[object, QAudioFormat], object] = QAudioSink,
    ) -> None:
        super().__init__()
        self._thread = QThread(self)
        self._bridge = _RelayBridge(self)
        self._event_receiver = _RelayEventReceiver(on_event, self)
        self._worker = _RelayWorker(source_factory, sink_factory)
        self._worker.moveToThread(self._thread)
        self._bridge.configure_requested.connect(self._worker.configure)
        self._bridge.stop_requested.connect(self._worker.stop)
        self._bridge.shutdown_requested.connect(self._worker.shutdown)
        self._worker.configured.connect(self._event_receiver.handle_configured)
        self._worker.error.connect(self._event_receiver.handle_error)
        self._thread.finished.connect(self._worker.deleteLater)
        self._closed = False

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    def apply(
        self,
        input_device: object,
        cable_device: object,
        audio_format: QAudioFormat,
        volume: float,
        generation: int,
    ) -> None:
        if self._closed:
            return
        if not self._thread.isRunning():
            self._thread.start()
        self._bridge.configure_requested.emit(
            input_device,
            cable_device,
            audio_format,
            volume,
            generation,
        )

    def stop(self) -> None:
        if not self._closed and self._thread.isRunning():
            self._bridge.stop_requested.emit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread.isRunning():
            self._bridge.shutdown_requested.emit()
            self._thread.wait()


class VirtualMicrophoneCoordinator:
    """Валидирует конфигурацию relay и публикует его состояние."""

    def __init__(
        self,
        on_status: Callable[[AudioRoutingStatus], None],
        runtime_factory: Callable[
            [Callable[[int, str | None], None]],
            RelayRuntime,
        ] = QtRelayRuntime,
    ) -> None:
        self._on_status = on_status
        self._runtime = runtime_factory(self._handle_runtime_event)
        self._status: AudioRoutingStatus | None = None
        self._closed = False
        self._generation = 0

    def start(
        self,
        input_device: object | None,
        cable_device: object | None,
        volume: float,
    ) -> None:
        self.apply(input_device, cable_device, volume)

    def apply(
        self,
        input_device: object | None,
        cable_device: object | None,
        volume: float,
    ) -> None:
        if self._closed:
            return
        self._validate_volume(volume)
        self._generation += 1
        if input_device is None:
            self._runtime.stop()
            self._set_status("microphone_missing", "Микрофон недоступен")
            return
        if cable_device is None:
            self._runtime.stop()
            self._set_status("cable_missing", "VB-CABLE не найден")
            return
        audio_format = select_relay_format(input_device, cable_device)
        if audio_format is None:
            self._runtime.stop()
            self._set_status("pipeline_error", "Нет общего PCM-формата")
            return
        self._runtime.apply(
            input_device,
            cable_device,
            audio_format,
            volume,
            self._generation,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._runtime.close()

    def _handle_runtime_event(self, generation: int, message: str | None) -> None:
        if generation != self._generation or self._closed:
            return
        if message is None:
            self._set_status("active", "Виртуальный микрофон активен")
        else:
            self._set_status("pipeline_error", f"Ошибка аудиопотока: {message}")

    def _set_status(self, code: str, message: str) -> None:
        status = AudioRoutingStatus(code, message)  # type: ignore[arg-type]
        if status == self._status:
            return
        self._status = status
        self._on_status(status)

    @staticmethod
    def _validate_volume(volume: float) -> None:
        if (
            isinstance(volume, bool)
            or not isinstance(volume, (int, float))
            or not math.isfinite(volume)
            or not 0.0 <= volume <= 1.0
        ):
            raise ValueError("Громкость relay должна быть от 0 до 1")
