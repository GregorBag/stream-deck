"""Текстовый протокол панели; не зависит от COM-порта, Qt и часов."""

from dataclasses import dataclass
import re


BAUD_RATE = 115200
PROTOCOL_VERSION = 1
DEVICE_NAME = "DJ_POLTORASHKA"
HEARTBEAT_INTERVAL_MS = 500
CONNECTION_TIMEOUT_MS = 2000
MAX_LINE_BYTES = 192


def _require_int(value: int, minimum: int, maximum: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name}: требуется целое число от {minimum} до {maximum}")


@dataclass(frozen=True)
class Hello:
    device_name: str = DEVICE_NAME
    version: int = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.device_name != DEVICE_NAME:
            raise ValueError("Неизвестное устройство")
        _require_int(self.version, PROTOCOL_VERSION, PROTOCOL_VERSION, "version")


@dataclass(frozen=True)
class Ping:
    sequence: int

    def __post_init__(self) -> None:
        _require_int(self.sequence, 0, 65535, "sequence")


@dataclass(frozen=True)
class Pong:
    sequence: int

    def __post_init__(self) -> None:
        _require_int(self.sequence, 0, 65535, "sequence")


@dataclass(frozen=True)
class PanelState:
    sliders: tuple[int, int, int, int]
    buttons: int

    def __post_init__(self) -> None:
        sliders = tuple(self.sliders)
        if len(sliders) != 4:
            raise ValueError("STATE должен содержать четыре ползунка")
        for value in sliders:
            _require_int(value, 0, 1023, "slider")
        _require_int(self.buttons, 0, 65535, "buttons")
        object.__setattr__(self, "sliders", sliders)


@dataclass(frozen=True)
class LedUpdate:
    """Логический порядок: LED1–LED8, затем подсветка SW1–SW16."""

    brightness_percent: int
    colors: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        _require_int(self.brightness_percent, 0, 50, "brightness")
        colors = tuple(tuple(color) for color in self.colors)
        if len(colors) != 24:
            raise ValueError("LEDS должен содержать 24 цвета")
        maximum = round(255 * self.brightness_percent / 100)
        for color in colors:
            if len(color) != 3:
                raise ValueError("Цвет должен содержать три компонента RGB")
            for value in color:
                _require_int(value, 0, maximum, "RGB")
        object.__setattr__(self, "colors", colors)


Message = Hello | Ping | Pong | PanelState | LedUpdate


def encode_message(message: Message) -> bytes:
    if isinstance(message, Hello):
        line = f"HELLO {message.device_name} {message.version}"
    elif isinstance(message, Ping):
        line = f"PING {message.sequence}"
    elif isinstance(message, Pong):
        line = f"PONG {message.sequence}"
    elif isinstance(message, PanelState):
        sliders = " ".join(str(value) for value in message.sliders)
        line = f"STATE {sliders} {message.buttons:04X}"
    elif isinstance(message, LedUpdate):
        colors = "".join(f"{red:02X}{green:02X}{blue:02X}" for red, green, blue in message.colors)
        line = f"LEDS {message.brightness_percent} {colors}"
    else:
        raise TypeError("Неизвестный тип сообщения протокола")
    return f"{line}\n".encode("ascii")


def _decimal(text: str) -> int:
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError("Ожидалось десятичное неотрицательное число")
    return int(text)


def decode_line(line: bytes) -> Message:
    """Разобрать одну строку без завершающего LF или CRLF."""
    if len(line) > MAX_LINE_BYTES:
        raise ValueError("Превышена максимальная длина сообщения")
    try:
        text = line.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("Сообщение должно содержать только ASCII") from error
    parts = text.split(" ")
    match parts:
        case ["HELLO", name, version]:
            return Hello(name, _decimal(version))
        case ["PING", sequence]:
            return Ping(_decimal(sequence))
        case ["PONG", sequence]:
            return Pong(_decimal(sequence))
        case ["STATE", first, second, third, fourth, buttons]:
            if not re.fullmatch(r"[0-9A-Fa-f]{4}", buttons):
                raise ValueError("Маска кнопок должна содержать четыре hex-цифры")
            return PanelState(tuple(_decimal(value) for value in (first, second, third, fourth)), int(buttons, 16))
        case ["LEDS", brightness, colors]:
            if not re.fullmatch(r"[0-9A-Fa-f]{144}", colors):
                raise ValueError("Ожидались 24 RGB-цвета без разделителей")
            values = tuple(int(colors[index:index + 2], 16) for index in range(0, 144, 2))
            return LedUpdate(_decimal(brightness), tuple(values[index:index + 3] for index in range(0, 72, 3)))
        case _:
            raise ValueError("Неизвестный формат сообщения")


@dataclass(frozen=True)
class DecodeResult:
    messages: tuple[Message, ...]
    errors: tuple[str, ...]


class StreamDecoder:
    """Накапливает фрагменты строк; повреждённую строку пропускает целиком."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._discarding = False

    def reset(self) -> None:
        self._buffer.clear()
        self._discarding = False

    def feed(self, data: bytes) -> DecodeResult:
        messages = []
        errors = []
        for value in data:
            if value == 10:
                if self._discarding:
                    self._discarding = False
                else:
                    line = bytes(self._buffer)
                    if line.endswith(b"\r"):
                        line = line[:-1]
                    try:
                        messages.append(decode_line(line))
                    except ValueError as error:
                        errors.append(str(error))
                self._buffer.clear()
            elif not self._discarding:
                self._buffer.append(value)
                if len(self._buffer) > MAX_LINE_BYTES:
                    self._buffer.clear()
                    self._discarding = True
                    errors.append("Превышена максимальная длина сообщения")
        return DecodeResult(tuple(messages), tuple(errors))


class LightingUpdateTracker:
    """Подавляет дубли только после успешной записи в транспорт."""

    def __init__(self) -> None:
        self._sent: LedUpdate | None = None

    def prepare(self, update: LedUpdate) -> bytes | None:
        if update == self._sent:
            return None
        return encode_message(update)

    def confirm_sent(self, update: LedUpdate) -> None:
        self._sent = update

    def reset(self) -> None:
        # Новому подключению нужен полный кадр даже при тех же цветах.
        self._sent = None
