"""Управление общей громкостью Windows с помощью потенциометра Arduino.

Запуск:
    py -m pip install pyserial pycaw
    py src/volume.py
    py src/volume.py --port COM3
"""

import argparse
import sys
import time
from collections import deque

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
MIN_VOLUME_CHANGE = 3
FILTER_SIZE = 5
ARDUINO_MARKERS = ("arduino", "ch340", "ch341", "cp210", "usb serial")


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


def read_potentiometer(connection: serial.Serial) -> float | None:
    """Прочитать значение из однострочного или трёхстрочного формата."""
    line = connection.readline().decode("ascii", errors="ignore").strip()
    if not line:
        return None

    marker = "Potentiometer:"
    try:
        if marker in line:
            value_text = line.split(marker, 1)[1].split(",", 1)[0]
        elif line in ("0", "1"):
            value_text = connection.readline().decode("ascii", errors="ignore").strip()
        else:
            return None
        value = float(value_text)
    except ValueError:
        return None

    return max(0.0, min(1.0, value))


def main() -> int:
    parser = argparse.ArgumentParser(description="Регулятор громкости Windows с Arduino")
    parser.add_argument("--port", help="порт Arduino, например COM3")
    args = parser.parse_args()

    try:
        port = args.port or find_port()
        endpoint_volume = AudioUtilities.GetSpeakers().EndpointVolume

        with serial.Serial(port, BAUD_RATE, timeout=1.0) as connection:
            # Arduino Nano после открытия порта может перезапуститься.
            time.sleep(2.0)
            connection.reset_input_buffer()
            measurements = deque(maxlen=FILTER_SIZE)
            previous_volume = None
            print(f"Порт {port}. Для выхода нажмите Ctrl+C.")

            while True:
                value = read_potentiometer(connection)
                if value is None:
                    continue
                measurements.append(value)
                filtered_value = sum(measurements) / len(measurements)
                volume = round(filtered_value * 100)

                if previous_volume is None or abs(volume - previous_volume) >= MIN_VOLUME_CHANGE:
                    endpoint_volume.SetMasterVolumeLevelScalar(volume / 100, None)
                    previous_volume = volume
                    print(f"\rГромкость: {volume:3d}%", end="", flush=True)
    except KeyboardInterrupt:
        print("\nРабота завершена.")
        return 0
    except (RuntimeError, serial.SerialException, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
