import pytest

from dj_poltorashka.audio.models import (
    AudioMemberState,
    AudioTarget,
    AudioTargetSnapshot,
)
from dj_poltorashka.audio.windows_backend import WindowsAudioBackend


class RecoverableAudioError(Exception):
    pass


class FakeEndpointVolume:
    def __init__(self, volume: float, muted: bool):
        self.volume = volume
        self.muted = muted

    def GetMasterVolumeLevelScalar(self) -> float:
        return self.volume

    def GetMute(self) -> bool:
        return self.muted

    def SetMasterVolumeLevelScalar(self, volume: float, context) -> None:
        self.volume = volume

    def SetMute(self, muted: bool, context) -> None:
        self.muted = muted


class FakeDevice:
    def __init__(
        self,
        device_id: str,
        name: str,
        volume: float,
        muted: bool,
    ):
        self.id = device_id
        self.FriendlyName = name
        self.EndpointVolume = FakeEndpointVolume(volume, muted)


class FakeSimpleAudioVolume:
    def __init__(self, volume: float, muted: bool):
        self.volume = volume
        self.muted = muted

    def GetMasterVolume(self) -> float:
        return self.volume

    def GetMute(self) -> bool:
        return self.muted

    def SetMasterVolume(self, volume: float, context) -> None:
        self.volume = volume

    def SetMute(self, muted: bool, context) -> None:
        self.muted = muted


class FakeProcess:
    def __init__(
        self,
        executable_path: str | None = None,
        error: Exception | None = None,
    ):
        self.executable_path = executable_path
        self.error = error

    def exe(self) -> str:
        if self.error is not None:
            raise self.error
        assert self.executable_path is not None
        return self.executable_path


class FakeSession:
    def __init__(
        self,
        instance_id: str,
        process: FakeProcess | None,
        volume: float,
        muted: bool,
        error: Exception | None = None,
    ):
        self.InstanceIdentifier = instance_id
        self.Process = process
        self._simple_audio_volume = FakeSimpleAudioVolume(volume, muted)
        self.error = error

    @property
    def SimpleAudioVolume(self) -> FakeSimpleAudioVolume:
        if self.error is not None:
            raise self.error
        return self._simple_audio_volume


class FakeAudioUtilities:
    def __init__(self) -> None:
        self.speakers: FakeDevice | None = None
        self.raw_microphone = object()
        self.microphone: FakeDevice | None = None
        self.sessions: list[FakeSession] = []
        self.created_devices: list[object] = []

    def GetSpeakers(self) -> FakeDevice | None:
        return self.speakers

    def GetMicrophone(self):
        return self.raw_microphone

    def CreateDevice(self, raw_device) -> FakeDevice | None:
        self.created_devices.append(raw_device)
        return self.microphone

    def GetAllSessions(self) -> list[FakeSession]:
        return self.sessions


def make_backend(utilities: FakeAudioUtilities) -> WindowsAudioBackend:
    return WindowsAudioBackend(
        audio_utilities=utilities,
        recoverable_errors=(RecoverableAudioError,),
    )


@pytest.mark.parametrize(
    ("target", "device_attribute", "expected_id", "expected_name"),
    (
        (AudioTarget("master"), "speakers", "render-1", "Speakers"),
        (AudioTarget("microphone"), "microphone", "capture-1", "USB Mic"),
    ),
)
def test_read_endpoint_returns_default_device_state(
    target: AudioTarget,
    device_attribute: str,
    expected_id: str,
    expected_name: str,
) -> None:
    utilities = FakeAudioUtilities()
    setattr(
        utilities,
        device_attribute,
        FakeDevice(expected_id, expected_name, 0.65, True),
    )
    backend = make_backend(utilities)

    snapshot = backend.read_target(target)

    assert snapshot == AudioTargetSnapshot(
        (AudioMemberState(expected_id, 0.65, True, expected_name),)
    )
    if target.target_kind == "microphone":
        assert utilities.created_devices == [utilities.raw_microphone]


@pytest.mark.parametrize(
    ("target", "device_attribute"),
    (
        (AudioTarget("master"), "speakers"),
        (AudioTarget("microphone"), "microphone"),
    ),
)
def test_write_endpoint_sets_scalar_volume_and_mute(
    target: AudioTarget,
    device_attribute: str,
) -> None:
    utilities = FakeAudioUtilities()
    device = FakeDevice("device-1", "Device", 0.2, False)
    setattr(utilities, device_attribute, device)
    backend = make_backend(utilities)

    backend.write_target(target, 0.8, True)

    assert device.EndpointVolume.volume == 0.8
    assert device.EndpointVolume.muted


def test_read_application_groups_all_matching_executable_sessions() -> None:
    utilities = FakeAudioUtilities()
    utilities.sessions = [
        FakeSession(
            "session-b",
            FakeProcess(r"c:\apps\PLAYER.exe"),
            0.7,
            True,
        ),
        FakeSession(
            "session-a",
            FakeProcess(r"C:\Apps\Player.exe"),
            0.4,
            False,
        ),
        FakeSession(
            "other",
            FakeProcess(r"C:\Apps\Browser.exe"),
            1.0,
            False,
        ),
    ]
    backend = make_backend(utilities)

    snapshot = backend.read_target(
        AudioTarget("application", r"C:\Apps\Player.exe")
    )

    assert snapshot.members == (
        AudioMemberState("session-a", 0.4, False, "player"),
        AudioMemberState("session-b", 0.7, True, "player"),
    )


def test_write_application_updates_every_matching_session() -> None:
    utilities = FakeAudioUtilities()
    matching = (
        FakeSession("session-a", FakeProcess(r"C:\Apps\Player.exe"), 0.2, False),
        FakeSession("session-b", FakeProcess(r"C:\Apps\Player.exe"), 0.3, False),
    )
    other = FakeSession(
        "other",
        FakeProcess(r"C:\Apps\Browser.exe"),
        0.4,
        False,
    )
    utilities.sessions = [*matching, other]
    backend = make_backend(utilities)

    backend.write_target(
        AudioTarget("application", r"C:\Apps\Player.exe"),
        0.9,
        True,
    )

    assert all(
        session._simple_audio_volume.volume == 0.9
        and session._simple_audio_volume.muted
        for session in matching
    )
    assert other._simple_audio_volume.volume == 0.4
    assert not other._simple_audio_volume.muted


@pytest.mark.parametrize(
    "broken_session",
    (
        FakeSession("system", None, 0.5, False),
        FakeSession(
            "vanished",
            FakeProcess(error=RecoverableAudioError("NoSuchProcess")),
            0.5,
            False,
        ),
        FakeSession(
            "denied",
            FakeProcess(error=RecoverableAudioError("AccessDenied")),
            0.5,
            False,
        ),
        FakeSession(
            "disconnected",
            FakeProcess(r"C:\Apps\Player.exe"),
            0.5,
            False,
            error=RecoverableAudioError("COMError"),
        ),
    ),
)
def test_broken_session_is_skipped_without_hiding_valid_session(
    broken_session: FakeSession,
) -> None:
    utilities = FakeAudioUtilities()
    valid = FakeSession(
        "valid",
        FakeProcess(r"C:\Apps\Player.exe"),
        0.6,
        False,
    )
    utilities.sessions = [broken_session, valid]
    backend = make_backend(utilities)

    snapshot = backend.read_target(
        AudioTarget("application", r"C:\Apps\Player.exe")
    )

    assert snapshot.members == (
        AudioMemberState("valid", 0.6, False, "player"),
    )


def test_missing_default_endpoint_returns_empty_snapshot() -> None:
    utilities = FakeAudioUtilities()
    utilities.speakers = None
    backend = make_backend(utilities)

    assert backend.read_target(AudioTarget("master")) == AudioTargetSnapshot(())
