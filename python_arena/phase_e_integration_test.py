"""Phase E integration checks for chat, viewers, and shield."""

from shared.constants import (
    C_CHAT,
    C_MOVE,
    C_WATCH,
    S_CHAT,
    S_GAME_STATE,
    S_WATCH_ACK,
)
from shared.protocol import recv_msg, send_msg
from phase_d_integration_test import read_until, start_match, start_server, stop_server


def test_player_chat() -> None:
    proc, port = start_server()
    alice = None
    bob = None
    try:
        alice, bob, _alice_start, _bob_start = start_match(port)
        send_msg(alice, {"type": C_CHAT, "to": "bob", "message": "hello bob"})
        chat = read_until(bob, S_CHAT)
        assert chat == {"type": S_CHAT, "from": "alice", "message": "hello bob"}
    finally:
        for sock in (alice, bob):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        stop_server(proc)


def test_viewer_watch_and_fan_chat() -> None:
    proc, port = start_server()
    alice = None
    bob = None
    viewer = None
    try:
        alice, bob, _alice_start, _bob_start = start_match(port)
        viewer = start_match_viewer(port)

        watch_ack = read_until(viewer, S_WATCH_ACK)
        assert "state" in watch_ack
        state = read_until(viewer, S_GAME_STATE)["state"]
        assert set(state["snakes"]) == {"alice", "bob"}

        send_msg(viewer, {"type": C_MOVE, "direction": "UP"})
        state_after_viewer_move = read_until(viewer, S_GAME_STATE)["state"]
        assert set(state_after_viewer_move["snakes"]) == {"alice", "bob"}

        send_msg(viewer, {"type": C_CHAT, "to": None, "message": "go players"})
        bob_chat = read_until(bob, S_CHAT)
        assert bob_chat == {"type": S_CHAT, "from": "fan", "message": "go players"}
    finally:
        for sock in (alice, bob, viewer):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        stop_server(proc)


def start_match_viewer(port: int):
    from phase_d_integration_test import connect_user

    viewer = connect_user(port, "fan", "cyan")
    send_msg(viewer, {"type": C_WATCH})
    return viewer


def test_shield_state_reaches_clients() -> None:
    proc, port = start_server()
    alice = None
    bob = None
    try:
        alice, bob, _alice_start, _bob_start = start_match(port)
        send_msg(alice, {"type": C_MOVE, "direction": "DOWN"})
        state = read_until(alice, S_GAME_STATE)["state"]
        snake = state["snakes"]["alice"]
        assert "shielded" in snake
        assert "shield_ticks" in snake
    finally:
        for sock in (alice, bob):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        stop_server(proc)


def main() -> None:
    test_player_chat()
    test_viewer_watch_and_fan_chat()
    test_shield_state_reaches_clients()
    print("Phase E integration test passed.")


if __name__ == "__main__":
    main()
