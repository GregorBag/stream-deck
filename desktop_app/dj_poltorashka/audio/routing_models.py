"""Неизменяемые типы виртуального микрофона."""

from dataclasses import dataclass
from typing import Literal


AudioRoutingStatusCode = Literal[
    "active",
    "cable_missing",
    "microphone_missing",
    "monitor_missing",
    "pipeline_error",
]

_STATUS_CODES = {
    "active",
    "cable_missing",
    "microphone_missing",
    "monitor_missing",
    "pipeline_error",
}


@dataclass(frozen=True)
class AudioDeviceDescriptor:
    device_id: str
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("Идентификатор аудиоустройства не должен быть пустым")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Название аудиоустройства не должно быть пустым")
        object.__setattr__(self, "description", self.description.strip())


@dataclass(frozen=True)
class AudioRoutingStatus:
    code: AudioRoutingStatusCode
    message: str

    def __post_init__(self) -> None:
        if self.code not in _STATUS_CODES:
            raise ValueError("Неизвестное состояние аудиомаршрутизации")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Сообщение состояния не должно быть пустым")
        object.__setattr__(self, "message", self.message.strip())
