from dj_poltorashka.audio.routing_models import AudioRoutingStatus
from dj_poltorashka.audio.routing_service import AudioRoutingService
from dj_poltorashka.audio.routing_settings import AudioRoutingSettings


class FakeRegistry:
    def __init__(self) -> None:
        self.default_input: object | None = "default-microphone"
        self.default_monitor: object | None = "default-monitor"
        self.inputs: dict[str, object] = {"usb": "usb-microphone"}
        self.monitors: dict[str, object] = {"phones": "headphones"}
        self.cable: object | None = "cable-input"
        self.callback = lambda: None
        self.close_count = 0

    def resolve_input(self, device_id: str | None) -> object | None:
        return self.default_input if device_id is None else self.inputs.get(device_id)

    def resolve_monitor(self, device_id: str | None) -> object | None:
        return self.default_monitor if device_id is None else self.monitors.get(device_id)

    def resolve_cable_input(self) -> object | None:
        return self.cable

    def on_devices_changed(self, callback: object) -> None:
        self.callback = callback  # type: ignore[assignment]

    def close(self) -> None:
        self.close_count += 1


class FakeRelay:
    def __init__(self, on_status: object) -> None:
        self.on_status = on_status
        self.calls: list[tuple[object | None, object | None, float]] = []
        self.close_count = 0

    def start(self, input_device: object, cable_device: object, volume: float) -> None:
        self.apply(input_device, cable_device, volume)

    def apply(
        self,
        input_device: object | None,
        cable_device: object | None,
        volume: float,
    ) -> None:
        self.calls.append((input_device, cable_device, volume))

    def close(self) -> None:
        self.close_count += 1


def make_service(
    settings: AudioRoutingSettings = AudioRoutingSettings(),
) -> tuple[AudioRoutingService, FakeRegistry, FakeRelay, list[AudioRoutingStatus]]:
    registry = FakeRegistry()
    relay_holder: list[FakeRelay] = []
    statuses: list[AudioRoutingStatus] = []

    def relay_factory(on_status: object) -> FakeRelay:
        relay = FakeRelay(on_status)
        relay_holder.append(relay)
        return relay

    service = AudioRoutingService(registry, settings, statuses.append, relay_factory)
    return service, registry, relay_holder[0], statuses


def test_start_with_defaults_uses_one_resolved_snapshot() -> None:
    service, registry, relay, statuses = make_service()

    service.start()

    assert relay.calls == [("default-microphone", "cable-input", 0.5)]
    assert service.monitor_device() == "default-monitor"
    assert service.cable_device() == "cable-input"
    assert service.status.code == "active"
    assert [state.code for state in statuses] == ["active"]


def test_missing_explicit_devices_do_not_fall_back_to_defaults() -> None:
    settings = AudioRoutingSettings("missing", "missing", 1.0, 1.0)
    service, _, relay, statuses = make_service(settings)

    service.start()

    assert relay.calls[-1][:2] == (None, "cable-input")
    assert service.monitor_device() is None
    assert service.status.code == "microphone_missing"
    assert [state.code for state in statuses] == ["microphone_missing"]


def test_default_device_change_switches_automatically_and_coalesces_status() -> None:
    service, registry, relay, statuses = make_service()
    service.start()
    registry.default_input = "new-default-microphone"
    registry.default_monitor = "new-default-monitor"

    registry.callback()
    registry.callback()

    assert relay.calls[-1][0] == "new-default-microphone"
    assert service.monitor_device() == "new-default-monitor"
    assert [state.code for state in statuses] == ["active"]


def test_degraded_routes_remain_independently_available_and_recover() -> None:
    service, registry, relay, statuses = make_service()
    service.start()

    registry.cable = None
    service.refresh_devices()
    assert service.monitor_device() == "default-monitor"
    assert service.cable_device() is None
    assert service.status.code == "cable_missing"

    registry.cable = "cable-input"
    registry.default_monitor = None
    service.refresh_devices()
    assert service.cable_device() == "cable-input"
    assert service.status.code == "monitor_missing"

    registry.default_monitor = "default-monitor"
    registry.default_input = None
    service.refresh_devices()
    assert relay.calls[-1][:2] == (None, "cable-input")
    assert service.cable_device() == "cable-input"
    assert service.status.code == "microphone_missing"

    registry.default_input = "default-microphone"
    service.refresh_devices()
    assert service.status.code == "active"
    assert [state.code for state in statuses] == [
        "active", "cable_missing", "monitor_missing", "microphone_missing", "active"
    ]


def test_apply_refresh_and_close_are_safe_during_rapid_changes() -> None:
    service, registry, relay, _ = make_service()
    service.start()

    service.apply(AudioRoutingSettings("usb", "phones", 0.6, 0.7))
    service.refresh_devices()
    service.close()
    service.close()
    service.refresh_devices()

    assert relay.calls[-1] == ("usb-microphone", "cable-input", 0.3)
    assert relay.close_count == 1
    assert registry.close_count == 1
