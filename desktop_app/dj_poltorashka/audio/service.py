"""Согласование активной конфигурации с фактическим состоянием аудиоцелей."""

from dataclasses import replace
from typing import Protocol

from dj_poltorashka.audio.models import (
    AudioMemberState,
    AudioTarget,
    AudioTargetSnapshot,
    ChannelAudioUpdate,
)
from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
)


_VOLUME_TOLERANCE = 0.005


class AudioBackend(Protocol):
    """Минимальный интерфейс доступа к операционной аудиосистеме."""

    def read_target(self, target: AudioTarget) -> AudioTargetSnapshot:
        ...

    def write_target(
        self,
        target: AudioTarget,
        volume: float,
        muted: bool,
    ) -> None:
        ...


class UnavailableAudioBackend:
    """Backend для запуска интерфейса без доступного Windows Audio."""

    def __init__(self, message: str):
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Описание недоступности не должно быть пустым")
        self._message = message.strip()

    def read_target(self, target: AudioTarget) -> AudioTargetSnapshot:
        return AudioTargetSnapshot((), self._message)

    def write_target(
        self,
        target: AudioTarget,
        volume: float,
        muted: bool,
    ) -> None:
        return None


class AudioService:
    """Поддерживает единое состояние конфигурации и аудиосистемы."""

    def __init__(self, backend: AudioBackend):
        self._backend = backend
        self._panel: PanelConfiguration | None = None
        self._desired: dict[AudioTarget, tuple[float, bool]] = {}
        self._members: dict[AudioTarget, dict[str, AudioMemberState]] = {}
        self._pending_apply: set[AudioTarget] = set()
        self._pending_adopt: set[AudioTarget] = set()

    def apply_configuration(self, panel: PanelConfiguration) -> None:
        self._set_configuration(panel)

    def adopt_channel(
        self,
        panel: PanelConfiguration,
        channel_index: int,
    ) -> None:
        if isinstance(channel_index, bool) or not isinstance(channel_index, int):
            raise IndexError("Индекс канала должен быть целым числом")
        if not 0 <= channel_index < len(panel.channels):
            raise IndexError("Индекс канала находится вне допустимого диапазона")

        self._set_configuration(panel)
        target = AudioTarget.for_channel(panel.channels[channel_index])
        if target is None:
            raise ValueError("Неназначенный канал нельзя подхватить")
        self._pending_apply.discard(target)
        self._pending_adopt.add(target)

    def poll(self) -> tuple[ChannelAudioUpdate, ...]:
        if self._panel is None:
            return ()

        updates: list[ChannelAudioUpdate] = []
        snapshots: dict[AudioTarget, AudioTargetSnapshot | Exception] = {}
        for channel_index, channel in enumerate(self._panel.channels):
            target = AudioTarget.for_channel(channel)
            if target is None:
                continue

            if target not in snapshots:
                try:
                    snapshots[target] = self._backend.read_target(target)
                except OSError as error:
                    snapshots[target] = error
            snapshot = snapshots[target]
            if isinstance(snapshot, Exception):
                updates.append(
                    self._unavailable_update(channel_index, channel, target)
                )
                continue

            try:
                updates.append(
                    self._reconcile_target(
                        channel_index,
                        channel,
                        target,
                        snapshot,
                    )
                )
            except OSError:
                updates.append(
                    self._unavailable_update(channel_index, channel, target)
                )

        return tuple(updates)

    def _set_configuration(self, panel: PanelConfiguration) -> None:
        targets: set[AudioTarget] = set()
        for channel in panel.channels:
            target = AudioTarget.for_channel(channel)
            if target is None:
                continue
            targets.add(target)
            desired = (channel.volume, channel.muted)
            if self._desired.get(target) != desired:
                self._pending_apply.add(target)
            self._desired[target] = desired

        removed_targets = set(self._desired) - targets
        for target in removed_targets:
            self._desired.pop(target, None)
            self._members.pop(target, None)
            self._pending_apply.discard(target)
            self._pending_adopt.discard(target)
        self._panel = panel

    def _reconcile_target(
        self,
        channel_index: int,
        channel: MixerChannelConfig,
        target: AudioTarget,
        snapshot: AudioTargetSnapshot,
    ) -> ChannelAudioUpdate:
        if snapshot.error is not None:
            return self._unavailable_update(channel_index, channel, target)
        if not snapshot.members:
            self._members[target] = {}
            if target in self._pending_adopt:
                self._pending_adopt.discard(target)
                self._pending_apply.add(target)
            availability = (
                "waiting" if target.target_kind == "application" else "unavailable"
            )
            return ChannelAudioUpdate(
                channel_index,
                channel.volume,
                channel.muted,
                availability,
                channel.display_name,
                False,
                target,
            )

        members = {member.member_id: member for member in snapshot.members}
        previous = self._members.get(target, {})
        display_name = self._display_name(members)

        if target in self._pending_adopt:
            selected = members[sorted(members)[-1]]
            desired = (selected.volume, selected.muted)
            self._desired[target] = desired
            self._pending_adopt.discard(target)
            self._pending_apply.discard(target)
            if any(
                not self._matches(member, *desired)
                for member in members.values()
            ):
                self._backend.write_target(target, *desired)
                members = self._normalized_members(members, *desired)
            self._members[target] = members
            return ChannelAudioUpdate(
                channel_index,
                selected.volume,
                selected.muted,
                "active",
                selected.display_name,
                True,
                target,
            )

        new_member_ids = set(members) - set(previous)
        if target in self._pending_apply or new_member_ids:
            desired = self._desired[target]
            self._backend.write_target(target, *desired)
            self._pending_apply.discard(target)
            members = self._normalized_members(members, *desired)
            self._members[target] = members
            return ChannelAudioUpdate(
                channel_index,
                desired[0],
                desired[1],
                "active",
                display_name,
                False,
                target,
            )

        changed_members = tuple(
            member
            for member_id, member in members.items()
            if member_id in previous
            and not self._same_state(member, previous[member_id])
        )
        if changed_members:
            selected = sorted(changed_members, key=lambda member: member.member_id)[-1]
            desired = (selected.volume, selected.muted)
            self._desired[target] = desired
            self._backend.write_target(target, *desired)
            members = self._normalized_members(members, *desired)
            self._members[target] = members
            return ChannelAudioUpdate(
                channel_index,
                selected.volume,
                selected.muted,
                "active",
                selected.display_name,
                True,
                target,
            )

        desired = self._desired[target]
        self._members[target] = members
        return ChannelAudioUpdate(
            channel_index,
            desired[0],
            desired[1],
            "active",
            display_name,
            False,
            target,
        )

    @staticmethod
    def _display_name(members: dict[str, AudioMemberState]) -> str:
        return members[sorted(members)[0]].display_name

    @staticmethod
    def _matches(
        member: AudioMemberState,
        volume: float,
        muted: bool,
    ) -> bool:
        return abs(member.volume - volume) <= _VOLUME_TOLERANCE and (
            member.muted == muted
        )

    @staticmethod
    def _same_state(first: AudioMemberState, second: AudioMemberState) -> bool:
        return AudioService._matches(first, second.volume, second.muted)

    @staticmethod
    def _normalized_members(
        members: dict[str, AudioMemberState],
        volume: float,
        muted: bool,
    ) -> dict[str, AudioMemberState]:
        return {
            member_id: replace(member, volume=volume, muted=muted)
            for member_id, member in members.items()
        }

    @staticmethod
    def _unavailable_update(
        channel_index: int,
        channel: MixerChannelConfig,
        target: AudioTarget,
    ) -> ChannelAudioUpdate:
        return ChannelAudioUpdate(
            channel_index,
            channel.volume,
            channel.muted,
            "unavailable",
            channel.display_name,
            False,
            target,
        )
