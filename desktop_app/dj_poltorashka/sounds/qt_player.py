"""Парное воспроизведение звуков через монитор и VB-CABLE."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

from dj_poltorashka.audio.headroom import calculate_bus_levels


class QtSoundPlayerFactory:
    """Создаёт пары независимых Qt-проигрывателей и управляет sound bus."""

    def __init__(
        self,
        media_devices=None,
        media_player_type=QMediaPlayer,
        audio_output_type=QAudioOutput,
        monitor_device_provider: Callable[[], object | None] | None = None,
        cable_device_provider: Callable[[], object | None] | None = None,
        mix_gains_provider: Callable[[], tuple[float, float]] | None = None,
        on_routing_error: Callable[[str], None] | None = None,
    ) -> None:
        self._media_devices = media_devices or QMediaDevices()
        self._media_player_type = media_player_type
        self._audio_output_type = audio_output_type
        self._monitor_device_provider = (
            monitor_device_provider or self._media_devices.defaultAudioOutput
        )
        self._cable_device_provider = cable_device_provider or (lambda: None)
        self._mix_gains_provider = mix_gains_provider or (lambda: (1.0, 1.0))
        self._on_routing_error = on_routing_error or (lambda message: None)
        self._players: set[_PairedQtSoundPlayer] = set()
        self._virtual_players: set[_PairedQtSoundPlayer] = set()
        self._media_devices.audioOutputsChanged.connect(self._update_outputs)

    def create(
        self,
        path: Path,
        on_finished: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> "_PairedQtSoundPlayer":
        player = _PairedQtSoundPlayer(
            path,
            self._media_player_type,
            self._audio_output_type,
            self._monitor_device_provider(),
            self._cable_device_provider(),
            on_finished,
            on_error,
            self._on_routing_error,
            self._set_virtual_active,
            self._discard,
        )
        self._players.add(player)
        return player

    def _update_outputs(self) -> None:
        monitor = self._monitor_device_provider()
        cable = self._cable_device_provider()
        for player in tuple(self._players):
            player.set_output_devices(monitor, cable)

    def _set_virtual_active(
        self,
        player: "_PairedQtSoundPlayer",
        active: bool,
    ) -> None:
        if active:
            self._virtual_players.add(player)
        else:
            self._virtual_players.discard(player)
        self._update_virtual_volumes()

    def _update_virtual_volumes(self) -> None:
        microphone_gain, sound_gain = self._mix_gains_provider()
        levels = calculate_bus_levels(
            microphone_gain,
            sound_gain,
            len(self._virtual_players),
        )
        for player in tuple(self._virtual_players):
            player.set_virtual_volume(levels.per_sound)

    def _discard(self, player: "_PairedQtSoundPlayer") -> None:
        self._players.discard(player)
        self._virtual_players.discard(player)
        self._update_virtual_volumes()


class _QtEndpoint:
    def __init__(
        self,
        role: str,
        path: Path,
        device: object,
        media_player_type,
        audio_output_type,
        on_finished: Callable[[str], None],
        on_error: Callable[[str, str], None],
    ) -> None:
        self.role = role
        self._on_finished = on_finished
        self._on_error = on_error
        self._terminal = False
        self._closed = False
        self._audio_output = audio_output_type()
        self._audio_output.setDevice(device)
        self._media_player = media_player_type()
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
        self._media_player.mediaStatusChanged.connect(self._handle_media_status)
        self._media_player.errorOccurred.connect(self._handle_error)

    @property
    def terminal(self) -> bool:
        return self._terminal

    def start(self) -> None:
        self._media_player.setPosition(0)
        self._media_player.play()

    def stop(self) -> None:
        self._media_player.stop()

    def set_device(self, device: object | None) -> None:
        if device is not None:
            self._audio_output.setDevice(device)

    def set_volume(self, volume: float) -> None:
        self._audio_output.setVolume(volume)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._media_player.deleteLater()
        self._audio_output.deleteLater()

    def _handle_media_status(self, status: object) -> None:
        if (
            not self._closed
            and not self._terminal
            and status == QMediaPlayer.MediaStatus.EndOfMedia
        ):
            self._terminal = True
            self._on_finished(self.role)

    def _handle_error(self, error: object, message: str) -> None:
        if self._closed or self._terminal:
            return
        self._terminal = True
        normalized = message.strip() if isinstance(message, str) else ""
        self._on_error(self.role, normalized or "Ошибка Qt Multimedia")


class _PairedQtSoundPlayer:
    def __init__(
        self,
        path: Path,
        media_player_type,
        audio_output_type,
        monitor_device: object | None,
        cable_device: object | None,
        on_finished: Callable[[], None],
        on_error: Callable[[str], None],
        on_routing_error: Callable[[str], None],
        on_virtual_state: Callable[["_PairedQtSoundPlayer", bool], None],
        on_closed: Callable[["_PairedQtSoundPlayer"], None],
    ) -> None:
        self._on_finished = on_finished
        self._on_error = on_error
        self._on_routing_error = on_routing_error
        self._on_virtual_state = on_virtual_state
        self._on_closed = on_closed
        self._closed = False
        self._completion_reported = False
        self._starting = False
        self._started_roles: set[str] = set()
        self._successful_roles: set[str] = set()
        self._failed_messages: list[str] = []
        self._endpoints: dict[str, _QtEndpoint] = {}
        if monitor_device is not None:
            self._endpoints["monitor"] = _QtEndpoint(
                "monitor", path, monitor_device, media_player_type,
                audio_output_type, self._endpoint_finished, self._endpoint_failed,
            )
            self._endpoints["monitor"].set_volume(1.0)
        if cable_device is not None:
            self._endpoints["virtual"] = _QtEndpoint(
                "virtual", path, cable_device, media_player_type,
                audio_output_type, self._endpoint_finished, self._endpoint_failed,
            )

    def start(self) -> None:
        if self._closed:
            return
        self._starting = True
        for role, endpoint in self._endpoints.items():
            try:
                endpoint.start()
                if not endpoint.terminal:
                    self._started_roles.add(role)
                    if role == "virtual":
                        self._on_virtual_state(self, True)
            except Exception as error:
                message = str(error).strip() or type(error).__name__
                self._failed_messages.append(message)
                endpoint.close()
                if role == "virtual":
                    self._on_routing_error(message)
        self._starting = False
        if not self._started_roles:
            self._report_error()

    def stop(self) -> None:
        for endpoint in self._endpoints.values():
            endpoint.stop()

    def set_output_devices(
        self,
        monitor_device: object | None,
        cable_device: object | None,
    ) -> None:
        monitor = self._endpoints.get("monitor")
        virtual = self._endpoints.get("virtual")
        if monitor is not None:
            monitor.set_device(monitor_device)
        if virtual is not None:
            virtual.set_device(cable_device)

    def set_virtual_volume(self, volume: float) -> None:
        endpoint = self._endpoints.get("virtual")
        if endpoint is not None and "virtual" in self._started_roles:
            endpoint.set_volume(volume)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if "virtual" in self._started_roles:
            self._on_virtual_state(self, False)
        self._started_roles.clear()
        self._on_closed(self)
        for endpoint in self._endpoints.values():
            endpoint.close()

    def _endpoint_finished(self, role: str) -> None:
        if self._closed or role not in self._started_roles:
            return
        self._started_roles.remove(role)
        self._successful_roles.add(role)
        if role == "virtual":
            self._on_virtual_state(self, False)
        self._report_terminal_if_ready()

    def _endpoint_failed(self, role: str, message: str) -> None:
        if self._closed:
            return
        self._failed_messages.append(message)
        was_started = role in self._started_roles
        self._started_roles.discard(role)
        if role == "virtual":
            if was_started:
                self._on_virtual_state(self, False)
            self._on_routing_error(message)
        if not self._starting:
            self._report_terminal_if_ready()

    def _report_terminal_if_ready(self) -> None:
        if self._completion_reported or self._started_roles:
            return
        if self._successful_roles:
            self._completion_reported = True
            self._on_finished()
        else:
            self._report_error()

    def _report_error(self) -> None:
        if self._completion_reported:
            return
        self._completion_reported = True
        message = "; ".join(self._failed_messages) or "Нет доступного аудиовыхода"
        self._on_error(message)
