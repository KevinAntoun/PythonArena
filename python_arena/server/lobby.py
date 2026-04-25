"""Thread-safe connected-client registry and broadcast helper."""

import threading
from typing import Dict


class Lobby:
    """Registry of connected clients and the current active game."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: Dict[str, "ClientHandler"] = {}
        self._game = None

    def register(self, username: str, handler) -> bool:
        with self._lock:
            if username in self._clients:
                return False
            self._clients[username] = handler
            return True

    def unregister(self, username: str) -> None:
        with self._lock:
            self._clients.pop(username, None)

    def online_players(self) -> list[str]:
        with self._lock:
            return list(self._clients.keys())

    def player_list_payload(self) -> dict:
        with self._lock:
            players = list(self._clients.keys())
            game = self._game

        spectatable_usernames: list[str] = []
        if game is not None:
            spectatable_usernames = [game.p1.username, game.p2.username]

        return {
            "players": players,
            "game_in_progress": game is not None,
            "spectatable_usernames": spectatable_usernames,
        }

    def get_handler(self, username: str):
        with self._lock:
            return self._clients.get(username)

    def set_game(self, game) -> None:
        with self._lock:
            self._game = game

    def get_game(self):
        with self._lock:
            return self._game

    def clear_game(self, game=None) -> None:
        with self._lock:
            if game is None or self._game is game:
                self._game = None

    def broadcast(self, msg: dict, exclude: set[str] | None = None) -> None:
        exclude = exclude or set()
        with self._lock:
            targets = dict(self._clients)

        for username, handler in targets.items():
            if username in exclude:
                continue
            try:
                handler.send(msg)
            except Exception:
                pass
