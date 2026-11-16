"""Операции окна настроек над системными параметрами."""

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from dj_poltorashka.application.autostart import WindowsAutostart
from dj_poltorashka.audio.routing_models import AudioDeviceDescriptor
from dj_poltorashka.audio.routing_settings import AudioRoutingSettings
from dj_poltorashka.panel.lighting import LightingSettings, LightingSettingsRepository
from dj_poltorashka.panel.connection import PanelConnectionStatus

if TYPE_CHECKING:
    from dj_poltorashka.panel.worker import PanelCoordinator
    from dj_poltorashka.panel.transport import PanelPort


class SettingsController:
    """Предоставляет настройкам проверенное фактическое состояние системы."""

    def __init__(
        self,
        autostart: WindowsAutostart,
        routing_repository: object | None = None,
        device_registry: object | None = None,
        on_routing_change: Callable[[AudioRoutingSettings], None] | None = None,
        initial_routing_settings: AudioRoutingSettings | None = None,
        lighting_repository: LightingSettingsRepository | None = None,
        initial_lighting_settings: LightingSettings | None = None,
        panel_coordinator: "PanelCoordinator | None" = None,
        on_lighting_change: Callable[[LightingSettings], None] | None = None,
    ) -> None:
        self._autostart = autostart
        self._panel_coordinator = panel_coordinator
        self._on_lighting_change = on_lighting_change or (lambda settings: None)
        self._lighting_repository = lighting_repository
        self._lighting_settings = initial_lighting_settings or (
            lighting_repository.load() if lighting_repository is not None else LightingSettings()
        )
        self._routing_repository = routing_repository
        self._device_registry = device_registry
        self._on_routing_change = on_routing_change or (lambda settings: None)
        if initial_routing_settings is not None:
            self._routing_settings = initial_routing_settings
        elif routing_repository is not None:
            self._routing_settings = routing_repository.load()
        else:
            self._routing_settings = AudioRoutingSettings()

    def autostart_enabled(self) -> bool:
        return self._autostart.is_enabled()

    def lighting_settings(self) -> LightingSettings:
        return self._lighting_settings

    def set_lighting_settings(self, settings: LightingSettings) -> None:
        if not isinstance(settings, LightingSettings):
            raise ValueError("Ожидались LightingSettings")
        if self._lighting_repository is not None:
            self._lighting_repository.save(settings)
        self._lighting_settings = settings
        self._on_lighting_change(settings)

    def panel_ports(self) -> tuple["PanelPort", ...]:
        return self._panel_coordinator.ports if self._panel_coordinator else ()

    def selected_panel_port(self) -> str | None:
        return self._panel_coordinator.selected_port if self._panel_coordinator else None

    def panel_status(self) -> PanelConnectionStatus:
        return self._panel_coordinator.status if self._panel_coordinator else PanelConnectionStatus()

    def select_panel_port(self, name: str | None) -> None:
        if self._panel_coordinator:
            self._panel_coordinator.select_port(name)

    def refresh_panel_ports(self) -> None:
        if self._panel_coordinator:
            self._panel_coordinator.refresh_ports()

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
