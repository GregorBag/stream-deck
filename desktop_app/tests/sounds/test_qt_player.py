from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from dj_poltorashka.sounds.qt_player import QtSoundPlayerFactory


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self.callbacks.append(callback)

    def emit(self, *arguments: object) -> None:
        for callback in tuple(self.callbacks):
            callback(*arguments)  # type: ignore[operator]


class FakeMediaDevices:
    def __init__(self) -> None:
        self.audioOutputsChanged = FakeSignal()

    def defaultAudioOutput(self) -> str:
        return "default"


class FakeAudioOutput:
    instances: list["FakeAudioOutput"] = []

    def __init__(self) -> None:
        self.device: object | None = None
        self.volumes: list[float] = []
        self.deleted = 0
        self.instances.append(self)

    def setDevice(self, device: object) -> None:
        self.device = device

    def setVolume(self, volume: float) -> None:
        self.volumes.append(volume)

    def deleteLater(self) -> None:
        self.deleted += 1


class FakeMediaPlayer:
    instances: list["FakeMediaPlayer"] = []
    fail_devices: set[object] = set()

    def __init__(self) -> None:
        self.mediaStatusChanged = FakeSignal()
        self.errorOccurred = FakeSignal()
        self.output: FakeAudioOutput | None = None
        self.play_count = 0
        self.stop_count = 0
        self.instances.append(self)

    def setAudioOutput(self, output: FakeAudioOutput) -> None:
        self.output = output

    def setSource(self, source: object) -> None:
        self.source = source

    def setPosition(self, position: int) -> None:
        self.position = position

    def play(self) -> None:
        self.play_count += 1
        if self.output is not None and self.output.device in self.fail_devices:
            raise RuntimeError(f"failed {self.output.device}")

    def stop(self) -> None:
        self.stop_count += 1

    def deleteLater(self) -> None:
        pass


def make_factory(
    monitor: object | None,
    cable: object | None,
    routing_errors: list[str] | None = None,
) -> QtSoundPlayerFactory:
    FakeAudioOutput.instances.clear()
    FakeMediaPlayer.instances.clear()
    FakeMediaPlayer.fail_devices.clear()
    return QtSoundPlayerFactory(
        FakeMediaDevices(),
        media_player_type=FakeMediaPlayer,
        audio_output_type=FakeAudioOutput,
        monitor_device_provider=lambda: monitor,
        cable_device_provider=lambda: cable,
        mix_gains_provider=lambda: (1.0, 1.0),
        on_routing_error=(
            routing_errors.append if routing_errors is not None else lambda message: None
        ),
    )


@pytest.mark.parametrize(
    ("monitor", "cable", "expected_device", "expected_volume"),
    [("headphones", None, "headphones", 1.0), (None, "cable", "cable", 0.5)],
)
def test_single_available_route_starts(
    tmp_path: Path,
    monitor: object | None,
    cable: object | None,
    expected_device: object,
    expected_volume: float,
) -> None:
    player = make_factory(monitor, cable).create(
        tmp_path / "sound.wav", lambda: None, lambda message: None
    )

    player.start()

    assert len(FakeMediaPlayer.instances) == 1
    assert FakeAudioOutput.instances[0].device == expected_device
    assert FakeAudioOutput.instances[0].volumes[-1] == expected_volume


def test_paired_routes_finish_once_after_both_sides(tmp_path: Path) -> None:
    finished: list[str] = []
    player = make_factory("headphones", "cable").create(
        tmp_path / "sound.wav", lambda: finished.append("done"), lambda message: None
    )
    player.start()
    monitor, cable = FakeMediaPlayer.instances

    monitor.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
    assert finished == []
    cable.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
    cable.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)

    assert finished == ["done"]


def test_simultaneous_virtual_players_share_sound_bus(tmp_path: Path) -> None:
    factory = make_factory("headphones", "cable")
    first = factory.create(tmp_path / "first.wav", lambda: None, lambda message: None)
    second = factory.create(tmp_path / "second.wav", lambda: None, lambda message: None)

    first.start()
    second.start()

    virtual_outputs = [
        output for output in FakeAudioOutput.instances if output.device == "cable"
    ]
    assert [output.volumes[-1] for output in virtual_outputs] == [0.25, 0.25]


def test_active_virtual_players_apply_changed_sound_gain(tmp_path: Path) -> None:
    gains = [1.0, 1.0]
    FakeAudioOutput.instances.clear()
    FakeMediaPlayer.instances.clear()
    factory = QtSoundPlayerFactory(
        FakeMediaDevices(),
        media_player_type=FakeMediaPlayer,
        audio_output_type=FakeAudioOutput,
        monitor_device_provider=lambda: "headphones",
        cable_device_provider=lambda: "cable",
        mix_gains_provider=lambda: (gains[0], gains[1]),
    )
    player = factory.create(
        tmp_path / "sound.wav", lambda: None, lambda message: None
    )
    player.start()
    virtual_output = next(
        output for output in FakeAudioOutput.instances if output.device == "cable"
    )

    gains[1] = 0.2
    factory.update_mix_gains()

    assert virtual_output.volumes[-1] == 0.1


def test_active_player_applies_changed_monitor_device(tmp_path: Path) -> None:
    monitor = ["headphones"]
    FakeAudioOutput.instances.clear()
    FakeMediaPlayer.instances.clear()
    factory = QtSoundPlayerFactory(
        FakeMediaDevices(),
        media_player_type=FakeMediaPlayer,
        audio_output_type=FakeAudioOutput,
        monitor_device_provider=lambda: monitor[0],
        cable_device_provider=lambda: "cable",
    )
    factory.create(
        tmp_path / "sound.wav", lambda: None, lambda message: None
    ).start()
    monitor_output = next(
        output for output in FakeAudioOutput.instances if output.device == "headphones"
    )

    monitor[0] = "speakers"
    factory.update_output_devices()

    assert monitor_output.device == "speakers"


def test_successful_virtual_start_reports_routing_recovery(tmp_path: Path) -> None:
    recoveries: list[str] = []
    FakeAudioOutput.instances.clear()
    FakeMediaPlayer.instances.clear()
    factory = QtSoundPlayerFactory(
        FakeMediaDevices(),
        media_player_type=FakeMediaPlayer,
        audio_output_type=FakeAudioOutput,
        monitor_device_provider=lambda: "headphones",
        cable_device_provider=lambda: "cable",
        on_routing_active=lambda: recoveries.append("active"),
    )

    factory.create(
        tmp_path / "sound.wav", lambda: None, lambda message: None
    ).start()

    assert recoveries == ["active"]


def test_virtual_failure_keeps_monitor_and_reports_routing_error(tmp_path: Path) -> None:
    routing_errors: list[str] = []
    playback_errors: list[str] = []
    factory = make_factory("headphones", "cable", routing_errors)
    FakeMediaPlayer.fail_devices.add("cable")
    player = factory.create(
        tmp_path / "sound.wav", lambda: None, playback_errors.append
    )

    player.start()

    assert FakeMediaPlayer.instances[0].play_count == 1
    assert playback_errors == []
    assert routing_errors == ["failed cable"]


def test_both_route_failures_report_one_playback_error(tmp_path: Path) -> None:
    errors: list[str] = []
    factory = make_factory("headphones", "cable")
    FakeMediaPlayer.fail_devices.update({"headphones", "cable"})
    player = factory.create(tmp_path / "sound.wav", lambda: None, errors.append)

    player.start()

    assert len(errors) == 1


def test_closed_pair_ignores_stale_callbacks(tmp_path: Path) -> None:
    finished: list[str] = []
    player = make_factory("headphones", "cable").create(
        tmp_path / "sound.wav", lambda: finished.append("done"), lambda message: None
    )
    player.start()
    endpoints = tuple(FakeMediaPlayer.instances)

    player.close()
    for endpoint in endpoints:
        endpoint.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)

    assert finished == []
