"""Start the server and verify challenge -> accept -> game start.

Run from this directory:
    python server_game_start_smoke_test.py
"""

import re
import socket
import subprocess
import sys
import time

from shared.constants import (
    C_CHALLENGE,
    C_CHALLENGE_RESP,
    C_CONNECT,
    S_CHALLENGE,
    S_CHALLENGE_ACK,
    S_CONNECT_ACK,
    S_GAME_START,
)
from shared.protocol import recv_msg, send_msg


def connect_user(port: int, username: str, color: str) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.settimeout(5)
    send_msg(sock, {"type": C_CONNECT, "username": username, "color": color})
    ack = recv_msg(sock)
    assert ack["type"] == S_CONNECT_ACK
    assert ack["status"] == "ok"
    recv_msg(sock)
    return sock


def read_until(sock: socket.socket, msg_type: str) -> dict:
    while True:
        msg = recv_msg(sock)
        if msg and msg.get("type") == msg_type:
            return msg


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.server", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    alice = None
    bob = None

    try:
        if proc.stdout is None:
            raise RuntimeError("Server stdout was not captured")

        line = proc.stdout.readline().strip()
        match = re.search(r"port (\d+)", line)
        if not match:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Server did not report a port. stdout={line!r} stderr={stderr!r}")
        port = int(match.group(1))

        alice = connect_user(port, "alice", "green")
        bob = connect_user(port, "bob", "blue")

        send_msg(alice, {"type": C_CHALLENGE, "target": "bob"})
        challenge = read_until(bob, S_CHALLENGE)
        assert challenge["from"] == "alice"

        send_msg(bob, {"type": C_CHALLENGE_RESP, "from": "alice", "accepted": True})
        alice_ack = read_until(alice, S_CHALLENGE_ACK)
        bob_ack = read_until(bob, S_CHALLENGE_ACK)
        assert alice_ack["accepted"] is True
        assert bob_ack["accepted"] is True

        alice_start = read_until(alice, S_GAME_START)
        bob_start = read_until(bob, S_GAME_START)
        assert alice_start["your_snake"] == "alice"
        assert bob_start["your_snake"] == "bob"

        print("Server challenge/game-start smoke test passed.")
    finally:
        for sock in (alice, bob):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
