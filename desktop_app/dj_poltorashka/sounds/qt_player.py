"""Адаптер Qt Multimedia для воспроизведения локальных звуков."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer


class QtSoundPlayerFactory:
    """Создаёт проигрыватели и обновляет их устройство вывода."""

    def __init__(
        self,
        media_devices=None,
        media_player_type=QMediaPlayer,
        audio_output_type=QAudioOutput,
    ) -> None:
        self._media_devices = media_devices or QMediaDevices()
        self._media_player_type = media_player_type
        self._audio_output_type = audio_output_type
        self._players: set[_QtSoundPlayer] = set()
        self._media_devices.audioOutputsChanged.connect(
            self._update_default_output
        )

    def create(
        self,
        path: Path,
        on_finished: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> "_QtSoundPlayer":
        player = _QtSoundPlayer(
            path,
            self._media_player_type,
            self._audio_output_type,
            self._media_devices.defaultAudioOutput(),
            on_finished,
            on_error,
            self._discard,
        )
        self._players.add(player)
        return player

    def _update_default_output(self) -> None:
        device = self._media_devices.defaultAudioOutput()
        for player in tuple(self._players):
            player.set_output_device(device)

    def _discard(self, player: "_QtSoundPlayer") -> None:
        self._players.discard(player)


class _QtSoundPlayer:
    def __init__(
        self,
        path: Path,
        media_player_type,
        audio_output_type,
        output_device,
        on_finished: Callable[[], None],
        on_error: Callable[[str], None],
        on_closed: Callable[["_QtSoundPlayer"], None],
    ) -> None:
        self._on_finished = on_finished
        self._on_error = on_error
        self._on_closed = on_closed
        self._closed = False
        self._audio_output = audio_output_type()
        self._audio_output.setDevice(output_device)
        self._media_player = media_player_type()
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setSource(
            QUrl.fromLocalFile(str(Path(path).resolve()))
        )
        self._media_player.mediaStatusChanged.connect(
            self._handle_media_status
        )
        self._media_player.errorOccurred.connect(self._handle_error)

    def start(self) -> None:
        self._media_player.setPosition(0)
        self._media_player.play()

    def stop(self) -> None:
        self._media_player.stop()

    def set_output_device(self, device) -> None:
        self._audio_output.setDevice(device)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._on_closed(self)
        self._media_player.deleteLater()
        self._audio_output.deleteLater()

    def _handle_media_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._on_finished()

    def _handle_error(self, error, message: str) -> None:
        normalized = message.strip() if isinstance(message, str) else ""
        self._on_error(normalized or "Ошибка Qt Multimedia")

