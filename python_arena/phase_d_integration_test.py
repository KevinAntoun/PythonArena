"""Phase D integration checks against the real socket server."""

import re
import socket
import subprocess
import sys
import time

from shared.constants import (
    C_CHALLENGE,
    C_CHALLENGE_RESP,
    C_CONNECT,
    C_MOVE,
    S_CHALLENGE,
    S_CHALLENGE_ACK,
    S_CONNECT_ACK,
    S_GAME_END,
    S_GAME_START,
    S_GAME_STATE,
    S_PLAYER_LIST,
    TICK_RATE,
)
from shared.protocol import recv_msg, send_msg


def start_server() -> tuple[subprocess.Popen, int]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.server", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.stdout is None:
        raise RuntimeError("Server stdout was not captured")
    line = proc.stdout.readline().strip()
    match = re.search(r"port (\d+)", line)
    if not match:
        stderr = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"Server did not report a port. stdout={line!r} stderr={stderr!r}")
    return proc, int(match.group(1))


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def connect_user(port: int, username: str, color: str) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.settimeout(5)
    send_msg(sock, {"type": C_CONNECT, "username": username, "color": color})
    ack = recv_msg(sock)
    assert ack["type"] == S_CONNECT_ACK
    assert ack["status"] == "ok"
    player_list = read_until(sock, S_PLAYER_LIST)
    assert username in player_list["players"]
    return sock


def read_until(sock: socket.socket, msg_type: str) -> dict:
    while True:
        msg = recv_msg(sock)
        if msg and msg.get("type") == msg_type:
            return msg


def start_match(port: int) -> tuple[socket.socket, socket.socket, dict, dict]:
    alice = connect_user(port, "alice", "green")
    bob = connect_user(port, "bob", "blue")

    send_msg(alice, {"type": C_CHALLENGE, "target": "bob"})
    challenge = read_until(bob, S_CHALLENGE)
    assert challenge["from"] == "alice"

    send_msg(bob, {"type": C_CHALLENGE_RESP, "from": "alice", "accepted": True})
    assert read_until(alice, S_CHALLENGE_ACK)["accepted"] is True
    assert read_until(bob, S_CHALLENGE_ACK)["accepted"] is True

    alice_start = read_until(alice, S_GAME_START)
    bob_start = read_until(bob, S_GAME_START)
    assert alice_start["your_snake"] == "alice"
    assert bob_start["your_snake"] == "bob"
    return alice, bob, alice_start, bob_start


def test_movement_sync() -> None:
    proc, port = start_server()
    alice = None
    bob = None
    try:
        alice, bob, _alice_start, _bob_start = start_match(port)
        send_msg(alice, {"type": C_MOVE, "direction": "DOWN"})

        alice_states = collect_states(alice, 5)
        bob_states = collect_states(bob, 5)

        assert len(alice_states) >= 5
        assert len(bob_states) >= 5
        assert alice_states[-1]["tick"] >= alice_states[0]["tick"] + 4
        assert bob_states[-1]["tick"] >= bob_states[0]["tick"] + 4

        alice_by_tick = {s["tick"]: s for s in alice_states}
        bob_by_tick = {s["tick"]: s for s in bob_states}
        common_ticks = set(alice_by_tick) & set(bob_by_tick)
        assert common_ticks, "No common broadcast tick observed by both clients"
        tick = max(common_ticks)
        alice_state = alice_by_tick[tick]
        bob_state = bob_by_tick[tick]
        assert alice_state == bob_state
        assert alice_state["snakes"]["alice"]["direction"] == "DOWN"

        elapsed_ticks = alice_states[-1]["tick"] - alice_states[0]["tick"]
        assert elapsed_ticks <= TICK_RATE * 2
    finally:
        for sock in (alice, bob):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        stop_server(proc)


def collect_states(sock: socket.socket, count: int) -> list[dict]:
    states = []
    deadline = time.monotonic() + 2.0
    while len(states) < count and time.monotonic() < deadline:
        msg = recv_msg(sock)
        if msg and msg.get("type") == S_GAME_STATE:
            states.append(msg["state"])
    return states


def test_disconnect_winner() -> None:
    proc, port = start_server()
    alice = None
    bob = None
    try:
        alice, bob, _alice_start, _bob_start = start_match(port)
        alice.shutdown(socket.SHUT_RDWR)
        alice.close()
        alice = None

        end = read_until(bob, S_GAME_END)
        assert end["winner"] == "bob"
    finally:
        for sock in (alice, bob):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        stop_server(proc)


def main() -> None:
    test_movement_sync()
    test_disconnect_winner()
    print("Phase D integration test passed.")


if __name__ == "__main__":
    main()
