from dataclasses import FrozenInstanceError, replace

import pytest

from dj_poltorashka.audio.models import (
    AudioMemberState,
    AudioTarget,
    AudioTargetSnapshot,
    ChannelAudioUpdate,
)
from dj_poltorashka.audio.service import AudioService, UnavailableAudioBackend
from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    SoundButtonConfig,
)


class FakeAudioBackend:
    def __init__(self) -> None:
        self.snapshots: dict[AudioTarget, AudioTargetSnapshot] = {}
        self.read_errors: dict[AudioTarget, OSError] = {}
        self.writes: list[tuple[AudioTarget, float, bool]] = []

    def read_target(self, target: AudioTarget) -> AudioTargetSnapshot:
        if target in self.read_errors:
            raise self.read_errors[target]
        return self.snapshots.get(target, AudioTargetSnapshot(()))

    def write_target(
        self,
        target: AudioTarget,
        volume: float,
        muted: bool,
    ) -> None:
        self.writes.append((target, volume, muted))
        snapshot = self.snapshots.get(target, AudioTargetSnapshot(()))
        self.snapshots[target] = AudioTargetSnapshot(
            tuple(
                replace(member, volume=volume, muted=muted)
                for member in snapshot.members
            )
        )


def make_member(
    member_id: str,
    volume: float,
    muted: bool = False,
    display_name: str = "Устройство",
) -> AudioMemberState:
    return AudioMemberState(member_id, volume, muted, display_name)


def make_panel(*channels: MixerChannelConfig) -> PanelConfiguration:
    padded_channels = (*channels, *(
        MixerChannelConfig("unassigned", 0.0, False)
        for _ in range(4 - len(channels))
    ))
    return PanelConfiguration(
        channels=padded_channels,
        sound_buttons=tuple(SoundButtonConfig() for _ in range(8)),
    )


@pytest.mark.parametrize(
    ("channel", "expected"),
    (
        (
            MixerChannelConfig("master", 0.5, False),
            AudioTarget("master"),
        ),
        (
            MixerChannelConfig("microphone", 0.5, False),
            AudioTarget("microphone"),
        ),
        (
            MixerChannelConfig(
                "application",
                0.5,
                False,
                application_path=r"C:\Apps\PLAYER.exe",
            ),
            AudioTarget("application", r"c:\apps\player.exe"),
        ),
    ),
)
def test_audio_target_is_derived_from_assigned_channel(
    channel: MixerChannelConfig,
    expected: AudioTarget,
) -> None:
    assert AudioTarget.for_channel(channel) == expected


def test_unassigned_channel_has_no_audio_target() -> None:
    channel = MixerChannelConfig("unassigned", 0.0, False)

    assert AudioTarget.for_channel(channel) is None


@pytest.mark.parametrize(
    "volume",
    (-0.01, 1.01, float("nan")),
)
def test_audio_member_rejects_volume_outside_scalar_range(volume: float) -> None:
    with pytest.raises(ValueError, match="Громкость"):
        AudioMemberState("member-1", volume, False, "Устройство")


def test_audio_member_is_immutable() -> None:
    member = AudioMemberState("member-1", 0.5, False, "Устройство")

    with pytest.raises(FrozenInstanceError):
        member.volume = 0.8


def test_channel_audio_update_is_immutable() -> None:
    update = ChannelAudioUpdate(
        channel_index=2,
        volume=0.7,
        muted=True,
        availability="active",
        display_name="Player",
        externally_changed=True,
    )

    with pytest.raises(FrozenInstanceError):
        update.muted = False


def test_channel_audio_update_rejects_unknown_availability() -> None:
    with pytest.raises(ValueError, match="доступности"):
        ChannelAudioUpdate(
            channel_index=0,
            volume=0.5,
            muted=False,
            availability="missing",
            display_name=None,
            externally_changed=False,
        )


def test_apply_configuration_writes_saved_state_to_available_target() -> None:
    target = AudioTarget("master")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("speakers", 0.2),)
    )
    service = AudioService(backend)
    panel = make_panel(MixerChannelConfig("master", 0.8, True))

    service.apply_configuration(panel)
    updates = service.poll()

    assert backend.snapshots[target].members[0].volume == 0.8
    assert backend.snapshots[target].members[0].muted
    assert updates == (
        ChannelAudioUpdate(0, 0.8, True, "active", "Устройство", False),
    )


def test_adopt_channel_uses_actual_state_without_overwriting_it() -> None:
    target = AudioTarget("application", r"C:\Apps\Player.exe")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("session-a", 0.3, True, "Player"),)
    )
    service = AudioService(backend)
    panel = make_panel(
        MixerChannelConfig(
            "application",
            0.8,
            False,
            application_path=r"C:\Apps\Player.exe",
        )
    )

    service.adopt_channel(panel, 0)
    updates = service.poll()

    assert backend.writes == []
    assert updates[0] == ChannelAudioUpdate(
        0,
        0.3,
        True,
        "active",
        "Player",
        True,
    )


def test_adopt_configuration_uses_actual_state_for_all_targets() -> None:
    master = AudioTarget("master")
    microphone = AudioTarget("microphone")
    backend = FakeAudioBackend()
    backend.snapshots[master] = AudioTargetSnapshot(
        (make_member("speakers", 0.26),)
    )
    backend.snapshots[microphone] = AudioTargetSnapshot(
        (make_member("microphone", 0.41, True, "Микрофон"),)
    )
    service = AudioService(backend)
    panel = make_panel(
        MixerChannelConfig("master", 1.0, False),
        MixerChannelConfig("microphone", 1.0, False),
    )

    service.adopt_configuration(panel)
    updates = service.poll()

    assert backend.writes == []
    assert updates == (
        ChannelAudioUpdate(
            0,
            0.26,
            False,
            "active",
            "Устройство",
            True,
        ),
        ChannelAudioUpdate(
            1,
            0.41,
            True,
            "active",
            "Микрофон",
            True,
        ),
    )


def test_adopt_configuration_does_not_normalize_program_sessions() -> None:
    target = AudioTarget("application", r"C:\Apps\Player.exe")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (
            make_member("session-a", 0.2, False, "Player"),
            make_member("session-b", 0.7, False, "Player"),
        )
    )
    service = AudioService(backend)
    panel = make_panel(
        MixerChannelConfig(
            "application",
            1.0,
            False,
            application_path=r"C:\Apps\Player.exe",
        )
    )

    service.adopt_configuration(panel)
    updates = service.poll()

    assert backend.writes == []
    assert tuple(
        member.volume for member in backend.snapshots[target].members
    ) == (0.2, 0.7)
    assert updates[0].volume == 0.7
    assert updates[0].externally_changed


def test_adopt_unavailable_master_waits_for_actual_state() -> None:
    target = AudioTarget("master")
    backend = FakeAudioBackend()
    service = AudioService(backend)
    panel = make_panel(MixerChannelConfig("master", 1.0, False))

    service.adopt_configuration(panel)
    unavailable = service.poll()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("speakers", 0.26, True),)
    )
    active = service.poll()

    assert unavailable[0].availability == "unavailable"
    assert backend.writes == []
    assert active[0] == ChannelAudioUpdate(
        0,
        0.26,
        True,
        "active",
        "Устройство",
        True,
    )


def test_program_waits_then_applies_state_when_session_appears() -> None:
    target = AudioTarget("application", r"C:\Apps\Player.exe")
    backend = FakeAudioBackend()
    service = AudioService(backend)
    panel = make_panel(
        MixerChannelConfig(
            "application",
            0.6,
            True,
            application_path=r"C:\Apps\Player.exe",
            display_name="Player",
        )
    )

    service.apply_configuration(panel)
    waiting = service.poll()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("session-a", 1.0, False, "Player"),)
    )
    active = service.poll()

    assert waiting[0].availability == "waiting"
    assert active[0] == ChannelAudioUpdate(
        0,
        0.6,
        True,
        "active",
        "Player",
        False,
    )
    assert backend.snapshots[target].members[0].volume == 0.6


def test_adopt_waiting_program_applies_saved_state_when_session_appears() -> None:
    target = AudioTarget("application", r"C:\Apps\Player.exe")
    backend = FakeAudioBackend()
    service = AudioService(backend)
    panel = make_panel(
        MixerChannelConfig(
            "application",
            0.6,
            True,
            application_path=r"C:\Apps\Player.exe",
            display_name="Player",
        )
    )

    service.adopt_channel(panel, 0)
    waiting = service.poll()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("session-a", 1.0, False, "Player"),)
    )
    active = service.poll()

    assert waiting[0].availability == "waiting"
    assert not active[0].externally_changed
    assert backend.snapshots[target].members[0].volume == 0.6
    assert backend.snapshots[target].members[0].muted


def test_new_program_member_receives_saved_group_state() -> None:
    target = AudioTarget("application", r"C:\Apps\Player.exe")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("session-a", 0.7, False, "Player"),)
    )
    service = AudioService(backend)
    service.apply_configuration(
        make_panel(
            MixerChannelConfig(
                "application",
                0.7,
                False,
                application_path=r"C:\Apps\Player.exe",
            )
        )
    )
    service.poll()
    backend.writes.clear()
    backend.snapshots[target] = AudioTargetSnapshot(
        (
            make_member("session-a", 0.7, False, "Player"),
            make_member("session-b", 0.1, True, "Player"),
        )
    )

    update = service.poll()[0]

    assert backend.writes == [(target, 0.7, False)]
    assert all(
        member.volume == 0.7 and not member.muted
        for member in backend.snapshots[target].members
    )
    assert not update.externally_changed


def test_external_member_change_updates_and_normalizes_program_group() -> None:
    target = AudioTarget("application", r"C:\Apps\Player.exe")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (
            make_member("session-a", 0.7, False, "Player"),
            make_member("session-b", 0.7, False, "Player"),
        )
    )
    service = AudioService(backend)
    service.apply_configuration(
        make_panel(
            MixerChannelConfig(
                "application",
                0.7,
                False,
                application_path=r"C:\Apps\Player.exe",
            )
        )
    )
    service.poll()
    backend.writes.clear()
    backend.snapshots[target] = AudioTargetSnapshot(
        (
            make_member("session-a", 0.2, True, "Player"),
            make_member("session-b", 0.7, False, "Player"),
        )
    )

    update = service.poll()[0]

    assert update.volume == 0.2
    assert update.muted
    assert update.externally_changed
    assert backend.writes == [(target, 0.2, True)]


def test_simultaneous_changes_use_lexicographically_last_member() -> None:
    target = AudioTarget("application", r"C:\Apps\Player.exe")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (
            make_member("session-a", 0.5, False, "Player"),
            make_member("session-b", 0.5, False, "Player"),
        )
    )
    service = AudioService(backend)
    service.apply_configuration(
        make_panel(
            MixerChannelConfig(
                "application",
                0.5,
                False,
                application_path=r"C:\Apps\Player.exe",
            )
        )
    )
    service.poll()
    backend.writes.clear()
    backend.snapshots[target] = AudioTargetSnapshot(
        (
            make_member("session-a", 0.2, True, "Player"),
            make_member("session-b", 0.9, False, "Player"),
        )
    )

    update = service.poll()[0]

    assert (update.volume, update.muted) == (0.9, False)
    assert backend.writes == [(target, 0.9, False)]


def test_small_volume_rounding_after_write_is_not_external_change() -> None:
    target = AudioTarget("master")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("speakers", 0.2),)
    )
    service = AudioService(backend)
    service.apply_configuration(make_panel(MixerChannelConfig("master", 0.5, False)))
    service.poll()
    backend.writes.clear()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("speakers", 0.504),)
    )

    update = service.poll()[0]

    assert not update.externally_changed
    assert backend.writes == []


def test_default_endpoint_change_applies_saved_state_to_new_device() -> None:
    target = AudioTarget("master")
    backend = FakeAudioBackend()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("speakers", 0.4),)
    )
    service = AudioService(backend)
    service.apply_configuration(make_panel(MixerChannelConfig("master", 0.4, True)))
    service.poll()
    backend.writes.clear()
    backend.snapshots[target] = AudioTargetSnapshot(
        (make_member("headphones", 1.0),)
    )

    update = service.poll()[0]

    assert backend.writes == [(target, 0.4, True)]
    assert update.display_name == "Устройство"
    assert not update.externally_changed


def test_backend_error_does_not_hide_other_channel_update() -> None:
    master = AudioTarget("master")
    microphone = AudioTarget("microphone")
    backend = FakeAudioBackend()
    backend.read_errors[master] = OSError("device failed")
    backend.snapshots[microphone] = AudioTargetSnapshot(
        (make_member("microphone", 0.6, False, "USB Mic"),)
    )
    service = AudioService(backend)
    service.apply_configuration(
        make_panel(
            MixerChannelConfig("master", 0.5, False),
            MixerChannelConfig("microphone", 0.6, False),
        )
    )

    updates = service.poll()

    assert updates[0].availability == "unavailable"
    assert updates[1].availability == "active"
    assert updates[1].display_name == "USB Mic"


def test_unavailable_backend_returns_unavailable_update() -> None:
    service = AudioService(UnavailableAudioBackend("Pycaw недоступен"))
    service.apply_configuration(make_panel(MixerChannelConfig("master", 0.5, False)))

    update = service.poll()[0]

    assert update.availability == "unavailable"
    assert update.display_name is None
