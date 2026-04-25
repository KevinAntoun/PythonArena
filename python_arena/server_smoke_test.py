"""Start the real server and verify the C_CONNECT handshake.

Run from this directory:
    python server_smoke_test.py
"""

import re
import socket
import subprocess
import sys
import time

from shared.constants import C_CONNECT, S_CONNECT_ACK, S_PLAYER_LIST
from shared.protocol import recv_msg, send_msg


def connect_user(port: int, username: str) -> tuple[socket.socket, list[dict]]:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    send_msg(
        sock,
        {"type": C_CONNECT, "username": username, "color": "green"},
    )
    messages = [recv_msg(sock)]
    if messages[0].get("status") == "ok":
        messages.append(recv_msg(sock))
    return sock, messages


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.server", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        if proc.stdout is None:
            raise RuntimeError("Server stdout was not captured")

        line = proc.stdout.readline().strip()
        match = re.search(r"port (\d+)", line)
        if not match:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Server did not report a port. stdout={line!r} stderr={stderr!r}")
        port = int(match.group(1))

        first_sock, first = connect_user(port, "alice")
        assert first[0]["type"] == S_CONNECT_ACK
        assert first[0]["status"] == "ok"
        assert first[1]["type"] == S_PLAYER_LIST
        assert "alice" in first[1]["players"]

        second_sock, second = connect_user(port, "alice")
        assert second[0]["type"] == S_CONNECT_ACK
        assert second[0]["status"] == "error"
        second_sock.close()
        first_sock.close()

        print("Server handshake smoke test passed.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
