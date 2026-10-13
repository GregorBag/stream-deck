"""Жизненный цикл независимых проигрывателей звуковых кнопок."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class SoundPlayer(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def close(self) -> None:
        ...


class SoundPlayerFactory(Protocol):
    def create(
        self,
        path: Path,
        on_finished: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> SoundPlayer:
        ...


class SoundPlaybackService:
    """Поддерживает не более одного запуска на каждой из восьми кнопок."""

    def __init__(
        self,
        player_factory: SoundPlayerFactory,
        on_started: Callable[[int, Path], None],
        on_finished: Callable[[int], None],
        on_error: Callable[[int, str], None],
    ) -> None:
        self._player_factory = player_factory
        self._on_started = on_started
        self._on_finished = on_finished
        self._on_error = on_error
        self._players: dict[int, tuple[int, SoundPlayer]] = {}
        self._generation = 0

    def play(self, button_index: int, path: Path) -> bool:
        self._require_button_index(button_index)
        sound_path = Path(path)
        self._release(button_index, stop=True)
        self._generation += 1
        generation = self._generation

        try:
            player = self._player_factory.create(
                sound_path,
                lambda: self._handle_finished(button_index, generation),
                lambda message: self._handle_error(
                    button_index,
                    generation,
                    message,
                ),
            )
            self._players[button_index] = (generation, player)
            player.start()
        except Exception as error:
            current = self._players.get(button_index)
            if current is not None and current[0] == generation:
                self._release(button_index, stop=True)
            message = str(error).strip() or type(error).__name__
            self._on_error(button_index, message)
            return False
        if not self._is_current(button_index, generation):
            return False
        self._on_started(button_index, sound_path)
        return True

    def close(self) -> None:
        for button_index in tuple(self._players):
            self._release(button_index, stop=True)

    def _handle_finished(self, button_index: int, generation: int) -> None:
        if not self._is_current(button_index, generation):
            return
        self._release(button_index, stop=False)
        self._on_finished(button_index)

    def _handle_error(
        self,
        button_index: int,
        generation: int,
        message: str,
    ) -> None:
        if not self._is_current(button_index, generation):
            return
        self._release(button_index, stop=True)
        normalized = message.strip() if isinstance(message, str) else ""
        self._on_error(button_index, normalized or "Неизвестная ошибка воспроизведения")

    def _is_current(self, button_index: int, generation: int) -> bool:
        current = self._players.get(button_index)
        return current is not None and current[0] == generation

    def _release(self, button_index: int, stop: bool) -> None:
        current = self._players.pop(button_index, None)
        if current is None:
            return
        player = current[1]
        if stop:
            player.stop()
        player.close()

    @staticmethod
    def _require_button_index(button_index: int) -> None:
        if (
            isinstance(button_index, bool)
            or not isinstance(button_index, int)
            or not 0 <= button_index < 8
        ):
            raise IndexError("Индекс звуковой кнопки должен быть от 0 до 7")
