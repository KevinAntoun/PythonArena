"""Regression checks for client screen message-transition ordering."""

import queue

from client.screens.lobby_screen import LobbyScreen
from client.screens.username_screen import UsernameScreen
from client.screens.waiting_screen import WaitingScreen
from shared.constants import S_CHALLENGE_ACK, S_CONNECT_ACK, S_GAME_START, S_GAME_STATE, S_PLAYER_LIST


class FakeNet:
    def __init__(self) -> None:
        self.inbound_q = queue.Queue()
        self.username = "alice"

    def drain_messages(self) -> list[dict]:
        messages = []
        while not self.inbound_q.empty():
            messages.append(self.inbound_q.get_nowait())
        return messages

    def defer_messages(self, messages: list[dict]) -> None:
        for msg in reversed(messages):
            replacement = queue.Queue()
            replacement.put(msg)
            while not self.inbound_q.empty():
                replacement.put(self.inbound_q.get_nowait())
            self.inbound_q = replacement


def main() -> None:
    net = FakeNet()
    username = UsernameScreen(net)
    player_list = {"type": S_PLAYER_LIST, "players": ["bob", "alice"]}
    net.inbound_q.put({"type": S_CONNECT_ACK, "status": "ok", "username": "alice"})
    net.inbound_q.put(player_list)
    assert username.update([]) == ("transition", "lobby")
    assert net.drain_messages() == [player_list]

    net = FakeNet()
    screen = LobbyScreen(net)
    state = {"snakes": {"alice": {}, "bob": {}}}

    net.inbound_q.put({"type": S_CHALLENGE_ACK, "accepted": True, "from": "bob"})
    net.inbound_q.put(
        {
            "type": S_GAME_START,
            "your_snake": "alice",
            "opponent": "bob",
            "state": state,
        }
    )
    action = screen.update([])
    assert action == (
        "transition",
        "game",
        {
            "type": S_GAME_START,
            "your_snake": "alice",
            "opponent": "bob",
            "state": state,
        },
    )

    net = FakeNet()
    waiting = WaitingScreen(net)
    waiting.on_enter({"opponent": "bob"})
    net.inbound_q.put({"type": S_GAME_STATE, "state": state})
    action = waiting.update([])
    assert action == (
        "transition",
        "game",
        {"your_snake": "alice", "opponent": "bob", "state": state},
    )

    print("Client transition smoke test passed.")


if __name__ == "__main__":
    main()
