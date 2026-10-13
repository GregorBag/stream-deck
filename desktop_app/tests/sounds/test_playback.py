"""Правила воспроизведения звуковых кнопок."""

from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from dj_poltorashka.sounds.playback import SoundPlaybackService
from dj_poltorashka.sounds.qt_player import QtSoundPlayerFactory


class FakePlayer:
    def __init__(self, path: Path, on_finished, on_error) -> None:
        self.path = path
        self.on_finished = on_finished
        self.on_error = on_error
        self.start_count = 0
        self.stop_count = 0
        self.close_count = 0
        self.start_error: RuntimeError | None = None
        self.fail_during_start = False

    def start(self) -> None:
        self.start_count += 1
        if self.start_error is not None:
            raise self.start_error
        if self.fail_during_start:
            self.on_error("decoder failed during start")

    def stop(self) -> None:
        self.stop_count += 1

    def close(self) -> None:
        self.close_count += 1


class FakePlayerFactory:
    def __init__(self) -> None:
        self.players: list[FakePlayer] = []
        self.start_error: RuntimeError | None = None
        self.fail_during_start = False

    def create(self, path: Path, on_finished, on_error) -> FakePlayer:
        player = FakePlayer(path, on_finished, on_error)
        player.start_error = self.start_error
        player.fail_during_start = self.fail_during_start
        self.players.append(player)
        return player


def test_play_validates_button_index(tmp_path: Path) -> None:
    service = SoundPlaybackService(FakePlayerFactory(), lambda *args: None,
                                   lambda *args: None, lambda *args: None)

    with pytest.raises(IndexError):
        service.play(-1, tmp_path / "sound.wav")
    with pytest.raises(IndexError):
        service.play(8, tmp_path / "sound.wav")
    with pytest.raises(IndexError):
        service.play(True, tmp_path / "sound.wav")


def test_same_button_restarts_without_affecting_other_button(
    tmp_path: Path,
) -> None:
    factory = FakePlayerFactory()
    started: list[tuple[int, Path]] = []
    service = SoundPlaybackService(
        factory,
        lambda index, path: started.append((index, path)),
        lambda index: None,
        lambda index, message: None,
    )
    first_path = tmp_path / "first.wav"
    second_path = tmp_path / "second.mp3"

    service.play(0, first_path)
    first_player = factory.players[-1]
    service.play(1, second_path)
    other_player = factory.players[-1]
    service.play(0, first_path)
    replacement = factory.players[-1]

    assert first_player.start_count == 1
    assert first_player.stop_count == 1
    assert first_player.close_count == 1
    assert other_player.stop_count == 0
    assert other_player.close_count == 0
    assert replacement.start_count == 1
    assert started == [(0, first_path), (1, second_path), (0, first_path)]


def test_late_finish_from_replaced_player_does_not_remove_new_run(
    tmp_path: Path,
) -> None:
    factory = FakePlayerFactory()
    finished: list[int] = []
    service = SoundPlaybackService(
        factory,
        lambda index, path: None,
        finished.append,
        lambda index, message: None,
    )

    service.play(3, tmp_path / "sound.wav")
    old_player = factory.players[-1]
    service.play(3, tmp_path / "sound.wav")
    new_player = factory.players[-1]
    old_player.on_finished()
    new_player.on_finished()

    assert new_player.close_count == 1
    assert finished == [3]


def test_error_closes_only_affected_slot(tmp_path: Path) -> None:
    factory = FakePlayerFactory()
    errors: list[tuple[int, str]] = []
    service = SoundPlaybackService(
        factory,
        lambda index, path: None,
        lambda index: None,
        lambda index, message: errors.append((index, message)),
    )
    service.play(0, tmp_path / "first.wav")
    service.play(1, tmp_path / "second.wav")
    failed = factory.players[0]
    unaffected = factory.players[1]

    failed.on_error("decoder failed")

    assert failed.stop_count == 1
    assert failed.close_count == 1
    assert unaffected.stop_count == 0
    assert unaffected.close_count == 0
    assert errors == [(0, "decoder failed")]


@pytest.mark.parametrize("error_during_callback", (False, True))
def test_synchronous_start_error_does_not_report_success(
    tmp_path: Path,
    error_during_callback: bool,
) -> None:
    factory = FakePlayerFactory()
    if error_during_callback:
        factory.fail_during_start = True
    else:
        factory.start_error = RuntimeError("decoder failed during start")
    started: list[int] = []
    errors: list[tuple[int, str]] = []
    service = SoundPlaybackService(
        factory,
        lambda index, path: started.append(index),
        lambda index: None,
        lambda index, message: errors.append((index, message)),
    )

    result = service.play(0, tmp_path / "sound.wav")

    assert not result
    assert started == []
    assert errors == [(0, "decoder failed during start")]
    assert factory.players[0].close_count == 1


def test_close_stops_and_releases_all_players(tmp_path: Path) -> None:
    factory = FakePlayerFactory()
    service = SoundPlaybackService(factory, lambda *args: None,
                                   lambda *args: None, lambda *args: None)
    service.play(0, tmp_path / "first.wav")
    service.play(7, tmp_path / "second.wav")

    service.close()
    service.close()

    assert [player.stop_count for player in factory.players] == [1, 1]
    assert [player.close_count for player in factory.players] == [1, 1]


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self, *arguments) -> None:
        for callback in tuple(self.callbacks):
            callback(*arguments)


class FakeMediaDevices:
    def __init__(self) -> None:
        self.audioOutputsChanged = FakeSignal()
        self.default_device = "speakers"

    def defaultAudioOutput(self):
        return self.default_device


class FakeAudioOutput:
    instances: list["FakeAudioOutput"] = []

    def __init__(self) -> None:
        self.devices = []
        self.deleted = 0
        self.instances.append(self)

    def setDevice(self, device) -> None:
        self.devices.append(device)

    def deleteLater(self) -> None:
        self.deleted += 1


class FakeMediaPlayer:
    instances: list["FakeMediaPlayer"] = []

    def __init__(self) -> None:
        self.mediaStatusChanged = FakeSignal()
        self.errorOccurred = FakeSignal()
        self.output = None
        self.sources = []
        self.positions = []
        self.play_count = 0
        self.stop_count = 0
        self.deleted = 0
        self.instances.append(self)

    def setAudioOutput(self, output) -> None:
        self.output = output

    def setSource(self, source) -> None:
        self.sources.append(source)

    def setPosition(self, position: int) -> None:
        self.positions.append(position)

    def play(self) -> None:
        self.play_count += 1

    def stop(self) -> None:
        self.stop_count += 1

    def deleteLater(self) -> None:
        self.deleted += 1


def make_qt_factory(devices: FakeMediaDevices) -> QtSoundPlayerFactory:
    FakeAudioOutput.instances.clear()
    FakeMediaPlayer.instances.clear()
    return QtSoundPlayerFactory(
        devices,
        media_player_type=FakeMediaPlayer,
        audio_output_type=FakeAudioOutput,
    )


def test_qt_player_uses_local_file_and_reports_finish_and_error(
    tmp_path: Path,
) -> None:
    devices = FakeMediaDevices()
    factory = make_qt_factory(devices)
    finished: list[str] = []
    errors: list[str] = []
    path = tmp_path / "sound.wav"
    player = factory.create(
        path,
        lambda: finished.append("finished"),
        errors.append,
    )

    player.start()
    media = FakeMediaPlayer.instances[0]
    output = FakeAudioOutput.instances[0]

    assert Path(media.sources[0].toLocalFile()) == path.resolve()
    assert media.positions == [0]
    assert media.play_count == 1
    assert output.devices == ["speakers"]

    media.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
    media.errorOccurred.emit(QMediaPlayer.Error.ResourceError, "bad file")
    assert finished == ["finished"]
    assert errors == ["bad file"]


def test_qt_factory_updates_default_output_for_every_active_player(
    tmp_path: Path,
) -> None:
    devices = FakeMediaDevices()
    factory = make_qt_factory(devices)
    first = factory.create(tmp_path / "first.wav", lambda: None, lambda _: None)
    second = factory.create(tmp_path / "second.wav", lambda: None, lambda _: None)

    devices.default_device = "headphones"
    devices.audioOutputsChanged.emit()

    assert [output.devices for output in FakeAudioOutput.instances] == [
        ["speakers", "headphones"],
        ["speakers", "headphones"],
    ]

    first.close()
    second.close()
    assert all(media.deleted == 1 for media in FakeMediaPlayer.instances)
    assert all(output.deleted == 1 for output in FakeAudioOutput.instances)
