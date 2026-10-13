"""Проверки фонового выполнения аудиосервиса."""

from collections.abc import Callable
from threading import Event, Timer

from PySide6.QtCore import QThread
from pytestqt.qtbot import QtBot

from dj_poltorashka.audio.worker import AudioCoordinator
from dj_poltorashka.configuration.models import (
    MixerChannelConfig,
    PanelConfiguration,
    SoundButtonConfig,
)


def make_panel() -> PanelConfiguration:
    return PanelConfiguration(
        channels=tuple(
            MixerChannelConfig("unassigned", 0.5, False)
            for _ in range(4)
        ),
        sound_buttons=tuple(SoundButtonConfig() for _ in range(8)),
    )


class FakeAudioService:
    def __init__(self) -> None:
        self.apply_calls: list[tuple[PanelConfiguration, QThread]] = []
        self.adopt_calls: list[tuple[PanelConfiguration, int, QThread]] = []
        self.poll_threads: list[QThread] = []
        self.poll_action: Callable[[], tuple[object, ...]] = lambda: ()

    def apply_configuration(self, panel: PanelConfiguration) -> None:
        self.apply_calls.append((panel, QThread.currentThread()))

    def adopt_channel(
        self,
        panel: PanelConfiguration,
        channel_index: int,
    ) -> None:
        self.adopt_calls.append((panel, channel_index, QThread.currentThread()))

    def poll(self) -> tuple[object, ...]:
        self.poll_threads.append(QThread.currentThread())
        return self.poll_action()


def test_coordinator_runs_commands_and_poll_in_worker_thread(
    qtbot: QtBot,
) -> None:
    service = FakeAudioService()
    updates: list[tuple[object, ...]] = []
    errors: list[str] = []
    coordinator = AudioCoordinator(service, updates.append, errors.append)
    panel = make_panel()

    try:
        coordinator.start(panel)
        qtbot.waitUntil(lambda: bool(service.poll_threads))
        coordinator.apply_configuration(panel)
        coordinator.adopt_channel(panel, 2)
        qtbot.waitUntil(
            lambda: bool(service.apply_calls) and bool(service.adopt_calls)
        )

        main_thread = QThread.currentThread()
        assert coordinator.poll_interval_ms == 250
        assert coordinator.is_running
        assert service.poll_threads[0] is not main_thread
        assert service.apply_calls[-1][1] is service.poll_threads[0]
        assert service.adopt_calls[-1][2] is service.poll_threads[0]
        assert updates
        assert errors == []
    finally:
        coordinator.close()

    assert not coordinator.is_running


def test_coordinator_initializes_com_inside_worker_thread(qtbot: QtBot) -> None:
    service = FakeAudioService()
    initialized: list[QThread] = []
    uninitialized: list[QThread] = []
    coordinator = AudioCoordinator(
        service,
        lambda updates: None,
        lambda error: None,
        initialize_thread=lambda: initialized.append(QThread.currentThread()),
        uninitialize_thread=lambda: uninitialized.append(QThread.currentThread()),
    )

    coordinator.start(make_panel())
    qtbot.waitUntil(lambda: bool(initialized))
    coordinator.close()

    assert initialized[0] is not QThread.currentThread()
    assert uninitialized == initialized


def test_coordinator_reports_repeated_error_only_once_until_success(
    qtbot: QtBot,
) -> None:
    service = FakeAudioService()
    errors: list[str] = []
    attempts = 0

    def poll() -> tuple[object, ...]:
        nonlocal attempts
        attempts += 1
        if attempts <= 2 or attempts == 4:
            raise RuntimeError("ошибка опроса")
        return ()

    service.poll_action = poll
    coordinator = AudioCoordinator(service, lambda updates: None, errors.append)

    try:
        coordinator.start(make_panel())
        qtbot.waitUntil(lambda: attempts >= 4, timeout=1500)
        qtbot.waitUntil(lambda: len(errors) >= 2)
        assert errors == ["ошибка опроса", "ошибка опроса"]
    finally:
        coordinator.close()


def test_close_waits_for_active_poll_and_stops_thread(qtbot: QtBot) -> None:
    service = FakeAudioService()
    poll_started = Event()
    release_poll = Event()

    def blocking_poll() -> tuple[object, ...]:
        poll_started.set()
        release_poll.wait(timeout=2)
        return ()

    service.poll_action = blocking_poll
    coordinator = AudioCoordinator(service, lambda updates: None, lambda error: None)
    coordinator.start(make_panel())
    qtbot.waitUntil(poll_started.is_set)

    release_timer = Timer(0.1, release_poll.set)
    release_timer.start()
    coordinator.close()
    release_timer.join(timeout=1)

    assert not coordinator.is_running
    assert release_poll.is_set()
