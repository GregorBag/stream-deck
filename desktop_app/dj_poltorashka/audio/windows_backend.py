"""Адаптер Windows Core Audio на основе Pycaw."""

from pathlib import PureWindowsPath

from dj_poltorashka.audio.models import (
    AudioMemberState,
    AudioTarget,
    AudioTargetSnapshot,
)
from dj_poltorashka.configuration.models import normalize_executable_path


class WindowsAudioBackend:
    """Читает и изменяет endpoint и программные аудиосессии Windows."""

    def __init__(
        self,
        audio_utilities=None,
        recoverable_errors: tuple[type[BaseException], ...] | None = None,
    ):
        if audio_utilities is None:
            audio_utilities, default_errors = _load_pycaw()
            if recoverable_errors is None:
                recoverable_errors = default_errors
        self._audio_utilities = audio_utilities
        self._recoverable_errors = recoverable_errors or (OSError,)

    def read_target(self, target: AudioTarget) -> AudioTargetSnapshot:
        try:
            if target.target_kind == "application":
                return self._read_application(target)
            device = self._get_endpoint(target)
            if device is None:
                return AudioTargetSnapshot(())
            volume = device.EndpointVolume
            name = device.FriendlyName or self._endpoint_fallback_name(target)
            return AudioTargetSnapshot(
                (
                    AudioMemberState(
                        str(device.id),
                        float(volume.GetMasterVolumeLevelScalar()),
                        bool(volume.GetMute()),
                        name,
                    ),
                )
            )
        except self._recoverable_errors as error:
            raise OSError("Не удалось прочитать состояние аудиоцели") from error

    def write_target(
        self,
        target: AudioTarget,
        volume: float,
        muted: bool,
    ) -> None:
        try:
            if target.target_kind == "application":
                self._write_application(target, volume, muted)
                return
            device = self._get_endpoint(target)
            if device is None:
                return
            endpoint_volume = device.EndpointVolume
            endpoint_volume.SetMasterVolumeLevelScalar(volume, None)
            endpoint_volume.SetMute(muted, None)
        except self._recoverable_errors as error:
            raise OSError("Не удалось изменить состояние аудиоцели") from error

    def _get_endpoint(self, target: AudioTarget):
        if target.target_kind == "master":
            return self._audio_utilities.GetSpeakers()
        raw_microphone = self._audio_utilities.GetMicrophone()
        if raw_microphone is None:
            return None
        return self._audio_utilities.CreateDevice(raw_microphone)

    def _read_application(self, target: AudioTarget) -> AudioTargetSnapshot:
        members: list[AudioMemberState] = []
        for session in self._matching_sessions(target):
            try:
                session_volume = session.SimpleAudioVolume
                members.append(
                    AudioMemberState(
                        str(session.InstanceIdentifier),
                        float(session_volume.GetMasterVolume()),
                        bool(session_volume.GetMute()),
                        PureWindowsPath(target.application_path or "").stem,
                    )
                )
            except self._recoverable_errors:
                continue
        members.sort(key=lambda member: member.member_id)
        return AudioTargetSnapshot(tuple(members))

    def _write_application(
        self,
        target: AudioTarget,
        volume: float,
        muted: bool,
    ) -> None:
        for session in self._matching_sessions(target):
            try:
                session_volume = session.SimpleAudioVolume
                session_volume.SetMasterVolume(volume, None)
                session_volume.SetMute(muted, None)
            except self._recoverable_errors:
                continue

    def _matching_sessions(self, target: AudioTarget) -> tuple[object, ...]:
        matching_sessions: list[object] = []
        try:
            sessions = self._audio_utilities.GetAllSessions()
        except self._recoverable_errors as error:
            raise OSError("Не удалось получить аудиосессии Windows") from error

        for session in sessions:
            try:
                process = session.Process
                if process is None:
                    continue
                process_path = normalize_executable_path(process.exe())
                if process_path == target.application_path:
                    matching_sessions.append(session)
            except self._recoverable_errors:
                continue
        return tuple(matching_sessions)

    @staticmethod
    def _endpoint_fallback_name(target: AudioTarget) -> str:
        if target.target_kind == "master":
            return "Общая громкость"
        return "Микрофон"


def _load_pycaw():
    from _ctypes import COMError

    import psutil
    from pycaw.pycaw import AudioUtilities

    recoverable_errors = (
        OSError,
        COMError,
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess,
    )
    return AudioUtilities, recoverable_errors
