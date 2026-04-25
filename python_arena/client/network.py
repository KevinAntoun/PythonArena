"""Client-side socket wrapper with a background receive queue."""

import queue
import socket
import threading

from shared.constants import (
    C_DISCONNECT,
    DIR_DOWN,
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    S_ERROR,
)
from shared.protocol import recv_msg, send_msg


class NetworkManager:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self.inbound_q: queue.Queue[dict] = queue.Queue()
        self._deferred_messages: list[dict] = []
        self._deferred_lock = threading.Lock()
        self._recv_thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self.connected = False
        self.username = ""
        self.snake_color = "green"
        self.auto_play = False
        self.key_bindings = {
            DIR_UP: ord("w"),
            DIR_DOWN: ord("s"),
            DIR_LEFT: ord("a"),
            DIR_RIGHT: ord("d"),
        }

    def connect(self, host: str, port: int) -> None:
        self.disconnect(send_disconnect=False)
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(None)
        self.connected = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def send(self, msg: dict) -> None:
        if not self.sock or not self.connected:
            raise ConnectionError("Not connected to server")
        with self._send_lock:
            send_msg(self.sock, msg)

    def disconnect(self, send_disconnect: bool = True) -> None:
        sock = self.sock
        if sock and send_disconnect and self.connected:
            try:
                send_msg(sock, {"type": C_DISCONNECT})
            except OSError:
                pass

        self.connected = False
        self.sock = None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def drain_messages(self) -> list[dict]:
        with self._deferred_lock:
            messages = list(self._deferred_messages)
            self._deferred_messages.clear()
        while True:
            try:
                messages.append(self.inbound_q.get_nowait())
            except queue.Empty:
                return messages

    def defer_messages(self, messages: list[dict]) -> None:
        if not messages:
            return
        with self._deferred_lock:
            self._deferred_messages = list(messages) + self._deferred_messages

    def _recv_loop(self) -> None:
        assert self.sock is not None
        sock = self.sock
        while self.connected and sock is self.sock:
            try:
                msg = recv_msg(sock)
            except (ConnectionError, OSError, ValueError) as exc:
                if self.connected:
                    self.inbound_q.put(
                        {"type": S_ERROR, "reason": f"Connection lost: {exc}"}
                    )
                break
            if msg is None:
                break
            self.inbound_q.put(msg)
        if sock is self.sock:
            self.connected = False
