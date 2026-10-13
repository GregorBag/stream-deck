import pytest

from dj_poltorashka.audio.routing_models import AudioDeviceDescriptor
from dj_poltorashka.audio.routing_settings import AudioRoutingSettings
from dj_poltorashka.application.settings_controller import SettingsController


class FakeAutostart:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.requested_states: list[bool] = []
        self.read_error: OSError | None = None
        self.write_error: OSError | None = None

    def is_enabled(self) -> bool:
        if self.read_error is not None:
            raise self.read_error
        return self.enabled

    def set_enabled(self, enabled: bool) -> None:
        if self.write_error is not None:
            raise self.write_error
        self.requested_states.append(enabled)
        self.enabled = enabled


def test_autostart_enabled_returns_adapter_state() -> None:
    autostart = FakeAutostart(enabled=True)

    assert SettingsController(autostart).autostart_enabled()


@pytest.mark.parametrize("enabled", (True, False))
def test_set_autostart_enabled_returns_re_read_state(enabled: bool) -> None:
    autostart = FakeAutostart(enabled=not enabled)
    controller = SettingsController(autostart)

    actual_state = controller.set_autostart_enabled(enabled)

    assert autostart.requested_states == [enabled]
    assert actual_state is enabled


def test_read_error_is_not_hidden() -> None:
    autostart = FakeAutostart()
    autostart.read_error = PermissionError("read denied")

    with pytest.raises(PermissionError, match="read denied"):
        SettingsController(autostart).autostart_enabled()


def test_write_error_is_not_hidden_and_state_is_not_re_read() -> None:
    autostart = FakeAutostart()
    autostart.write_error = PermissionError("write denied")
    controller = SettingsController(autostart)

    with pytest.raises(PermissionError, match="write denied"):
        controller.set_autostart_enabled(True)

    assert autostart.requested_states == []


class FakeRoutingRepository:
    def __init__(self) -> None:
        self.settings = AudioRoutingSettings()
        self.saved: list[AudioRoutingSettings] = []
        self.error: OSError | None = None

    def load(self) -> AudioRoutingSettings:
        return self.settings

    def save(self, settings: AudioRoutingSettings) -> None:
        if self.error is not None:
            raise self.error
        self.saved.append(settings)
        self.settings = settings


class FakeDeviceRegistry:
    def inputs(self) -> tuple[AudioDeviceDescriptor, ...]:
        return (
            AudioDeviceDescriptor("01", "Микрофон"),
            AudioDeviceDescriptor("02", "Микрофон"),
        )

    def outputs(self) -> tuple[AudioDeviceDescriptor, ...]:
        return (AudioDeviceDescriptor("10", "Наушники"),)


def make_routing_controller(
    repository: FakeRoutingRepository,
    changes: list[AudioRoutingSettings],
) -> SettingsController:
    return SettingsController(
        FakeAutostart(),
        repository,
        FakeDeviceRegistry(),
        changes.append,
    )


def test_routing_changes_persist_before_complete_snapshot_callback() -> None:
    repository = FakeRoutingRepository()
    changes: list[AudioRoutingSettings] = []
    controller = make_routing_controller(repository, changes)

    controller.set_input_device("02")
    controller.set_monitor_device(None)
    controller.set_microphone_gain(0.35)
    controller.set_sound_gain(0.65)

    assert repository.saved == changes
    assert changes[-1] == AudioRoutingSettings("02", None, 0.35, 0.65)
    assert controller.routing_settings() == changes[-1]


def test_failed_routing_save_does_not_partially_mutate_or_notify() -> None:
    repository = FakeRoutingRepository()
    repository.error = PermissionError("save denied")
    changes: list[AudioRoutingSettings] = []
    controller = make_routing_controller(repository, changes)

    with pytest.raises(PermissionError, match="save denied"):
        controller.set_sound_gain(0.2)

    assert controller.routing_settings() == AudioRoutingSettings()
    assert changes == []


def test_controller_returns_distinct_devices_with_duplicate_descriptions() -> None:
    controller = make_routing_controller(FakeRoutingRepository(), [])

    assert [item.device_id for item in controller.input_devices()] == ["01", "02"]
    assert [item.device_id for item in controller.monitor_devices()] == ["10"]
