"""Управление общей громкостью Windows и воспроизведением MP3.

Запуск:
    py -m pip install pyserial pycaw
    py src/volume.py
    py src/volume.py --port COM3
"""

import argparse
import ctypes
import sys
import time
from collections import deque
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Не найден pyserial. Установите: py -m pip install pyserial", file=sys.stderr)
    raise SystemExit(1)

try:
    from pycaw.pycaw import AudioUtilities
except ImportError:
    print("Не найден pycaw. Установите: py -m pip install pycaw", file=sys.stderr)
    raise SystemExit(1)


BAUD_RATE = 9600
MIN_VOLUME_CHANGE = 1
FILTER_SIZE = 5
ARDUINO_MARKERS = ("arduino", "ch340", "ch341", "cp210", "usb serial")
AUDIO_FILE = Path(__file__).resolve().parent.parent / "meow-1.mp3"


class Mp3Player:
    """Проигрыватель одного MP3-файла через Windows MCI."""

    def __init__(self, audio_file: Path):
        self._winmm = ctypes.WinDLL("winmm")
        self._mci_send_string = self._winmm.mciSendStringW
        self._mci_send_string.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]
        self._mci_send_string.restype = ctypes.c_uint
        self._mci_get_error_string = self._winmm.mciGetErrorStringW
        self._mci_get_error_string.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        self._mci_get_error_string.restype = ctypes.c_bool
        self._alias = "dj_poltorashka_audio"
        self._send(f'open "{audio_file}" type mpegvideo alias {self._alias}')

    def play(self) -> None:
        """Запустить файл с начала."""
        self._send(f"stop {self._alias}")
        self._send(f"seek {self._alias} to start")
        self._send(f"play {self._alias}")

    def close(self) -> None:
        self._send(f"close {self._alias}")

    def _send(self, command: str) -> None:
        error_code = self._mci_send_string(command, None, 0, None)
        if error_code == 0:
            return

        message = ctypes.create_unicode_buffer(256)
        self._mci_get_error_string(error_code, message, len(message))
        raise OSError(f"Ошибка MCI {error_code}: {message.value}")


def find_port() -> str:
    """Найти наиболее похожий на Arduino последовательный порт."""
    ports = sorted(list_ports.comports(), key=lambda item: item.device)
    if not ports:
        raise RuntimeError("Последовательные порты не найдены")

    candidates = []
    for port in ports:
        description = (port.description or "").lower()
        if any(marker in description for marker in ARDUINO_MARKERS):
            candidates.append(port)

    if len(candidates) == 1:
        return candidates[0].device
    if len(ports) == 1:
        return ports[0].device

    port_list = ", ".join(f"{port.device} ({port.description})" for port in ports)
    raise RuntimeError(f"Не удалось однозначно выбрать порт: {port_list}. Укажите --port")


def read_data(connection: serial.Serial) -> tuple[float, bool] | None:
    min_value = 490
    max_value = 990

    line = connection.readline().decode("ascii", errors="ignore").strip()
    if not line:
        return None

    fields = line.split("|")
    if len(fields) != 2:
        return None

    try:
        value = (float(fields[0]) - min_value) / (max_value - min_value)
        button_pressed = bool(int(fields[1]))
    except ValueError:
        return None

    return max(0.0, min(1.0, value)), button_pressed


def main() -> int:
    parser = argparse.ArgumentParser(description="Регулятор громкости и MP3-кнопка с Arduino")
    parser.add_argument("--port", help="порт Arduino, например COM3")
    args = parser.parse_args()

    if not AUDIO_FILE.is_file():
        parser.error(f"файл не найден: {AUDIO_FILE}")

    player = None
    try:
        port = args.port or find_port()
        endpoint_volume = AudioUtilities.GetSpeakers().EndpointVolume
        player = Mp3Player(AUDIO_FILE)

        with serial.Serial(port, BAUD_RATE, timeout=1.0) as connection:
            # Arduino Nano после открытия порта может перезапуститься.
            time.sleep(2.0)
            connection.reset_input_buffer()
            measurements = deque(maxlen=FILTER_SIZE)
            previous_volume = None
            previous_button_pressed = False
            print(f"Порт {port}. MP3: {AUDIO_FILE}. Для выхода нажмите Ctrl+C.")

            while True:
                data = read_data(connection)
                if data is None:
                    continue

                potentiometer, button_pressed = data
                measurements.append(potentiometer)
                filtered_value = sum(measurements) / len(measurements)
                volume = round(filtered_value * 100)

                if previous_volume is None or abs(volume - previous_volume) >= MIN_VOLUME_CHANGE:
                    endpoint_volume.SetMasterVolumeLevelScalar(volume / 100, None)
                    previous_volume = volume

                if button_pressed and not previous_button_pressed:
                    player.play()
                    print("\nВоспроизведение MP3")

                previous_button_pressed = button_pressed
                print(f"\rГромкость: {volume:3d}%", end="", flush=True)
    except KeyboardInterrupt:
        print("\nРабота завершена.")
        return 0
    except (RuntimeError, serial.SerialException, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    finally:
        if player is not None:
            try:
                player.close()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
