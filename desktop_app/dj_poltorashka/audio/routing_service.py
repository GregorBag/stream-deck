"""Координация устройств, microphone relay и статуса маршрутизации."""

from collections.abc import Callable
from dataclasses import dataclass

from dj_poltorashka.audio.headroom import calculate_bus_levels
from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.audio.routing_settings import AudioRoutingSettings
from dj_poltorashka.audio.virtual_microphone import VirtualMicrophoneCoordinator


@dataclass(frozen=True)
class ResolvedRoutingSnapshot:
    settings: AudioRoutingSettings
    input_device: object | None
    monitor_device: object | None
    cable_device: object | None


def _device_key(device: object | None) -> object | None:
    if device is None:
        return None
    id_reader = getattr(device, "id", None)
    return bytes(id_reader()) if callable(id_reader) else device


def _relay_key(snapshot: ResolvedRoutingSnapshot) -> tuple[object | None, object | None, float]:
    voice_level = calculate_bus_levels(
        snapshot.settings.microphone_gain,
        snapshot.settings.sound_gain,
        0,
    ).microphone
    return (
        _device_key(snapshot.input_device),
        _device_key(snapshot.cable_device),
        voice_level,
    )


class AudioRoutingService:
    """Применяет один согласованный снимок устройств за обновление."""

    def __init__(
        self,
        device_registry: object,
        settings: AudioRoutingSettings,
        on_status: Callable[[AudioRoutingStatus], None],
        relay_factory: Callable[[Callable[[AudioRoutingStatus], None]], object] = (
            VirtualMicrophoneCoordinator
        ),
    ) -> None:
        self._registry = device_registry
        self._settings = settings
        self._on_status = on_status
        self._relay = relay_factory(self._handle_relay_status)
        self._snapshot = ResolvedRoutingSnapshot(settings, None, None, None)
        self._status = AudioRoutingStatus(
            "pipeline_error",
            "Виртуальный микрофон ещё не запущен",
        )
        self._started = False
        self._relay_started = False
        self._closed = False
        self._refreshing = False
        self._pending_relay_status: AudioRoutingStatus | None = None
        self._relay_status: AudioRoutingStatus | None = None
        self._playback_error: str | None = None

    @property
    def status(self) -> AudioRoutingStatus:
        return self._status

    def start(self) -> None:
        if self._closed or self._started:
            return
        self._started = True
        self._registry.on_devices_changed(self.refresh_devices)
        self.refresh_devices()

    def apply(self, settings: AudioRoutingSettings) -> None:
        if not isinstance(settings, AudioRoutingSettings):
            raise ValueError("Ожидался AudioRoutingSettings")
        if self._closed:
            return
        self._settings = settings
        if self._started:
            self.refresh_devices()

    def refresh_devices(self) -> None:
        if self._closed or not self._started:
            return
        previous_snapshot = self._snapshot
        snapshot = ResolvedRoutingSnapshot(
            self._settings,
            self._registry.resolve_input(self._settings.input_device_id),
            self._registry.resolve_monitor(self._settings.monitor_device_id),
            self._registry.resolve_cable_input(),
        )
        self._snapshot = snapshot
        if self._relay_started and _relay_key(snapshot) == _relay_key(previous_snapshot):
            self._publish_combined_status()
            return
        voice_level = _relay_key(snapshot)[2]
        self._refreshing = True
        self._pending_relay_status = None
        self._relay_status = None
        try:
            if not self._relay_started:
                self._relay.start(
                    snapshot.input_device,
                    snapshot.cable_device,
                    voice_level,
                )
                self._relay_started = True
            else:
                self._relay.apply(
                    snapshot.input_device,
                    snapshot.cable_device,
                    voice_level,
                )
        finally:
            self._refreshing = False
        if self._pending_relay_status is not None:
            self._relay_status = self._pending_relay_status
        self._publish_combined_status()

    def monitor_device(self) -> object | None:
        return self._snapshot.monitor_device

    def cable_device(self) -> object | None:
        return self._snapshot.cable_device

    def report_pipeline_error(self, message: str) -> None:
        normalized = message.strip() if isinstance(message, str) else ""
        self._playback_error = normalized or "неизвестная ошибка"
        self._publish_combined_status()

    def report_pipeline_active(self) -> None:
        self._playback_error = None
        self._publish_combined_status()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._relay.close()
        self._registry.close()

    def _handle_relay_status(self, status: AudioRoutingStatus) -> None:
        if self._closed:
            return
        if self._refreshing:
            self._pending_relay_status = status
            return
        self._relay_status = status
        self._publish_combined_status()

    def _publish_combined_status(self) -> None:
        device_status = self._device_status(self._snapshot)
        if device_status.code != "active":
            self._set_status(device_status)
            return
        if self._relay_status is not None and self._relay_status.code != "active":
            self._set_status(self._relay_status)
            return
        if self._playback_error is not None:
            self._set_status(
                AudioRoutingStatus(
                    "pipeline_error",
                    f"Ошибка аудиопотока: {self._playback_error}",
                )
            )
            return
        if self._relay_status is None:
            self._set_status(
                AudioRoutingStatus(
                    "pipeline_error",
                    "Виртуальный микрофон запускается",
                )
            )
            return
        self._set_status(device_status)

    def _set_status(self, status: AudioRoutingStatus) -> None:
        if status == self._status:
            return
        self._status = status
        self._on_status(status)

    @staticmethod
    def _device_status(snapshot: ResolvedRoutingSnapshot) -> AudioRoutingStatus:
        if snapshot.cable_device is None:
            return AudioRoutingStatus("cable_missing", "VB-CABLE не найден")
        if snapshot.input_device is None:
            return AudioRoutingStatus(
                "microphone_missing",
                "Физический микрофон недоступен",
            )
        if snapshot.monitor_device is None:
            return AudioRoutingStatus(
                "monitor_missing",
                "Мониторинг звука недоступен",
            )
        return AudioRoutingStatus("active", "Виртуальный микрофон активен")
