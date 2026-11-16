"""Подключение к выбранному порту, повторные попытки и сеанс протокола."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Literal

from dj_poltorashka.panel.protocol import LedUpdate
from dj_poltorashka.panel.session import PanelSession, SessionResult
from dj_poltorashka.panel.transport import EmulatedPanelTransport, PanelTransport, create_transport


RECONNECT_INTERVAL_MS = 1000
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PanelConnectionStatus:
    code: Literal["disconnected", "connecting", "connected", "reconnecting"] = "disconnected"
    port_name: str | None = None
    message: str = "Панель не подключена"


@dataclass(frozen=True)
class ConnectionUpdate:
    status: PanelConnectionStatus
    result: SessionResult = SessionResult()


class PanelConnection:
    def __init__(self, factory: Callable[[str], PanelTransport] = create_transport):
        self._factory = factory
        self._transport: PanelTransport | None = None
        self._session = PanelSession(self._write)
        self._port_name: str | None = None
        self._status = PanelConnectionStatus()
        self._ready_at_ms = 0
        self._next_attempt_ms = 0
        self._session_started = False

    def _write(self, data: bytes) -> int:
        if self._transport is None:
            raise OSError("Порт панели закрыт")
        return self._transport.write(data)

    def _close_transport(self) -> None:
        self._session.close()
        self._session_started = False
        if self._transport is not None:
            try:
                self._transport.close()
            except OSError as error:
                _LOGGER.warning("Ошибка закрытия порта панели: %s", error)
            finally:
                self._transport = None

    def _failed(self, now_ms: int, message: str) -> ConnectionUpdate:
        self._close_transport()
        self._next_attempt_ms = now_ms + RECONNECT_INTERVAL_MS
        self._status = PanelConnectionStatus("reconnecting", self._port_name, f"{message}. Повторное подключение…")
        return ConnectionUpdate(self._status, SessionResult(errors=(message,)))

    def select_port(self, port_name: str | None, now_ms: int) -> ConnectionUpdate:
        if port_name is not None and (not isinstance(port_name, str) or not port_name.strip()):
            raise ValueError("Требуется имя порта или None")
        self._close_transport()
        self._port_name = port_name
        self._status = PanelConnectionStatus()
        self._next_attempt_ms = now_ms
        return self.poll(now_ms)

    def set_lighting(self, update: LedUpdate, now_ms: int) -> ConnectionUpdate:
        result = self._session.set_lighting(update, now_ms)
        if self._session_started and self._session.status == "closed":
            return self._failed(now_ms, result.errors[-1] if result.errors else "Связь потеряна")
        return ConnectionUpdate(self._status, result)

    def press_emulated_button(self, index: int, now_ms: int) -> ConnectionUpdate:
        if isinstance(self._transport, EmulatedPanelTransport) and self._session.status == "connected":
            try:
                self._transport.press_button(index)
            except OSError as error:
                return self._failed(now_ms, str(error) or type(error).__name__)
        return ConnectionUpdate(self._status)

    def poll(self, now_ms: int) -> ConnectionUpdate:
        if self._port_name is None:
            return ConnectionUpdate(self._status)
        if self._transport is None:
            if now_ms < self._next_attempt_ms:
                return ConnectionUpdate(self._status)
            try:
                self._transport = self._factory(self._port_name)
            except OSError as error:
                return self._failed(now_ms, str(error) or type(error).__name__)
            self._ready_at_ms = now_ms + self._transport.settle_ms
            self._status = PanelConnectionStatus("connecting", self._port_name, "Подключение к панели…")
        try:
            data = self._transport.read()
            if not self._session_started:
                if now_ms < self._ready_at_ms:
                    return ConnectionUpdate(self._status)
                self._session_started = True
                result = self._session.start(now_ms)
            elif data:
                result = self._session.receive(data, now_ms)
            else:
                result = SessionResult()
            if self._session.status == "closed":
                return self._failed(now_ms, result.errors[-1] if result.errors else "Связь потеряна")
            tick = self._session.tick(now_ms)
            if self._session.status == "closed":
                return self._failed(now_ms, tick.errors[-1] if tick.errors else "Связь потеряна")
        except OSError as error:
            return self._failed(now_ms, str(error) or type(error).__name__)
        if self._session.status == "connected":
            self._status = PanelConnectionStatus("connected", self._port_name, "Панель подключена")
        return ConnectionUpdate(self._status, SessionResult(result.states, result.events, result.errors + tick.errors))

    def close(self) -> None:
        self._port_name = None
        self._close_transport()
        self._status = PanelConnectionStatus()
