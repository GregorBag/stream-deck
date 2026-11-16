"""Обмен через две очереди байтов и запускаемый пример без платы."""

from collections import deque

from dj_poltorashka.panel.emulator import PanelEmulator
from dj_poltorashka.panel.events import PanelEvent
from dj_poltorashka.panel.protocol import LedUpdate, PanelState
from dj_poltorashka.panel.session import PanelSession, SessionResult


class PanelSimulation:
    """Стенд для проверки сеанса; chunk_size имитирует дробление чтения порта."""

    def __init__(self, *, chunk_size: int = 16, initial_state: PanelState | None = None):
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
            raise ValueError("Размер фрагмента должен быть положительным целым числом")
        self._chunk_size = chunk_size
        self._to_board: deque[bytes] = deque()
        self._to_host: deque[bytes] = deque()
        self.drop_to_board = False
        self.drop_to_host = False
        self.transmitted: list[bytes] = []
        self.events: list[PanelEvent] = []
        self.states: list[PanelState] = []
        self.errors: list[str] = []
        self.board = PanelEmulator(initial_state)
        self.session = PanelSession(self._write)

    def _write(self, data: bytes) -> int:
        self.transmitted.append(data)
        if not self.drop_to_board:
            self._to_board.append(data)
        return len(data)

    def _record(self, result: SessionResult) -> None:
        self.events.extend(result.events)
        self.states.extend(result.states)
        self.errors.extend(result.errors)

    def _pump(self, now_ms: int) -> None:
        # Ограничение обнаружит ошибочный бесконечный обмен HELLO.
        for _ in range(32):
            if not self._to_board and not self._to_host:
                return
            while self._to_board:
                data = self._to_board.popleft()
                for offset in range(0, len(data), self._chunk_size):
                    result = self.board.receive(data[offset:offset + self._chunk_size], now_ms)
                    self.errors.extend(result.errors)
                    if result.data and not self.drop_to_host:
                        self._to_host.append(result.data)
            while self._to_host:
                data = self._to_host.popleft()
                if self.drop_to_host:
                    continue
                for offset in range(0, len(data), self._chunk_size):
                    self._record(self.session.receive(data[offset:offset + self._chunk_size], now_ms))
        raise RuntimeError("Сеанс не завершил обработку очередей")

    def start(self, now_ms: int) -> None:
        self._to_board.clear()
        self._to_host.clear()
        self.board.reset_connection(now_ms)
        self._record(self.session.start(now_ms))
        self._pump(now_ms)

    def advance(self, now_ms: int) -> None:
        self.board.tick(now_ms)
        self._record(self.session.tick(now_ms))
        self._pump(now_ms)

    def set_lighting(self, update: LedUpdate, now_ms: int) -> None:
        self._record(self.session.set_lighting(update, now_ms))
        self._pump(now_ms)

    def set_state(self, state: PanelState, now_ms: int) -> None:
        data = self.board.set_state(state, now_ms)
        if data and not self.drop_to_host:
            self._to_host.append(data)
        self._pump(now_ms)

    def restart_board(self, now_ms: int) -> None:
        data = self.board.restart(now_ms)
        if not self.drop_to_host:
            self._to_host.append(data)
        self._pump(now_ms)


def main() -> None:
    simulation = PanelSimulation(chunk_size=1)
    colors = tuple((index, index, index) for index in range(24))
    simulation.set_lighting(LedUpdate(50, colors), 0)
    simulation.start(0)
    print(f"Подключение: {simulation.session.status}")
    simulation.set_state(PanelState((0, 1023, 512, 1), 0x8101), 100)
    print(f"Ползунки: {simulation.states[-1].sliders}")
    print(f"События: {simulation.events}")
    simulation.advance(500)
    led_count = sum(data.startswith(b"LEDS ") for data in simulation.transmitted)
    print(f"Отправлено кадров подсветки после heartbeat: {led_count}")
    simulation.drop_to_board = simulation.drop_to_host = True
    for now_ms in (1000, 1500, 2000, 2500):
        simulation.advance(now_ms)
    print(f"После потери связи: {simulation.session.status}")
    print(f"Периметр: {simulation.board.lighting(2500).colors[0]}")
    print(f"Через 500 мс: {simulation.board.lighting(3000).colors[0]}")
    simulation.drop_to_board = simulation.drop_to_host = False
    event_count = len(simulation.events)
    simulation.start(3000)
    print(f"Переподключение: {simulation.session.status}")
    print(f"Ложных нажатий при переподключении: {len(simulation.events) - event_count}")
    print(f"Сообщения диагностики: {simulation.errors}")


if __name__ == "__main__":
    main()
