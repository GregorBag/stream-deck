"""Программная модель платы: протокол, органы управления и подсветка."""

from dataclasses import dataclass

from dj_poltorashka.panel.protocol import (
    CONNECTION_TIMEOUT_MS, Hello, LedUpdate, PanelState, Ping,
    Pong, StreamDecoder, encode_message,
)


@dataclass(frozen=True)
class EmulatorResult:
    data: bytes = b""
    errors: tuple[str, ...] = ()


class PanelEmulator:
    def __init__(self, state: PanelState | None = None):
        self._state = state or PanelState((0, 0, 0, 0), 0)
        self._decoder = StreamDecoder()
        self._connected = False
        self._now_ms = 0
        self._last_ping_ms = 0
        self._disconnected_at_ms = 0
        self._lighting: LedUpdate | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> PanelState:
        return self._state

    def tick(self, now_ms: int) -> None:
        if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms < self._now_ms:
            raise ValueError("Требуется монотонное неотрицательное время в миллисекундах")
        self._now_ms = now_ms
        if self._connected and now_ms - self._last_ping_ms >= CONNECTION_TIMEOUT_MS:
            self._connected = False
            self._disconnected_at_ms = self._last_ping_ms + CONNECTION_TIMEOUT_MS

    def reset_connection(self, now_ms: int) -> None:
        self.tick(now_ms)
        self._decoder.reset()
        self._connected = False
        self._disconnected_at_ms = now_ms

    def restart(self, now_ms: int) -> bytes:
        self.reset_connection(now_ms)
        self._lighting = None
        return encode_message(Hello())

    def receive(self, data: bytes, now_ms: int) -> EmulatorResult:
        self.tick(now_ms)
        decoded = self._decoder.feed(data)
        replies = []
        errors = list(decoded.errors)
        for message in decoded.messages:
            if isinstance(message, Hello):
                self._connected = True
                self._last_ping_ms = now_ms
                replies.extend((encode_message(Hello()), encode_message(self._state)))
            elif not self._connected:
                errors.append("Требуется HELLO приложения")
            elif isinstance(message, Ping):
                self._last_ping_ms = now_ms
                replies.append(encode_message(Pong(message.sequence)))
            elif isinstance(message, LedUpdate):
                self._lighting = message
            else:
                errors.append("Сообщение недопустимо в направлении приложение → плата")
        return EmulatorResult(b"".join(replies), tuple(errors))

    def set_state(self, state: PanelState, now_ms: int) -> bytes:
        if not isinstance(state, PanelState):
            raise ValueError("Ожидался PanelState")
        self.tick(now_ms)
        changed = state != self._state
        self._state = state
        return encode_message(state) if self._connected and changed else b""

    def lighting(self, now_ms: int) -> LedUpdate:
        self.tick(now_ms)
        current = self._lighting or LedUpdate(50, ((0, 0, 0),) * 24)
        if self._connected:
            return current
        white_on = (now_ms - self._disconnected_at_ms) % 1000 < 500
        value = round(255 * current.brightness_percent / 100) if white_on else 0
        return LedUpdate(current.brightness_percent, ((value, value, value),) * 8 + current.colors[8:])
