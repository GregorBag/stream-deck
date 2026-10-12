import pytest

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
