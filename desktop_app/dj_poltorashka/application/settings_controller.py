"""Операции окна настроек над системными параметрами."""

from collections.abc import Callable
from dataclasses import replace

from dj_poltorashka.application.autostart import WindowsAutostart
from dj_poltorashka.audio.routing_models import AudioDeviceDescriptor
from dj_poltorashka.audio.routing_settings import AudioRoutingSettings


class SettingsController:
    """Предоставляет настройкам проверенное фактическое состояние системы."""

    def __init__(
        self,
        autostart: WindowsAutostart,
        routing_repository: object | None = None,
        device_registry: object | None = None,
        on_routing_change: Callable[[AudioRoutingSettings], None] | None = None,
    ) -> None:
        self._autostart = autostart
        self._routing_repository = routing_repository
        self._device_registry = device_registry
        self._on_routing_change = on_routing_change or (lambda settings: None)
        self._routing_settings = (
            routing_repository.load()
            if routing_repository is not None
            else AudioRoutingSettings()
        )

    def autostart_enabled(self) -> bool:
        return self._autostart.is_enabled()

    def set_autostart_enabled(self, enabled: bool) -> bool:
        self._autostart.set_enabled(enabled)
        return self._autostart.is_enabled()

    def routing_settings(self) -> AudioRoutingSettings:
        return self._routing_settings

    def input_devices(self) -> tuple[AudioDeviceDescriptor, ...]:
        if self._device_registry is None:
            return ()
        return self._device_registry.inputs()

    def monitor_devices(self) -> tuple[AudioDeviceDescriptor, ...]:
        if self._device_registry is None:
            return ()
        return self._device_registry.outputs()

    def set_input_device(self, device_id: str | None) -> None:
        self._replace_routing_settings(input_device_id=device_id)

    def set_monitor_device(self, device_id: str | None) -> None:
        self._replace_routing_settings(monitor_device_id=device_id)

    def set_microphone_gain(self, value: float) -> None:
        self._replace_routing_settings(microphone_gain=value)

    def set_sound_gain(self, value: float) -> None:
        self._replace_routing_settings(sound_gain=value)

    def _replace_routing_settings(self, **changes: object) -> None:
        updated = replace(self._routing_settings, **changes)
        if self._routing_repository is not None:
            self._routing_repository.save(updated)
        self._routing_settings = updated
        self._on_routing_change(updated)
