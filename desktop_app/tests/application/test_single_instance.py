from uuid import uuid4

import pytest
from PySide6.QtNetwork import QLocalServer
from pytestqt.qtbot import QtBot

from dj_poltorashka.application.single_instance import SingleInstanceController


def unique_server_name() -> str:
    return f"dj-poltorashka-test-{uuid4().hex}"


@pytest.mark.parametrize("command", ("show", "ping"))
def test_command_is_delivered_and_client_disconnects(
    qtbot: QtBot,
    command: str,
) -> None:
    server = SingleInstanceController(unique_server_name())
    client = SingleInstanceController(server.server_name)
    received: list[str] = []
    server.listen(received.append)

    assert client.notify_existing(command)
    qtbot.waitUntil(lambda: received == [command])

    assert not client.is_connected
    client.close()
    server.close()


def test_unknown_command_is_rejected_before_connection() -> None:
    controller = SingleInstanceController(unique_server_name())

    with pytest.raises(ValueError, match="Команда должна быть show или ping"):
        controller.notify_existing("invalid")


def test_listen_does_not_remove_live_server_name(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = unique_server_name()
    first = SingleInstanceController(name)
    first.listen(lambda command: None)
    second = SingleInstanceController(name)
    removed: list[str] = []
    monkeypatch.setattr(
        QLocalServer,
        "removeServer",
        lambda server_name: removed.append(server_name) or True,
    )

    assert second.notify_existing("ping")

    assert removed == []
    second.close()
    first.close()


def test_failed_probe_allows_stale_server_name_removal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = unique_server_name()
    controller = SingleInstanceController(name)
    listen_results = iter((False, True))
    removed: list[str] = []
    monkeypatch.setattr(
        controller.server,
        "listen",
        lambda server_name: next(listen_results),
    )
    monkeypatch.setattr(
        QLocalServer,
        "removeServer",
        lambda server_name: removed.append(server_name) or True,
    )

    assert not controller.notify_existing("ping")
    controller.listen(lambda command: None)

    assert removed == [name]
    controller.close()


def test_only_one_concurrent_controller_can_become_server(qtbot: QtBot) -> None:
    name = unique_server_name()
    first = SingleInstanceController(name)
    second = SingleInstanceController(name)

    assert not first.notify_existing("ping")
    assert not second.notify_existing("ping")
    first.listen(lambda command: None)

    with pytest.raises(RuntimeError, match="уже запущен"):
        second.listen(lambda command: None)
    assert second.notify_existing("ping")

    second.close()
    first.close()
