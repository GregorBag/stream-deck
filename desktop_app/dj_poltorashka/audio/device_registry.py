"""Обнаружение и разрешение устройств Qt Multimedia."""

from collections.abc import Callable

from PySide6.QtMultimedia import QMediaDevices

from dj_poltorashka.audio.routing_models import AudioDeviceDescriptor


def audio_device_id(device: object) -> str:
    """Возвращает устойчивый идентификатор Qt-устройства в hex-виде."""

    return bytes(device.id()).hex()  # type: ignore[attr-defined]


class QtAudioDeviceRegistry:
    """Предоставляет актуальный снимок входных и выходных устройств."""

    def __init__(self, media_devices: object | None = None):
        self._media_devices = media_devices or QMediaDevices()
        self._callbacks: list[Callable[[], None]] = []
        self._closed = False
        self._change_handler = self._handle_devices_changed
        self._media_devices.audioInputsChanged.connect(self._change_handler)
        self._media_devices.audioOutputsChanged.connect(self._change_handler)

    def inputs(self) -> tuple[AudioDeviceDescriptor, ...]:
        return self._descriptors(self._media_devices.audioInputs())

    def outputs(self) -> tuple[AudioDeviceDescriptor, ...]:
        return self._descriptors(self._media_devices.audioOutputs())

    def resolve_input(self, device_id: str | None):
        if device_id is None:
            return self._media_devices.defaultAudioInput()
        return self._find(self._media_devices.audioInputs(), device_id)

    def resolve_monitor(self, device_id: str | None):
        if device_id is None:
            return self._media_devices.defaultAudioOutput()
        return self._find(self._media_devices.audioOutputs(), device_id)

    def resolve_cable_input(self):
        for device in self._media_devices.audioOutputs():
            description = " ".join(device.description().split()).casefold()
            if description.startswith("cable input") and (
                "vb-audio virtual cable" in description
            ):
                return device
        return None

    def on_devices_changed(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            raise ValueError("Обработчик изменения устройств должен быть вызываемым")
        if self._closed:
            return
        self._callbacks.append(callback)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._media_devices.audioInputsChanged.disconnect(self._change_handler)
        self._media_devices.audioOutputsChanged.disconnect(self._change_handler)
        self._callbacks.clear()

    def _handle_devices_changed(self) -> None:
        if self._closed:
            return
        for callback in tuple(self._callbacks):
            callback()

    @staticmethod
    def _descriptors(devices: object) -> tuple[AudioDeviceDescriptor, ...]:
        descriptors = tuple(
            AudioDeviceDescriptor(audio_device_id(device), device.description())
            for device in devices  # type: ignore[union-attr]
        )
        return tuple(
            sorted(
                descriptors,
                key=lambda item: (item.description.casefold(), item.device_id),
            )
        )

    @staticmethod
    def _find(devices: object, device_id: str):
        for device in devices:  # type: ignore[union-attr]
            if audio_device_id(device) == device_id:
                return device
        return None
