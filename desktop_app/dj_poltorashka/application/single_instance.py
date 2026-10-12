"""Обмен командами между экземплярами настольного приложения."""

from collections.abc import Callable
import getpass
import hashlib

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


_VALID_COMMANDS = ("show", "ping")


def _default_server_name() -> str:
    user_id = hashlib.sha256(getpass.getuser().encode("utf-8")).hexdigest()[:12]
    return f"dj-poltorashka-{user_id}"


class SingleInstanceController:
    """Обеспечивает один сервер приложения для текущего пользователя."""

    def __init__(self, server_name: str | None = None):
        self._server_name = server_name or _default_server_name()
        self._server = QLocalServer()
        self._server.newConnection.connect(self._accept_connections)
        self._on_command: Callable[[str], None] | None = None
        self._clients: dict[QLocalSocket, bytearray] = {}
        self._outgoing_socket: QLocalSocket | None = None
        self._probe_failed = False

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def server(self) -> QLocalServer:
        return self._server

    @property
    def is_connected(self) -> bool:
        return (
            self._outgoing_socket is not None
            and self._outgoing_socket.state() == QLocalSocket.ConnectedState
        )

    def notify_existing(self, command: str) -> bool:
        if command not in _VALID_COMMANDS:
            raise ValueError("Команда должна быть show или ping")

        socket = QLocalSocket()
        self._outgoing_socket = socket
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(250):
            self._probe_failed = True
            socket.abort()
            self._outgoing_socket = None
            return False

        message = f"{command}\n".encode("utf-8")
        written = socket.write(message)
        delivered = written == len(message)
        if delivered and socket.bytesToWrite() > 0:
            delivered = self._wait_for_write(socket)
        socket.disconnectFromServer()
        if socket.state() != QLocalSocket.UnconnectedState:
            socket.waitForDisconnected(500)
        self._outgoing_socket = None
        return delivered

    @staticmethod
    def _wait_for_write(socket: QLocalSocket) -> bool:
        event_loop = QEventLoop()

        def finish_if_written(bytes_written: int) -> None:
            if socket.bytesToWrite() == 0:
                event_loop.quit()

        socket.bytesWritten.connect(finish_if_written)
        socket.errorOccurred.connect(lambda error: event_loop.quit())
        QTimer.singleShot(500, event_loop.quit)
        event_loop.exec()
        return socket.bytesToWrite() == 0

    def listen(self, on_command: Callable[[str], None]) -> None:
        self._on_command = on_command
        if self._server.listen(self._server_name):
            return

        if not self._probe_failed:
            raise RuntimeError(self._server.errorString())
        if not QLocalServer.removeServer(self._server_name):
            raise RuntimeError("Не удалось удалить устаревшее имя сервера")
        if not self._server.listen(self._server_name):
            raise RuntimeError(self._server.errorString())

    def close(self) -> None:
        if self._outgoing_socket is not None:
            self._outgoing_socket.abort()
            self._outgoing_socket = None
        for socket in tuple(self._clients):
            socket.abort()
        self._clients.clear()
        self._server.close()

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            self._clients[socket] = bytearray()
            socket.readyRead.connect(
                lambda connected_socket=socket: self._read_commands(
                    connected_socket
                )
            )
            socket.disconnected.connect(
                lambda connected_socket=socket: self._clients.pop(
                    connected_socket,
                    None,
                )
            )
            self._read_commands(socket)

    def _read_commands(self, socket: QLocalSocket) -> None:
        buffer = self._clients.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        while b"\n" in buffer:
            raw_command, remainder = buffer.split(b"\n", maxsplit=1)
            buffer[:] = remainder
            try:
                command = raw_command.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if command in _VALID_COMMANDS and self._on_command is not None:
                self._on_command(command)
