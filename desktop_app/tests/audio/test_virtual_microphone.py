from PySide6.QtCore import QThread
from PySide6.QtMultimedia import QAudio, QAudioFormat
from pytestqt.qtbot import QtBot

from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.audio.virtual_microphone import (
    AudioRelayPump,
    QtRelayRuntime,
    VirtualMicrophoneCoordinator,
    select_relay_format,
)


def make_format(rate: int, channels: int = 1) -> QAudioFormat:
    audio_format = QAudioFormat()
    audio_format.setSampleRate(rate)
    audio_format.setChannelCount(channels)
    audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    return audio_format


def format_key(audio_format: QAudioFormat) -> tuple[int, int, object]:
    return (
        audio_format.sampleRate(),
        audio_format.channelCount(),
        audio_format.sampleFormat(),
    )


class FakeFormatDevice:
    def __init__(
        self,
        preferred: QAudioFormat,
        supported: set[tuple[int, int, object]],
    ) -> None:
        self._preferred = preferred
        self._supported = supported

    def preferredFormat(self) -> QAudioFormat:
        return self._preferred

    def isFormatSupported(self, audio_format: QAudioFormat) -> bool:
        return format_key(audio_format) in self._supported


def test_select_relay_format_prefers_mutually_supported_input_format() -> None:
    preferred = make_format(44100, 2)
    supported = {format_key(preferred)}

    selected = select_relay_format(
        FakeFormatDevice(preferred, supported),
        FakeFormatDevice(make_format(96000), supported),
    )

    assert selected is not None
    assert format_key(selected) == (44100, 2, QAudioFormat.SampleFormat.Int16)


def test_select_relay_format_falls_back_to_48khz_signed_16_bit() -> None:
    fallback = make_format(48000, 1)
    supported = {format_key(fallback)}

    selected = select_relay_format(
        FakeFormatDevice(make_format(44100), supported),
        FakeFormatDevice(make_format(96000), supported),
    )

    assert selected is not None
    assert format_key(selected) == (48000, 1, QAudioFormat.SampleFormat.Int16)


def test_select_relay_format_returns_none_without_common_pcm_format() -> None:
    assert select_relay_format(
        FakeFormatDevice(make_format(44100), {format_key(make_format(44100))}),
        FakeFormatDevice(make_format(48000), {format_key(make_format(48000))}),
    ) is None


class FakeReadable:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def bytesAvailable(self) -> int:
        return len(self.data)

    def read(self, amount: int) -> bytes:
        result = self.data[:amount]
        self.data = self.data[amount:]
        return result


class FakeWritable:
    def __init__(self, free: int) -> None:
        self.free = free
        self.writes: list[bytes] = []

    def bytesFree(self) -> int:
        return self.free

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        return len(data)


def test_relay_pump_forwards_only_available_bytes() -> None:
    source = FakeReadable(b"abc")
    sink = FakeWritable(20)

    AudioRelayPump(source, sink, period_bytes=10).forward()

    assert sink.writes == [b"abc"]


def test_relay_pump_discards_stale_excess_under_backpressure() -> None:
    source = FakeReadable(b"0123456789")
    sink = FakeWritable(4)

    AudioRelayPump(source, sink, period_bytes=6).forward()

    assert sink.writes == [b"6789"]
    assert source.bytesAvailable() == 0


def test_relay_pump_writes_only_complete_pcm_frames() -> None:
    source = FakeReadable(b"0123456789")
    sink = FakeWritable(7)

    AudioRelayPump(source, sink, period_bytes=9, bytes_per_frame=4).forward()

    assert sink.writes == [b"4567"]


def test_relay_pump_preserves_pcm_frame_split_between_reads() -> None:
    source = FakeReadable(b"abc")
    sink = FakeWritable(16)
    pump = AudioRelayPump(source, sink, period_bytes=16, bytes_per_frame=4)

    pump.forward()
    source.data += b"defgh"
    pump.forward()

    assert sink.writes == [b"abcdefgh"]


class FakeRuntime:
    def __init__(self, on_event: object) -> None:
        self.on_event = on_event
        self.apply_calls: list[tuple[object, object, QAudioFormat, float, int]] = []
        self.stop_count = 0
        self.close_count = 0

    def apply(
        self,
        input_device: object,
        cable_device: object,
        audio_format: QAudioFormat,
        volume: float,
        generation: int,
    ) -> None:
        self.apply_calls.append(
            (input_device, cable_device, audio_format, volume, generation)
        )

    def stop(self) -> None:
        self.stop_count += 1

    def close(self) -> None:
        self.close_count += 1


def make_compatible_devices() -> tuple[FakeFormatDevice, FakeFormatDevice]:
    audio_format = make_format(48000)
    supported = {format_key(audio_format)}
    return (
        FakeFormatDevice(audio_format, supported),
        FakeFormatDevice(audio_format, supported),
    )


def test_coordinator_reports_absence_and_coalesces_identical_state() -> None:
    statuses: list[AudioRoutingStatus] = []
    runtime_holder: list[FakeRuntime] = []

    def factory(on_error: object) -> FakeRuntime:
        runtime = FakeRuntime(on_error)
        runtime_holder.append(runtime)
        return runtime

    coordinator = VirtualMicrophoneCoordinator(statuses.append, factory)

    coordinator.start(None, object(), 0.5)
    coordinator.apply(None, object(), 0.5)
    coordinator.apply(object(), None, 0.5)

    assert [status.code for status in statuses] == [
        "microphone_missing",
        "cable_missing",
    ]
    assert runtime_holder[0].stop_count == 3


def test_coordinator_reconfigures_devices_and_closes_idempotently() -> None:
    statuses: list[AudioRoutingStatus] = []
    runtime_holder: list[FakeRuntime] = []

    def factory(on_error: object) -> FakeRuntime:
        runtime = FakeRuntime(on_error)
        runtime_holder.append(runtime)
        return runtime

    first_input, cable = make_compatible_devices()
    second_input, _ = make_compatible_devices()
    coordinator = VirtualMicrophoneCoordinator(statuses.append, factory)

    coordinator.start(first_input, cable, 0.4)
    coordinator.apply(second_input, cable, 0.8)
    runtime_holder[0].on_event(2, None)  # type: ignore[operator]
    coordinator.close()
    coordinator.close()

    runtime = runtime_holder[0]
    assert [call[0] for call in runtime.apply_calls] == [first_input, second_input]
    assert [call[3] for call in runtime.apply_calls] == [0.4, 0.8]
    assert [status.code for status in statuses] == ["active"]
    assert runtime.close_count == 1


def test_coordinator_ignores_stale_runtime_events() -> None:
    statuses: list[AudioRoutingStatus] = []
    runtime_holder: list[FakeRuntime] = []

    def factory(on_event: object) -> FakeRuntime:
        runtime = FakeRuntime(on_event)
        runtime_holder.append(runtime)
        return runtime

    first_input, cable = make_compatible_devices()
    second_input, _ = make_compatible_devices()
    coordinator = VirtualMicrophoneCoordinator(statuses.append, factory)

    coordinator.start(first_input, cable, 0.4)
    coordinator.apply(second_input, cable, 0.8)
    runtime = runtime_holder[0]
    runtime.on_event(1, None)  # type: ignore[operator]
    runtime.on_event(2, None)  # type: ignore[operator]
    runtime.on_event(1, "late failure")  # type: ignore[operator]

    assert [status.code for status in statuses] == ["active"]


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self.callbacks.append(callback)


class FakeSource:
    def __init__(self, device: object, audio_format: QAudioFormat) -> None:
        self.created_thread = QThread.currentThread()
        self.ready = FakeSignal()
        self.stopped = False

    def start(self) -> FakeReadable:
        readable = FakeReadable(b"")
        readable.readyRead = self.ready  # type: ignore[attr-defined]
        return readable

    def stop(self) -> None:
        self.stopped = True

    def deleteLater(self) -> None:
        pass


class FakeSink:
    def __init__(self, device: object, audio_format: QAudioFormat) -> None:
        self.created_thread = QThread.currentThread()
        self.volume = 0.0
        self.stopped = False

    def setBufferSize(self, size: int) -> None:
        self.buffer_size = size

    def bufferSize(self) -> int:
        return self.buffer_size

    def setVolume(self, volume: float) -> None:
        self.volume = volume

    def start(self) -> FakeWritable:
        return FakeWritable(4096)

    def stop(self) -> None:
        self.stopped = True

    def deleteLater(self) -> None:
        pass


class FakeOpenErrorSource(FakeSource):
    def __init__(self, device: object, audio_format: QAudioFormat) -> None:
        super().__init__(device, audio_format)
        self.stateChanged = FakeSignal()
        self.callbacks_at_start = 0

    def start(self) -> FakeReadable:
        self.callbacks_at_start = len(self.stateChanged.callbacks)
        readable = super().start()
        self.stateChanged.emit(QAudio.State.StoppedState)
        return readable

    def error(self) -> QAudio.Error:
        return QAudio.Error.OpenError

    def state(self) -> QAudio.State:
        return QAudio.State.StoppedState


def test_active_qt_runtime_closes_worker_thread(qtbot: QtBot) -> None:
    sources: list[FakeSource] = []
    sinks: list[FakeSink] = []

    def source_factory(device: object, audio_format: QAudioFormat) -> FakeSource:
        source = FakeSource(device, audio_format)
        sources.append(source)
        return source

    def sink_factory(device: object, audio_format: QAudioFormat) -> FakeSink:
        sink = FakeSink(device, audio_format)
        sinks.append(sink)
        return sink

    runtime = QtRelayRuntime(
        lambda generation, message: None,
        source_factory,
        sink_factory,
    )
    runtime.apply(object(), object(), make_format(48000), 0.35, 1)
    qtbot.waitUntil(lambda: bool(sources) and bool(sinks))

    runtime.close()

    assert sources[0].created_thread is not QThread.currentThread()
    assert sinks[0].created_thread is sources[0].created_thread
    assert sinks[0].volume == 0.35
    assert sources[0].stopped
    assert sinks[0].stopped
    assert not runtime.is_running


def test_qt_runtime_delivers_errors_on_owner_thread(qtbot: QtBot) -> None:
    callback_threads: list[QThread] = []

    def fail_source(device: object, audio_format: QAudioFormat) -> object:
        raise RuntimeError("source failed")

    runtime = QtRelayRuntime(
        lambda generation, message: callback_threads.append(QThread.currentThread()),
        fail_source,
        FakeSink,
    )
    try:
        runtime.apply(object(), object(), make_format(48000), 0.35, 1)
        qtbot.waitUntil(lambda: bool(callback_threads))

        assert callback_threads == [QThread.currentThread()]
    finally:
        runtime.close()


def test_qt_runtime_does_not_report_active_after_synchronous_open_error(
    qtbot: QtBot,
) -> None:
    events: list[tuple[int, str | None]] = []
    sources: list[FakeOpenErrorSource] = []

    def source_factory(
        device: object,
        audio_format: QAudioFormat,
    ) -> FakeOpenErrorSource:
        source = FakeOpenErrorSource(device, audio_format)
        sources.append(source)
        return source

    runtime = QtRelayRuntime(
        lambda generation, message: events.append((generation, message)),
        source_factory,
        FakeSink,
    )
    try:
        runtime.apply(object(), object(), make_format(48000), 0.35, 1)
        qtbot.waitUntil(lambda: bool(events))

        assert sources[0].callbacks_at_start == 1
        assert len(events) == 1
        assert events[0][0] == 1
        assert events[0][1] is not None
    finally:
        runtime.close()
