"""Сеанс связи приложения с панелью, без Qt и конкретного транспорта."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from dj_poltorashka.panel.events import MutePressed, PanelEvent, PresetPressed, SoundPressed
from dj_poltorashka.panel.protocol import (
    CONNECTION_TIMEOUT_MS, HEARTBEAT_INTERVAL_MS, Hello, LedUpdate,
    LightingUpdateTracker, PanelState, Ping, Pong, StreamDecoder, encode_message,
)


@dataclass(frozen=True)
class SessionResult:
    states: tuple[PanelState, ...] = ()
    events: tuple[PanelEvent, ...] = ()
    errors: tuple[str, ...] = ()


class PanelSession:
    """Принимает монотонное время в мс; write должен записать всю строку."""

    def __init__(self, write: Callable[[bytes], int]):
        self._write = write
        self._decoder = StreamDecoder()
        self._lighting_tracker = LightingUpdateTracker()
        self._lighting: LedUpdate | None = None
        self._status: Literal["closed", "handshaking", "connected"] = "closed"
        self._previous_state: PanelState | None = None
        self._pending_pings: dict[int, int] = {}
        self._next_sequence = 0
        self._now_ms = 0
        self._last_confirmed_ms = 0
        self._last_ping_ms = 0
        self._latest_confirmed_ping_ms = -1

    @property
    def status(self) -> Literal["closed", "handshaking", "connected"]:
        return self._status

    def _check_time(self, now_ms: int) -> None:
        if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms < self._now_ms:
            raise ValueError("Требуется монотонное неотрицательное время в миллисекундах")
        self._now_ms = now_ms

    def close(self) -> None:
        self._status = "closed"
        self._decoder.reset()
        self._previous_state = None
        self._pending_pings.clear()
        self._lighting_tracker.reset()

    def _send(self, data: bytes) -> str | None:
        try:
            written = self._write(data)
            if written != len(data):
                raise OSError("Транспорт записал неполное сообщение")
        except OSError as error:
            self.close()
            return str(error) or type(error).__name__
        return None

    def start(self, now_ms: int) -> SessionResult:
        self._check_time(now_ms)
        self.close()
        self._status = "handshaking"
        self._last_confirmed_ms = now_ms
        self._latest_confirmed_ping_ms = -1
        error = self._send(encode_message(Hello()))
        return SessionResult(errors=(error,) if error else ())

    def _expire(self) -> str | None:
        if self._status != "closed" and self._now_ms - self._last_confirmed_ms >= CONNECTION_TIMEOUT_MS:
            self.close()
            return "Потеряна связь с панелью"
        return None

    def _send_ping(self) -> str | None:
        sequence = self._next_sequence
        self._next_sequence = (sequence + 1) % 65536
        error = self._send(encode_message(Ping(sequence)))
        if error is None:
            self._pending_pings[sequence] = self._now_ms
            self._last_ping_ms = self._now_ms
        return error

    def _send_lighting(self) -> str | None:
        if self._status != "connected" or self._lighting is None:
            return None
        data = self._lighting_tracker.prepare(self._lighting)
        if data is None:
            return None
        error = self._send(data)
        if error is None:
            self._lighting_tracker.confirm_sent(self._lighting)
        return error

    def set_lighting(self, update: LedUpdate, now_ms: int) -> SessionResult:
        if not isinstance(update, LedUpdate):
            raise ValueError("Ожидался LedUpdate")
        self._check_time(now_ms)
        self._lighting = update
        error = self._expire() or self._send_lighting()
        return SessionResult(errors=(error,) if error else ())

    def tick(self, now_ms: int) -> SessionResult:
        self._check_time(now_ms)
        error = self._expire()
        if error is None and self._status == "connected" and now_ms - self._last_ping_ms >= HEARTBEAT_INTERVAL_MS:
            error = self._send_ping()
        return SessionResult(errors=(error,) if error else ())

    def receive(self, data: bytes, now_ms: int) -> SessionResult:
        self._check_time(now_ms)
        error = self._expire()
        if error:
            return SessionResult(errors=(error,))
        if self._status == "closed":
            return SessionResult()
        decoded = self._decoder.feed(data)
        errors = list(decoded.errors)
        states = []
        events = []
        for message in decoded.messages:
            if isinstance(message, Hello):
                if self._status == "connected":
                    # Новое HELLO означает перезапуск платы: запросить полный обмен заново.
                    result = self.start(now_ms)
                    errors.extend(result.errors)
                    break
                self._status = "connected"
                self._last_confirmed_ms = now_ms
                self._lighting_tracker.reset()
                error = self._send_ping() or self._send_lighting()
                if error:
                    errors.append(error)
                    break
            elif self._status != "connected":
                errors.append("Сообщение получено до HELLO")
            elif isinstance(message, Pong):
                sent_at = self._pending_pings.pop(message.sequence, None)
                if sent_at is None or sent_at <= self._latest_confirmed_ping_ms:
                    errors.append("Получен неожиданный или устаревший PONG")
                else:
                    self._latest_confirmed_ping_ms = sent_at
                    self._last_confirmed_ms = now_ms
                    self._pending_pings = {
                        sequence: timestamp for sequence, timestamp in self._pending_pings.items()
                        if timestamp > sent_at
                    }
            elif isinstance(message, PanelState):
                states.append(message)
                if self._previous_state is not None:
                    pressed = message.buttons & ~self._previous_state.buttons
                    for index in range(16):
                        if pressed & (1 << index):
                            if index < 8:
                                events.append(SoundPressed(index))
                            elif index < 12:
                                events.append(MutePressed(index - 8))
                            else:
                                events.append(PresetPressed(index - 12))
                self._previous_state = message
            else:
                errors.append("Сообщение недопустимо в направлении плата → приложение")
        return SessionResult(tuple(states), tuple(events), tuple(errors))
