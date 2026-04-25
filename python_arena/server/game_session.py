"""Threaded server-side game loop."""

import threading
import time

from shared.constants import (
    DIR_LEFT,
    DIR_RIGHT,
    GAME_DURATION,
    GRID_COLS,
    GRID_ROWS,
    INITIAL_HEALTH,
    S_GAME_END,
    S_GAME_START,
    S_GAME_STATE,
    S_PLAYER_LIST,
    TICK_RATE,
)
from server.game_logic import (
    determine_winner,
    is_game_over,
    place_obstacles,
    spawn_pies,
    tick,
)
from server.game_state import GameState, SnakeState


class GameSession(threading.Thread):
    """Runs the authoritative match loop and broadcasts snapshots."""

    def __init__(self, player1_handler, player2_handler, lobby):
        super().__init__(daemon=True)
        self.p1 = player1_handler
        self.p2 = player2_handler
        self.lobby = lobby
        self.state = GameState(time_left=float(GAME_DURATION))
        self._moves: dict[str, str] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ended = False
        self._forced_winner: str | None = None
        self.viewers = []

    def submit_move(self, username: str, direction: str) -> None:
        with self._lock:
            self._moves[username] = direction

    def add_viewer(self, handler) -> None:
        with self._lock:
            if handler not in self.viewers:
                self.viewers.append(handler)

    def remove_viewer(self, handler) -> None:
        with self._lock:
            if handler in self.viewers:
                self.viewers.remove(handler)

    def handle_player_disconnect(self, username: str) -> None:
        with self._lock:
            if self._ended:
                return
            self._forced_winner = self._opponent_username(username)
            self._stop_event.set()

    def stop(self) -> None:
        self._stop_event.set()

    def _opponent_username(self, username: str) -> str | None:
        if username == self.p1.username:
            return self.p2.username
        if username == self.p2.username:
            return self.p1.username
        return None

    def _init_state(self) -> None:
        p1_start = [(2, 2), (1, 2), (0, 2)]
        p2_start = [
            (GRID_COLS - 3, GRID_ROWS - 3),
            (GRID_COLS - 2, GRID_ROWS - 3),
            (GRID_COLS - 1, GRID_ROWS - 3),
        ]

        self.state.snakes[self.p1.username] = SnakeState(
            username=self.p1.username,
            body=p1_start,
            direction=DIR_RIGHT,
            health=INITIAL_HEALTH,
            color=self.p1.snake_color,
        )
        self.state.snakes[self.p2.username] = SnakeState(
            username=self.p2.username,
            body=p2_start,
            direction=DIR_LEFT,
            health=INITIAL_HEALTH,
            color=self.p2.snake_color,
        )
        place_obstacles(self.state)
        spawn_pies(self.state)

    def _handlers(self) -> list:
        with self._lock:
            viewers = list(self.viewers)
        return [self.p1, self.p2] + viewers

    def _broadcast(self, msg: dict) -> None:
        for handler in self._handlers():
            try:
                handler.send(msg)
            except Exception:
                pass

    def _broadcast_state(self) -> None:
        self._broadcast({"type": S_GAME_STATE, "state": self.state.to_dict()})

    def run(self) -> None:
        self._init_state()

        for handler in [self.p1, self.p2]:
            opponent = self.p2 if handler is self.p1 else self.p1
            handler.send(
                {
                    "type": S_GAME_START,
                    "your_snake": handler.username,
                    "opponent": opponent.username,
                    "state": self.state.to_dict(),
                }
            )

        interval = 1.0 / TICK_RATE
        last = time.monotonic()

        while not self._stop_event.is_set():
            now = time.monotonic()
            dt = now - last
            last = now

            with self._lock:
                moves = dict(self._moves)
                self._moves.clear()

            tick(self.state, moves, dt)
            self._broadcast_state()

            if is_game_over(self.state):
                break

            elapsed = time.monotonic() - now
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        with self._lock:
            self._ended = True
            winner = self._forced_winner

        if winner is None:
            winner = determine_winner(self.state)

        self._broadcast(
            {
                "type": S_GAME_END,
                "winner": winner,
                "state": self.state.to_dict(),
            }
        )
        self.lobby.clear_game(self)
        self.lobby.broadcast({"type": S_PLAYER_LIST, **self.lobby.player_list_payload()})
