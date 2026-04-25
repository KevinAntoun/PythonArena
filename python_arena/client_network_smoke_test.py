"""Verify NetworkManager can connect, send C_CONNECT, and receive ACK/list."""

import re
import subprocess
import sys
import time

from client.network import NetworkManager
from shared.constants import C_CONNECT, S_CONNECT_ACK, S_PLAYER_LIST


def wait_for_types(
    net: NetworkManager, msg_types: set[str], timeout: float = 5.0
) -> dict[str, dict]:
    deadline = time.monotonic() + timeout
    found = {}
    while time.monotonic() < deadline:
        for msg in net.drain_messages():
            msg_type = msg.get("type")
            if msg_type in msg_types:
                found[msg_type] = msg
            if msg_types.issubset(found):
                return found
        time.sleep(0.02)
    missing = ", ".join(sorted(msg_types - set(found)))
    raise TimeoutError(f"Timed out waiting for {missing}")


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.server", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    net = NetworkManager()

    try:
        if proc.stdout is None:
            raise RuntimeError("Server stdout was not captured")
        line = proc.stdout.readline().strip()
        match = re.search(r"port (\d+)", line)
        if not match:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Server did not report a port. stdout={line!r} stderr={stderr!r}")

        net.connect("127.0.0.1", int(match.group(1)))
        net.send({"type": C_CONNECT, "username": "client_smoke", "color": "cyan"})

        messages = wait_for_types(net, {S_CONNECT_ACK, S_PLAYER_LIST})
        ack = messages[S_CONNECT_ACK]
        assert ack["status"] == "ok"
        players = messages[S_PLAYER_LIST]
        assert "client_smoke" in players["players"]

        print("Client network smoke test passed.")
    finally:
        net.disconnect()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    main()
